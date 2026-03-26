"""Workflow #35: Installment Tracker — Phase 1 Priority.

Tracks installment payment plans (Buy Now Pay Later, etc.) and alerts
before each payment date.

Recommended phase: 1 (quick_win_score: 13)
Trust level: auto
Category: budget

TODO: Implement after scaffolding is approved.

Workflow states:
- idle -> payment_approaching -> reminder_sent -> paid | missed

Service interface:
- add_installment_plan(merchant, total, payments, dates) -> Plan
- check_upcoming(days_ahead) -> list[UpcomingPayment]
- mark_paid(payment_id) -> None
"""

# TODO: Implement BaseWorkflow subclass, schemas, tests
