import click
import frappe
from frappe.commands import pass_context


@click.command("rename-from-polygin")
@pass_context
def rename_from_polygin_cmd(context):
	"""Move this site from the old app name (polygin) to mith_wa_polygin. Run once, before migrate."""
	from mith_wa_polygin.patches.rename_from_polygin import execute

	for site in context.sites:
		frappe.init(site=site)
		frappe.connect()
		try:
			execute()
			click.echo(f"{site}: now on mith_wa_polygin; run `bench --site {site} migrate`")
		finally:
			frappe.destroy()


commands = [rename_from_polygin_cmd]
