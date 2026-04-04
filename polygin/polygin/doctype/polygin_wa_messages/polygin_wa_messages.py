import re

from frappe.model.document import Document


class PolyginWaMessages(Document):
	"""Stores incoming and outgoing WhatsApp messages received via Polygin webhooks."""

	def before_insert(self):
		if self.sender_mobile and not self.normalized_phone:
			self.normalized_phone = _normalize_phone_for_matching(self.sender_mobile)
		if not self.direction:
			self.direction = "incoming"


def _normalize_phone_for_matching(phone):
	digits = re.sub(r"[^0-9]", "", str(phone or ""))
	return digits[-10:] if len(digits) >= 10 else digits
