import frappe

from polygin.utils import normalize_phone_for_matching


def execute():
	messages = [
		{"sender_name": "Rahul Sharma", "sender_mobile": "+918861577838", "message": "Hi, I'm interested in your services", "message_type": "text", "timestamp": "2026-04-04 09:00:00", "origin": "meta", "direction": "incoming"},
		{"sender_name": "You", "sender_mobile": "+918861577838", "message": "Hello Rahul! Thanks for reaching out. How can we help you today?", "message_type": "text", "timestamp": "2026-04-04 09:02:00", "origin": "outgoing", "direction": "outgoing"},
		{"sender_name": "Rahul Sharma", "sender_mobile": "+918861577838", "message": "I need a quote for your enterprise plan", "message_type": "text", "timestamp": "2026-04-04 09:05:00", "origin": "meta", "direction": "incoming"},
		{"sender_name": "You", "sender_mobile": "+918861577838", "message": "Sure! Let me send you the details.", "message_type": "text", "timestamp": "2026-04-04 09:06:00", "origin": "outgoing", "direction": "outgoing"},
		{"sender_name": "Rahul Sharma", "sender_mobile": "+918861577838", "message": "Also, can you send me a brochure?", "message_type": "text", "timestamp": "2026-04-04 09:10:00", "origin": "meta", "direction": "incoming"},
		{"sender_name": "You", "sender_mobile": "+918861577838", "message": "[Template: enterprise_welcome]", "message_type": "template", "timestamp": "2026-04-04 09:12:00", "origin": "outgoing", "direction": "outgoing"},
		{"sender_name": "Rahul Sharma", "sender_mobile": "+918861577838", "message": "Thanks! That looks great. When can we schedule a demo?", "message_type": "text", "timestamp": "2026-04-04 09:30:00", "origin": "meta", "direction": "incoming"},
		{"sender_name": "You", "sender_mobile": "+918861577838", "message": "How about tomorrow at 3 PM?", "message_type": "text", "timestamp": "2026-04-04 09:32:00", "origin": "outgoing", "direction": "outgoing"},
		{"sender_name": "Rahul Sharma", "sender_mobile": "+918861577838", "message": "Perfect, that works for me!", "message_type": "text", "timestamp": "2026-04-04 09:35:00", "origin": "meta", "direction": "incoming"},
		{"sender_name": "Rahul Sharma", "sender_mobile": "+918861577838", "message": "Just confirming - demo is still on for today at 3 PM?", "message_type": "text", "timestamp": "2026-04-04 11:45:00", "origin": "meta", "direction": "incoming"},
		{"sender_name": "You", "sender_mobile": "+918861577838", "message": "Yes, confirmed! I'll send you the meeting link shortly.", "message_type": "text", "timestamp": "2026-04-04 11:47:00", "origin": "outgoing", "direction": "outgoing"},
	]

	for m in messages:
		doc = frappe.get_doc({
			"doctype": "Polygin Wa Messages",
			"sender_name": m["sender_name"],
			"sender_mobile": m["sender_mobile"],
			"message": m["message"],
			"message_type": m["message_type"],
			"timestamp": m["timestamp"],
			"origin": m["origin"],
			"direction": m["direction"],
			"normalized_phone": normalize_phone_for_matching(m["sender_mobile"]),
			"uid": frappe.generate_hash(length=10),
		})
		doc.insert(ignore_permissions=True)

	# Ensure a Lead exists with this phone
	leads = frappe.get_all("Lead", filters={"mobile_no": ["like", "%8861577838%"]}, limit=1)
	if not leads:
		lead = frappe.get_doc({
			"doctype": "Lead",
			"first_name": "Rahul",
			"last_name": "Sharma",
			"mobile_no": "+918861577838",
			"email_id": "rahul.sharma.demo@example.com",
			"company_name": "Test Corp",
			"source": "Website",
		})
		lead.insert(ignore_permissions=True)

	frappe.db.commit()
	print(f"Inserted {len(messages)} dummy messages")
