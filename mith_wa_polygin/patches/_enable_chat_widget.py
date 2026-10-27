import frappe

def execute():
	frappe.db.set_single_value("Polygin Settings", "enable_chat_widget", 1)
	frappe.db.commit()
	print("Chat widget enabled")
