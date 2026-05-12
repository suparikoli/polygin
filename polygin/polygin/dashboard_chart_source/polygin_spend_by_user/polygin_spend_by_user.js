frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Polygin Spend by User"] = {
	method: "polygin.polygin.insights.get_spend_by_user",
	filters: [],
};
