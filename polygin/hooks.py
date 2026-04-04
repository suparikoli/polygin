app_name = "polygin"
app_title = "Polygin"
app_publisher = "Mithtech Innovative Solutions PVT LTD"
app_description = "Send WhatsApp template messages from ERPNext using Polyg.in with configurable buttons and dynamic field mapping."
app_email = "manoj@mith.tech"
app_license = "mit"

add_to_apps_screen = [
	{
		"name": "polygin",
		"logo": "/assets/polygin/images/polygin_logo.webp",
		"title": "Polygin",
		"route": "/app/polygin",
	}
]

app_include_css = "/assets/polygin/css/polygin_chat.css?v=19"
app_include_js = "/assets/polygin/js/polygin_chat.js?v=21"

doctype_js = {
	"Lead": "public/js/polygin.js",
	"Contact": "public/js/polygin.js",
	"Customer": "public/js/polygin.js",
	"Supplier": "public/js/polygin.js",
	"Opportunity": "public/js/polygin.js",
	"Sales Invoice": "public/js/polygin.js",
	"Sales Order": "public/js/polygin.js",
	"Quotation": "public/js/polygin.js",
	"Delivery Note": "public/js/polygin.js",
	"Purchase Order": "public/js/polygin.js",
	"Purchase Invoice": "public/js/polygin.js",
	"Purchase Receipt": "public/js/polygin.js",
}
