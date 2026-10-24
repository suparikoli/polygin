import frappe


DOCTYPE_TEMPLATE_MSG = (
	"Hi {{1}},\n\n"
	"Good news! Your requested {{2}} document, *{{3}}*, is now available.\n\n"
	"You can download it here:\n{{4}}\n\n"
	"Let me know if you need any assistance."
)

TRANSACTIONAL_DOCTYPES = [
	"Sales Invoice", "Sales Order", "Quotation",
	"Delivery Note", "Purchase Order", "Purchase Invoice",
	"Purchase Receipt",
]


def execute():
	"""Migrate variable mappings into Polygin Button rows and create default doctype templates."""

	settings = frappe.get_single("Polygin Settings")

	# 1. Migrate existing variable mappings into button rows
	mappings = settings.get("variable_mapping") or []
	buttons = settings.get("buttons") or []

	for btn in buttons:
		# Find variable mappings for this template
		btn_mappings = sorted(
			[m for m in mappings if (m.template_name or "").strip() == (btn.template_name or "").strip()],
			key=lambda m: int(m.variable_index or 0),
		)
		for mapping in btn_mappings:
			idx = int(mapping.variable_index or 0)
			if 1 <= idx <= 9:
				field = f"var_{idx}"
				if not btn.get(field):
					btn.set(field, mapping.field_name)

	# 2. Create default doctype template entries
	existing_doctype_templates = {
		(btn.template_name, btn.for_doctype)
		for btn in buttons
		if btn.template_name == "doctype"
	}

	for dt in TRANSACTIONAL_DOCTYPES:
		if ("doctype", dt) not in existing_doctype_templates:
			settings.append("buttons", {
				"button_name": "Send Document",
				"template_name": "doctype",
				"for_doctype": dt,
				"is_programmatic": 1,
				"is_active": 1,
				"message": DOCTYPE_TEMPLATE_MSG,
			})

	settings.save(ignore_permissions=True)
	frappe.db.commit()
	print("Migrated variable mappings and created doctype templates")
