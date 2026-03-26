"""Workflow #29: Rent Reminder Agent — Phase 1 Priority.

Sends rent payment reminders to tenants on a schedule.

Recommended phase: 1 (quick_win_score: 13)
Trust level: auto
Category: property

TODO: Implement after scaffolding is approved.

Workflow states:
- idle -> reminder_due -> reminder_sent -> confirmed_paid | overdue

Service interface:
- check_due_rents() -> list[RentDue]
- send_reminder(rent_due) -> None
- mark_paid(tenant_id, month) -> None
"""

# TODO: Implement BaseWorkflow subclass
# TODO: Add scheduling (e.g., 3 days before due, on due date, 3 days after)
# TODO: Add schemas and tests
