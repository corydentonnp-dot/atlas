# Atlas Phase 3B Progress Report

**Date**: March 26, 2026  
**Session**: Phase 3B — Remaining non-adapter quick wins  
**Tests**: 73/73 passing  
**Status**: Remaining top-priority implementation is now concentrated in adapter-blocked communication workflows and persistence wiring.

---

## Completed In This Session

### Property Workflows
- **#21 insurance_proof_tracker**
  - Tracks active renter's insurance proofs
  - Flags expiring and missing coverage
  - Supports proof refresh and total coverage aggregation

- **#22 utility_setup_reminder_agent**
  - Creates default move-in utility checklists
  - Tracks due-soon and overdue connection tasks
  - Records completion and completion-rate progress

- **#30 renewal_prompt_agent**
  - Tracks lease end dates and outreach windows
  - Generates prep checklists for renewal conversations
  - Records tenant response outcomes

### Budget Workflows
- **#37 subscription_tracker**
  - Tracks recurring renewals and auto-renew risk
  - Normalizes subscription costs into monthly burn
  - Supports cancellation scheduling

- **#41 shared_household_spend_summary_agent**
  - Summarizes shared spend by person and category
  - Produces settlement suggestions for a period
  - Fits naturally beside shared_expense_classifier

### Additional Workflow
- **#104 private_intent_capture_router**
  - Captures local-only freeform intents
  - Routes intents to existing workflows using keyword heuristics
  - Marks low-confidence items for review instead of over-routing

---

## Verification

- Added **18 new tests** in [tests/workflows/test_phase3b_workflows.py](tests/workflows/test_phase3b_workflows.py)
- Verified new workflow batch in isolation: **18/18 passing**
- Verified full suite: **73/73 passing** in 9.01s

---

## Current Top-Priority State

Implemented from the original top-15 shortlist:
- amazon_return_window_agent
- np_license_tracker
- dea_tracker
- installment_tracker
- bls_acls_renewal_agent
- home_maintenance_scheduler
- insurance_proof_tracker
- utility_setup_reminder_agent
- renewal_prompt_agent
- private_intent_capture_router
- subscription_tracker
- shared_household_spend_summary_agent

Still blocked by missing adapter capability or credentials:
- overdue_text_resurfacer
- promise_tracker
- furnished_finder_lead_responder

Highest-value next engineering moves:
1. Wire repository-backed persistence into the already implemented workflows.
2. Decide whether to build message-source abstractions before Gmail/Telegram credentials exist.
3. Finish blocked communication workflows once adapter surfaces are ready.