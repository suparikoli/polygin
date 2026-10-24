frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Polygin Spend Trend Daily"] = {
	method: "mith_wa_polygin.mith_wa_polygin.insights.get_spend_trend_daily",
	filters: [],
};
