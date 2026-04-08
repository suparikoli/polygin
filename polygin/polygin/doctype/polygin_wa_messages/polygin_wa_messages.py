import json as _json

import frappe
from frappe.model.document import Document

from polygin.utils import normalize_phone_for_matching


class PolyginWaMessages(Document):
	"""Stores incoming and outgoing WhatsApp messages received via Polygin webhooks."""

	def before_insert(self):
		if self.sender_mobile and not self.normalized_phone:
			self.normalized_phone = normalize_phone_for_matching(self.sender_mobile)
		# Always derive direction from raw_data.route — the webhook may send
		# incorrect direction, but the route field from Polyg.in is authoritative.
		self.direction = self._detect_direction()
		# Extract media URL from webhook payload so the chat widget can render it.
		if not self.media_file and self.raw_data:
			self.media_file = self._extract_media_url()

	def after_insert(self):
		try:
			self._notify_last_agent()
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Polygin: notify_last_agent failed")

	def _detect_direction(self):
		"""Detect message direction from raw webhook data."""
		if self.raw_data:
			try:
				data = _json.loads(self.raw_data) if isinstance(self.raw_data, str) else self.raw_data
				route = (data.get("route") or "").upper()
				if route == "OUTGOING":
					return "outgoing"
			except (ValueError, TypeError, AttributeError):
				pass
		if self.origin == "outgoing":
			return "outgoing"
		return "incoming"

	def _extract_media_url(self):
		"""Extract media link from raw webhook data (msgContext.{type}.link)."""
		try:
			data = _json.loads(self.raw_data) if isinstance(self.raw_data, str) else self.raw_data
			ctx = data.get("msgContext") or {}
			for key in ("document", "image", "video", "audio"):
				media = ctx.get(key)
				if isinstance(media, dict) and media.get("link"):
					return media["link"]
		except (ValueError, TypeError, AttributeError):
			pass
		return None

	def _notify_last_agent(self):
		"""Notify the last ERPNext user who handled this conversation about new activity.

		Rules:
		- Look up the most recent prior outgoing message sent from ERPNext (origin='outgoing')
		  for the same normalized_phone.
		- Notify that message's owner via Frappe's Notification Log (bell icon).
		- Skip self-notification if the current message is also owned by that same user.
		"""
		if not self.normalized_phone:
			return

		# 1. Most recent ERPNext-originated conversational message for this phone
		prior_msg = frappe.db.sql(
			"""
			SELECT owner, creation
			FROM `tabPolygin Wa Messages`
			WHERE normalized_phone = %s
			  AND direction = 'outgoing'
			  AND origin = 'outgoing'
			  AND name != %s
			ORDER BY creation DESC
			LIMIT 1
			""",
			(self.normalized_phone, self.name or ""),
			as_dict=True,
		)

		# 2. Most recent Polygin Message Log entry (= template sent via Template API).
		#    Template sends don't create a local Polygin Wa Messages record, so we
		#    look up who sent the template by matching the recipient phone.
		like = f"%{self.normalized_phone}%"
		prior_log = frappe.db.sql(
			"""
			SELECT owner, creation
			FROM `tabPolygin Message Log`
			WHERE recipient LIKE %s
			  AND status = 'Success'
			ORDER BY creation DESC
			LIMIT 1
			""",
			(like,),
			as_dict=True,
		)

		# Build the set of users to notify:
		#   - Last person to chat (most recent ERPNext user who sent a chat
		#     message OR template to this contact)
		#   - Document owner (Lead/Customer/etc. owner — the CRM rep)
		# If neither is available, fall back to Administrator.
		target_users = set()

		candidates = []
		if prior_msg:
			candidates.append(prior_msg[0])
		if prior_log:
			candidates.append(prior_log[0])
		if candidates:
			candidates.sort(key=lambda r: r.creation, reverse=True)
			owner = candidates[0].owner
			if owner and owner not in ("Administrator", "Guest"):
				target_users.add(owner)

		# Resolve the linked CRM record from the phone (used both for finding
		# the document owner AND for the notification link target).
		linked = _find_linked_contact(self.normalized_phone)
		if linked:
			try:
				doc_owner = frappe.db.get_value(linked[0], linked[1], "owner")
				if doc_owner and doc_owner not in ("Administrator", "Guest"):
					target_users.add(doc_owner)
			except Exception:
				pass

		# Absolute fallback
		if not target_users:
			target_users.add("Administrator")

		# Skip self-notification: remove the currently-sending agent from the set
		if self.origin == "outgoing" and self.owner:
			target_users.discard(self.owner)
		if not target_users:
			return

		# Build subject — identify who actually sent the message.
		# Cases:
		#   direction=incoming              → contact replied (sender_name = contact)
		#   origin='outgoing'               → ERPNext user sent from chat widget
		#                                     (sender_name = agent, sender_mobile = recipient)
		#   origin='meta', direction='outgoing' → sent from Polyg.in web app
		#                                          (sender_name = contact, sender_mobile = contact)
		logo = "<img src='/assets/polygin/images/polygin_logo.webp' style='width:16px;height:16px;vertical-align:middle;margin-right:4px;'/>"

		if self.direction == "incoming":
			contact = self.sender_name or self.sender_mobile or "contact"
			subject = f"{logo} New WhatsApp reply from {contact}"
		elif self.origin == "outgoing":
			agent = (
				self.responding_agent
				or (frappe.utils.get_fullname(self.owner) if self.owner else None)
				or "An agent"
			)
			recipient = self.sender_mobile or "contact"
			subject = f"{logo} {agent} sent WhatsApp to {recipient}"
		else:
			# Sent from Polyg.in web app / bot — echoed back by webhook
			contact = self.sender_name or self.sender_mobile or "contact"
			subject = f"{logo} Polygin sent WhatsApp to {contact}"

		snippet = (self.message or f"[{self.message_type or 'message'}]")[:140]

		# Resolve a linked contact/lead so clicking the notification opens that
		# record (which auto-loads the chat widget via the ?polygin_chat=open hint).
		# (linked was already computed above when looking up the doc owner.)
		if linked:
			doctype, docname = linked
			link = f"/app/{frappe.scrub(doctype).replace('_', '-')}/{docname}?polygin_chat=open"
		else:
			doctype, docname = "Polygin Wa Messages", self.name
			link = f"/app/polygin-wa-messages/{self.name}?polygin_chat=open"

		from_user = self.owner if self.owner not in (None, "Guest") else "Administrator"

		# Create one Notification Log entry per target user
		for user in target_users:
			frappe.get_doc({
				"doctype": "Notification Log",
				"subject": subject,
				"email_content": snippet,
				"for_user": user,
				"type": "Alert",
				"document_type": doctype,
				"document_name": docname,
				"link": link,
				"from_user": from_user,
			}).insert(ignore_permissions=True)


def _find_linked_contact(normalized_phone):
	"""Find a Lead/Contact/Customer/etc. matching this phone number.

	Returns (doctype, docname) or None. Uses SQL LIKE on the last-10-digit
	normalized phone for an indexed, fast lookup.
	"""
	if not normalized_phone:
		return None

	from polygin.utils import normalize_phone_for_matching

	like = f"%{normalized_phone}%"
	# (doctype, fields to check) — priority order. Master records (Customer,
	# Lead, Supplier) come first, then transactional records as fallbacks.
	candidates = [
		("Customer", ["mobile_no", "contact_mobile", "contact_phone"]),
		("Lead", ["whatsapp_no", "mobile_no", "phone"]),
		("Supplier", ["mobile_no", "contact_mobile", "contact_phone"]),
		("Opportunity", ["contact_mobile", "contact_phone"]),
		("Quotation", ["contact_mobile", "contact_phone"]),
		("Sales Order", ["contact_mobile", "contact_phone"]),
		("Sales Invoice", ["contact_mobile", "contact_phone"]),
		("Delivery Note", ["contact_mobile", "contact_phone"]),
		("Purchase Order", ["contact_mobile", "contact_phone"]),
		("Purchase Invoice", ["contact_mobile", "contact_phone"]),
		("Purchase Receipt", ["contact_mobile", "contact_phone"]),
	]

	for doctype, fields in candidates:
		for field in fields:
			try:
				rows = frappe.db.sql(
					f"SELECT name, `{field}` AS val FROM `tab{doctype}` WHERE `{field}` LIKE %s LIMIT 10",
					(like,),
					as_dict=True,
				)
			except Exception:
				continue
			for row in rows:
				if normalize_phone_for_matching(row.val) == normalized_phone:
					return (doctype, row.name)

	# Contact doctype: phones are in the `Contact Phone` child table.
	# A Contact is typically linked to a Customer/Lead via `Dynamic Link`,
	# so prefer returning that parent record (Customer > Lead > Supplier).
	try:
		contact_rows = frappe.db.sql(
			"SELECT DISTINCT parent FROM `tabContact Phone` WHERE phone LIKE %s LIMIT 20",
			(like,),
			as_dict=True,
		)
	except Exception:
		contact_rows = []

	for crow in contact_rows:
		contact_name = crow.parent
		# Verify the phone actually normalizes to the same value
		phones = frappe.db.sql(
			"SELECT phone FROM `tabContact Phone` WHERE parent = %s",
			(contact_name,),
			as_dict=True,
		)
		if not any(normalize_phone_for_matching(p.phone) == normalized_phone for p in phones):
			continue

		# Look up which record this Contact is linked to (Dynamic Link)
		try:
			links = frappe.db.sql(
				"""
				SELECT link_doctype, link_name
				FROM `tabDynamic Link`
				WHERE parent = %s AND parenttype = 'Contact'
				  AND link_doctype IN ('Customer', 'Lead', 'Supplier')
				ORDER BY FIELD(link_doctype, 'Customer', 'Lead', 'Supplier')
				LIMIT 1
				""",
				(contact_name,),
				as_dict=True,
			)
		except Exception:
			links = []
		if links:
			return (links[0].link_doctype, links[0].link_name)
		# Fallback: return the Contact itself
		return ("Contact", contact_name)

	return None
