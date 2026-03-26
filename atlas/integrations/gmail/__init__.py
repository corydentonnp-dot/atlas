"""Gmail integration adapter.

TODO: Implement after scaffolding is approved.
Required credentials: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
OAuth flow required for first-time setup.

Capabilities:
- list_messages(query, limit) -> list[EmailMessage]
- get_message(message_id) -> EmailMessage
- send_message(to, subject, body, draft_only=True) -> str
- list_threads(query, limit) -> list[EmailThread]
- mark_read(message_id) -> None
- add_label(message_id, label) -> None
- search(query) -> list[EmailMessage]

Privacy notes:
- All email data stays local
- OAuth tokens stored in secure local storage
- No email content sent to external services
"""
