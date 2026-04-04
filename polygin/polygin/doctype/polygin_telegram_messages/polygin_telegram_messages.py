from frappe.model.document import Document

from polygin.utils import normalize_phone_for_matching


class PolyginTelegramMessages(Document):
	"""Stores incoming and outgoing Telegram messages received via Polygin webhooks."""

	def before_insert(self):
		if self.sender_mobile and not self.normalized_phone:
			self.normalized_phone = normalize_phone_for_matching(self.sender_mobile)
		if not self.direction:
			self.direction = "incoming"
