frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Polygin Spend by User"] = {
	method: "mith_wa_polygin.mith_wa_polygin.insights.get_spend_by_user",
	filters: [],
};
