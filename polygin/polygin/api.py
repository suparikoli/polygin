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
