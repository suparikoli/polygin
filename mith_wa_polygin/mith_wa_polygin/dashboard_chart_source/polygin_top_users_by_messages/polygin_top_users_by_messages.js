frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Polygin Top Users by Messages"] = {
	method: "mith_wa_polygin.mith_wa_polygin.insights.get_top_users_by_messages",
	filters: [],
};
