# Next Build Recommendations

Last updated: 2026-03-26

## Immediate Target

Deliver durable core plus five workflow slices, not more scaffolding.

## Build Order

1. Durable Core Data
- Add SQLAlchemy models: approvals, audit_entries, workflow_runs.
- Wire Alembic target metadata and create initial migration.
- Add repository layer for approval/audit/workflow run persistence.

2. Worker Reliability
- Implement arq worker config and tasks:
  - expire_stale_approvals
  - flush_digest
  - daily_deadline_scan
- Add retry/timeouts and idempotency keys.

3. API Hardening
- Add API tests for:
  - GET /health
  - GET /ready
  - GET /workflows
  - POST /workflows/{id}/trigger
  - approval endpoints
- Add standard error response model.

4. Workflow Deepening (highest speed-to-value)
- promo_apr_deadline: escalation schedule + payoff recommendations persisted.
- filing_deadline_tracker: recurring deadlines and extension handling.
- maintenance_intake: contractor assignment queue and approval action payloads.
- shared_expense_classifier: merchant memory-backed classifier.
- rent_reminder: monthly schedule with quiet-hours-aware notification.

5. Documentation Hygiene
- Keep implementation status and roadmap in one canonical source.
- Remove stale claims from docs that imply unimplemented behavior.

## Ten Workflows To Keep Stubbed For Now

- listing_refresh_agent
- showing_coordinator
- message_triage_agent
- tone_softener
- multi_option_reply_generator
- fb_marketplace_watcher
- tesla_readiness
- award_trip
- dual_departure_presence
- market_thesis

## Hard Dependencies For Later

- Gmail/Google OAuth credentials
- Telegram bot token/chat id for real delivery
- Home Assistant URL/token
- Tesla account tokens

## Exit Criteria For Next Tranche

- Core persistence migration created and applied successfully.
- All core services use repositories (no in-memory-only path for production mode).
- At least five workflows pass end-to-end tests with policy + approval + audit hooks.
- Test suite remains green and includes API integration tests.
