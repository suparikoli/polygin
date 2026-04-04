/**
 * Polygin Chat Widget
 *
 * A WhatsApp-style live chat widget that integrates into Frappe DocType forms.
 * Loaded globally via app_include_js, instantiated from polygin.js per-form.
 */

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
			<button class="polygin-chat-bubble" title="Chat on WhatsApp">
				<svg viewBox="0 0 24 24"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
			</button>
		`);
		this.$bubble.on("click", () => this.expand_to_widget());
		$("body").append(this.$bubble);
	}

	remove_bubble() {
		if (this.$bubble) {
			this.$bubble.remove();
			this.$bubble = null;
		}
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
	}

	collapse_to_widget() {
		if (!this.$widget) return;
		this.isFullscreen = false;
		this.$widget.removeClass("polygin-chat-fullscreen");
	}

	collapse_to_bubble() {
		this.isOpen = false;
		this.stop_polling();
		this.stop_countdown();
		this.remove_widget();
		this.render_bubble();
	}

	remove_widget() {
		if (this.$widget) {
			this.$widget.remove();
			this.$widget = null;
		}
	}

	_render_widget_content() {
		const initials = (this.contact_name || "?").charAt(0).toUpperCase();

		this.$widget.html(`
			<div class="polygin-chat-header">
				<div class="polygin-chat-avatar">${initials}</div>
				<div class="polygin-chat-header-info">
					<div class="polygin-chat-header-name">${frappe.utils.escape_html(this.contact_name)}</div>
					<div class="polygin-chat-header-phone">${frappe.utils.escape_html(this.phone)}</div>
				</div>
				<div class="polygin-chat-header-actions">
					<span class="polygin-traffic-light polygin-tl-close" title="Close"></span>
					<span class="polygin-traffic-light polygin-tl-minimize" title="Minimize"></span>
					<span class="polygin-traffic-light polygin-tl-fullscreen" title="Fullscreen"></span>
				</div>
			</div>
			<div class="polygin-chat-response-window" style="display:none;"></div>
			<div class="polygin-chat-messages">
				<div class="polygin-chat-loading">Loading messages...</div>
			</div>
			<div class="polygin-chat-input-container" style="position:relative;">
				<div class="polygin-chat-input-area">
					<button class="polygin-chat-attach-btn" title="Attach">&#x1F4CE;</button>
					<div class="polygin-chat-input-wrapper">
						<textarea rows="1" placeholder="Type a message..."></textarea>
					</div>
					<button class="polygin-chat-send-btn" title="Send">&#x27A4;</button>
				</div>
			</div>
		`);

		// Event bindings — traffic light buttons
		this.$widget.find(".polygin-tl-close").on("click", () => this.collapse_to_bubble());
		this.$widget.find(".polygin-tl-minimize").on("click", () => {
			if (this.isFullscreen) this.collapse_to_widget();
			else this.collapse_to_bubble();
		});
		this.$widget.find(".polygin-tl-fullscreen").on("click", () => {
			this.isFullscreen ? this.collapse_to_widget() : this.expand_to_fullscreen();
		});
		this.$widget.find(".polygin-chat-send-btn").on("click", () => this.send_text_message());
		this.$widget.find("textarea").on("keydown", (e) => {
			if (e.key === "Enter" && !e.shiftKey) {
				e.preventDefault();
				this.send_text_message();
			}
		});
		// Auto-resize textarea
		this.$widget.find("textarea").on("input", function () {
			this.style.height = "auto";
			this.style.height = Math.min(this.scrollHeight, 100) + "px";
		});
		// Attach button
		this.$widget.find(".polygin-chat-attach-btn").on("click", (e) => {
			e.stopPropagation();
			this.toggle_attach_menu();
		});
		// Close attach menu on outside click
		$(document).on("click.polygin_attach", () => this.close_attach_menu());
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
		if (this.pollInterval) {
			clearInterval(this.pollInterval);
			this.pollInterval = null;
		}
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
					for (const m of newMsgs) {
						this.messages.push(m);
						this.messageIds.add(m.id);
					}
					this.messages.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
					this.render_messages();
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
			if (msgDate !== lastDate) {
				lastDate = msgDate;
				$list.append(`<div class="polygin-date-separator"><span>${msgDate}</span></div>`);
			}
			$list.append(this._render_message(msg));
		}

		if (wasAtBottom) {
			$list[0].scrollTop = $list[0].scrollHeight;
		}
	}

	_render_message(msg) {
		const isTemplate = msg.source === "template_log" || msg.message_type === "template";
		const dirClass = isTemplate
			? "polygin-msg-template"
			: msg.direction === "outgoing"
			? "polygin-msg-outgoing"
			: "polygin-msg-incoming";

		let content = "";

		if (isTemplate) {
			content += `<div class="polygin-msg-badge">Template</div>`;
		}

		if (msg.direction === "incoming" && msg.sender_name) {
			content += `<div class="polygin-msg-sender">${frappe.utils.escape_html(msg.sender_name)}</div>`;
		}

		// Media rendering
		if (msg.media_url && msg.message_type === "image") {
			content += `<div class="polygin-msg-image"><img src="${frappe.utils.escape_html(msg.media_url)}" loading="lazy" onclick="window.open(this.src, '_blank')"></div>`;
		} else if (msg.media_url && msg.message_type === "video") {
			content += `<div class="polygin-msg-video"><video controls src="${frappe.utils.escape_html(msg.media_url)}"></video></div>`;
		} else if (msg.media_url && msg.message_type === "audio") {
			content += `<div class="polygin-msg-audio"><audio controls src="${frappe.utils.escape_html(msg.media_url)}"></audio></div>`;
		} else if (msg.media_url && msg.message_type === "document") {
			const fname = (msg.media_url || "").split("/").pop() || "Document";
			content += `<a class="polygin-msg-document" href="${frappe.utils.escape_html(msg.media_url)}" target="_blank">
				<span class="polygin-msg-doc-icon">&#x1F4C4;</span>
				<span class="polygin-msg-doc-name">${frappe.utils.escape_html(fname)}</span>
			</a>`;
		}

		if (msg.message) {
			content += `<div class="polygin-msg-text">${frappe.utils.escape_html(msg.message)}</div>`;
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
			$rw.html(`<span class="rw-icon">&#x26A0;</span> Response window expired — send a template to re-engage`);
		}
	}

	_start_countdown(seconds) {
		this.stop_countdown();
		let remaining = seconds;
		const $rw = this.$widget ? this.$widget.find(".polygin-chat-response-window") : null;
		if (!$rw || !$rw.length) return;

		const update = () => {
			if (remaining <= 0) {
				this.responseWindow.is_active = false;
				this.render_response_window();
				this._update_input_state();
				return;
			}
			const h = Math.floor(remaining / 3600);
			const m = Math.floor((remaining % 3600) / 60);
			$rw.html(`<span class="rw-icon">&#x23F0;</span> Response window: ${h}h ${m}m remaining`);
			remaining--;
		};

		update();
		this.countdownInterval = setInterval(update, 1000);
	}

	stop_countdown() {
		if (this.countdownInterval) {
			clearInterval(this.countdownInterval);
			this.countdownInterval = null;
		}
	}

	_update_input_state() {
		if (!this.$widget) return;
		const $container = this.$widget.find(".polygin-chat-input-container");

		if (this.responseWindow.is_active) {
			// Show normal input
			$container.html(`
				<div class="polygin-chat-input-area">
					<button class="polygin-chat-attach-btn" title="Attach">&#x1F4CE;</button>
					<div class="polygin-chat-input-wrapper">
						<textarea rows="1" placeholder="Type a message..."></textarea>
					</div>
					<button class="polygin-chat-send-btn" title="Send">&#x27A4;</button>
				</div>
			`);
			this.$widget.find(".polygin-chat-send-btn").on("click", () => this.send_text_message());
			this.$widget.find("textarea").on("keydown", (e) => {
				if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); this.send_text_message(); }
			});
			this.$widget.find("textarea").on("input", function () {
				this.style.height = "auto";
				this.style.height = Math.min(this.scrollHeight, 100) + "px";
			});
			this.$widget.find(".polygin-chat-attach-btn").on("click", (e) => {
				e.stopPropagation();
				this.toggle_attach_menu();
			});
		} else {
			// Show expired state with template buttons
			this._load_template_buttons($container);
		}
	}

	_load_template_buttons($container) {
		if (this.templateButtons !== null) {
			this._render_expired_input($container, this.templateButtons);
			return;
		}
		frappe.call({
			method: "polygin.api.get_buttons",
			callback: (r) => {
				this.templateButtons = r.message || [];
				this._render_expired_input($container, this.templateButtons);
			},
		});
	}

	_render_expired_input($container, buttons) {
		let btnHtml = "";
		if (buttons.length > 0) {
			btnHtml = buttons.map((b) =>
				`<button class="polygin-chat-template-btn" data-template="${frappe.utils.escape_html(b.template_name)}">${frappe.utils.escape_html(b.button_name)}</button>`
			).join("");
		} else {
			btnHtml = `<span style="color:#856404;font-size:13px;">No templates configured.</span>`;
		}

		$container.html(`
			<div class="polygin-chat-expired-bar">
				<p>24-hour response window expired. Send a template to re-engage.</p>
				<div class="polygin-chat-template-btns">${btnHtml}</div>
			</div>
		`);

		$container.find(".polygin-chat-template-btn").on("click", (e) => {
			const templateName = $(e.target).data("template");
			this._send_template(templateName);
		});
	}

	_send_template(templateName) {
		// Determine best target field for the current doctype
		const fieldMap = {
			Lead: ["whatsapp_no", "mobile_no", "phone"],
			Contact: ["mobile_no", "phone"],
			Customer: ["mobile_no"],
			Opportunity: ["whatsapp", "phone"],
		};
		const fields = fieldMap[this.doctype] || ["mobile_no"];
		const targetField = fields[0]; // use the first available

		frappe.call({
			method: "polygin.api.send_whatsapp_template",
			args: {
				doctype: this.doctype,
				docname: this.docname,
				template_name: templateName,
				target_field: targetField,
			},
			freeze: true,
			freeze_message: __("Sending template..."),
			callback: (r) => {
				const resp = r.message || {};
				if (resp.success) {
					frappe.show_alert({ message: __("Template sent!"), indicator: "green" });
					// Re-fetch messages to show the new template
					setTimeout(() => this.fetch_messages(), 1500);
				} else {
					frappe.msgprint(resp.message || __("Failed to send template."));
				}
			},
		});
	}

	// ── Sending Messages ─────────────────────────────────────

	send_text_message() {
		if (!this.$widget || this.isSending) return;
		const $textarea = this.$widget.find("textarea");
		const text = ($textarea.val() || "").trim();
		if (!text) return;

		this.isSending = true;
		this.$widget.find(".polygin-chat-send-btn").prop("disabled", true);

		frappe.call({
			method: "polygin.api.send_chat_message",
			args: { phone: this.phone, message_type: "text", content: text },
			callback: (r) => {
				const resp = r.message || {};
				if (resp.success) {
					$textarea.val("").css("height", "auto");
					// Optimistic: add the message locally
					const now = new Date().toISOString().replace("T", " ").substring(0, 19);
					const newMsg = {
						id: "local_" + Date.now(),
						direction: "outgoing",
						message: text,
						message_type: "text",
						media_url: null,
						timestamp: now,
						sender_name: frappe.session.user_fullname || "You",
						source: "message",
						origin: "outgoing",
					};
					this.messages.push(newMsg);
					this.messageIds.add(newMsg.id);
					this.render_messages();
					// Scroll to bottom
					const $list = this.$widget.find(".polygin-chat-messages");
					$list[0].scrollTop = $list[0].scrollHeight;
				} else {
					frappe.show_alert({ message: resp.message || __("Failed to send"), indicator: "red" });
				}
			},
			error: () => {
				frappe.show_alert({ message: __("Failed to send message"), indicator: "red" });
			},
			always: () => {
				this.isSending = false;
				if (this.$widget) this.$widget.find(".polygin-chat-send-btn").prop("disabled", false);
			},
		});
	}

	// ── Attachments ──────────────────────────────────────────

	toggle_attach_menu() {
		if (this.attachMenuOpen) {
			this.close_attach_menu();
		} else {
			this.show_attach_menu();
		}
	}

	show_attach_menu() {
		this.close_attach_menu();
		this.attachMenuOpen = true;

		const $menu = $(`
			<div class="polygin-chat-attach-menu">
				<div class="polygin-chat-attach-item" data-type="image">
					<span class="attach-icon">&#x1F5BC;</span> Image
				</div>
				<div class="polygin-chat-attach-item" data-type="video">
					<span class="attach-icon">&#x1F3AC;</span> Video
				</div>
				<div class="polygin-chat-attach-item" data-type="audio">
					<span class="attach-icon">&#x1F3B5;</span> Audio
				</div>
				<div class="polygin-chat-attach-item" data-type="document">
					<span class="attach-icon">&#x1F4C4;</span> Document
				</div>
				<div class="polygin-chat-attach-item" data-type="interactive_list">
					<span class="attach-icon">&#x1F4CB;</span> List Message
				</div>
				<div class="polygin-chat-attach-item" data-type="interactive_button">
					<span class="attach-icon">&#x1F518;</span> Reply Buttons
				</div>
			</div>
		`);

		$menu.find(".polygin-chat-attach-item").on("click", (e) => {
			e.stopPropagation();
			const type = $(e.currentTarget).data("type");
			this.close_attach_menu();
			if (type === "interactive_list") {
				this.show_list_composer();
			} else if (type === "interactive_button") {
				this.show_button_composer();
			} else {
				this._pick_file(type);
			}
		});

		this.$widget.find(".polygin-chat-input-container").append($menu);
	}

	close_attach_menu() {
		this.attachMenuOpen = false;
		$(".polygin-chat-attach-menu").remove();
	}

	_pick_file(type) {
		const acceptMap = {
			image: "image/jpeg,image/png,image/webp",
			video: "video/mp4,video/3gpp",
			audio: "audio/mpeg,audio/aac,audio/mp4,audio/amr,audio/opus",
			document: ".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt",
		};
		const limitMap = { image: 5, video: 16, audio: 16, document: 75 }; // MB

		const $input = $(`<input type="file" accept="${acceptMap[type] || "*/*"}" style="display:none">`);
		$("body").append($input);

		$input.on("change", () => {
			const file = $input[0].files[0];
			$input.remove();
			if (!file) return;

			const sizeMB = file.size / (1024 * 1024);
			if (sizeMB > (limitMap[type] || 75)) {
				frappe.msgprint(__(`File too large. Max size for ${type}: ${limitMap[type]}MB`));
				return;
			}
			this._upload_and_send(file, type);
		});

		$input.trigger("click");
	}

	_upload_and_send(file, type) {
		// Show uploading indicator
		if (this.$widget) {
			this.$widget.find(".polygin-chat-uploading").remove();
			this.$widget.find(".polygin-chat-input-container").before(
				`<div class="polygin-chat-uploading">Uploading ${type}...</div>`
			);
		}

		const formData = new FormData();
		formData.append("file", file);

		$.ajax({
			url: "/api/method/polygin.api.upload_chat_media",
			type: "POST",
			data: formData,
			processData: false,
			contentType: false,
			headers: { "X-Frappe-CSRF-Token": frappe.csrf_token },
			success: (r) => {
				if (this.$widget) this.$widget.find(".polygin-chat-uploading").remove();
				const data = r.message || {};
				if (!data.success) {
					frappe.msgprint(data.message || __("Upload failed"));
					return;
				}
				// Now send the message with the file URL
				frappe.call({
					method: "polygin.api.send_chat_message",
					args: {
						phone: this.phone,
						message_type: type,
						media_url: data.file_url,
						caption: file.name,
					},
					callback: (r2) => {
						const resp = r2.message || {};
						if (resp.success) {
							frappe.show_alert({ message: __(`${type} sent!`), indicator: "green" });
							setTimeout(() => this.fetch_messages(), 1000);
						} else {
							frappe.msgprint(resp.message || __("Failed to send"));
						}
					},
				});
			},
			error: () => {
				if (this.$widget) this.$widget.find(".polygin-chat-uploading").remove();
				frappe.msgprint(__("File upload failed"));
			},
		});
	}

	// ── Interactive Message Composers ─────────────────────────

	show_list_composer() {
		if (!this.$widget) return;
		const $overlay = $(`
			<div class="polygin-interactive-overlay">
				<div class="polygin-interactive-modal">
					<h4>List Message</h4>
					<label>Header</label>
					<input type="text" class="list-header" placeholder="Header text">
					<label>Body</label>
					<textarea class="list-body" rows="2" placeholder="Body text (required)"></textarea>
					<label>Footer</label>
					<input type="text" class="list-footer" placeholder="Footer text">
					<label>Button Text</label>
					<input type="text" class="list-button" placeholder="e.g. Choose option" value="Choose option">
					<label>Section Title</label>
					<input type="text" class="list-section-title" placeholder="Section 1">
					<label>Options (one per line: id | title | description)</label>
					<textarea class="list-options" rows="4" placeholder="opt1 | Option 1 | Description here&#10;opt2 | Option 2 | Another desc"></textarea>
					<div class="modal-actions">
						<button class="btn-cancel">Cancel</button>
						<button class="btn-send">Send</button>
					</div>
				</div>
			</div>
		`);

		$overlay.find(".btn-cancel").on("click", () => $overlay.remove());
		$overlay.find(".btn-send").on("click", () => {
			const body = $overlay.find(".list-body").val().trim();
			if (!body) { frappe.msgprint(__("Body text is required")); return; }

			const rows = $overlay.find(".list-options").val().trim().split("\n").filter(Boolean).map((line) => {
				const parts = line.split("|").map((s) => s.trim());
				return { id: parts[0] || "", title: parts[1] || parts[0] || "", description: parts[2] || "" };
			});

			const interactive = {
				type: "list",
				header: { type: "text", text: $overlay.find(".list-header").val().trim() || "" },
				body: { text: body },
				footer: { text: $overlay.find(".list-footer").val().trim() || "" },
				action: {
					button: $overlay.find(".list-button").val().trim() || "Choose",
					sections: [{ title: $overlay.find(".list-section-title").val().trim() || "Options", rows: rows }],
				},
			};

			$overlay.remove();
			this._send_interactive("interactive_list", interactive, body);
		});

		this.$widget.append($overlay);
	}

	show_button_composer() {
		if (!this.$widget) return;
		const $overlay = $(`
			<div class="polygin-interactive-overlay">
				<div class="polygin-interactive-modal">
					<h4>Reply Buttons</h4>
					<label>Body</label>
					<textarea class="btn-body" rows="2" placeholder="Choose an option (required)"></textarea>
					<label>Buttons (one per line: id | title, max 3)</label>
					<textarea class="btn-options" rows="3" placeholder="yes | Yes&#10;no | No&#10;maybe | Maybe"></textarea>
					<div class="modal-actions">
						<button class="btn-cancel">Cancel</button>
						<button class="btn-send">Send</button>
					</div>
				</div>
			</div>
		`);

		$overlay.find(".btn-cancel").on("click", () => $overlay.remove());
		$overlay.find(".btn-send").on("click", () => {
			const body = $overlay.find(".btn-body").val().trim();
			if (!body) { frappe.msgprint(__("Body text is required")); return; }

			const buttons = $overlay.find(".btn-options").val().trim().split("\n").filter(Boolean).slice(0, 3).map((line) => {
				const parts = line.split("|").map((s) => s.trim());
				return { type: "reply", reply: { id: parts[0] || "", title: parts[1] || parts[0] || "" } };
			});

			if (buttons.length === 0) { frappe.msgprint(__("Add at least one button")); return; }

			const interactive = {
				type: "button",
				body: { text: body },
				action: { buttons: buttons },
			};

			$overlay.remove();
			this._send_interactive("interactive_button", interactive, body);
		});

		this.$widget.append($overlay);
	}

	_send_interactive(type, interactiveData, displayText) {
		frappe.call({
			method: "polygin.api.send_chat_message",
			args: {
				phone: this.phone,
				message_type: type,
				content: displayText,
				interactive_data: JSON.stringify(interactiveData),
			},
			callback: (r) => {
				const resp = r.message || {};
				if (resp.success) {
					frappe.show_alert({ message: __("Interactive message sent!"), indicator: "green" });
					setTimeout(() => this.fetch_messages(), 1000);
				} else {
					frappe.msgprint(resp.message || __("Failed to send"));
				}
			},
		});
	}

	// ── Phone Resolution (static) ────────────────────────────

	static resolve_phone(frm) {
		const fieldPriority = {
			Lead: ["whatsapp_no", "mobile_no", "phone"],
			Contact: ["mobile_no", "phone"],
			Customer: ["mobile_no"],
			Opportunity: ["whatsapp", "phone"],
		};
		const fields = fieldPriority[frm.doctype] || ["mobile_no", "phone"];
		for (const f of fields) {
			const val = frm.doc[f];
			if (val && val.trim()) return val.trim();
		}
		return null;
	}

	static resolve_contact_name(frm) {
		if (frm.doctype === "Lead") {
			return frm.doc.lead_name || frm.doc.first_name || frm.doc.company_name || "";
		} else if (frm.doctype === "Contact") {
			return frm.doc.first_name ? `${frm.doc.first_name} ${frm.doc.last_name || ""}`.trim() : "";
		} else if (frm.doctype === "Customer") {
			return frm.doc.customer_name || frm.doc.name || "";
		} else if (frm.doctype === "Opportunity") {
			return frm.doc.customer_name || frm.doc.party_name || "";
		}
		return "";
	}

	// ── Date/Time Formatting ─────────────────────────────────

	_format_date(ts) {
		try {
			const d = new Date(ts);
			if (isNaN(d.getTime())) return "";
			const today = new Date();
			const yesterday = new Date(today);
			yesterday.setDate(yesterday.getDate() - 1);

			if (d.toDateString() === today.toDateString()) return "Today";
			if (d.toDateString() === yesterday.toDateString()) return "Yesterday";
			return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
		} catch { return ""; }
	}

	_format_time(ts) {
		try {
			const d = new Date(ts);
			if (isNaN(d.getTime())) return "";
			return d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: true });
		} catch { return ""; }
	}

	// ── Lifecycle ─────────────────────────────────────────────

	destroy() {
		this.stop_polling();
		this.stop_countdown();
		this.remove_widget();
		this.remove_bubble();
		$(document).off("click.polygin_attach");
		if (window._polygin_chat_instance === this) {
			window._polygin_chat_instance = null;
		}
	}
}

// Global singleton reference
window._polygin_chat_instance = null;
window.PolyginChat = PolyginChat;
