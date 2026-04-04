import frappe

from polygin.utils import normalize_phone_for_matching


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
			normalized = normalize_phone_for_matching(record.sender_mobile)
			frappe.db.set_value(doctype, record.name, "normalized_phone", normalized, update_modified=False)

		# Set direction to incoming for all records that don't have it set
		qb_table = frappe.qb.DocType(doctype)
		frappe.qb.update(qb_table).set(qb_table.direction, "incoming").where(
			(qb_table.direction.isnull()) | (qb_table.direction == "")
		).run()

	frappe.db.commit()
