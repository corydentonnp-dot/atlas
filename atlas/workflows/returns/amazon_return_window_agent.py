"""Workflow #43: Amazon Return Window Agent — Phase 1 Priority.

Tracks Amazon order return windows and alerts before they close.

Recommended phase: 1 (quick_win_score: 15)
Trust level: auto
Category: returns

TODO: Implement after scaffolding is approved.

Workflow states:
- idle -> tracking -> warning_7d -> warning_3d -> window_closed | returned

Service interface:
- add_order(order_id, item, purchase_date, return_deadline) -> TrackedOrder
- check_closing_soon(days_ahead) -> list[TrackedOrder]
- mark_returned(order_id) -> None
- mark_keeping(order_id) -> None
"""

# TODO: Implement BaseWorkflow subclass
# TODO: Add escalating notification schedule
# TODO: Add schemas and tests
