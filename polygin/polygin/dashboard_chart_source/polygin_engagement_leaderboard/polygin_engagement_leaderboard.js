frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Polygin Engagement Leaderboard"] = {
	method: "polygin.polygin.insights.get_engagement_leaderboard",
	filters: [],
};
