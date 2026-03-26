"""Workflow #61: NP License Tracker — Phase 1 Priority.

Tracks NP license expiration dates and renewal requirements.
Career-critical — missing this could prevent working.

Recommended phase: 1 (quick_win_score: 15)
Trust level: auto
Category: licensure

TODO: Implement after scaffolding is approved.

Workflow states:
- active -> renewal_window_open -> reminder_sent -> renewed | expired

Service interface:
- add_license(type, state, number, expiry, renewal_reqs) -> License
- check_expiring(days_ahead) -> list[License]
- mark_renewed(license_id, new_expiry) -> None
- get_renewal_checklist(license_id) -> list[Requirement]
"""

# TODO: Implement BaseWorkflow subclass
# TODO: Add schemas and tests
