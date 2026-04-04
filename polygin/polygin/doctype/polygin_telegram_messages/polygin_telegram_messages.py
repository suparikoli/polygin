import json as _json

from frappe.model.document import Document

from polygin.utils import normalize_phone_for_matching


class PolyginTelegramMessages(Document):
	"""Stores incoming and outgoing Telegram messages received via Polygin webhooks."""

	def before_insert(self):
		if self.sender_mobile and not self.normalized_phone:
			self.normalized_phone = normalize_phone_for_matching(self.sender_mobile)
		# Always derive direction from raw_data.route — authoritative source.
		self.direction = self._detect_direction()

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
