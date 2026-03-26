"""Workflow #5: Fiancée Follow-Through Agent — Phase 2.

Tracks shared commitments, tasks, and follow-ups between you and your fiancée.
RELATIONSHIP-SENSITIVE: Extra care with tone and approval level.

Recommended phase: 2 (quick_win_score: 7)
Trust level: draft (never auto for relational)
Category: communication

TODO: Implement after scaffolding is approved.

Workflow states:
- idle -> commitment_detected -> tracking -> reminder_due -> resolved | escalated

Service interface:
- detect_commitments(messages) -> list[SharedCommitment]
- check_overdue() -> list[SharedCommitment]
- draft_gentle_reminder(commitment) -> str
"""

# TODO: Implement BaseWorkflow subclass
# TODO: Add schemas and tests
# TODO: Relationship-sensitive policy hooks
