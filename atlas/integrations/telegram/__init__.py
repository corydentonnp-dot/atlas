"""Telegram bot integration adapter — primary command/control interface.

TODO: Implement after scaffolding is approved.
Required credentials: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

Capabilities:
- send_message(text, parse_mode, reply_markup) -> int
- send_approval_prompt(approval) -> int
- handle_callback(callback_data) -> None
- send_digest(items) -> int
- register_command(command, handler) -> None
- send_document(file, caption) -> int
- edit_message(message_id, text) -> None

Commands to register:
- /status — system status
- /pending — pending approvals
- /approve <id> — approve an action
- /reject <id> — reject an action
- /workflows — list active workflows
- /trigger <workflow> — manually trigger a workflow
- /quiet — toggle quiet mode
- /intent <text> — capture an intent
"""
