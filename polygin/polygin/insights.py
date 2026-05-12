"""Polygin Insights: aggregate metrics for the Polygin dashboard.

Powers Number Cards (Custom type) and Dashboard Charts (Custom source)
shown in the Polygin Insights dashboard.
"""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, get_datetime, getdate, now_datetime
from frappe.utils.dashboard import cache_source

from polygin.utils import normalize_phone_for_matching


WA_DOCTYPE = "Polygin Wa Messages"
TG_DOCTYPE = "Polygin Telegram Messages"
LOG_DOCTYPE = "Polygin Message Log"


def _normalize_recipients(recipients):
	out = set()
	for r in recipients:
		n = normalize_phone_for_matching(r)
		if n:
			out.add(n)
	return out


def _count_replies_for_recipients(normalized_recipients):
	"""Count incoming messages from any recipient phone, across WA + Telegram."""
	if not normalized_recipients:
		return 0
	phones = list(normalized_recipients)
	count = 0
	for dt in (WA_DOCTYPE, TG_DOCTYPE):
		count += frappe.db.count(
			dt,
			filters={"direction": "incoming", "normalized_phone": ("in", phones)},
		)
	return count


# ---------------------------------------------------------------------------
# Number Card methods (referenced by Number Card.method)
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_reply_rate():
	"""Percent of unique recipients (with at least one Success send) who replied."""
	rows = frappe.get_all(
		LOG_DOCTYPE,
		filters={"status": "Success"},
		fields=["recipient"],
	)
	recipients = _normalize_recipients(r.recipient for r in rows if r.recipient)
	if not recipients:
		return {"value": 0, "fieldtype": "Percent"}

	repliers = set()
	for dt in (WA_DOCTYPE, TG_DOCTYPE):
		incoming = frappe.get_all(
			dt,
			filters={"direction": "incoming", "normalized_phone": ("in", list(recipients))},
			fields=["normalized_phone"],
			distinct=True,
		)
		for row in incoming:
			if row.normalized_phone:
				repliers.add(row.normalized_phone)

	rate = (len(repliers) / len(recipients)) * 100.0
	return {"value": flt(rate, 2), "fieldtype": "Percent"}


@frappe.whitelist()
def get_active_conversations():
	"""Recipients with an incoming message in the last 24h (response window open)."""
	cutoff = frappe.utils.add_to_date(now_datetime(), hours=-24)
	phones = set()
	for dt in (WA_DOCTYPE, TG_DOCTYPE):
		rows = frappe.get_all(
			dt,
			filters={"direction": "incoming", "creation": (">=", cutoff)},
			fields=["normalized_phone"],
			distinct=True,
		)
		for r in rows:
			if r.normalized_phone:
				phones.add(r.normalized_phone)
	return {"value": len(phones), "fieldtype": "Int"}


@frappe.whitelist()
def get_top_user_score():
	"""Engagement score for the highest-engagement user (replies / sent * 100)."""
	board = _engagement_leaderboard()
	if not board:
		return {"value": 0, "fieldtype": "Percent"}
	top = board[0]
	return {"value": flt(top["engagement"], 2), "fieldtype": "Percent"}


# ---------------------------------------------------------------------------
# Spend metrics
# ---------------------------------------------------------------------------


def _settings_currency():
	return frappe.utils.cstr(frappe.db.get_single_value("Polygin Settings", "currency")) or "INR"


def _spend_card(value):
	return {
		"value": flt(value, 2),
		"fieldtype": "Currency",
		"currency": _settings_currency(),
	}


@frappe.whitelist()
def get_spend_today():
	"""Total cost of successful template sends today."""
	today = getdate()
	total = (
		frappe.db.sql(
			"""
			SELECT COALESCE(SUM(cost), 0)
			FROM `tabPolygin Message Log`
			WHERE status = 'Success' AND DATE(timestamp) = %s
			""",
			(today,),
		)[0][0]
		or 0
	)
	return _spend_card(total)


@frappe.whitelist()
def get_spend_this_month():
	"""Total cost of successful template sends in the current month."""
	today = getdate()
	first_day = today.replace(day=1)
	total = (
		frappe.db.sql(
			"""
			SELECT COALESCE(SUM(cost), 0)
			FROM `tabPolygin Message Log`
			WHERE status = 'Success' AND DATE(timestamp) BETWEEN %s AND %s
			""",
			(first_day, today),
		)[0][0]
		or 0
	)
	return _spend_card(total)


@frappe.whitelist()
def get_avg_cost_per_reply():
	"""Total spend divided by replies received (across WA + Telegram)."""
	total_spend = (
		frappe.db.sql(
			"SELECT COALESCE(SUM(cost), 0) FROM `tabPolygin Message Log` WHERE status = 'Success'"
		)[0][0]
		or 0
	)
	replies = 0
	for dt in (WA_DOCTYPE, TG_DOCTYPE):
		replies += frappe.db.count(dt, filters={"direction": "incoming"})
	if not replies:
		return _spend_card(0)
	return _spend_card(flt(total_spend) / replies)


@frappe.whitelist()
def get_top_spender():
	"""Spend of the highest-spending user in the current month."""
	today = getdate()
	first_day = today.replace(day=1)
	rows = frappe.db.sql(
		"""
		SELECT owner, COALESCE(SUM(cost), 0) AS spend
		FROM `tabPolygin Message Log`
		WHERE status = 'Success' AND DATE(timestamp) BETWEEN %s AND %s
		GROUP BY owner
		ORDER BY spend DESC
		LIMIT 1
		""",
		(first_day, today),
		as_dict=True,
	)
	if not rows:
		return _spend_card(0)
	return _spend_card(rows[0].spend)


@frappe.whitelist()
@cache_source
def get_spend_by_user(
	chart_name=None,
	chart=None,
	no_cache=None,
	filters=None,
	from_date=None,
	to_date=None,
	timespan=None,
	time_interval=None,
	heatmap_year=None,
):
	"""Top 10 users ranked by total spend (Success only)."""
	rows = frappe.db.sql(
		"""
		SELECT owner, COALESCE(SUM(cost), 0) AS spend
		FROM `tabPolygin Message Log`
		WHERE status = 'Success'
		GROUP BY owner
		ORDER BY spend DESC
		LIMIT 10
		""",
		as_dict=True,
	)
	labels = [frappe.utils.get_fullname(r.owner) or r.owner for r in rows]
	values = [flt(r.spend, 2) for r in rows]
	return {
		"labels": labels,
		"datasets": [{"name": _("Spend"), "values": values}],
	}


@frappe.whitelist()
@cache_source
def get_spend_trend_daily(
	chart_name=None,
	chart=None,
	no_cache=None,
	filters=None,
	from_date=None,
	to_date=None,
	timespan=None,
	time_interval=None,
	heatmap_year=None,
):
	"""Daily spend for the last 30 days."""
	to_dt = getdate()
	from_dt = frappe.utils.add_days(to_dt, -29)
	rows = frappe.db.sql(
		"""
		SELECT DATE(timestamp) AS d, COALESCE(SUM(cost), 0) AS spend
		FROM `tabPolygin Message Log`
		WHERE status = 'Success' AND DATE(timestamp) BETWEEN %(f)s AND %(t)s
		GROUP BY DATE(timestamp)
		""",
		{"f": from_dt, "t": to_dt},
		as_dict=True,
	)
	by_day = {str(r.d): flt(r.spend, 2) for r in rows if r.d}

	labels, values = [], []
	cur = from_dt
	for _i in range(30):
		labels.append(frappe.utils.formatdate(cur, "MMM dd"))
		values.append(by_day.get(str(cur), 0))
		cur = frappe.utils.add_days(cur, 1)

	return {
		"labels": labels,
		"datasets": [{"name": _("Spend"), "values": values}],
	}


@frappe.whitelist()
def get_spend_breakdown():
	"""Plain JSON breakdown by user, template, and category — for ad-hoc use."""
	by_user = frappe.db.sql(
		"""
		SELECT owner, COUNT(*) AS sent, COALESCE(SUM(cost), 0) AS spend
		FROM `tabPolygin Message Log`
		WHERE status = 'Success'
		GROUP BY owner
		ORDER BY spend DESC
		""",
		as_dict=True,
	)
	by_template = frappe.db.sql(
		"""
		SELECT template, COUNT(*) AS sent, COALESCE(SUM(cost), 0) AS spend
		FROM `tabPolygin Message Log`
		WHERE status = 'Success'
		GROUP BY template
		ORDER BY spend DESC
		""",
		as_dict=True,
	)
	by_category = frappe.db.sql(
		"""
		SELECT category, COUNT(*) AS sent, COALESCE(SUM(cost), 0) AS spend
		FROM `tabPolygin Message Log`
		WHERE status = 'Success'
		GROUP BY category
		ORDER BY spend DESC
		""",
		as_dict=True,
	)
	return {
		"currency": _settings_currency(),
		"by_user": [
			{"user": r.owner, "user_label": frappe.utils.get_fullname(r.owner) or r.owner,
			 "sent": r.sent, "spend": flt(r.spend, 2)}
			for r in by_user
		],
		"by_template": [{"template": r.template or "(unknown)", "sent": r.sent, "spend": flt(r.spend, 2)} for r in by_template],
		"by_category": [{"category": r.category or "(uncategorized)", "sent": r.sent, "spend": flt(r.spend, 2)} for r in by_category],
	}


# ---------------------------------------------------------------------------
# Dashboard Chart sources (referenced by Dashboard Chart.source)
# ---------------------------------------------------------------------------


@frappe.whitelist()
@cache_source
def get_top_users_by_messages(
	chart_name=None,
	chart=None,
	no_cache=None,
	filters=None,
	from_date=None,
	to_date=None,
	timespan=None,
	time_interval=None,
	heatmap_year=None,
):
	"""Top 10 ERPNext users ranked by templated messages sent (Success only)."""
	rows = frappe.db.sql(
		"""
		SELECT owner, COUNT(*) AS sent
		FROM `tabPolygin Message Log`
		WHERE status = 'Success'
		GROUP BY owner
		ORDER BY sent DESC
		LIMIT 10
		""",
		as_dict=True,
	)
	labels = [frappe.utils.get_fullname(r.owner) or r.owner for r in rows]
	values = [r.sent for r in rows]
	return {
		"labels": labels,
		"datasets": [{"name": _("Messages Sent"), "values": values}],
	}


@frappe.whitelist()
@cache_source
def get_engagement_leaderboard(
	chart_name=None,
	chart=None,
	no_cache=None,
	filters=None,
	from_date=None,
	to_date=None,
	timespan=None,
	time_interval=None,
	heatmap_year=None,
):
	"""Per-user engagement: replies received divided by messages sent (top 10)."""
	board = _engagement_leaderboard()[:10]
	labels = [r["user_label"] for r in board]
	sent = [r["sent"] for r in board]
	replies = [r["replies"] for r in board]
	return {
		"labels": labels,
		"datasets": [
			{"name": _("Sent"), "values": sent},
			{"name": _("Replies"), "values": replies},
		],
	}


@frappe.whitelist()
@cache_source
def get_sent_vs_replies_daily(
	chart_name=None,
	chart=None,
	no_cache=None,
	filters=None,
	from_date=None,
	to_date=None,
	timespan=None,
	time_interval=None,
	heatmap_year=None,
):
	"""Daily Sent vs Replies for the last 30 days."""
	to_dt = getdate()
	from_dt = frappe.utils.add_days(to_dt, -29)

	sent_rows = frappe.db.sql(
		"""
		SELECT DATE(timestamp) AS d, COUNT(*) AS c
		FROM `tabPolygin Message Log`
		WHERE status = 'Success' AND DATE(timestamp) BETWEEN %(f)s AND %(t)s
		GROUP BY DATE(timestamp)
		""",
		{"f": from_dt, "t": to_dt},
		as_dict=True,
	)
	sent_by_day = {str(r.d): r.c for r in sent_rows if r.d}

	reply_by_day = defaultdict(int)
	for dt in (WA_DOCTYPE, TG_DOCTYPE):
		rows = frappe.db.sql(
			f"""
			SELECT DATE(creation) AS d, COUNT(*) AS c
			FROM `tab{dt}`
			WHERE direction = 'incoming' AND DATE(creation) BETWEEN %(f)s AND %(t)s
			GROUP BY DATE(creation)
			""",
			{"f": from_dt, "t": to_dt},
			as_dict=True,
		)
		for r in rows:
			if r.d:
				reply_by_day[str(r.d)] += r.c

	labels, sent_vals, reply_vals = [], [], []
	cur = from_dt
	for _i in range(30):
		key = str(cur)
		labels.append(frappe.utils.formatdate(cur, "MMM dd"))
		sent_vals.append(sent_by_day.get(key, 0))
		reply_vals.append(reply_by_day.get(key, 0))
		cur = frappe.utils.add_days(cur, 1)

	return {
		"labels": labels,
		"datasets": [
			{"name": _("Sent"), "values": sent_vals},
			{"name": _("Replies"), "values": reply_vals},
		],
	}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _engagement_leaderboard():
	"""Compute per-user [{user, sent, replies, engagement%}], sorted by engagement."""
	logs = frappe.get_all(
		LOG_DOCTYPE,
		filters={"status": "Success"},
		fields=["owner", "recipient", "reference_doctype", "reference_name", "timestamp"],
	)
	if not logs:
		return []

	# Group recipients per user
	recipients_per_user = defaultdict(set)
	first_send_by_pair = {}  # (user, normalized_phone) -> earliest send timestamp
	for r in logs:
		phone = normalize_phone_for_matching(r.recipient)
		if not phone:
			continue
		recipients_per_user[r.owner].add(phone)
		key = (r.owner, phone)
		ts = get_datetime(r.timestamp) if r.timestamp else None
		if ts and (key not in first_send_by_pair or ts < first_send_by_pair[key]):
			first_send_by_pair[key] = ts

	# Replies per user: count incoming messages from those recipients sent
	# AFTER the earliest log entry for the (user, phone) pair, so replies are
	# attributed to the user who actually triggered the conversation.
	all_phones = list({p for s in recipients_per_user.values() for p in s})
	replies_per_pair = defaultdict(int)  # (phone) -> count of incoming
	if all_phones:
		for dt in (WA_DOCTYPE, TG_DOCTYPE):
			rows = frappe.get_all(
				dt,
				filters={"direction": "incoming", "normalized_phone": ("in", all_phones)},
				fields=["normalized_phone", "creation"],
			)
			for row in rows:
				replies_per_pair[(row.normalized_phone, row.creation)] += 1

	board = []
	for user, phones in recipients_per_user.items():
		sent = sum(1 for r in logs if r.owner == user)
		replies = 0
		for phone in phones:
			first_send = first_send_by_pair.get((user, phone))
			for (rp, created), c in replies_per_pair.items():
				if rp == phone and (not first_send or created >= first_send):
					replies += c
		engagement = (replies / sent * 100.0) if sent else 0.0
		board.append(
			{
				"user": user,
				"user_label": frappe.utils.get_fullname(user) or user,
				"sent": sent,
				"replies": replies,
				"engagement": flt(engagement, 2),
			}
		)

	board.sort(key=lambda x: x["engagement"], reverse=True)
	return board


@frappe.whitelist()
def get_engagement_table():
	"""Plain JSON list for the leaderboard — used by the workspace shortcut/page."""
	return _engagement_leaderboard()
