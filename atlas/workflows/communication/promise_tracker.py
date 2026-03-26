"""Workflow #12: Promise Tracker — Phase 1 Priority.

Extracts commitments/promises made in messages and tracks them
so nothing falls through the cracks.

Recommended phase: 1 (quick_win_score: 11)
Trust level: draft
Category: communication

TODO: Implement after scaffolding is approved.

Workflow states:
- idle -> scanning -> promises_found -> tracking -> due -> resolved | overdue

Service interface:
- extract_promises(messages) -> list[Promise]
- check_overdue() -> list[Promise]
- mark_resolved(promise_id) -> None
- remind(promise) -> None

Schemas needed:
- Promise(source, text, made_to, made_by, due_date, status)
"""

# TODO: Implement BaseWorkflow subclass
# TODO: Implement promise extraction (NLP/pattern matching)
# TODO: Add schemas and tests
