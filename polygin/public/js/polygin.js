function polygin_send_template(frm, template_name, target_field) {
	frappe.call({
		method: "polygin.api.send_whatsapp_template",
		args: {
			doctype: frm.doctype,
			docname: frm.docname,
			template_name: template_name,
			target_field: target_field,
		},
		freeze: true,
		freeze_message: __("Sending WhatsApp template..."),
		callback: function (r) {
			if (r.exc) {
				frappe.msgprint(__("Server error while sending WhatsApp template. Please check Error Log."));
				return;
			}
			const response = r.message || {};
			if (response.success) {
				frappe.show_alert({
					message: response.message || __("WhatsApp template sent successfully."),
					indicator: "green",
				});
			} else {
				frappe.msgprint(response.message || __("Unable to send WhatsApp template."));
			}
		},
		error: function () {
			frappe.msgprint(__("Request failed before receiving a valid response from server."));
		},
	});
}

function polygin_add_buttons(frm, buttons) {
	const target_fields = [
		{ label: "Mobile", fieldname: "mobile_no" },
		{ label: "Phone", fieldname: "phone" },
		{ label: "WhatsApp", fieldname: "whatsapp_no" },
	];

	(buttons || []).forEach((button_config) => {
		target_fields.forEach((target) => {
			const button_label = `${button_config.button_name} - ${target.label}`;
			frm.add_custom_button(
				__(button_label),
				() => polygin_send_template(frm, button_config.template_name, target.fieldname),
				__("Polygin")
			);
		});
	});
}

function polygin_handle_refresh(frm) {
	if (frm._polygin_buttons_added || frm._polygin_buttons_loading) {
		return;
	}

	frm._polygin_buttons_loading = true;

	frappe.call({
		method: "polygin.api.get_buttons",
		callback: function (r) {
			polygin_add_buttons(frm, r.message);
			frm._polygin_buttons_added = true;
		},
		error: function () {
			// Allow a retry on next refresh if button fetch fails.
			frm._polygin_buttons_added = false;
		},
		always: function () {
			frm._polygin_buttons_loading = false;
		},
	});
}

// ── Chat Widget Integration ──────────────────────────────────
// Cache the chat widget setting to avoid repeated API calls.
let _polygin_chat_enabled = null;

function polygin_init_chat(frm) {
	if (frm.is_new()) {
		if (window._polygin_chat_instance) {
			window._polygin_chat_instance.destroy();
		}
		return;
	}

	if (typeof PolyginChat === "undefined") return;

	const mount = () => {
		const phone = PolyginChat.resolve_phone(frm);
		if (!phone) {
			if (window._polygin_chat_instance) {
				window._polygin_chat_instance.destroy();
			}
			return;
		}

		const name = PolyginChat.resolve_contact_name(frm);

		// If same phone and same doc, keep existing instance
		if (
			window._polygin_chat_instance &&
			window._polygin_chat_instance.phone === phone &&
			window._polygin_chat_instance.docname === frm.docname
		) {
			return;
		}

		// Destroy old instance and create new
		if (window._polygin_chat_instance) {
			window._polygin_chat_instance.destroy();
		}
		window._polygin_chat_instance = new PolyginChat({
			phone: phone,
			contact_name: name || phone,
			doctype: frm.doctype,
			docname: frm.docname,
		});
	};

	if (_polygin_chat_enabled !== null) {
		if (_polygin_chat_enabled) mount();
		return;
	}

	frappe.call({
		method: "polygin.api.get_chat_settings",
		callback: (r) => {
			const data = r.message || {};
			_polygin_chat_enabled = !!data.enable_chat_widget;
			if (_polygin_chat_enabled) mount();
		},
		error: () => { _polygin_chat_enabled = false; },
	});
}

// ── DocType Event Handlers ───────────────────────────────────

frappe.ui.form.on("Lead", {
	refresh: function (frm) {
		polygin_handle_refresh(frm);
		polygin_init_chat(frm);
	},
});

frappe.ui.form.on("Contact", {
	refresh: function (frm) {
		polygin_handle_refresh(frm);
		polygin_init_chat(frm);
	},
});

frappe.ui.form.on("Customer", {
	refresh: function (frm) {
		polygin_handle_refresh(frm);
		polygin_init_chat(frm);
	},
});

frappe.ui.form.on("Supplier", {
	refresh: function (frm) {
		polygin_handle_refresh(frm);
		polygin_init_chat(frm);
	},
});

frappe.ui.form.on("Opportunity", {
	refresh: function (frm) {
		polygin_handle_refresh(frm);
		polygin_init_chat(frm);
	},
});

const _polygin_transaction_doctypes = [
	"Sales Invoice", "Sales Order", "Quotation",
	"Delivery Note", "Purchase Order", "Purchase Invoice",
];
_polygin_transaction_doctypes.forEach((dt) => {
	frappe.ui.form.on(dt, {
		refresh: function (frm) {
			polygin_handle_refresh(frm);
			polygin_init_chat(frm);
		},
	});
});
