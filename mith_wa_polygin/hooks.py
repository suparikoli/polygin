app_name = "mith_wa_polygin"
app_title = "Mith WA Polygin"
app_publisher = "Mithtech Innovative Solutions PVT LTD"
app_description = "Send WhatsApp template messages from ERPNext using Polyg.in with configurable buttons and dynamic field mapping."
app_email = "manoj@mith.tech"
app_license = "mit"

add_to_apps_screen = [
	{
		"name": "mith_wa_polygin",
		"logo": "/assets/mith_wa_polygin/images/polygin_logo.png",
		"title": "Polygin",
		"route": "/app/polygin",
	}
]

app_include_css = "/assets/mith_wa_polygin/css/polygin_chat.css?v=19"
app_include_js = [
	"/assets/mith_wa_polygin/js/polygin_chat.js?v=21",
	"/assets/mith_wa_polygin/js/polygin_notifications.js?v=5",
]

doctype_js = {
	"Lead": "public/js/mith_wa_polygin.js",
	"Contact": "public/js/mith_wa_polygin.js",
	"Customer": "public/js/mith_wa_polygin.js",
	"Supplier": "public/js/mith_wa_polygin.js",
	"Opportunity": "public/js/mith_wa_polygin.js",
	"Sales Invoice": "public/js/mith_wa_polygin.js",
	"Sales Order": "public/js/mith_wa_polygin.js",
	"Quotation": "public/js/mith_wa_polygin.js",
	"Delivery Note": "public/js/mith_wa_polygin.js",
	"Purchase Order": "public/js/mith_wa_polygin.js",
	"Purchase Invoice": "public/js/mith_wa_polygin.js",
	"Purchase Receipt": "public/js/mith_wa_polygin.js",
}
