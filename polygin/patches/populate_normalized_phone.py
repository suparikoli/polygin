import re

import frappe


def execute():
	"""Populate normalized_phone and direction for all existing message records."""

	for doctype in ("Polygin Wa Messages", "Polygin Telegram Messages"):
		if not frappe.db.table_exists(doctype):
			continue

		records = frappe.get_all(
			doctype,
			filters={"normalized_phone": ("in", ("", None))},
			fields=["name", "sender_mobile"],
			limit_page_length=0,
		)

		for record in records:
			normalized = _normalize(record.sender_mobile)
			frappe.db.set_value(doctype, record.name, "normalized_phone", normalized, update_modified=False)

		# Set direction to incoming for all records that don't have it set
		frappe.db.sql(
			f"UPDATE `tab{doctype}` SET direction = 'incoming' WHERE direction IS NULL OR direction = ''"
		)

	frappe.db.commit()


def _normalize(phone):
	digits = re.sub(r"[^0-9]", "", str(phone or ""))
	return digits[-10:] if len(digits) >= 10 else digits
