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

	const mount = async () => {
		const phone = await PolyginChat.resolve_phone_async(frm);
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

		// Auto-open chat widget when arriving from a Polygin notification link
		try {
			const params = new URLSearchParams(window.location.search);
			if (params.get("polygin_chat") === "open") {
				setTimeout(() => {
					try { window._polygin_chat_instance.expand_to_widget(); } catch (e) {}
				}, 300);
				// Strip the query param so refreshes don't keep reopening
				params.delete("polygin_chat");
				const newSearch = params.toString();
				const newUrl = window.location.pathname + (newSearch ? "?" + newSearch : "") + window.location.hash;
				window.history.replaceState({}, "", newUrl);
			}
		} catch (e) {}
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

const _polygin_all_doctypes = [
	"Lead", "Contact", "Customer", "Supplier", "Opportunity",
	"Sales Invoice", "Sales Order", "Quotation",
	"Delivery Note", "Purchase Order", "Purchase Invoice",
	"Purchase Receipt",
];

_polygin_all_doctypes.forEach((dt) => {
	frappe.ui.form.on(dt, {
		refresh: function (frm) {
			polygin_init_chat(frm);
		},
	});
});
