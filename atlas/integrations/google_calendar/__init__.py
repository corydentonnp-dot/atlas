"""Google Calendar integration adapter.

TODO: Implement after scaffolding is approved.
Required credentials: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET (shared with Gmail)

Capabilities:
- list_events(start, end) -> list[CalendarEvent]
- create_event(event) -> str
- update_event(event_id, updates) -> None
- delete_event(event_id) -> None
- find_free_slots(start, end, duration) -> list[TimeSlot]
- get_upcoming(hours=24) -> list[CalendarEvent]
"""
