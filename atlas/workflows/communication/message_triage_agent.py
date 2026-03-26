"""Workflow #8: Message Triage Agent — Phase 1.

Categorizes and prioritizes incoming messages across all channels
to surface what needs attention first.

Recommended phase: 1 (quick_win_score: 8)
Trust level: draft
Required credentials: Gmail or message source access
Category: communication

TODO: Implement after scaffolding is approved.

Workflow states:
- idle -> messages_received -> triaged -> notified

Service interface:
- triage_messages(messages) -> list[TriagedMessage]
- get_priority_queue() -> list[TriagedMessage]
"""

# TODO: Implement BaseWorkflow subclass
# TODO: Add schemas and tests
