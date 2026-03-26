"""Workflow #36: Promo APR Deadline Agent — Phase 1 TOP PRIORITY.

Tracks promotional APR periods on credit cards and alerts well before
they expire to allow balance payoff or transfer.

Recommended phase: 1 (quick_win_score: 16 — HIGHEST)
Trust level: auto
Category: budget

TODO: Implement after scaffolding is approved.

Workflow states:
- idle -> tracking -> warning_30d -> warning_7d -> deadline_reached -> resolved

Service interface:
- add_promo(card, apr, balance, promo_end_date, regular_apr) -> PromoAPR
- check_approaching(days_ahead) -> list[PromoAPR]
- calculate_payoff_plan(promo) -> PayoffPlan
- mark_resolved(promo_id, action_taken) -> None

Schemas needed:
- PromoAPR(card_name, promo_rate, regular_rate, balance, end_date, status)
- PayoffPlan(monthly_payment, months_remaining, total_interest_saved)

Integration points:
- Notification service (escalating alerts: 60d, 30d, 14d, 7d, 3d, 1d)
- Card portal adapter (optional: auto-fetch promo details)
"""

# TODO: Implement BaseWorkflow subclass
# TODO: Implement escalating notification schedule
# TODO: Implement payoff calculator
# TODO: Add schemas and tests
