frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Polygin Engagement Leaderboard"] = {
	method: "mith_wa_polygin.mith_wa_polygin.insights.get_engagement_leaderboard",
	filters: [],
};
