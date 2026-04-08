// Polygin notifications tab — adds a "Polygin" tab in Frappe's notification
// dropdown that lists Polygin notifications (identified by a link containing
// `polygin_chat=open`). Also plays a ding on new arrivals.

(function () {
	// ── Notification sound (gentle two-tone chime via WebAudio) ──────
	let _ctx = null;
	function playDing() {
		try {
			if (!_ctx) {
				const Ctx = window.AudioContext || window.webkitAudioContext;
				if (!Ctx) return;
				_ctx = new Ctx();
			}
			if (_ctx.state === "suspended") _ctx.resume();
			const now = _ctx.currentTime;
			// Soft two-note sine chime — high-to-higher, gentle on the ears.
			[
				{ f: 1046, t: 0.0, d: 0.14 },  // C6
				{ f: 1568, t: 0.12, d: 0.22 }, // G6
			].forEach(({ f, t, d }) => {
				const osc = _ctx.createOscillator();
				const gain = _ctx.createGain();
				osc.type = "sine";
				osc.frequency.value = f;
				gain.gain.setValueAtTime(0, now + t);
				gain.gain.linearRampToValueAtTime(0.18, now + t + 0.02);
				gain.gain.exponentialRampToValueAtTime(0.0001, now + t + d);
				osc.connect(gain).connect(_ctx.destination);
				osc.start(now + t);
				osc.stop(now + t + d + 0.02);
			});
		} catch (e) {}
	}

	// Unlock the AudioContext on the first user gesture so subsequent
	// programmatic dings work without autoplay errors.
	function primeAudioUnlock() {
		const unlock = () => {
			try {
				if (!_ctx) {
					const Ctx = window.AudioContext || window.webkitAudioContext;
					if (Ctx) _ctx = new Ctx();
				}
				if (_ctx && _ctx.state === "suspended") _ctx.resume();
			} catch (e) {}
			document.removeEventListener("click", unlock);
			document.removeEventListener("keydown", unlock);
		};
		document.addEventListener("click", unlock);
		document.addEventListener("keydown", unlock);
	}

	function installGlobalSoundListener() {
		if (!frappe.realtime || frappe.realtime.__polygin_sound_bound) return;
		frappe.realtime.__polygin_sound_bound = true;
		frappe.realtime.on("notification", () => {
			frappe.db
				.get_list("Notification Log", {
					filters: {
						for_user: frappe.session.user,
						link: ["like", "%polygin_chat=open%"],
					},
					fields: ["name", "creation", "read"],
					order_by: "creation desc",
					limit: 1,
				})
				.then((rows) => {
					if (!rows || !rows.length) return;
					const latest = rows[0];
					if (latest.read) return;
					if (Date.now() - new Date(latest.creation).getTime() < 15000) playDing();
				});
		});
	}

	// On page load, if there are any unread Polygin notifications, ding once
	// after the audio context is unlocked by the first user gesture.
	function checkUnreadOnLoad() {
		frappe.db
			.get_list("Notification Log", {
				filters: {
					for_user: frappe.session.user,
					link: ["like", "%polygin_chat=open%"],
					read: 0,
				},
				fields: ["name"],
				limit: 1,
			})
			.then((rows) => {
				if (!rows || !rows.length) return;
				// Try immediately (may be silent until user gesture), then queue
				// a one-shot on the next gesture as a fallback.
				playDing();
				const queuedDing = () => {
					playDing();
					document.removeEventListener("click", queuedDing);
					document.removeEventListener("keydown", queuedDing);
				};
				document.addEventListener("click", queuedDing, { once: true });
				document.addEventListener("keydown", queuedDing, { once: true });
			});
	}

	// ── Hide Polygin notifications from the main "Notifications" tab ──
	let _filterInstalled = false;
	function installNotificationsFilter() {
		if (_filterInstalled || !window.frappe || !frappe.call) return;
		_filterInstalled = true;

		// Wrap frappe.call so calls to get_notification_logs strip out Polygin ones.
		// IMPORTANT: frappe.call supports BOTH forms:
		//   frappe.call({ method, args, callback })
		//   frappe.call(method, args, callback)
		// We must forward all arguments unchanged, and only intercept when the
		// first form targets get_notification_logs.
		const origCall = frappe.call;
		frappe.call = function (...args) {
			const first = args[0];
			if (
				first &&
				typeof first === "object" &&
				first.method ===
					"frappe.desk.doctype.notification_log.notification_log.get_notification_logs"
			) {
				const origCb = first.callback;
				first.callback = function (r) {
					try {
						if (r && r.message && Array.isArray(r.message.notification_logs)) {
							r.message.notification_logs = r.message.notification_logs.filter(
								(n) => !(n.link && n.link.indexOf("polygin_chat=open") !== -1)
							);
						}
					} catch (e) {}
					if (origCb) origCb(r);
				};
			}
			return origCall.apply(this, args);
		};
	}

	// ── Polygin tab view ──────────────────────────────────────────────
	class PolyginNotificationsView {
		constructor(wrapper, parent, settings) {
			this.wrapper = wrapper;
			this.parent = parent;
			this.settings = settings;
			// Match BaseNotificationsView: create a container inside the panel.
			this.container = $(`<div></div>`).appendTo(this.wrapper);
			this.refresh();
			frappe.realtime.on("notification", () => this.refresh());
		}

		show() {
			this.container.show();
			this.refresh();
		}

		hide() {
			this.container.hide();
		}

		refresh() {
			frappe.db
				.get_list("Notification Log", {
					filters: {
						for_user: frappe.session.user,
						link: ["like", "%polygin_chat=open%"],
					},
					fields: [
						"name",
						"subject",
						"email_content",
						"document_type",
						"document_name",
						"link",
						"read",
						"creation",
						"from_user",
					],
					order_by: "creation desc",
					limit: 30,
				})
				.then((rows) => this.render(rows || []));
		}

		render(items) {
			this.container.empty();
			if (!items.length) {
				this.container.html(`
					<div class="notification-null-state">
						<div class="text-center">
							<img src="/assets/polygin/images/polygin_logo.webp"
								style="width:64px;height:64px;opacity:0.5;margin-bottom:12px;" />
							<div class="title">${__("No Polygin notifications")}</div>
							<div class="subtitle">${__("WhatsApp activity will appear here.")}</div>
						</div>
					</div>`);
				return;
			}

			items.forEach((n) => {
				this.container.append(this.get_item_html(n));
			});
		}

		get_item_html(n) {
			const timestamp = frappe.datetime.comment_when(n.creation);
			const read = n.read ? "" : "unread";
			const href = n.link || `/app/${(n.document_type || "").toLowerCase().replace(/ /g, "-")}/${encodeURIComponent(n.document_name || "")}`;
			const user = n.from_user || frappe.session.user;
			const avatar = frappe.avatar(user, "avatar-medium user-avatar");

			const message_html = `<div class="message">
				<div>${n.subject || ""}</div>
				<div class="notification-timestamp text-muted">${timestamp}</div>
			</div>`;

			const $item = $(`
				<a class="recent-item notification-item ${read}"
					href="${frappe.utils.escape_html(href)}"
					data-name="${frappe.utils.escape_html(n.name)}">
					<div class="notification-body">
						${avatar}
						${message_html}
					</div>
					<div class="mark-as-read" title="${__("Mark as Read")}"></div>
				</a>
			`);

			if (!n.read) {
				$item.find(".mark-as-read").on("click", (e) => {
					e.preventDefault();
					e.stopImmediatePropagation();
					frappe.db.set_value("Notification Log", n.name, "read", 1).then(() => {
						$item.removeClass("unread");
					});
				});
			}
			$item.on("click", () => {
				if (!n.read) frappe.db.set_value("Notification Log", n.name, "read", 1);
			});
			return $item;
		}
	}

	// ── Patch frappe.ui.Notifications to inject the Polygin tab ──────
	function installPatch() {
		if (!frappe.ui || !frappe.ui.Notifications) {
			return setTimeout(installPatch, 200);
		}
		if (frappe.ui.Notifications.__polygin_patched) return;
		frappe.ui.Notifications.__polygin_patched = true;

		const origSetupHeaders = frappe.ui.Notifications.prototype.setup_headers;

		frappe.ui.Notifications.prototype.setup_headers = function () {
			// Inject the panel DOM element BEFORE the original runs — so switch_tab
			// can find it. Place it before .panel-changelog-feed.
			const body = this.dropdown_list.find(".notification-list-body");
			if (!body.find(".panel-polygin").length) {
				const $panel = $(`<div class="panel-polygin"></div>`);
				const $changelogPanel = body.find(".panel-changelog-feed");
				if ($changelogPanel.length) {
					$changelogPanel.before($panel);
				} else {
					body.append($panel);
				}
			}
			this.panel_polygin = this.dropdown_list.find(".panel-polygin");

			// Run the original — it will build the 3 native categories and call
			// switch_tab(categories[0]), showing only the Notifications view.
			origSetupHeaders.call(this);

			// Inject the Polygin category into the array BEFORE changelog_feed.
			const polyginCategory = {
				label: __("Polygin"),
				id: "polygin",
				view: PolyginNotificationsView,
				el: this.panel_polygin,
			};

			const idx = this.categories.findIndex((c) => c.id === "changelog_feed");
			const insertAt = idx >= 0 ? idx : this.categories.length;

			// Build and insert the <li> tab before the changelog tab
			const $tab = $(
				`<li class="notifications-category" id="polygin" data-toggle="collapse">${polyginCategory.label}</li>`
			);
			$tab.on("click", (e) => {
				e.stopImmediatePropagation();
				this.switch_tab(polyginCategory);
			});
			polyginCategory.$tab = $tab;

			const $navItem = this.dropdown_list.find(".notification-item-tabs");
			const $changelogTab = $navItem.find("#changelog_feed");
			if ($changelogTab.length) {
				$changelogTab.before($tab);
			} else {
				$navItem.append($tab);
			}

			this.categories.splice(insertAt, 0, polyginCategory);

			// Instantiate the tab view. Its container starts visible; we hide it
			// immediately because the "Notifications" tab is active at startup.
			const view = new PolyginNotificationsView(
				polyginCategory.el,
				this.dropdown,
				this.notification_settings
			);
			view.hide();
			this.tabs["polygin"] = view;
		};
	}

	$(document).ready(() => {
		primeAudioUnlock();
		installNotificationsFilter();
		installPatch();
		installGlobalSoundListener();
		// Small delay so frappe.session is ready.
		setTimeout(checkUnreadOnLoad, 1500);
	});
})();
