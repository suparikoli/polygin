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

frappe.ui.form.on("Lead", {
	refresh: function (frm) {
		polygin_handle_refresh(frm);
	},
});

frappe.ui.form.on("Contact", {
	refresh: function (frm) {
		polygin_handle_refresh(frm);
	},
});

frappe.ui.form.on("Customer", {
	refresh: function (frm) {
		polygin_handle_refresh(frm);
	},
});
