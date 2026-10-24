import json

import frappe


def execute():
	"""Fix direction for existing messages by reading route from raw_data."""

	for doctype in ("Polygin Wa Messages", "Polygin Telegram Messages"):
		if not frappe.db.table_exists(doctype):
			continue

		records = frappe.get_all(
			doctype,
			filters={"direction": "incoming"},
			fields=["name", "raw_data", "origin"],
			limit_page_length=0,
		)

		updated = 0
		for record in records:
			if not record.raw_data:
				continue
			try:
				data = json.loads(record.raw_data)
				route = (data.get("route") or "").upper()
				if route == "OUTGOING":
					frappe.db.set_value(doctype, record.name, "direction", "outgoing", update_modified=False)
					updated += 1
			except (ValueError, TypeError):
				continue

		if updated:
			frappe.db.commit()
			print(f"Fixed direction for {updated} messages in {doctype}")
