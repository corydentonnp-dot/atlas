"""Location / presence adapter interface.

TODO: Implement after scaffolding is approved.
Primary source: Home Assistant presence detection.
Could also use phone location APIs or manual check-in.

Capabilities:
- get_presence(person) -> PresenceState (home / away / unknown)
- get_all_presence() -> dict[str, PresenceState]
- on_presence_change(person, callback) -> None
- is_both_away() -> bool
- is_both_home() -> bool
- get_last_departure(person) -> datetime | None
"""
