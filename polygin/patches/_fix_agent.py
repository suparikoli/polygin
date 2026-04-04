import frappe

def execute():
	frappe.db.sql("UPDATE `tabPolygin Wa Messages` SET responding_agent = 'Administrator' WHERE direction = 'outgoing' AND (responding_agent IS NULL OR responding_agent = '')")
	frappe.db.commit()
	print("Done")
