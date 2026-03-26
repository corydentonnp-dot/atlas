"""Workflow #4: Family Check-In Agent — Phase 3.

Periodic reminders to check in with family members you haven't
contacted recently.

Recommended phase: 3 (quick_win_score: 5)
Trust level: draft
Category: communication

TODO: Implement after scaffolding is approved.

Workflow states:
- idle -> check_due -> reminder_sent -> check_in_done | snoozed

Service interface:
- get_overdue_check_ins() -> list[FamilyContact]
- send_reminder(contact) -> None
"""

# TODO: Implement BaseWorkflow subclass
# TODO: Add schemas and tests
