import json as _json

import frappe
from frappe.model.document import Document

from polygin.utils import normalize_phone_for_matching


class PolyginWaMessages(Document):
	"""Stores incoming and outgoing WhatsApp messages received via Polygin webhooks."""

	def before_insert(self):
		if self.sender_mobile and not self.normalized_phone:
			self.normalized_phone = normalize_phone_for_matching(self.sender_mobile)
		# Always derive direction from raw_data.route — the webhook may send
		# incorrect direction, but the route field from Polyg.in is authoritative.
		self.direction = self._detect_direction()
		# Extract media URL from webhook payload so the chat widget can render it.
		if not self.media_file and self.raw_data:
			self.media_file = self._extract_media_url()

	def after_insert(self):
		try:
			self._notify_last_agent()
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Polygin: notify_last_agent failed")

	def _detect_direction(self):
		"""Detect message direction from raw webhook data."""
		if self.raw_data:
			try:
				data = _json.loads(self.raw_data) if isinstance(self.raw_data, str) else self.raw_data
				route = (data.get("route") or "").upper()
				if route == "OUTGOING":
					return "outgoing"
			except (ValueError, TypeError, AttributeError):
				pass
		if self.origin == "outgoing":
			return "outgoing"
		return "incoming"

	def _extract_media_url(self):
		"""Extract media link from raw webhook data (msgContext.{type}.link)."""
		try:
			data = _json.loads(self.raw_data) if isinstance(self.raw_data, str) else self.raw_data
			ctx = data.get("msgContext") or {}
			for key in ("document", "image", "video", "audio"):
				media = ctx.get(key)
				if isinstance(media, dict) and media.get("link"):
					return media["link"]
		except (ValueError, TypeError, AttributeError):
			pass
		return None

	def _notify_last_agent(self):
		"""Notify the last ERPNext user who handled this conversation about new activity.

		Rules:
		- Look up the most recent prior outgoing message sent from ERPNext (origin='outgoing')
		  for the same normalized_phone.
		- Notify that message's owner via Frappe's Notification Log (bell icon).
		- Skip self-notification if the current message is also owned by that same user.
		"""
		if not self.normalized_phone:
			return

		prior = frappe.db.sql(
			"""
			SELECT owner, responding_agent
			FROM `tabPolygin Wa Messages`
			WHERE normalized_phone = %s
			  AND direction = 'outgoing'
			  AND origin = 'outgoing'
			  AND name != %s
			ORDER BY creation DESC
			LIMIT 1
			""",
			(self.normalized_phone, self.name or ""),
			as_dict=True,
		)

		# Fallback: if no prior ERPNext-originated message exists for this contact,
		# notify the Administrator so the conversation isn't missed.
		target_user = (prior[0].owner if prior else None) or "Administrator"
		if target_user == "Guest":
			return

		# Skip self-notification: the agent themselves just sent this message from ERPNext
		if self.origin == "outgoing" and self.owner == target_user:
			return

		# Build subject
		who = self.sender_name or self.sender_mobile or "WhatsApp"
		if self.direction == "incoming":
			subject = f"New WhatsApp reply from {who}"
		else:
			subject = f"New WhatsApp activity with {who}"

		snippet = (self.message or f"[{self.message_type or 'message'}]")[:140]

		frappe.get_doc({
			"doctype": "Notification Log",
			"subject": subject,
			"email_content": snippet,
			"for_user": target_user,
			"type": "Alert",
			"document_type": "Polygin Wa Messages",
			"document_name": self.name,
			"from_user": self.owner if self.owner not in (None, "Guest") else "Administrator",
		}).insert(ignore_permissions=True)
