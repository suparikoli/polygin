frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Polygin Sent vs Replies Daily"] = {
	method: "mith_wa_polygin.mith_wa_polygin.insights.get_sent_vs_replies_daily",
	filters: [],
};
