"""Workflow #1: Overdue Text Resurfacer — Phase 1 Priority.

Surfaces stale unanswered messages that need follow-up.
Scans message history for threads where the other party is waiting
for a reply, or where you said you'd do something and haven't.

Recommended phase: 1 (quick_win_score: 11)
Trust level: draft
Required credentials: Gmail or message source access
Category: communication

TODO: Implement after scaffolding is approved.

Workflow states:
- idle -> scanning -> found_overdue -> draft_prepared -> sent | dismissed

Service interface:
- scan_messages(lookback_days) -> list[OverdueThread]
- prioritize(threads) -> list[OverdueThread]
- draft_reply(thread) -> DraftReply
- send_or_queue(draft, approval) -> None

Integration points:
- Gmail adapter (or other message source)
- Notification service (Telegram alert for found items)
- Approval queue (draft replies need user review)
- Memory service (learn which contacts matter most)

Schemas needed:
- OverdueThread(contact, last_message, days_overdue, urgency)
- DraftReply(thread_id, suggested_text, confidence)
"""

# TODO: Implement BaseWorkflow subclass
# TODO: Implement OverdueTextResurfacerService
# TODO: Implement state machine transitions
# TODO: Add Pydantic schemas for OverdueThread, DraftReply
# TODO: Add tests
# TODO: Wire up Gmail adapter
# TODO: Add notification hooks
