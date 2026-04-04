import re


def normalize_phone_for_matching(phone):
	"""Strip to last 10 digits for cross-format phone matching."""
	digits = re.sub(r"[^0-9]", "", str(phone or ""))
	return digits[-10:] if len(digits) >= 10 else digits
