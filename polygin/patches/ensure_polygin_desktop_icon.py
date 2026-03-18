import json

import frappe


def _build_icon_payload(icon):
	return {
		"label": icon.label,
		"bg_color": icon.bg_color,
		"link": icon.link,
		"link_type": icon.link_type,
		"app": icon.app,
		"icon_type": icon.icon_type,
		"parent_icon": icon.parent_icon,
		"icon": icon.icon,
		"link_to": icon.link_to,
		"idx": icon.idx,
		"standard": icon.standard,
		"logo_url": icon.logo_url,
		"hidden": icon.hidden,
		"name": icon.name,
		"restrict_removal": icon.restrict_removal,
		"icon_image": icon.icon_image,
		"child_icons": [],
	}


def execute():
	icon_name = frappe.db.get_value("Desktop Icon", {"app": "polygin", "icon_type": "App"}, "name")
	if not icon_name:
		icon = frappe.new_doc("Desktop Icon")
		icon.update(
			{
				"label": "Polygin",
				"icon_type": "App",
				"link_type": "External",
				"app": "polygin",
				"link": "/app/polygin",
				"logo_url": "/assets/polygin/images/polygin_logo.webp",
				"icon_image": "/assets/polygin/images/polygin_logo.webp",
				"standard": 1,
			}
		)
		icon.insert(ignore_permissions=True)
		icon_name = icon.name
	else:
		frappe.db.set_value("Desktop Icon", icon_name, "link", "/app/polygin")

	icon = frappe.get_doc("Desktop Icon", icon_name)
	icon_payload = _build_icon_payload(icon)

	for layout_name in frappe.get_all("Desktop Layout", pluck="name"):
		layout_raw = frappe.db.get_value("Desktop Layout", layout_name, "layout") or "[]"
		try:
			layout = json.loads(layout_raw)
		except Exception:
			layout = []

		if any(item.get("app") == "polygin" or item.get("name") == icon.name for item in layout):
			continue

		layout.append(icon_payload)
		frappe.db.set_value("Desktop Layout", layout_name, "layout", json.dumps(layout))
		frappe.cache.hdel("desktop_icons", layout_name)
		frappe.cache.hdel("bootinfo", layout_name)

