import re

import frappe
import requests


POLYGIN_TEMPLATE_ENDPOINT = "/api/v1/send_templet"
REQUEST_TIMEOUT = 20


def normalize_phone(phone, default_country_code):
	"""Normalize phone number by stripping separators and ensuring country code."""

	clean_number = re.sub(r"[\s-]+", "", cstr(phone).strip())
	clean_number = re.sub(r"[^0-9+]", "", clean_number)
	if not clean_number:
		return ""

	if clean_number.startswith("00"):
		clean_number = f"+{clean_number[2:]}"

	if clean_number.startswith("+"):
		return clean_number

	clean_number = clean_number.lstrip("0")
	country_code = cstr(default_country_code).strip() or "+91"
	if not country_code.startswith("+"):
		country_code = f"+{country_code}"
	# Validate country code is numeric (after +)
	if not re.match(r"^\+\d{1,4}$", country_code):
		country_code = "+91"
	country_digits = country_code[1:]

	# If number already includes country code (without +), only prepend "+".
	if country_digits and clean_number.startswith(country_digits):
		return f"+{clean_number}"

	normalized = f"{country_code}{clean_number}"
	# Basic guard to avoid sending empty or non-numeric targets to API.
	return normalized if re.search(r"\d", normalized) else ""


def _get_template_row(template_name, doctype=None):
	"""Find the matching Polygin Button row for a template + optional DocType."""
	settings = frappe.get_single("Polygin Settings")
	rows = [
		row for row in settings.get("buttons")
		if cstr(row.template_name).strip() == cstr(template_name).strip()
		and cint(row.is_active) == 1
	]
	# Prefer row matching the specific DocType
	if doctype:
		for row in rows:
			if cstr(row.for_doctype).strip() == cstr(doctype).strip():
				return row
	# Fallback: row with no doctype filter, or first match
	for row in rows:
		if not cstr(row.for_doctype).strip():
			return row
	return rows[0] if rows else None


def _build_programmatic_vars(template_name, doc, doctype, docname):
	"""Resolve variables programmatically for built-in templates."""
	if template_name == "doctype":
		contact_name = (
			doc.get("contact_person") or doc.get("customer_name")
			or doc.get("supplier_name") or doc.get("lead_name")
			or doc.get("first_name") or ""
		)
		doctype_label = (doctype or "").replace("_", " ")
		site_url = frappe.utils.get_url()
		pdf_url = (
			f"{site_url}/api/method/frappe.utils.print_format.download_pdf"
			f"?doctype={doctype}&name={docname}&format=Standard&no_letterhead=0"
			f"&key={frappe.generate_hash(length=20)}"
		)
		return [contact_name, doctype_label, docname, pdf_url]
	return []


def build_example_array(doc, template_name, doctype=None, docname=None):
	"""Build ordered template variable list from the FB Approved Templates table."""
	row = _get_template_row(template_name, doctype)
	if not row:
		return []

	if cint(row.is_programmatic):
		return _build_programmatic_vars(template_name, doc, doctype or doc.doctype, docname or doc.name)

	# Field-based mapping: read var_1 through var_9
	example_arr = []
	for i in range(1, 10):
		field_name = cstr(row.get(f"var_{i}")).strip()
		if not field_name:
			continue
		val = doc.get(field_name)
		example_arr.append(cstr(val) if val not in (None, "") else "")
	return example_arr


def _build_message_text(row, example_arr):
	"""Build conversational message text by substituting {{1}}–{{9}} in the template message."""
	msg = cstr(row.message or "")
	for i, val in enumerate(example_arr, start=1):
		msg = msg.replace(f"{{{{{i}}}}}", cstr(val))
	return msg


def handle_api_response(response):
	"""Parse API response and return consistent success/failure structure."""

	status_code = getattr(response, "status_code", None)
	try:
		response_data = response.json() if response.content else {}
	except ValueError:
		raw_response = (response.text or "").strip()
		message = raw_response or "Invalid response received from Polyg.in."
		if status_code and status_code >= 400:
			message = f"Polyg.in API error ({status_code}): {message}"
		return {
			"success": False,
			"message": message,
			"response": {"status_code": status_code},
		}

	success = bool(response_data.get("success", status_code is None or status_code < 400))
	if not success:
		message = response_data.get("message") or "Polyg.in request failed."
		if status_code and status_code >= 400:
			message = f"Polyg.in API error ({status_code}): {message}"
		return {
			"success": False,
			"message": message,
			"response": response_data,
		}

	return {
		"success": True,
		"message": response_data.get("message") or "WhatsApp template sent successfully.",
		"response": response_data,
	}


def _resolve_cost(template_row, settings):
	"""Resolve per-send cost: button-level override beats settings default."""
	row_cost = frappe.utils.flt(template_row.get("cost_per_send")) if template_row else 0.0
	if row_cost > 0:
		return row_cost
	return frappe.utils.flt(settings.get("default_cost_per_send"))


def log_message(
	recipient,
	template_name,
	status,
	response_data,
	reference_doctype,
	reference_name,
	cost=0.0,
	currency=None,
	category=None,
):
	"""Persist Polyg.in API result in Polygin Message Log."""

	try:
		frappe.get_doc(
			{
				"doctype": "Polygin Message Log",
				"recipient": cstr(recipient),
				"template": cstr(template_name),
				"category": cstr(category) if category else None,
				"status": cstr(status),
				"cost": frappe.utils.flt(cost) if status == "Success" else 0.0,
				"currency": cstr(currency) if currency else None,
				"response": frappe.as_json(response_data),
				"reference_doctype": cstr(reference_doctype),
				"reference_name": cstr(reference_name),
				"timestamp": frappe.utils.now_datetime(),
			}
		).insert(ignore_permissions=True)
	except Exception:
		# Logging should never block message-sending flow.
		frappe.log_error(frappe.get_traceback(), "Polygin Message Log Insert Failed")


def _parse_request_exception(exc):
	"""Extract a meaningful error payload from request exceptions."""

	response = getattr(exc, "response", None)
	if response is not None:
		parsed = handle_api_response(response)
		return parsed.get("message"), parsed.get("response")

	return str(exc), {"message": str(exc)}


@frappe.whitelist()
def get_buttons(doctype=None):
	"""Return active Polygin template buttons configured in settings."""

	settings = frappe.get_single("Polygin Settings")
	results = []
	for row in settings.get("buttons"):
		if cint(row.is_active) != 1:
			continue
		# Filter by doctype if provided
		if doctype and cstr(row.for_doctype).strip() and cstr(row.for_doctype).strip() != cstr(doctype).strip():
			continue
		results.append({
			"button_name": row.button_name,
			"template_name": row.template_name,
			"for_doctype": row.for_doctype,
			"message": row.message,
			"is_programmatic": cint(row.is_programmatic),
		})
	return results


@frappe.whitelist()
def send_whatsapp_template(doctype, docname, template_name, phone=None, target_field=None):
	"""Send a WhatsApp template — conversational if 24h window open, else via Template API."""

	try:
		if not cstr(doctype).strip() or not cstr(docname).strip():
			return {"success": False, "message": "Document type and document name are required."}
		if not cstr(template_name).strip():
			return {"success": False, "message": "Template name is required."}

		doc = frappe.get_doc(doctype, docname)
		settings = frappe.get_single("Polygin Settings")

		api_key = settings.get_password("api_key")
		base_url = cstr(settings.base_url).strip() or "https://polyg.in"
		default_country_code = cstr(settings.default_country_code).strip() or "+91"

		if not api_key:
			return {"success": False, "message": "Polygin API key is not configured in Polygin Settings."}

		# Resolve phone number
		raw_phone = phone or (doc.get(target_field) if target_field else None)
		if not raw_phone:
			return {"success": False, "message": "Phone number not provided."}

		normalized_phone = normalize_phone(raw_phone, default_country_code)
		if not normalized_phone:
			return {"success": False, "message": "Invalid phone number."}

		# Build variables
		example_arr = build_example_array(doc, template_name, doctype, docname)
		template_row = _get_template_row(template_name, doctype)

		# Check 24h response window
		normalized_match = normalize_phone_for_matching(raw_phone)
		window_active = _is_window_active(normalized_match)

		if window_active and template_row and cstr(template_row.message).strip():
			# Send as conversational text
			message_text = _build_message_text(template_row, example_arr)
			result = send_chat_message(phone=raw_phone, message_type="text", content=message_text)
			if result.get("success"):
				result["message"] = "Sent as conversation message (24h window active)."
			return result
		else:
			# Send via Template API
			url = f"{base_url.rstrip('/')}{POLYGIN_TEMPLATE_ENDPOINT}"
			headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
			payload = {
				"sendTo": normalized_phone,
				"templetName": template_name,
				"exampleArr": example_arr,
				"token": api_key,
			}
			response = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
			result = handle_api_response(response)

			# Always log template sends so we can track the originating ERPNext
			# user (needed for notification routing). The enable_logging flag is
			# honoured only for Failed entries to keep the log clean.
			if result.get("success") or settings.enable_logging:
				log_message(
					recipient=normalized_phone, template_name=template_name,
					status="Success" if result.get("success") else "Failed",
					response_data=result.get("response") or {"message": result.get("message")},
					reference_doctype=doctype, reference_name=docname,
					cost=_resolve_cost(template_row, settings),
					currency=cstr(settings.get("currency")) or None,
					category=cstr(template_row.get("category")) if template_row else None,
				)
			return result

	except requests.RequestException as exc:
		error_message, error_response = _parse_request_exception(exc)
		return {"success": False, "message": f"Failed to send: {error_message}"}
	except frappe.DoesNotExistError:
		return {"success": False, "message": f"{doctype} {docname} was not found."}
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Polygin: send_whatsapp_template failed")
		return {"success": False, "message": "An unexpected error occurred."}


# Aliases from frappe.utils for concise conversions used across this module.
cint = frappe.utils.cint
cstr = frappe.utils.cstr


# ---------------------------------------------------------------------------
# Chat Widget API
# ---------------------------------------------------------------------------


def _extract_media_url_from_raw(raw_data):
	"""Extract media link from raw webhook JSON (msgContext.{type}.link)."""
	import json as _json
	try:
		data = _json.loads(raw_data) if isinstance(raw_data, str) else raw_data
		ctx = data.get("msgContext") or {}
		for key in ("document", "image", "video", "audio"):
			media = ctx.get(key)
			if isinstance(media, dict) and media.get("link"):
				return media["link"]
	except (ValueError, TypeError, AttributeError):
		pass
	return None


POLYGIN_CONVERSATIONAL_ENDPOINT = "/api/v1/send-message"
_DEDUP_WINDOW_SECONDS = 120


def _deduplicate_outgoing(messages):
	"""Remove duplicate outgoing messages caused by webhook echo-back.

	When a message is sent from ERPNext via send_chat_message(), it is stored
	locally with origin='outgoing'. The Polyg.in webhook then echoes the same
	message back with origin='meta' and route='OUTGOING'. This function keeps
	the webhook version (which has richer data like metaChatId) and drops the
	local duplicate.
	"""
	# Group outgoing messages by (message_text, direction)
	# and check for origin=outgoing + origin=meta pairs within the time window.
	local_msgs = {}  # message_text -> list of indices
	for i, m in enumerate(messages):
		if m["direction"] == "outgoing" and m.get("origin") == "outgoing":
			local_msgs.setdefault(m["message"], []).append(i)

	drop_indices = set()
	for i, m in enumerate(messages):
		if m["direction"] != "outgoing" or m.get("origin") != "meta":
			continue
		# Check if there's a matching local message with the same text
		candidates = local_msgs.get(m["message"])
		if not candidates:
			continue
		for li in candidates:
			local_ts = _parse_timestamp(messages[li]["timestamp"])
			meta_ts = _parse_timestamp(m["timestamp"])
			if local_ts and meta_ts:
				diff = abs((meta_ts - local_ts).total_seconds())
				if diff <= _DEDUP_WINDOW_SECONDS:
					drop_indices.add(li)  # drop the local version
					break

	if drop_indices:
		messages = [m for i, m in enumerate(messages) if i not in drop_indices]
	return messages


def _is_window_active(normalized_match):
	"""Check if the 24h response window is active for a normalized phone."""
	last_incoming = frappe.get_all(
		"Polygin Wa Messages",
		filters={"normalized_phone": normalized_match, "direction": "incoming"},
		fields=["timestamp", "creation"],
		order_by="creation desc",
		limit_page_length=1,
	)
	if not last_incoming:
		return False
	last_ts = _parse_timestamp(last_incoming[0].timestamp) or last_incoming[0].creation
	if not last_ts:
		return False
	remaining = (last_ts + frappe.utils.datetime.timedelta(hours=24) - frappe.utils.now_datetime()).total_seconds()
	return remaining > 0


def normalize_phone_for_matching(phone):
	"""Strip to last 10 digits for cross-format phone matching."""
	from polygin.utils import normalize_phone_for_matching as _normalize
	return _normalize(phone)


def _parse_timestamp(ts_value):
	"""Parse timestamp from various formats (unix epoch string or ISO/datetime string)."""
	if not ts_value:
		return None
	try:
		return frappe.utils.get_datetime(float(ts_value))
	except (ValueError, TypeError, OSError):
		pass
	try:
		return frappe.utils.get_datetime(ts_value)
	except (ValueError, TypeError):
		return None


@frappe.whitelist()
def get_chat_messages(phone, channel="whatsapp", page=1, page_size=50):
	"""Fetch all messages for a phone number, merging incoming, outgoing, and template logs."""
	frappe.has_permission("Polygin Wa Messages", "read", throw=True)
	page = cint(page) or 1
	page_size = min(cint(page_size) or 50, 100)
	normalized = normalize_phone_for_matching(phone)

	if not normalized:
		return {"messages": [], "has_more": False, "response_window": {"is_active": False}}

	doctype = "Polygin Wa Messages" if channel == "whatsapp" else "Polygin Telegram Messages"
	messages = []

	# Fetch from message doctype
	raw_msgs = frappe.get_all(
		doctype,
		filters={"normalized_phone": normalized},
		fields=[
			"name", "sender_name", "sender_mobile", "message", "message_type",
			"media_file", "timestamp", "uid", "origin", "direction", "responding_agent", "raw_data", "creation",
		],
		order_by="creation desc",
		limit_page_length=page_size + 1,
		limit_start=(page - 1) * page_size,
	)

	has_more = len(raw_msgs) > page_size
	raw_msgs = raw_msgs[:page_size]

	for msg in raw_msgs:
		parsed_ts = _parse_timestamp(msg.timestamp)
		media_url = msg.media_file
		# Backfill: extract media URL from raw_data for older records missing media_file
		if not media_url and msg.raw_data and msg.message_type in ("document", "image", "video", "audio"):
			media_url = _extract_media_url_from_raw(msg.raw_data)
		messages.append({
			"id": msg.name,
			"direction": msg.direction or "incoming",
			"message": msg.message,
			"message_type": msg.message_type,
			"media_url": media_url,
			"timestamp": str(parsed_ts) if parsed_ts else str(msg.creation),
			"sender_name": msg.sender_name,
			"responding_agent": msg.responding_agent,
			"raw_data": msg.raw_data,
			"source": "message",
			"origin": msg.origin,
		})

	# Also fetch template sends from Polygin Message Log for this number
	if channel == "whatsapp" and page == 1:
		log_records = frappe.get_all(
			"Polygin Message Log",
			filters={"status": "Success"},
			fields=["name", "recipient", "template", "response", "timestamp", "creation", "owner"],
			order_by="creation desc",
			limit_page_length=50,
		)
		for log in log_records:
			log_normalized = normalize_phone_for_matching(log.recipient)
			if log_normalized == normalized:
				agent = frappe.utils.get_fullname(log.owner) if log.owner else "You"
				messages.append({
					"id": log.name,
					"direction": "outgoing",
					"message": f"[Template: {log.template}]",
					"message_type": "template",
					"media_url": None,
					"timestamp": str(log.timestamp or log.creation),
					"sender_name": agent,
					"responding_agent": agent,
					"source": "template_log",
					"origin": "outgoing",
				})

	# Sort all by timestamp ascending
	messages.sort(key=lambda m: m["timestamp"])

	# Deduplicate: when send_chat_message() stores a message locally (origin=outgoing)
	# AND the Polyg.in webhook echoes the same message back (origin=meta), both appear.
	# Keep the webhook version (richer data) and drop the local duplicate.
	messages = _deduplicate_outgoing(messages)

	# Compute response window from the last incoming message
	response_window = {"is_active": False, "seconds_remaining": 0, "expires_at": None}
	incoming_msgs = [m for m in messages if m["direction"] == "incoming"]
	if incoming_msgs:
		last_incoming_ts = _parse_timestamp(incoming_msgs[-1]["timestamp"])
		if last_incoming_ts:
			now = frappe.utils.now_datetime()
			expires_at = last_incoming_ts + frappe.utils.datetime.timedelta(hours=24)
			remaining = (expires_at - now).total_seconds()
			response_window = {
				"is_active": remaining > 0,
				"seconds_remaining": max(0, int(remaining)),
				"expires_at": str(expires_at),
			}

	return {"messages": messages, "has_more": has_more, "response_window": response_window}


@frappe.whitelist()
def send_chat_message(phone, message_type, content=None, media_url=None, caption=None, interactive_data=None):
	"""Send a message via Polygin Conversational API and store it locally."""
	import json as _json

	frappe.has_permission("Polygin Wa Messages", "write", throw=True)
	settings = frappe.get_single("Polygin Settings")
	api_key = settings.get_password("api_key")
	base_url = cstr(settings.base_url).strip() or "https://polyg.in"
	default_country_code = cstr(settings.default_country_code).strip() or "+91"

	if not api_key:
		return {"success": False, "message": "Polygin API key is not configured."}

	# Input validation
	if message_type == "text" and len(cstr(content)) > 4096:
		return {"success": False, "message": "Message too long. Max 4096 characters."}
	if caption and len(cstr(caption)) > 1024:
		return {"success": False, "message": "Caption too long. Max 1024 characters."}

	normalized_for_api = normalize_phone(phone, default_country_code)
	if not normalized_for_api:
		return {"success": False, "message": "Invalid phone number."}

	# Build messageObject based on type
	msg_obj = {"to": normalized_for_api.lstrip("+")}

	if message_type == "text":
		msg_obj["type"] = "text"
		msg_obj["text"] = {"preview_url": False, "body": content or ""}
	elif message_type == "image":
		msg_obj["type"] = "image"
		msg_obj["image"] = {"link": media_url}
	elif message_type == "audio":
		msg_obj["type"] = "audio"
		msg_obj["audio"] = {"link": media_url}
	elif message_type == "document":
		msg_obj["type"] = "document"
		msg_obj["document"] = {"link": media_url, "caption": caption or ""}
	elif message_type == "video":
		msg_obj["type"] = "video"
		msg_obj["video"] = {"link": media_url, "caption": caption or ""}
	elif message_type in ("interactive_list", "interactive_button"):
		msg_obj["type"] = "interactive"
		try:
			msg_obj["interactive"] = _json.loads(interactive_data) if isinstance(interactive_data, str) else interactive_data
		except (ValueError, TypeError):
			return {"success": False, "message": "Invalid interactive message data."}
	else:
		return {"success": False, "message": f"Unsupported message type: {message_type}"}

	# Send via Polygin API — conversational endpoint requires token as query param
	url = f"{base_url.rstrip('/')}{POLYGIN_CONVERSATIONAL_ENDPOINT}?token={api_key}"
	try:
		response = requests.post(
			url,
			json={"messageObject": msg_obj},
			headers={"Content-Type": "application/json"},
			timeout=REQUEST_TIMEOUT,
		)
		result = handle_api_response(response)
	except requests.RequestException as exc:
		error_message, _ = _parse_request_exception(exc)
		return {"success": False, "message": f"Failed to send message: {error_message}"}

	if not result.get("success"):
		return result

	# Store outgoing message locally
	display_message = content or caption or f"[{message_type}]"
	# Map message_type for storage
	stored_type = message_type
	if message_type == "interactive_list":
		stored_type = "interactive"
	elif message_type == "interactive_button":
		stored_type = "button"

	try:
		agent_name = frappe.utils.get_fullname(frappe.session.user)
		doc = frappe.get_doc({
			"doctype": "Polygin Wa Messages",
			"sender_name": agent_name,
			"sender_mobile": normalized_for_api,
			"message": display_message,
			"message_type": stored_type,
			"media_file": media_url,
			"timestamp": str(frappe.utils.now_datetime()),
			"origin": "outgoing",
			"direction": "outgoing",
			"responding_agent": agent_name,
			"normalized_phone": normalize_phone_for_matching(phone),
			"raw_data": interactive_data if message_type in ("interactive_list", "interactive_button") else None,
		})
		doc.insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Polygin Chat: Failed to store outgoing message")

	return result


ALLOWED_MEDIA_EXTENSIONS = {
	".jpg", ".jpeg", ".png", ".gif", ".webp",  # images
	".mp4", ".3gp",  # video
	".mp3", ".ogg", ".amr", ".aac",  # audio
	".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv",  # documents
}
MAX_UPLOAD_SIZE_MB = 75


@frappe.whitelist()
def upload_chat_media():
	"""Upload a file for sending via chat. Returns a public URL."""
	frappe.has_permission("Polygin Wa Messages", "write", throw=True)

	if "file" not in frappe.request.files:
		return {"success": False, "message": "No file provided."}

	filedata = frappe.request.files["file"]

	# Validate file extension
	import os
	_, ext = os.path.splitext(cstr(filedata.filename).lower())
	if ext not in ALLOWED_MEDIA_EXTENSIONS:
		return {"success": False, "message": f"File type '{ext}' is not allowed."}

	# Validate file size
	file_content = filedata.read()
	if len(file_content) > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
		return {"success": False, "message": f"File exceeds {MAX_UPLOAD_SIZE_MB}MB limit."}

	from frappe.utils.file_manager import save_file

	saved = save_file(
		filedata.filename,
		file_content,
		"Polygin Wa Messages",
		None,
		is_private=0,
	)

	file_url = saved.file_url
	if file_url and not file_url.startswith("http"):
		file_url = frappe.utils.get_url(file_url)

	return {"success": True, "file_url": file_url, "file_name": saved.file_name}


@frappe.whitelist()
def get_chat_settings():
	"""Return chat widget configuration."""
	settings = frappe.get_single("Polygin Settings")
	return {
		"enable_chat_widget": cint(settings.get("enable_chat_widget", 1)),
		"default_country_code": cstr(settings.default_country_code).strip() or "+91",
	}


@frappe.whitelist()
def get_quick_replies():
	"""Return active quick reply templates."""
	return frappe.get_all(
		"Polygin Quick Reply",
		filters={"is_active": 1},
		fields=["name", "title", "message", "message_type", "interactive_payload", "shortcode"],
		order_by="title asc",
	)


@frappe.whitelist()
def send_document_via_template(doctype, docname, phone):
	"""Send a document PDF — delegates to the unified send_whatsapp_template with template_name='doctype'."""
	return send_whatsapp_template(doctype=doctype, docname=docname, template_name="doctype", phone=phone)
