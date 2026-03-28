# Atlas Workflow Prioritization (Re-scored Against Real Repo State)

Last updated: 2026-03-26

## Re-Scoring Method

This re-score adjusts prior value scoring with implementation reality:

updated_priority = prior_quick_win_score + platform_fit_bonus - dependency_penalty - brittleness_penalty

Where:
- platform_fit_bonus: rewards workflows that align with currently implemented primitives.
- dependency_penalty: external account/API dependency cost at current phase.
- brittleness_penalty: browser/NLP fragility risk early.

## Current Architecture Fit Summary

Now implemented and usable:
- event bus
- state machine
- workflow base + registry
- policy engine
- approval queue (in-memory)
- audit service (in-memory)
- notification service with digest
- API health/readiness/workflow endpoints
- three runnable workflows

This favors workflows that are:
- event-driven
- date/deadline-centric
- low external dependency
- high leverage with reminders/approvals

## 5 Best Workflows To Deepen Next

1. promo_apr_deadline
- Why: already implemented, very high money-saving value, low dependency.
- Next depth: escalation schedule tiers, persistence, payoff-plan UX.

2. filing_deadline_tracker
- Why: already implemented, high consequence if missed, no external API required.
- Next depth: recurring deadline templates and extension support.

3. maintenance_intake
- Why: already implemented, high operational value for property management.
- Next depth: contractor queue, dispatch approval payload, status updates.

4. shared_expense_classifier
- Why: strong daily friction reduction and fits memory/policy roadmap.
- Next depth: merchant memory integration and settlement summaries.

5. rent_reminder
- Why: cheap and reliable with existing notification and scheduling patterns.
- Next depth: recurring schedules, escalation, digest-aware reminders.

## 10 Workflows That Should Remain Stubs For Now

1. listing_refresh_agent
2. showing_coordinator
3. message_triage_agent
4. tone_softener
5. multi_option_reply_generator
6. fb_marketplace_watcher
7. tesla_readiness
8. award_trip
9. dual_departure_presence
10. market_thesis

Reason: high fragility, heavy external dependency, or unclear immediate ROI.

## High-Value But Too Brittle Early

- furnished_finder_lead_responder
- message_triage_agent
- recruiter_reply workflows
- listing_refresh and browser-first automation workflows
- advanced NLP-dependent communication assistants

## Cheap Wins

- rent_reminder
- installment_tracker
- np_license_tracker
- dea_tracker
- bls_acls_renewal
- home_maintenance_scheduler

## Workflows Requiring External Accounts Before Meaningful Progress

- communication workflows requiring Gmail access
- any Telegram real-delivery workflow (without token/chat id)
- Home Assistant automation workflows
- Tesla workflows
- marketplace/social scraping workflows with account/session requirements

## Priority Shift Notes

Moved up:
- shared_expense_classifier
- rent_reminder
- installment_tracker

Moved down:
- message_triage_agent
- furnished_finder_lead_responder
- listing_refresh_agent

## Practical Build Rule

No new workflow category expansion until the selected top 5 workflows are:
- persistence-backed
- policy-hooked
- approval/audit integrated
- covered by tests
