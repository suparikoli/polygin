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
	country_digits = country_code[1:]

	# If number already includes country code (without +), only prepend "+".
	if country_digits and clean_number.startswith(country_digits):
		return f"+{clean_number}"

	normalized = f"{country_code}{clean_number}"
	# Basic guard to avoid sending empty or non-numeric targets to API.
	return normalized if re.search(r"\d", normalized) else ""


def build_example_array(doc, template_name):
	"""Build ordered template variable list from Polygin Settings mapping."""

	settings = frappe.get_single("Polygin Settings")
	mappings = [
		row
		for row in settings.get("variable_mapping")
		if cstr(row.template_name).strip() == cstr(template_name).strip()
	]
	mappings = sorted(mappings, key=lambda row: cint(row.variable_index))

	example_arr = []
	for mapping in mappings:
		mapped_value = doc.get(mapping.field_name)
		if mapped_value in (None, ""):
			mapped_value = mapping.default_value or ""
		example_arr.append(cstr(mapped_value))

	return example_arr


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
			"response": {"raw": response.text, "status_code": status_code},
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


def log_message(recipient, template_name, status, response_data, reference_doctype, reference_name):
	"""Persist Polyg.in API result in Polygin Message Log."""

	try:
		frappe.get_doc(
			{
				"doctype": "Polygin Message Log",
				"recipient": cstr(recipient),
				"template": cstr(template_name),
				"status": cstr(status),
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
def get_buttons():
	"""Return active Polygin template buttons configured in settings."""

	settings = frappe.get_single("Polygin Settings")
	return [
		{
			"button_name": row.button_name,
			"template_name": row.template_name,
		}
		for row in settings.get("buttons")
		if cint(row.is_active) == 1
	]


@frappe.whitelist()
def send_whatsapp_template(doctype, docname, template_name, target_field):
	"""Send a WhatsApp template message using Polyg.in."""

	try:
		if not cstr(doctype).strip() or not cstr(docname).strip():
			return {"success": False, "message": "Document type and document name are required."}
		if not cstr(template_name).strip():
			return {"success": False, "message": "Template name is required."}
		if not cstr(target_field).strip():
			return {"success": False, "message": "Target field is required."}

		doc = frappe.get_doc(doctype, docname)
		settings = frappe.get_single("Polygin Settings")

		api_key = settings.get_password("api_key")
		base_url = cstr(settings.base_url).strip() or "https://polyg.in"
		default_country_code = cstr(settings.default_country_code).strip() or "+91"

		if not api_key:
			return {"success": False, "message": "Polygin API key is not configured in Polygin Settings."}

		raw_phone_number = doc.get(target_field)
		if not raw_phone_number:
			return {
				"success": False,
				"message": f"Phone number not found in field '{target_field}' for {doctype} {docname}.",
			}

		normalized_phone = normalize_phone(raw_phone_number, default_country_code)
		if not normalized_phone:
			return {
				"success": False,
				"message": f"Invalid phone number in field '{target_field}' for {doctype} {docname}.",
			}
		example_arr = build_example_array(doc, template_name)

		url = f"{base_url.rstrip('/')}{POLYGIN_TEMPLATE_ENDPOINT}"
		headers = {
			"Authorization": f"Bearer {api_key}",
			"Content-Type": "application/json",
		}
		payload = {
			"sendTo": normalized_phone,
			"templetName": template_name,
			"exampleArr": example_arr,
			"token": api_key,
		}

		response = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)

		result = handle_api_response(response)
		if settings.enable_logging:
			log_message(
				recipient=normalized_phone,
				template_name=template_name,
				status="Success" if result.get("success") else "Failed",
				response_data=result.get("response") or {"message": result.get("message")},
				reference_doctype=doctype,
				reference_name=docname,
			)
		return result

	except requests.RequestException as exc:
		error_message, error_response = _parse_request_exception(exc)
		if frappe.db.get_single_value("Polygin Settings", "enable_logging"):
			log_message(
				recipient=locals().get("normalized_phone", ""),
				template_name=template_name,
				status="Failed",
				response_data=error_response,
				reference_doctype=doctype,
				reference_name=docname,
			)
		else:
			error_message = str(exc)
		return {"success": False, "message": f"Failed to send WhatsApp template: {error_message}"}
	except frappe.DoesNotExistError:
		return {"success": False, "message": f"{doctype} {docname} was not found."}
	except frappe.ValidationError as exc:
		return {"success": False, "message": cstr(exc)}
	except Exception:
		if frappe.db.get_single_value("Polygin Settings", "enable_logging"):
			log_message(
				recipient=locals().get("normalized_phone", ""),
				template_name=template_name,
				status="Failed",
				response_data={"message": "Unexpected error", "traceback": frappe.get_traceback()},
				reference_doctype=doctype,
				reference_name=docname,
			)
		return {"success": False, "message": "An unexpected error occurred while sending template message."}


# Aliases from frappe.utils for concise conversions used across this module.
cint = frappe.utils.cint
cstr = frappe.utils.cstr


# ---------------------------------------------------------------------------
# Chat Widget API
# ---------------------------------------------------------------------------

POLYGIN_CONVERSATIONAL_ENDPOINT = "/api/v1/send-message"


def normalize_phone_for_matching(phone):
	"""Strip to last 10 digits for cross-format phone matching."""
	digits = re.sub(r"[^0-9]", "", str(phone or ""))
	return digits[-10:] if len(digits) >= 10 else digits


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
	except Exception:
		return None


@frappe.whitelist()
def get_chat_messages(phone, channel="whatsapp", page=1, page_size=50):
	"""Fetch all messages for a phone number, merging incoming, outgoing, and template logs."""
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
			"media_file", "timestamp", "uid", "origin", "direction", "creation",
		],
		order_by="creation desc",
		limit_page_length=page_size + 1,
		limit_start=(page - 1) * page_size,
	)

	has_more = len(raw_msgs) > page_size
	raw_msgs = raw_msgs[:page_size]

	for msg in raw_msgs:
		parsed_ts = _parse_timestamp(msg.timestamp)
		messages.append({
			"id": msg.name,
			"direction": msg.direction or "incoming",
			"message": msg.message,
			"message_type": msg.message_type,
			"media_url": msg.media_file,
			"timestamp": str(parsed_ts) if parsed_ts else str(msg.creation),
			"sender_name": msg.sender_name,
			"source": "message",
			"origin": msg.origin,
		})

	# Also fetch template sends from Polygin Message Log for this number
	if channel == "whatsapp" and page == 1:
		log_records = frappe.get_all(
			"Polygin Message Log",
			filters={"status": "Success"},
			fields=["name", "recipient", "template", "response", "timestamp", "creation"],
			order_by="creation desc",
			limit_page_length=200,
		)
		for log in log_records:
			log_normalized = normalize_phone_for_matching(log.recipient)
			if log_normalized == normalized:
				messages.append({
					"id": log.name,
					"direction": "outgoing",
					"message": f"[Template: {log.template}]",
					"message_type": "template",
					"media_url": None,
					"timestamp": str(log.timestamp or log.creation),
					"sender_name": "You",
					"source": "template_log",
					"origin": "outgoing",
				})

	# Sort all by timestamp ascending
	messages.sort(key=lambda m: m["timestamp"])

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

	settings = frappe.get_single("Polygin Settings")
	api_key = settings.get_password("api_key")
	base_url = cstr(settings.base_url).strip() or "https://polyg.in"
	default_country_code = cstr(settings.default_country_code).strip() or "+91"

	if not api_key:
		return {"success": False, "message": "Polygin API key is not configured."}

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

	# Send via Polygin API
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
	try:
		doc = frappe.get_doc({
			"doctype": "Polygin Wa Messages",
			"sender_name": frappe.utils.get_fullname(frappe.session.user),
			"sender_mobile": normalized_for_api,
			"message": display_message,
			"message_type": message_type if message_type not in ("interactive_list", "interactive_button") else "interactive",
			"media_file": media_url,
			"timestamp": str(frappe.utils.now_datetime()),
			"origin": "outgoing",
			"direction": "outgoing",
			"normalized_phone": normalize_phone_for_matching(phone),
		})
		doc.insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Polygin Chat: Failed to store outgoing message")

	return result


@frappe.whitelist()
def upload_chat_media():
	"""Upload a file for sending via chat. Returns a public URL."""
	if "file" not in frappe.request.files:
		return {"success": False, "message": "No file provided."}

	filedata = frappe.request.files["file"]
	from frappe.utils.file_manager import save_file

	saved = save_file(
		filedata.filename,
		filedata.read(),
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
