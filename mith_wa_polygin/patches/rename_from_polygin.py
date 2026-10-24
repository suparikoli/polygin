"""Move a site from the old app name to this one (owner-approved rename, 2026-10-24).

A site that still lists `polygin` in its installed apps cannot migrate once the old folder is gone, and
migrate only runs patches of installed apps (and `bench execute` refuses an app that is not installed).
So on such a site, run this once before the first migrate (the command is in mith_wa_polygin/commands.py):

    bench --site <site> rename-from-polygin
    bench --site <site> migrate

The migrate then records this patch (it is in patches.txt); on any other site it does nothing.

What moves: the installed-apps list, Installed Application rows, Module Def records (renamed modules
included, with every link to them), app fields on desk records (Desktop Icon, Workspace Sidebar …),
Patch Log entries (so old patches don't run again) and dotted method paths. Scheduled Job Types of the
old app are deleted; migrate creates them again from hooks.py.
"""

import json

import frappe

OLD_APPS = ["polygin"]
NEW_APP = "mith_wa_polygin"
# old module name -> new module name
MODULES = {"Polygin": "Mith WA Polygin"}

# Desk doctypes that store an app name (Frappe v16)
APP_FIELDS = [
	("Desktop Icon", "app"),
	("Dock", "app"),
	("Sidebar", "app"),
	("Sidebar Item Group", "app"),
	("Workspace Sidebar", "app"),
	("Website Theme Ignore App", "app"),
	("User Invitation", "app_name"),
]
# Fields that hold a dotted Python path
METHOD_FIELDS = [("Number Card", "method"), ("Notification", "method")]


def execute():
	installed = json.loads(frappe.db.get_global("installed_apps") or "[]")
	has_old_modules = frappe.db.exists("Module Def", {"app_name": ("in", OLD_APPS)}) or any(
		frappe.db.exists("Module Def", m) for m in MODULES
	)
	if not set(OLD_APPS) & set(installed) and not has_old_modules:
		return

	_installed_apps(installed)
	_modules()
	for doctype, field in APP_FIELDS:
		if _has(doctype, field):
			for old in OLD_APPS:
				frappe.db.sql(f"update `tab{doctype}` set `{field}`=%s where `{field}`=%s", (NEW_APP, old))
	for old in OLD_APPS:
		_prefix("Patch Log", "patch", old)
		for doctype, field in METHOD_FIELDS:
			if _has(doctype, field):
				_prefix(doctype, field, old)
		frappe.db.delete("Scheduled Job Type", {"method": ("like", f"{old}.%")})

	frappe.db.commit()
	try:
		from frappe.installer import _sync_installed_apps_to_site_config

		_sync_installed_apps_to_site_config()
	except ImportError:
		pass
	frappe.clear_cache()


def _installed_apps(installed):
	apps = []
	for app in installed:
		app = NEW_APP if app in OLD_APPS else app
		if app not in apps:
			apps.append(app)
	frappe.db.set_global("installed_apps", json.dumps(apps))

	rows = frappe.get_all("Installed Application", filters={"app_name": ("in", OLD_APPS)}, pluck="name")
	if frappe.db.exists("Installed Application", {"app_name": NEW_APP}):
		for name in rows:
			frappe.db.delete("Installed Application", name)
	elif rows:
		frappe.db.set_value("Installed Application", rows[0], "app_name", NEW_APP)
		for name in rows[1:]:
			frappe.db.delete("Installed Application", name)


def _modules():
	for old, new in MODULES.items():
		if not frappe.db.exists("Module Def", old):
			continue
		if frappe.db.exists("Module Def", new):
			frappe.db.delete("Module Def", old)
		else:
			frappe.db.sql(
				"update `tabModule Def` set name=%s, module_name=%s where name=%s", (new, new, old)
			)
		_relink_module(old, new)
	frappe.db.sql(
		"update `tabModule Def` set app_name=%s where app_name in %s", (NEW_APP, tuple(OLD_APPS))
	)


def _relink_module(old, new):
	links = frappe.db.sql(
		"""select parent, fieldname from `tabDocField` where fieldtype='Link' and options='Module Def'
		union select dt, fieldname from `tabCustom Field` where fieldtype='Link' and options='Module Def'"""
	)
	links = [*links, ("Workspace Sidebar", "module"), ("Block Module", "module")]
	for doctype, field in set(links):
		if frappe.db.get_value("DocType", doctype, "issingle"):
			frappe.db.sql(
				"update `tabSingles` set value=%s where doctype=%s and field=%s and value=%s",
				(new, doctype, field, old),
			)
		elif _has(doctype, field):
			frappe.db.sql(f"update `tab{doctype}` set `{field}`=%s where `{field}`=%s", (new, old))


def _prefix(doctype, field, old):
	frappe.db.sql(
		f"update `tab{doctype}` set `{field}`=concat(%s, substring(`{field}`, %s)) where `{field}` like %s",
		(f"{NEW_APP}.", len(old) + 2, f"{old}.%"),
	)


def _has(doctype, field):
	return frappe.db.table_exists(doctype) and frappe.db.has_column(doctype, field)
