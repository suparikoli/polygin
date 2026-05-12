"""Backfill cost/currency on existing Polygin Message Log entries.

Uses the configured default_cost_per_send and currency from Polygin Settings.
Safe to run multiple times — only touches rows where cost is NULL or 0 and
status is Success.
"""

import frappe


def execute():
	if not frappe.db.table_exists("Polygin Message Log"):
		return

	settings = frappe.get_single("Polygin Settings")
	default_cost = frappe.utils.flt(settings.get("default_cost_per_send"))
	currency = frappe.utils.cstr(settings.get("currency")) or None

	if default_cost <= 0 and not currency:
		return

	# Build a template -> (cost, category) lookup so backfill respects per-template overrides.
	template_lookup = {}
	for row in settings.get("buttons") or []:
		key = frappe.utils.cstr(row.template_name).strip()
		if not key:
			continue
		row_cost = frappe.utils.flt(row.get("cost_per_send"))
		template_lookup[key] = (
			row_cost if row_cost > 0 else default_cost,
			frappe.utils.cstr(row.get("category")) or None,
		)

	logs = frappe.get_all(
		"Polygin Message Log",
		filters={"status": "Success", "cost": ("in", (0, None))},
		fields=["name", "template"],
	)
	for log in logs:
		key = frappe.utils.cstr(log.template).strip()
		cost, category = template_lookup.get(key, (default_cost, None))
		frappe.db.set_value(
			"Polygin Message Log",
			log.name,
			{"cost": cost, "currency": currency, "category": category},
			update_modified=False,
		)

	frappe.db.commit()
