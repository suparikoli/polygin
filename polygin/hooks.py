app_name = "polygin"
app_title = "Polygin"
app_publisher = "Mithtech Innovative Solutions PVT LTD"
app_description = "Send WhatsApp template messages from ERPNext using Polyg.in with configurable buttons and dynamic field mapping."
app_email = "manoj@mith.tech"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
add_to_apps_screen = [
	{
		"name": "polygin",
		"logo": "/assets/polygin/images/polygin_logo.webp",
		"title": "Polygin",
		"route": "/app/polygin",
	}
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "/assets/polygin/css/polygin_chat.css?v=13"
app_include_js = "/assets/polygin/js/polygin_chat.js?v=13"

# include js, css files in header of web template
# web_include_css = "/assets/polygin/css/polygin.css"
# web_include_js = "/assets/polygin/js/polygin.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "polygin/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
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
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "polygin/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "polygin.utils.jinja_methods",
# 	"filters": "polygin.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "polygin.install.before_install"
# after_install = "polygin.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "polygin.uninstall.before_uninstall"
# after_uninstall = "polygin.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "polygin.utils.before_app_install"
# after_app_install = "polygin.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "polygin.utils.before_app_uninstall"
# after_app_uninstall = "polygin.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "polygin.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"polygin.tasks.all"
# 	],
# 	"daily": [
# 		"polygin.tasks.daily"
# 	],
# 	"hourly": [
# 		"polygin.tasks.hourly"
# 	],
# 	"weekly": [
# 		"polygin.tasks.weekly"
# 	],
# 	"monthly": [
# 		"polygin.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "polygin.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "polygin.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "polygin.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "polygin.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["polygin.utils.before_request"]
# after_request = ["polygin.utils.after_request"]

# Job Events
# ----------
# before_job = ["polygin.utils.before_job"]
# after_job = ["polygin.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"polygin.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
