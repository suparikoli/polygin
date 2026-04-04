"""Public API module for whitelisted methods.

This keeps method paths stable as `polygin.api.<method>`.
"""

from polygin.polygin.api import (  # noqa: F401
	get_buttons,
	get_chat_messages,
	get_chat_settings,
	get_quick_replies,
	send_chat_message,
	send_whatsapp_template,
	upload_chat_media,
)
