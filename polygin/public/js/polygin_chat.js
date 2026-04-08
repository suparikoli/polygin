/**
 * Polygin Chat Widget
 *
 * A WhatsApp-style live chat widget that integrates into Frappe DocType forms.
 * Loaded globally via app_include_js, instantiated from polygin.js per-form.
 */

const TRANSACTIONAL_DOCTYPES = new Set([
	"Sales Invoice", "Sales Order", "Quotation",
	"Delivery Note", "Purchase Order", "Purchase Invoice",
	"Purchase Receipt",
]);

// WhatsApp character limits
const WA_LIMITS = {
	TEXT_BODY: 4096,
	INTERACTIVE_BODY: 1024,
	HEADER: 60,
	FOOTER: 60,
	BUTTON_TITLE: 20,
	LIST_BUTTON_TEXT: 20,
	SECTION_TITLE: 24,
	ROW_TITLE: 24,
	ROW_DESC: 72,
	MAX_BUTTONS: 3,
	MAX_ROWS: 10,
	MAX_SECTIONS: 10,
};

class PolyginChat {
	constructor({ phone, contact_name, doctype, docname }) {
		this.phone = phone;
		this.contact_name = contact_name || phone;
		this.doctype = doctype;
		this.docname = docname;
		this.messages = [];
		this.messageIds = new Set();
		this.pollInterval = null;
		this.countdownInterval = null;
		this.responseWindow = { is_active: false, seconds_remaining: 0 };
		this.isFullscreen = false;
		this.isOpen = false;
		this.isLoading = false;
		this.isSending = false;
		this.attachMenuOpen = false;
		this.templateButtons = null;

		this.$bubble = null;
		this.$widget = null;

		this.render_bubble();
	}

	// ── Bubble ───────────────────────────────────────────────

	render_bubble() {
		this.remove_bubble();
		this.$bubble = $(`
			<button class="polygin-chat-bubble" title="Chat via Polygin">
				<img src="/assets/polygin/images/polygin_logo.webp" alt="Polygin">
			</button>
		`);
		this.$bubble.on("click", () => this.expand_to_widget());
		$("body").append(this.$bubble);
	}

	remove_bubble() {
		if (this.$bubble) { this.$bubble.remove(); this.$bubble = null; }
	}

	// ── Widget Panel ─────────────────────────────────────────

	expand_to_widget() {
		this.remove_bubble();
		this.remove_widget();
		this.isOpen = true;
		this.isFullscreen = false;
		this.$widget = $(`<div class="polygin-chat-widget"></div>`);
		this._render_widget_content();
		$("body").append(this.$widget);
		this.fetch_messages();
		this.start_polling();
	}

	expand_to_fullscreen() {
		if (!this.$widget) return;
		this.isFullscreen = true;
		this.$widget.addClass("polygin-chat-fullscreen");
		this.$widget.find(".polygin-tl-fullscreen").addClass("polygin-tl-minimize-state");
	}

	collapse_to_widget() {
		if (!this.$widget) return;
		this.isFullscreen = false;
		this.$widget.removeClass("polygin-chat-fullscreen");
		this.$widget.find(".polygin-tl-fullscreen").removeClass("polygin-tl-minimize-state");
	}

	collapse_to_bubble() {
		this.isOpen = false;
		this.stop_polling();
		this.stop_countdown();
		this.remove_widget();
		this.render_bubble();
	}

	remove_widget() {
		if (this.$widget) { this.$widget.remove(); this.$widget = null; }
	}

	_render_widget_content() {
		const initials = (this.contact_name || "?").charAt(0).toUpperCase();
		const isTransactional = TRANSACTIONAL_DOCTYPES.has(this.doctype);
		const sendDocBtn = isTransactional ? `<button class="polygin-send-doc-btn" title="Send Document">&#x1F4E4;</button>` : "";
		this.$widget.html(`
			<div class="polygin-chat-header">
				<div class="polygin-chat-avatar">${initials}</div>
				<div class="polygin-chat-header-info">
					<div class="polygin-chat-header-name">${frappe.utils.escape_html(this.contact_name)}</div>
					<div class="polygin-chat-header-phone">${frappe.utils.escape_html(this.phone)}</div>
				</div>
				<div class="polygin-chat-header-actions">
					${sendDocBtn}
					<span class="polygin-traffic-light polygin-tl-fullscreen" title="Fullscreen"></span>
					<span class="polygin-traffic-light polygin-tl-close" title="Close"></span>
				</div>
			</div>
			<div class="polygin-chat-response-window" style="display:none;"></div>
			<div class="polygin-chat-messages">
				<div class="polygin-chat-loading">Loading messages...</div>
			</div>
			<div class="polygin-chat-input-container" style="position:relative;">
				<div class="polygin-chat-input-area">
					<button class="polygin-chat-attach-btn" title="Attach">&#x1F4CE;</button>
					<button class="polygin-chat-qr-btn" title="Quick Replies">&#x26A1;</button>
					<div class="polygin-chat-input-wrapper">
						<textarea rows="1" placeholder="Type a message..." maxlength="${WA_LIMITS.TEXT_BODY}"></textarea>
						<span class="polygin-char-count" style="display:none;">0/${WA_LIMITS.TEXT_BODY}</span>
					</div>
					<button class="polygin-chat-send-btn" title="Send">&#x27A4;</button>
				</div>
			</div>
			<div class="polygin-watermark">Powered by <a href="https://polyg.in" target="_blank">Polygin</a></div>
		`);

		this.$widget.find(".polygin-tl-close").on("click", () => this.collapse_to_bubble());
		this.$widget.find(".polygin-send-doc-btn").on("click", () => this._send_document());
		this.$widget.find(".polygin-tl-fullscreen").on("click", () => {
			this.isFullscreen ? this.collapse_to_widget() : this.expand_to_fullscreen();
		});
		this.$widget.find(".polygin-chat-send-btn").on("click", () => this.send_text_message());
		this._bindTextarea(this.$widget.find("textarea"));
		this.$widget.find(".polygin-chat-attach-btn").on("click", (e) => {
			e.stopPropagation();
			this.toggle_attach_menu();
		});
		this.$widget.find(".polygin-chat-qr-btn").on("click", (e) => {
			e.stopPropagation();
			this.show_quick_replies();
		});
		$(document).off("click.polygin_attach").on("click.polygin_attach", () => { this.close_attach_menu(); this._close_quick_replies(); });
	}

	_bindTextarea($ta) {
		$ta.on("keydown", (e) => {
			if (e.key === "Enter" && !e.shiftKey) {
				e.preventDefault();
				const val = $ta.val().trim();
				// Check for shortcode before sending
				if (val.startsWith("/") && !val.includes(" ")) {
					this._expandShortcode($ta, val.substring(1));
				} else {
					this.send_text_message();
				}
			}
		});
		$ta.on("input", function () {
			this.style.height = "auto";
			this.style.height = Math.min(this.scrollHeight, 100) + "px";
			const $counter = $(this).siblings(".polygin-char-count");
			const len = this.value.length;
			$counter.text(`${len}/${WA_LIMITS.TEXT_BODY}`);
			$counter.toggle(len > 0);
			$counter.toggleClass("over-limit", len > WA_LIMITS.TEXT_BODY);
		});
	}

	_expandShortcode($ta, code) {
		frappe.call({
			method: "polygin.api.get_quick_replies",
			callback: (r) => {
				const replies = r.message || [];
				const match = replies.find((qr) => qr.shortcode && qr.shortcode.toLowerCase() === code.toLowerCase());
				if (!match) {
					// No match — send as regular text
					this.send_text_message();
					return;
				}
				if (match.message_type === "text" || !match.message_type) {
					$ta.val(match.message).trigger("input").focus();
					frappe.show_alert({ message: __(`Shortcode /${code} expanded`), indicator: "blue" });
				} else {
					// Interactive quick reply — send directly
					let payload = null;
					try { payload = match.interactive_payload ? JSON.parse(match.interactive_payload) : null; } catch (e) { console.warn("Polygin: failed to parse interactive_payload", e); payload = null; }
					if (payload) {
						$ta.val("").trigger("input");
						const type = match.message_type === "button" ? "interactive_button" : "interactive_list";
						this._send_interactive(type, payload, match.message);
					} else {
						$ta.val(match.message).trigger("input").focus();
					}
				}
			},
		});
	}

	// ── Message Fetching ─────────────────────────────────────

	fetch_messages() {
		if (this.isLoading) return;
		this.isLoading = true;
		frappe.call({
			method: "polygin.api.get_chat_messages",
			args: { phone: this.phone, channel: "whatsapp", page: 1, page_size: 100 },
			callback: (r) => {
				if (!r.message) return;
				const data = r.message;
				this.messages = data.messages || [];
				this.messageIds = new Set(this.messages.map((m) => m.id));
				this.responseWindow = data.response_window || { is_active: false };
				this.render_messages();
				this.render_response_window();
				this._update_input_state();
			},
			always: () => { this.isLoading = false; },
		});
	}

	start_polling() {
		this.stop_polling();
		this.pollInterval = setInterval(() => this._poll_new(), 7000);
	}

	stop_polling() {
		if (this.pollInterval) { clearInterval(this.pollInterval); this.pollInterval = null; }
	}

	_poll_new() {
		if (this.isLoading || !this.isOpen) return;
		this.isLoading = true;
		frappe.call({
			method: "polygin.api.get_chat_messages",
			args: { phone: this.phone, channel: "whatsapp", page: 1, page_size: 100 },
			callback: (r) => {
				if (!r.message) return;
				const data = r.message;
				const newMsgs = (data.messages || []).filter((m) => !this.messageIds.has(m.id));
				if (newMsgs.length > 0) {
					for (const m of newMsgs) { this.messages.push(m); this.messageIds.add(m.id); }
					this.messages.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
					this._append_new_messages(newMsgs);
				}
				this.responseWindow = data.response_window || { is_active: false };
				this.render_response_window();
				this._update_input_state();
			},
			always: () => { this.isLoading = false; },
		});
	}

	// ── Render Messages ──────────────────────────────────────

	render_messages() {
		if (!this.$widget) return;
		const $list = this.$widget.find(".polygin-chat-messages");
		const wasAtBottom = $list[0].scrollHeight - $list[0].scrollTop - $list[0].clientHeight < 60;
		$list.empty();
		if (this.messages.length === 0) {
			$list.html('<div class="polygin-chat-empty">No messages yet</div>');
			return;
		}
		let lastDate = "";
		for (const msg of this.messages) {
			const msgDate = this._format_date(msg.timestamp);
			if (msgDate !== lastDate) { lastDate = msgDate; $list.append(`<div class="polygin-date-separator"><span>${msgDate}</span></div>`); }
			$list.append(this._render_message(msg));
		}
		if (wasAtBottom) { $list[0].scrollTop = $list[0].scrollHeight; }
	}

	_append_new_messages(newMsgs) {
		if (!this.$widget) return;
		const $list = this.$widget.find(".polygin-chat-messages");
		const wasAtBottom = $list[0].scrollHeight - $list[0].scrollTop - $list[0].clientHeight < 60;
		$list.find(".polygin-chat-empty").remove();
		const lastSep = $list.find(".polygin-date-separator:last span").text();
		for (const msg of newMsgs) {
			const msgDate = this._format_date(msg.timestamp);
			if (msgDate && msgDate !== lastSep) { $list.append(`<div class="polygin-date-separator"><span>${msgDate}</span></div>`); }
			$list.append(this._render_message(msg));
		}
		if (wasAtBottom) { $list[0].scrollTop = $list[0].scrollHeight; }
	}

	_render_message(msg) {
		const isTemplate = msg.source === "template_log" || msg.message_type === "template";
		const dirClass = isTemplate ? "polygin-msg-template" : msg.direction === "outgoing" ? "polygin-msg-outgoing" : "polygin-msg-incoming";
		let content = "";
		if (isTemplate) content += `<div class="polygin-msg-badge">Template</div>`;
		if (msg.direction === "outgoing" && msg.responding_agent) content += `<div class="polygin-msg-agent">${frappe.utils.escape_html(msg.responding_agent)}</div>`;

		if (msg.media_url && msg.message_type === "image") {
			content += `<div class="polygin-msg-image"><img src="${frappe.utils.escape_html(msg.media_url)}" loading="lazy" onclick="window.open(this.src, '_blank')"></div>`;
		} else if (msg.media_url && msg.message_type === "video") {
			content += `<div class="polygin-msg-video"><video controls src="${frappe.utils.escape_html(msg.media_url)}"></video></div>`;
		} else if (msg.media_url && msg.message_type === "audio") {
			content += `<div class="polygin-msg-audio"><audio controls src="${frappe.utils.escape_html(msg.media_url)}"></audio></div>`;
		} else if (msg.media_url && msg.message_type === "document") {
			const fname = decodeURIComponent((msg.media_url || "").split("/").pop() || "Document");
			content += `<a class="polygin-msg-document" href="${frappe.utils.escape_html(msg.media_url)}" target="_blank"><span class="polygin-msg-doc-icon">&#x1F4C4;</span><span class="polygin-msg-doc-name">${frappe.utils.escape_html(fname)}</span></a>`;
		}

		// Interactive messages (list/button)
		if (msg.message_type === "interactive" || msg.message_type === "button") {
			content += this._render_interactive(msg);
		} else if (msg.message) {
			// Strip redundant [Type] prefix when media is already rendered above
			let text = msg.message;
			if (msg.media_url) text = text.replace(/^\[(?:Document|Image|Video|Audio)\]\s*/i, "");
			if (text) content += this._render_text_with_readmore(text);
		}
		content += `<div class="polygin-msg-meta">${this._format_time(msg.timestamp)}</div>`;
		return `<div class="polygin-msg ${dirClass}">${content}</div>`;
	}

	// ── Response Window ──────────────────────────────────────

	render_response_window() {
		if (!this.$widget) return;
		const $rw = this.$widget.find(".polygin-chat-response-window");
		$rw.show();
		if (this.responseWindow.is_active) {
			$rw.removeClass("expired").addClass("active");
			this._start_countdown(this.responseWindow.seconds_remaining);
		} else {
			$rw.removeClass("active").addClass("expired");
			this.stop_countdown();
			$rw.html(`<span class="rw-icon">&#x26A0;</span> Response window expired \u2014 send a template to re-engage`);
		}
	}

	_start_countdown(seconds) {
		this.stop_countdown();
		let remaining = seconds;
		const $rw = this.$widget ? this.$widget.find(".polygin-chat-response-window") : null;
		if (!$rw || !$rw.length) return;
		const update = () => {
			remaining = Math.max(0, remaining);
			if (remaining <= 0) { this.responseWindow.is_active = false; this.render_response_window(); this._update_input_state(); return; }
			const h = Math.floor(remaining / 3600);
			const m = Math.floor((remaining % 3600) / 60);
			$rw.html(`<span class="rw-icon">&#x23F0;</span> Response window: ${h}h ${m}m remaining`);
			remaining--;
		};
		update();
		this.countdownInterval = setInterval(update, 1000);
	}

	stop_countdown() {
		if (this.countdownInterval) { clearInterval(this.countdownInterval); this.countdownInterval = null; }
	}

	_update_input_state() {
		if (!this.$widget) return;
		const $container = this.$widget.find(".polygin-chat-input-container");
		const isActive = this.responseWindow.is_active;
		const hasInput = $container.find(".polygin-chat-input-area").length > 0;
		const hasExpired = $container.find(".polygin-chat-expired-bar").length > 0;

		// Only rebuild if the state actually changed
		if (isActive && hasInput) return;
		if (!isActive && hasExpired) return;

		if (isActive) {
			$container.html(`
				<div class="polygin-chat-input-area">
					<button class="polygin-chat-attach-btn" title="Attach">&#x1F4CE;</button>
					<button class="polygin-chat-qr-btn" title="Quick Replies">&#x26A1;</button>
					<div class="polygin-chat-input-wrapper">
						<textarea rows="1" placeholder="Type a message..." maxlength="${WA_LIMITS.TEXT_BODY}"></textarea>
						<span class="polygin-char-count" style="display:none;">0/${WA_LIMITS.TEXT_BODY}</span>
					</div>
					<button class="polygin-chat-send-btn" title="Send">&#x27A4;</button>
				</div>
			`);
			this.$widget.find(".polygin-chat-send-btn").on("click", () => this.send_text_message());
			this._bindTextarea(this.$widget.find("textarea"));
			this.$widget.find(".polygin-chat-attach-btn").on("click", (e) => { e.stopPropagation(); this.toggle_attach_menu(); });
			this.$widget.find(".polygin-chat-qr-btn").on("click", (e) => { e.stopPropagation(); this.show_quick_replies(); });
		} else {
			this._load_template_buttons($container);
		}
	}

	_load_template_buttons($container) {
		if (this.templateButtons !== null) { this._render_expired_input($container, this.templateButtons); return; }
		frappe.call({
			method: "polygin.api.get_buttons",
			args: { doctype: this.doctype },
			callback: (r) => { this.templateButtons = r.message || []; this._render_expired_input($container, this.templateButtons); },
		});
	}

	_render_expired_input($container, buttons) {
		let btnHtml = buttons.length > 0
			? buttons.map((b) => `<button class="polygin-chat-template-btn" data-template="${frappe.utils.escape_html(b.template_name)}">${frappe.utils.escape_html(b.button_name)}</button>`).join("")
			: `<span style="color:#856404;font-size:13px;">No templates configured for this DocType.</span>`;
		$container.html(`<div class="polygin-chat-expired-bar"><p>24-hour response window expired. Send a template to re-engage.</p><div class="polygin-chat-template-btns">${btnHtml}</div></div>`);
		$container.find(".polygin-chat-template-btn").on("click", (e) => {
			const tn = $(e.target).data("template"); if (!tn) return; this._send_template(tn);
		});
	}

	_send_template(templateName) {
		frappe.prompt([
			{ fieldname: "phone", label: "Send to", fieldtype: "Data", default: this.phone, reqd: 1 },
		], (values) => {
			frappe.call({
				method: "polygin.api.send_whatsapp_template",
				args: { doctype: this.doctype, docname: this.docname, template_name: templateName, phone: values.phone },
				freeze: true, freeze_message: __("Sending..."),
				callback: (r) => {
					const resp = r.message || {};
					if (resp.success) { frappe.show_alert({ message: resp.message || __("Sent!"), indicator: "green" }); setTimeout(() => this.fetch_messages(), 1500); }
					else { frappe.msgprint(resp.message || __("Failed to send.")); }
				},
			});
		}, __("Send Template"), __("Send"));
	}

	_send_document() {
		frappe.prompt([
			{ fieldname: "phone", label: "Send to", fieldtype: "Data", default: this.phone, reqd: 1 },
		], (values) => {
			frappe.call({
				method: "polygin.api.send_document_via_template",
				args: { doctype: this.doctype, docname: this.docname, phone: values.phone },
				freeze: true, freeze_message: __("Sending document..."),
				callback: (r) => {
					const resp = r.message || {};
					if (resp.success) {
						frappe.show_alert({ message: resp.message || __("Document sent!"), indicator: "green" });
						setTimeout(() => this.fetch_messages(), 1500);
					} else {
						frappe.msgprint(resp.message || __("Failed to send document."));
					}
				},
			});
		}, __("Send Document"), __("Send"));
	}

	// ── Sending Messages ─────────────────────────────────────

	send_text_message() {
		if (!this.$widget || this.isSending) return;
		const $textarea = this.$widget.find("textarea");
		const text = ($textarea.val() || "").trim();
		if (!text) return;
		if (text.length > WA_LIMITS.TEXT_BODY) { frappe.show_alert({ message: __(`Message exceeds ${WA_LIMITS.TEXT_BODY} character limit`), indicator: "red" }); return; }

		this.isSending = true;
		this.$widget.find(".polygin-chat-send-btn").prop("disabled", true);
		frappe.call({
			method: "polygin.api.send_chat_message",
			args: { phone: this.phone, message_type: "text", content: text },
			callback: (r) => {
				const resp = r.message || {};
				if (resp.success) {
					$textarea.val("").css("height", "auto");
					this.$widget.find(".polygin-char-count").hide();
					const now = new Date().toISOString().replace("T", " ").substring(0, 19);
					const agentName = frappe.session.user_fullname || "You";
					const newMsg = { id: "local_" + Date.now(), direction: "outgoing", message: text, message_type: "text", media_url: null, timestamp: now, sender_name: agentName, responding_agent: agentName, source: "message", origin: "outgoing" };
					this.messages.push(newMsg); this.messageIds.add(newMsg.id); this.render_messages();
					const $list = this.$widget.find(".polygin-chat-messages"); $list[0].scrollTop = $list[0].scrollHeight;
				} else { frappe.show_alert({ message: resp.message || __("Failed to send"), indicator: "red" }); }
			},
			error: () => { frappe.show_alert({ message: __("Failed to send message"), indicator: "red" }); },
			always: () => { this.isSending = false; if (this.$widget) this.$widget.find(".polygin-chat-send-btn").prop("disabled", false); },
		});
	}

	// ── Attachments ──────────────────────────────────────────

	toggle_attach_menu() { this.attachMenuOpen ? this.close_attach_menu() : this.show_attach_menu(); }

	show_attach_menu() {
		this.close_attach_menu();
		this.attachMenuOpen = true;
		const $menu = $(`
			<div class="polygin-chat-attach-menu">
				<div class="polygin-chat-attach-item" data-type="image"><span class="attach-icon">&#x1F5BC;</span> Image</div>
				<div class="polygin-chat-attach-item" data-type="video"><span class="attach-icon">&#x1F3AC;</span> Video</div>
				<div class="polygin-chat-attach-item" data-type="audio"><span class="attach-icon">&#x1F3B5;</span> Audio</div>
				<div class="polygin-chat-attach-item" data-type="document"><span class="attach-icon">&#x1F4C4;</span> Document</div>
				<div class="polygin-chat-attach-item" data-type="interactive_list"><span class="attach-icon">&#x1F4CB;</span> List Message</div>
				<div class="polygin-chat-attach-item" data-type="interactive_button"><span class="attach-icon">&#x1F518;</span> Button Message</div>
			</div>
		`);
		$menu.find(".polygin-chat-attach-item").on("click", (e) => {
			e.stopPropagation();
			const type = $(e.currentTarget).data("type");
			this.close_attach_menu();
			if (type === "interactive_list") this.show_list_composer();
			else if (type === "interactive_button") this.show_button_composer();
			else this._pick_file_erpnext(type);
		});
		this.$widget.find(".polygin-chat-input-container").append($menu);
	}

	close_attach_menu() { this.attachMenuOpen = false; $(".polygin-chat-attach-menu").remove(); }

	// ── Quick Replies ─────────────────────────────────────────

	show_quick_replies() {
		this._close_quick_replies();
		this.close_attach_menu();

		const $ta = this.$widget ? this.$widget.find("textarea") : null;
		const typedText = ($ta && $ta.val() || "").trim();

		const $menu = $(`<div class="polygin-qr-menu"><div class="polygin-qr-loading">Loading...</div></div>`);
		this.$widget.find(".polygin-chat-input-container").append($menu);

		frappe.call({
			method: "polygin.api.get_quick_replies",
			callback: (r) => {
				const replies = r.message || [];
				$menu.empty();

				// Header
				$menu.append(`<div class="polygin-qr-header">&#x26A1; Quick Replies <a href="/app/polygin-quick-reply" target="_blank" class="polygin-qr-manage">Manage</a></div>`);

				// If text is typed, offer to save it as quick reply
				if (typedText) {
					const $save = $(`
						<div class="polygin-qr-item polygin-qr-save">
							<div class="polygin-qr-title">&#x2795; Save as Quick Reply</div>
							<div class="polygin-qr-preview">"${frappe.utils.escape_html(typedText.substring(0, 50))}${typedText.length > 50 ? "..." : ""}"</div>
						</div>
					`);
					$save.on("click", (e) => {
						e.stopPropagation();
						this._close_quick_replies();
						this._save_quick_reply(typedText);
					});
					$menu.append($save);
				}

				if (replies.length === 0 && !typedText) {
					$menu.append(`<div class="polygin-qr-empty"><p>No quick replies yet.</p><a href="/app/polygin-quick-reply/new" target="_blank" class="polygin-qr-create">+ Create Quick Reply</a></div>`);
					return;
				}

				for (const qr of replies) {
					const typeIcon = qr.message_type === "button" ? "&#x1F518;" : qr.message_type === "list" ? "&#x1F4CB;" : "&#x1F4AC;";
					const $item = $(`
						<div class="polygin-qr-item" title="${frappe.utils.escape_html(qr.message)}">
							<div class="polygin-qr-title"><span class="polygin-qr-type-icon">${typeIcon}</span> ${frappe.utils.escape_html(qr.title)}</div>
							<div class="polygin-qr-preview">${frappe.utils.escape_html((qr.message || "").substring(0, 50))}${(qr.message || "").length > 50 ? "..." : ""}</div>
							<div class="polygin-qr-actions-row">
								${qr.shortcode ? `<span class="polygin-qr-shortcode">/${frappe.utils.escape_html(qr.shortcode)}</span>` : ""}
								<a href="/app/polygin-quick-reply/${qr.name}" target="_blank" class="polygin-qr-edit" title="Edit">&#x270E;</a>
							</div>
						</div>
					`);
					// Click item to use it
					$item.on("click", (e) => {
						if ($(e.target).hasClass("polygin-qr-edit")) return; // let edit link work
						e.stopPropagation();
						this._close_quick_replies();
						if (qr.message_type === "text" || !qr.message_type) {
							const $ta = this.$widget.find("textarea");
							$ta.val(qr.message).trigger("input").focus();
						} else {
							// Interactive quick reply — send directly
							let payload = null;
							try { payload = qr.interactive_payload ? JSON.parse(qr.interactive_payload) : null; } catch (e) { console.warn("Polygin: failed to parse quick reply payload", e); payload = null; }
							if (payload) {
								const type = qr.message_type === "button" ? "interactive_button" : "interactive_list";
								this._send_interactive(type, payload, qr.message);
							} else {
								frappe.msgprint(__("This quick reply has no interactive payload configured. Edit it to add one."));
							}
						}
					});
					$menu.append($item);
				}
			},
		});
	}

	_save_quick_reply(text) {
		frappe.prompt([
			{ fieldname: "title", label: "Title", fieldtype: "Data", reqd: 1 },
			{ fieldname: "shortcode", label: "Shortcode (optional)", fieldtype: "Data" },
		], (values) => {
			frappe.call({
				method: "frappe.client.insert",
				args: {
					doc: {
						doctype: "Polygin Quick Reply",
						title: values.title,
						message: text,
						message_type: "text",
						shortcode: values.shortcode || "",
						is_active: 1,
					},
				},
				callback: () => {
					frappe.show_alert({ message: __("Quick reply saved!"), indicator: "green" });
				},
			});
		}, __("Save Quick Reply"), __("Save"));
	}

	_save_interactive_qr(msgType, bodyText, payload) {
		frappe.prompt([
			{ fieldname: "title", label: "Title", fieldtype: "Data", reqd: 1 },
			{ fieldname: "shortcode", label: "Shortcode (optional)", fieldtype: "Data" },
		], (values) => {
			frappe.call({
				method: "frappe.client.insert",
				args: {
					doc: {
						doctype: "Polygin Quick Reply",
						title: values.title,
						message: bodyText,
						message_type: msgType,
						interactive_payload: JSON.stringify(payload),
						shortcode: values.shortcode || "",
						is_active: 1,
					},
				},
				callback: () => {
					frappe.show_alert({ message: __("Quick reply saved!"), indicator: "green" });
				},
			});
		}, __("Save as Quick Reply"), __("Save"));
	}

	_close_quick_replies() { $(".polygin-qr-menu").remove(); }

	// ── Text Rendering with Read More ────────────────────────

	_render_text_with_readmore(text, maxLen = 215) {
		const trimmed = (text || "").trim();
		if (trimmed.length <= maxLen) {
			return `<div class="polygin-msg-text">${this._wa_format(trimmed)}</div>`;
		}
		let cutoff = trimmed.lastIndexOf(" ", maxLen);
		if (cutoff < maxLen * 0.6) cutoff = maxLen;
		const truncText = trimmed.substring(0, cutoff).trimEnd();
		const uid = `rm_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;
		return `<div class="polygin-msg-text"><span id="${uid}_s">${this._wa_format(truncText)}...<br><a href="#" class="polygin-readmore-link" onclick="document.getElementById('${uid}_s').style.display='none';document.getElementById('${uid}_f').style.display='block';return false;">Read more</a></span><span id="${uid}_f" style="display:none">${this._wa_format(trimmed)}<br><a href="#" class="polygin-readmore-link" onclick="document.getElementById('${uid}_f').style.display='none';document.getElementById('${uid}_s').style.display='block';return false;">Show less</a></span></div>`;
	}

	_wa_format(text) {
		// Escape HTML first, then render WhatsApp-style formatting
		return frappe.utils.escape_html(text || "")
			.replace(/\*([^*]+)\*/g, "<b>$1</b>")
			.replace(/_([^_]+)_/g, "<i>$1</i>");
	}

	// ── Interactive Message Rendering ─────────────────────────

	_render_interactive(msg) {
		let html = "";
		let data = null;
		try { data = msg.raw_data ? JSON.parse(msg.raw_data) : null; } catch (e) { console.warn("Polygin: failed to parse raw_data", e); data = null; }

		// Normalize: webhook raw_data nests interactive content inside msgContext.interactive
		// while locally-sent messages store {type, body, action} directly
		if (data && data.msgContext?.interactive) {
			data = data.msgContext.interactive;
		} else if (data && data.msgContext?.type === "interactive" && !data.body && !data.action) {
			data = data.msgContext.interactive || data.msgContext;
		}

		if (data && data.type === "list") {
			html += this._render_text_with_readmore(data.body?.text || msg.message || "");
			if (data.action?.sections) {
				html += `<div class="polygin-msg-interactive">`;
				for (const section of data.action.sections) {
					html += `<div class="polygin-int-section-title">${frappe.utils.escape_html(section.title || "")}</div>`;
					for (const row of (section.rows || [])) {
						html += `<div class="polygin-int-row"><span class="polygin-int-row-title">${frappe.utils.escape_html(row.title)}</span>`;
						if (row.description) html += `<span class="polygin-int-row-desc">${frappe.utils.escape_html(row.description)}</span>`;
						html += `</div>`;
					}
				}
				html += `</div>`;
			}
		} else if (data && data.type === "button") {
			html += this._render_text_with_readmore(data.body?.text || msg.message || "");
			if (data.action?.buttons) {
				html += `<div class="polygin-msg-buttons">`;
				for (const btn of data.action.buttons) {
					html += `<span class="polygin-int-btn">${frappe.utils.escape_html(btn.reply?.title || "")}</span>`;
				}
				html += `</div>`;
			}
		} else {
			// Fallback — no raw_data, show badge + text
			const badge = msg.message_type === "button" ? "Button Message" : "List Message";
			html += `<div class="polygin-msg-badge polygin-int-badge">${badge}</div>`;
			html += `<div class="polygin-msg-text">${frappe.utils.escape_html(msg.message || "[Interactive message]")}</div>`;
		}
		return html;
	}

	// ── File Upload via ERPNext File Manager ──────────────────

	_pick_file_erpnext(type) {
		const limitMap = { image: 5, video: 16, audio: 16, document: 75 };
		const restrictMap = {
			image: { allowed_file_types: ["image/*"] },
			video: { allowed_file_types: ["video/*"] },
			audio: { allowed_file_types: ["audio/*"] },
			document: {},
		};

		new frappe.ui.FileUploader({
			doctype: "Polygin Wa Messages",
			docname: null,
			make_attachments_public: true,
			restrictions: restrictMap[type] || {},
			on_success: (file) => {
				let file_url = file.file_url;
				if (file_url && !file_url.startsWith("http")) {
					file_url = frappe.urllib.get_full_url(file_url);
				}
				// Check file size
				if (file.file_size && file.file_size / (1024 * 1024) > (limitMap[type] || 75)) {
					frappe.show_alert({ message: __(`File too large. Max: ${limitMap[type]}MB for ${type}`), indicator: "red" });
					return;
				}
				this._send_media(file_url, type, file.file_name);
			},
		});
	}

	_send_media(file_url, type, file_name) {
		if (this.$widget) {
			this.$widget.find(".polygin-chat-uploading").remove();
			this.$widget.find(".polygin-chat-input-container").before(`<div class="polygin-chat-uploading">Sending ${type}...</div>`);
		}
		frappe.call({
			method: "polygin.api.send_chat_message",
			args: { phone: this.phone, message_type: type, media_url: file_url, caption: file_name || "" },
			callback: (r) => {
				const resp = r.message || {};
				if (resp.success) {
					frappe.show_alert({ message: __(`${type} sent!`), indicator: "green" });
					setTimeout(() => this.fetch_messages(), 1000);
				} else { frappe.msgprint(resp.message || __("Failed to send")); }
			},
			always: () => { if (this.$widget) this.$widget.find(".polygin-chat-uploading").remove(); },
		});
	}

	// ── List Message Composer ─────────────────────────────────

	show_list_composer() {
		if (!this.$widget) return;
		const $overlay = $(`
			<div class="polygin-interactive-overlay">
				<div class="polygin-interactive-modal polygin-composer">
					<div class="composer-header">
						<h4>List Message</h4>
						<button class="composer-close">&times;</button>
					</div>
					<div class="composer-body">
						<div class="composer-field">
							<label>Header text</label>
							<input type="text" class="lc-header" placeholder="Header text" maxlength="${WA_LIMITS.HEADER}">
							<span class="char-hint lc-header-count">0/${WA_LIMITS.HEADER}</span>
						</div>
						<div class="composer-field">
							<label>Body text <span class="required">*</span></label>
							<textarea class="lc-body" rows="3" placeholder="Body text" maxlength="${WA_LIMITS.INTERACTIVE_BODY}"></textarea>
							<span class="char-hint lc-body-count">0/${WA_LIMITS.INTERACTIVE_BODY}</span>
						</div>
						<div class="composer-field">
							<label>Footer (optional)</label>
							<input type="text" class="lc-footer" placeholder="Footer (optional)" maxlength="${WA_LIMITS.FOOTER}">
							<span class="char-hint lc-footer-count">0/${WA_LIMITS.FOOTER}</span>
						</div>
						<div class="composer-field">
							<label>Button label</label>
							<input type="text" class="lc-button" placeholder="e.g. View Options" value="View Options" maxlength="${WA_LIMITS.LIST_BUTTON_TEXT}">
							<span class="char-hint lc-button-count">0/${WA_LIMITS.LIST_BUTTON_TEXT}</span>
						</div>
						<div class="composer-sections"></div>
						<button class="composer-add-section">+ Add Section</button>
					</div>
					<label class="composer-save-qr"><input type="checkbox" class="save-qr-check"> &#x26A1; Save as Quick Reply</label>
					<div class="composer-footer-info">Fill in the required fields to send.</div>
					<div class="composer-actions">
						<button class="btn-cancel">Cancel</button>
						<button class="btn-send">Send</button>
					</div>
				</div>
			</div>
		`);

		// Wire char counts
		this._wireCharCount($overlay, ".lc-header", ".lc-header-count", WA_LIMITS.HEADER);
		this._wireCharCount($overlay, ".lc-body", ".lc-body-count", WA_LIMITS.INTERACTIVE_BODY);
		this._wireCharCount($overlay, ".lc-footer", ".lc-footer-count", WA_LIMITS.FOOTER);
		this._wireCharCount($overlay, ".lc-button", ".lc-button-count", WA_LIMITS.LIST_BUTTON_TEXT);

		// Add initial section
		this._addListSection($overlay.find(".composer-sections"));

		$overlay.find(".composer-add-section").on("click", () => {
			const $sections = $overlay.find(".composer-sections");
			if ($sections.children().length >= WA_LIMITS.MAX_SECTIONS) { frappe.show_alert({ message: __(`Max ${WA_LIMITS.MAX_SECTIONS} sections`), indicator: "orange" }); return; }
			this._addListSection($sections);
		});

		$overlay.find(".composer-close, .btn-cancel").on("click", () => $overlay.remove());
		$overlay.find(".btn-send").on("click", () => {
			const body = $overlay.find(".lc-body").val().trim();
			if (!body) { frappe.msgprint(__("Body text is required")); return; }

			// Collect sections
			const sections = [];
			let totalRows = 0;
			$overlay.find(".list-section").each(function () {
				const title = $(this).find(".section-title-input").val().trim();
				const rows = [];
				$(this).find(".list-option-row").each(function () {
					const rowTitle = $(this).find(".opt-title").val().trim();
					if (rowTitle) { rows.push({ id: rowTitle.toLowerCase().replace(/\s+/g, "_").substring(0, 24), title: rowTitle, description: $(this).find(".opt-desc").val().trim() }); }
				});
				totalRows += rows.length;
				if (rows.length > 0) sections.push({ title: title || "Options", rows });
			});

			if (totalRows === 0) { frappe.msgprint(__("Add at least one option")); return; }
			if (totalRows > WA_LIMITS.MAX_ROWS) { frappe.msgprint(__(`Max ${WA_LIMITS.MAX_ROWS} options total across all sections`)); return; }

			const interactive = {
				type: "list",
				header: { type: "text", text: $overlay.find(".lc-header").val().trim() },
				body: { text: body },
				footer: { text: $overlay.find(".lc-footer").val().trim() },
				action: { button: $overlay.find(".lc-button").val().trim() || "View Options", sections },
			};
			const saveQR = $overlay.find(".save-qr-check").is(":checked");
			$overlay.remove();
			this._send_interactive("interactive_list", interactive, body);
			if (saveQR) this._save_interactive_qr("list", body, interactive);
		});

		this.$widget.append($overlay);
	}

	_addListSection($container) {
		const idx = $container.children().length + 1;
		const $section = $(`
			<div class="list-section">
				<div class="section-header">
					<span class="section-icon">&#x2630;</span>
					<input type="text" class="section-title-input" placeholder="Section ${idx}" maxlength="${WA_LIMITS.SECTION_TITLE}">
					<span class="char-hint section-title-count">0/${WA_LIMITS.SECTION_TITLE}</span>
					<button class="section-delete" title="Remove section">&#x1F5D1;</button>
					<button class="section-toggle" title="Collapse">&#x25B2;</button>
				</div>
				<div class="section-options"></div>
				<button class="section-add-option">+ Add Option</button>
			</div>
		`);

		this._wireCharCount($section, ".section-title-input", ".section-title-count", WA_LIMITS.SECTION_TITLE);

		// Add 2 default options
		this._addListOption($section.find(".section-options"));
		this._addListOption($section.find(".section-options"));

		$section.find(".section-add-option").on("click", () => {
			const totalRows = $container.closest(".polygin-composer").find(".list-option-row").length;
			if (totalRows >= WA_LIMITS.MAX_ROWS) { frappe.show_alert({ message: __(`Max ${WA_LIMITS.MAX_ROWS} options total`), indicator: "orange" }); return; }
			this._addListOption($section.find(".section-options"));
		});
		$section.find(".section-delete").on("click", () => { if ($container.children().length > 1) $section.remove(); });
		$section.find(".section-toggle").on("click", function () {
			$section.find(".section-options, .section-add-option").toggle();
			$(this).text($section.find(".section-options").is(":visible") ? "\u25B2" : "\u25BC");
		});

		$container.append($section);
	}

	_addListOption($container) {
		const idx = $container.children().length + 1;
		const $row = $(`
			<div class="list-option-row">
				<div class="opt-num">${idx}</div>
				<div class="opt-fields">
					<input type="text" class="opt-title" placeholder="Option title" maxlength="${WA_LIMITS.ROW_TITLE}">
					<span class="char-hint opt-title-count">0/${WA_LIMITS.ROW_TITLE}</span>
					<input type="text" class="opt-desc" placeholder="Description" maxlength="${WA_LIMITS.ROW_DESC}">
					<span class="char-hint opt-desc-count">0/${WA_LIMITS.ROW_DESC}</span>
				</div>
				<button class="opt-delete" title="Remove">&#x1F5D1;</button>
			</div>
		`);
		this._wireCharCount($row, ".opt-title", ".opt-title-count", WA_LIMITS.ROW_TITLE);
		this._wireCharCount($row, ".opt-desc", ".opt-desc-count", WA_LIMITS.ROW_DESC);
		$row.find(".opt-delete").on("click", () => { if ($container.children().length > 1) $row.remove(); });
		$container.append($row);
	}

	// ── Button Message Composer ──────────────────────────────

	show_button_composer() {
		if (!this.$widget) return;
		const $overlay = $(`
			<div class="polygin-interactive-overlay">
				<div class="polygin-interactive-modal polygin-composer">
					<div class="composer-header">
						<h4>Button Message</h4>
						<button class="composer-close">&times;</button>
					</div>
					<div class="composer-body">
						<div class="composer-field">
							<label>Message body <span class="required">*</span></label>
							<textarea class="bc-body" rows="4" placeholder="Type your message..." maxlength="${WA_LIMITS.INTERACTIVE_BODY}"></textarea>
							<span class="char-hint bc-body-count">0/${WA_LIMITS.INTERACTIVE_BODY}</span>
						</div>
						<div class="button-list"></div>
						<button class="composer-add-button">+ Add Button</button>
					</div>
					<label class="composer-save-qr"><input type="checkbox" class="save-qr-check"> &#x26A1; Save as Quick Reply</label>
					<div class="composer-footer-info">Fill in the required fields to send.</div>
					<div class="composer-actions">
						<button class="btn-cancel">Cancel</button>
						<button class="btn-send">Send</button>
					</div>
				</div>
			</div>
		`);

		this._wireCharCount($overlay, ".bc-body", ".bc-body-count", WA_LIMITS.INTERACTIVE_BODY);

		// Add initial button
		this._addReplyButton($overlay.find(".button-list"));

		$overlay.find(".composer-add-button").on("click", () => {
			const $list = $overlay.find(".button-list");
			if ($list.children().length >= WA_LIMITS.MAX_BUTTONS) { frappe.show_alert({ message: __(`Max ${WA_LIMITS.MAX_BUTTONS} buttons`), indicator: "orange" }); return; }
			this._addReplyButton($list);
		});

		$overlay.find(".composer-close, .btn-cancel").on("click", () => $overlay.remove());
		$overlay.find(".btn-send").on("click", () => {
			const body = $overlay.find(".bc-body").val().trim();
			if (!body) { frappe.msgprint(__("Message body is required")); return; }

			const buttons = [];
			$overlay.find(".button-entry").each(function () {
				const title = $(this).find(".btn-title-input").val().trim();
				if (title) buttons.push({ type: "reply", reply: { id: title.toLowerCase().replace(/\s+/g, "_").substring(0, 20), title } });
			});
			if (buttons.length === 0) { frappe.msgprint(__("Add at least one button")); return; }

			const interactive = { type: "button", body: { text: body }, action: { buttons } };
			const saveQR = $overlay.find(".save-qr-check").is(":checked");
			$overlay.remove();
			this._send_interactive("interactive_button", interactive, body);
			if (saveQR) this._save_interactive_qr("button", body, interactive);
		});

		this.$widget.append($overlay);
	}

	_addReplyButton($container) {
		const idx = $container.children().length + 1;
		const $btn = $(`
			<div class="button-entry">
				<span class="btn-icon">&#x21A9;</span>
				<input type="text" class="btn-title-input" placeholder="Button ${idx}" maxlength="${WA_LIMITS.BUTTON_TITLE}">
				<span class="char-hint btn-char-count">0/${WA_LIMITS.BUTTON_TITLE}</span>
				<button class="btn-delete-entry" title="Remove">&#x1F5D1;</button>
			</div>
		`);
		this._wireCharCount($btn, ".btn-title-input", ".btn-char-count", WA_LIMITS.BUTTON_TITLE);
		$btn.find(".btn-delete-entry").on("click", () => { if ($container.children().length > 1) $btn.remove(); });
		$container.append($btn);
	}

	// ── Shared Helpers ───────────────────────────────────────

	_wireCharCount($scope, inputSel, countSel, limit) {
		$scope.find(inputSel).on("input", function () {
			const len = this.value.length;
			$scope.find(countSel).text(`${len}/${limit}`).toggleClass("over-limit", len >= limit);
		});
	}

	_send_interactive(type, interactiveData, displayText) {
		frappe.call({
			method: "polygin.api.send_chat_message",
			args: { phone: this.phone, message_type: type, content: displayText, interactive_data: JSON.stringify(interactiveData) },
			callback: (r) => {
				const resp = r.message || {};
				if (resp.success) { frappe.show_alert({ message: __("Message sent!"), indicator: "green" }); setTimeout(() => this.fetch_messages(), 1000); }
				else { frappe.msgprint(resp.message || __("Failed to send")); }
			},
		});
	}

	// ── Phone Resolution (static) ────────────────────────────

	static resolve_phone(frm) {
		const fieldPriority = {
			Lead: ["whatsapp_no", "mobile_no", "phone"],
			Contact: ["mobile_no", "phone"],
			Customer: ["mobile_no", "contact_mobile", "contact_phone"],
			Supplier: ["mobile_no", "contact_mobile", "contact_phone"],
			Opportunity: ["whatsapp", "phone"],
		};
		// Transactional DocTypes all use contact_mobile
		if (TRANSACTIONAL_DOCTYPES.has(frm.doctype)) {
			const fields = ["contact_mobile", "contact_phone"];
			for (const f of fields) { const val = frm.doc[f]; if (val && val.trim()) return val.trim(); }
			return null;
		}
		const fields = fieldPriority[frm.doctype] || ["mobile_no", "phone"];
		for (const f of fields) { const val = frm.doc[f]; if (val && val.trim()) return val.trim(); }
		return null;
	}

	static async resolve_phone_async(frm) {
		// Try sync first
		const phone = PolyginChat.resolve_phone(frm);
		if (phone) return phone;

		// For Customer/Supplier, fetch from linked contacts
		if (frm.doctype === "Customer" || frm.doctype === "Supplier") {
			try {
				const contacts = await frappe.xcall("frappe.client.get_list", {
					doctype: "Contact",
					filters: [
						["Dynamic Link", "link_doctype", "=", frm.doctype],
						["Dynamic Link", "link_name", "=", frm.docname],
					],
					fields: ["name", "mobile_no", "phone"],
					limit_page_length: 5,
				});
				for (const c of (contacts || [])) {
					// Check top-level fields first
					const val = (c.mobile_no || c.phone || "").trim();
					if (val) return val;
					// Fallback: check phone_nos child table
					try {
						const phoneNos = await frappe.xcall("frappe.client.get_list", {
							doctype: "Contact Phone",
							filters: { parent: c.name },
							fields: ["phone"],
							limit_page_length: 5,
						});
						for (const pn of (phoneNos || [])) {
							if (pn.phone && pn.phone.trim()) return pn.phone.trim();
						}
					} catch (e) { console.warn("Polygin: failed to fetch contact phone_nos", e); }
				}
			} catch (e) { console.warn("Polygin: failed to resolve contacts for", frm.doctype, e); }
		}
		return null;
	}

	static resolve_contact_name(frm) {
		if (frm.doctype === "Lead") return frm.doc.lead_name || frm.doc.first_name || frm.doc.company_name || "";
		if (frm.doctype === "Contact") return frm.doc.first_name ? `${frm.doc.first_name} ${frm.doc.last_name || ""}`.trim() : "";
		if (frm.doctype === "Customer") return frm.doc.customer_name || frm.doc.name || "";
		if (frm.doctype === "Supplier") return frm.doc.supplier_name || frm.doc.name || "";
		if (frm.doctype === "Opportunity") return frm.doc.customer_name || frm.doc.party_name || "";
		if (TRANSACTIONAL_DOCTYPES.has(frm.doctype)) return frm.doc.contact_person || frm.doc.customer_name || frm.doc.supplier_name || frm.doc.name || "";
		return "";
	}

	// ── Date/Time Formatting ─────────────────────────────────

	_format_date(ts) {
		try {
			const d = new Date(ts); if (isNaN(d.getTime())) return "";
			const today = new Date(); const yesterday = new Date(today); yesterday.setDate(yesterday.getDate() - 1);
			if (d.toDateString() === today.toDateString()) return "Today";
			if (d.toDateString() === yesterday.toDateString()) return "Yesterday";
			return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
		} catch { return ""; }
	}

	_format_time(ts) {
		try { const d = new Date(ts); if (isNaN(d.getTime())) return ""; return d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: true }); }
		catch { return ""; }
	}

	// ── Lifecycle ─────────────────────────────────────────────

	destroy() {
		this.stop_polling(); this.stop_countdown(); this.remove_widget(); this.remove_bubble();
		$(document).off("click.polygin_attach");
		if (window._polygin_chat_instance === this) window._polygin_chat_instance = null;
	}
}

window._polygin_chat_instance = null;
window.PolyginChat = PolyginChat;
