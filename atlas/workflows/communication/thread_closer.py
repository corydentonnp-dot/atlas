"""Workflow #3: Thread Closer — Phase 2.

Identifies conversation threads that can be closed with a short message
or that have naturally concluded and need no further action.

Recommended phase: 2 (quick_win_score: 7)
Trust level: draft
Category: communication

TODO: Implement after scaffolding is approved.

Workflow states:
- idle -> scanning -> closable_found -> draft_closer -> sent | skipped

Service interface:
- find_closable_threads(lookback_days) -> list[ClosableThread]
- draft_closer(thread) -> str
"""

# TODO: Implement BaseWorkflow subclass
# TODO: Add schemas and tests
