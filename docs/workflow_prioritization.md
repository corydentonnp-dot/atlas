# Atlas — Workflow Prioritization Matrix

> Scored ranking of all 105 workflows by value, difficulty, and recommended phase.
> Last updated: 2026-03-26

## Scoring Legend

All scores are 1–5 (1 = low, 5 = high).

| Column | Meaning |
|--------|---------|
| user_value | How much friction/value this removes/adds for the user |
| friction_reduction | How much daily annoyance this eliminates |
| forward_movement | How much this keeps life/business moving forward |
| build_difficulty | How hard to implement (5 = very hard) |
| maintenance_burden | Ongoing upkeep cost (5 = constant babysitting) |
| privacy_sensitivity | How sensitive the data is (5 = highly sensitive) |
| external_dependency | How many external APIs/credentials needed (5 = many) |
| automation_potential | How automatable (5 = fully automatable) |
| quick_win_score | Composite: (value + friction + forward + automation) - (difficulty + maintenance + dependency) |

### Trust Levels
- `auto` — system can act without asking
- `draft` — system prepares, user reviews before send
- `approval` — system proposes, user must approve
- `manual_only` — system surfaces info, user acts manually

---

## Phase 1 — Quick Wins & Core Value (Build First)

| # | ID | Name | Cat | Val | Fric | Fwd | Diff | Maint | Priv | Ext | Auto | Trust | QW Score | Notes |
|---|-----|------|-----|-----|------|-----|------|-------|------|-----|------|-------|----------|-------|
| 36 | promo_apr_deadline | Promo APR Deadline Agent | C | 5 | 5 | 4 | 1 | 1 | 3 | 1 | 5 | auto | **16** | Pure date tracking, no API needed, prevents real money loss |
| 43 | amazon_return_window | Amazon Return Window Agent | D | 5 | 5 | 3 | 1 | 1 | 2 | 1 | 5 | auto | **15** | Date tracking, manual entry, prevents lost money |
| 81 | filing_deadline_tracker | Filing Deadline Tracker | H | 5 | 5 | 5 | 1 | 1 | 2 | 1 | 5 | auto | **16** | Critical dates, no API, high consequence of missing |
| 31 | shared_expense_classifier | Shared Expense Classifier | C | 5 | 5 | 3 | 2 | 2 | 3 | 2 | 4 | draft | **11** | Daily friction, pattern-matchable, builds merchant memory |
| 26 | maintenance_intake | Maintenance Intake Agent | B | 5 | 4 | 5 | 2 | 2 | 2 | 2 | 4 | draft | **12** | Telegram trigger, form capture, dispatch prep |
| 1 | overdue_text_resurfacer | Overdue Text Resurfacer | A | 5 | 5 | 4 | 2 | 2 | 4 | 3 | 4 | draft | **11** | Communication debt reducer, needs message access |
| 29 | rent_reminder | Rent Reminder Agent | B | 4 | 4 | 4 | 1 | 1 | 2 | 2 | 5 | auto | **13** | Simple scheduler, Telegram notify |
| 37 | subscription_tracker | Subscription Tracker | C | 4 | 4 | 3 | 2 | 2 | 3 | 2 | 4 | auto | **9** | Manual entry + reminders, prevents waste |
| 61 | np_license_tracker | NP License Tracker | F | 5 | 4 | 5 | 1 | 1 | 2 | 1 | 4 | auto | **15** | Critical dates, career-protecting, no API |
| 12 | promise_tracker | Promise Tracker | A | 4 | 4 | 5 | 2 | 2 | 3 | 2 | 4 | draft | **11** | Extract commitments, remind, builds trust |

---

## Phase 1 — Core Platform Workflows (Also Build First)

| # | ID | Name | Cat | Val | Fric | Fwd | Diff | Maint | Priv | Ext | Auto | Trust | QW Score | Notes |
|---|-----|------|-----|-----|------|-----|------|-------|------|-----|------|-------|----------|-------|
| 13 | furnished_finder_lead | Furnished Finder Lead Responder | B | 5 | 5 | 5 | 3 | 3 | 3 | 3 | 4 | draft | **10** | Revenue-generating, needs email/FF access |
| 83 | home_maint_calendar | Home Maintenance Calendar | I | 4 | 4 | 4 | 2 | 1 | 1 | 1 | 5 | auto | **13** | Seasonal reminders, no API |
| 62 | dea_tracker | DEA Tracker | F | 5 | 3 | 5 | 1 | 1 | 2 | 1 | 4 | auto | **14** | Critical credential date |
| 63 | bls_acls_renewal | BLS/ACLS Renewal Agent | F | 4 | 3 | 5 | 1 | 1 | 2 | 1 | 4 | auto | **13** | Credential dates |
| 101 | date_night_planner | Date Night Planner | L | 4 | 4 | 3 | 2 | 2 | 2 | 2 | 4 | draft | **9** | Relationship value, fun, demonstrates system |
| 35 | installment_tracker | Installment Tracker | C | 4 | 4 | 3 | 1 | 1 | 3 | 1 | 5 | auto | **13** | Pure date + amount tracking |
| 8 | message_triage | Message Triage Agent | A | 5 | 5 | 4 | 3 | 3 | 4 | 3 | 3 | draft | **8** | High value but needs NLP + message access |

---

## Phase 2 — High Value, Moderate Effort

| # | ID | Name | Cat | Val | Fric | Fwd | Diff | Maint | Priv | Ext | Auto | Trust | QW Score | Notes |
|---|-----|------|-----|-----|------|-----|------|-------|------|-----|------|-------|----------|-------|
| 2 | unanswered_question | Unanswered Question Detector | A | 4 | 4 | 4 | 3 | 2 | 4 | 3 | 3 | draft | 7 | Needs message parsing |
| 3 | thread_closer | Thread Closer | A | 3 | 4 | 3 | 2 | 2 | 3 | 3 | 4 | draft | 7 | |
| 5 | fiance_follow_through | Fiancée Follow-Through Agent | A | 4 | 4 | 4 | 3 | 2 | 4 | 3 | 3 | draft | 7 | Relationship-sensitive |
| 9 | bump_draft | Bump Draft Agent | A | 4 | 4 | 3 | 2 | 2 | 3 | 3 | 4 | draft | 8 | |
| 10 | scheduling_reply | Scheduling Reply Agent | A | 4 | 4 | 3 | 3 | 2 | 3 | 3 | 4 | draft | 7 | |
| 14 | lead_screener | Lead Screener | B | 4 | 4 | 4 | 3 | 2 | 3 | 3 | 4 | draft | 8 | |
| 15 | lead_score | Lead Score Agent | B | 4 | 3 | 4 | 3 | 2 | 3 | 2 | 4 | draft | 8 | |
| 17 | rental_market_comp | Rental Market Comp Agent | B | 5 | 3 | 5 | 3 | 3 | 2 | 3 | 3 | draft | 7 | Needs listing data source |
| 21 | insurance_proof_tracker | Insurance Proof Tracker | B | 4 | 4 | 4 | 2 | 2 | 3 | 2 | 4 | auto | 10 | |
| 22 | utility_setup_reminder | Utility Setup Reminder | B | 3 | 3 | 4 | 2 | 1 | 2 | 1 | 4 | auto | 10 | |
| 30 | renewal_prompt | Renewal Prompt Agent | B | 4 | 3 | 5 | 2 | 2 | 3 | 2 | 4 | draft | 10 | |
| 32 | merchant_memory | Merchant Memory Agent | C | 4 | 4 | 2 | 2 | 2 | 3 | 2 | 4 | auto | 8 | Builds shared expense accuracy |
| 34 | settlement_prep | Settlement Prep Agent | C | 4 | 5 | 3 | 3 | 2 | 4 | 2 | 3 | draft | 7 | |
| 38 | abnormal_purchase | Abnormal Purchase Detector | C | 4 | 3 | 3 | 3 | 2 | 4 | 3 | 3 | auto | 4 | |
| 41 | shared_spend_summary | Shared Household Spend Summary | C | 4 | 4 | 3 | 2 | 2 | 3 | 2 | 4 | auto | 9 | |
| 46 | warranty_claim_builder | Warranty Claim Builder | D | 4 | 4 | 3 | 3 | 2 | 2 | 2 | 3 | draft | 7 | |
| 50 | receipt_finder | Receipt Finder | D | 4 | 4 | 2 | 3 | 2 | 3 | 3 | 3 | auto | 5 | |
| 64 | ce_opportunity | CE Opportunity Agent | F | 3 | 3 | 4 | 2 | 2 | 2 | 2 | 4 | auto | 8 | |
| 69 | better_job_watcher | Better Job Opportunity Watcher | G | 5 | 2 | 5 | 3 | 3 | 3 | 3 | 3 | draft | 6 | High value, needs job board access |
| 75 | rent_raise_strategy | Rent Raise Pricing Strategy | G | 5 | 3 | 5 | 3 | 2 | 2 | 3 | 3 | draft | 9 | |
| 77 | tax_law_change | Tax Law Change Watcher | H | 4 | 2 | 4 | 3 | 3 | 2 | 3 | 3 | manual_only | 5 | |
| 79 | deduction_opportunity | Deduction Opportunity Agent | H | 5 | 3 | 5 | 3 | 2 | 3 | 2 | 3 | draft | 9 | |
| 87 | price_drop_watcher | Price Drop Watcher | I | 4 | 3 | 3 | 3 | 3 | 2 | 3 | 4 | auto | 6 | |
| 90 | consumables_replenisher | Consumables Replenisher | I | 3 | 4 | 2 | 2 | 2 | 2 | 2 | 4 | draft | 7 | |
| 102 | credit_card_optimizer | Credit Card Spend Optimizer | L | 4 | 3 | 3 | 3 | 3 | 4 | 3 | 3 | draft | 4 | |
| 103 | dual_departure_presence | Dual Departure Presence Auto | L | 4 | 4 | 2 | 3 | 3 | 3 | 4 | 4 | auto | 4 | Needs HA + presence |
| 104 | intent_capture_router | Private Intent Capture Router | L | 5 | 4 | 4 | 3 | 2 | 5 | 1 | 3 | auto | 10 | Local only, high privacy |

---

## Phase 3 — Deferred / Complex / High-Dependency

| # | ID | Name | Cat | Val | Fric | Fwd | Diff | Maint | Priv | Ext | Auto | Trust | QW Score | Notes |
|---|-----|------|-----|-----|------|-----|------|-------|------|-----|------|-------|----------|-------|
| 4 | family_check_in | Family Check-In Agent | A | 3 | 3 | 3 | 2 | 2 | 3 | 3 | 3 | draft | 5 | |
| 6 | tone_softener | Tone Softener | A | 3 | 3 | 2 | 3 | 2 | 3 | 2 | 3 | draft | 4 | Needs NLP |
| 7 | no_reply_needed | No Reply Needed Filter | A | 3 | 4 | 2 | 3 | 2 | 3 | 3 | 4 | auto | 5 | |
| 11 | multi_option_reply | Multi-Option Reply Generator | A | 3 | 3 | 2 | 3 | 2 | 3 | 3 | 3 | draft | 3 | |
| 16 | showing_coordinator | Showing Coordinator | B | 4 | 4 | 4 | 3 | 3 | 3 | 3 | 3 | draft | 6 | |
| 18 | listing_refresh | Listing Refresh Agent | B | 3 | 3 | 3 | 3 | 4 | 2 | 4 | 3 | draft | 1 | Fragile browser automation |
| 19 | lease_packet_builder | Lease Packet Builder | B | 4 | 3 | 4 | 3 | 2 | 4 | 2 | 3 | draft | 7 | |
| 20 | lease_data_chase | Lease Data Chase Agent | B | 3 | 3 | 4 | 3 | 2 | 3 | 3 | 3 | draft | 5 | |
| 23 | move_in_sequence | Move-In Sequence Agent | B | 4 | 4 | 4 | 3 | 2 | 3 | 2 | 3 | draft | 8 | |
| 24 | move_out_sequence | Move-Out Sequence Agent | B | 4 | 4 | 4 | 3 | 2 | 3 | 2 | 3 | draft | 8 | |
| 25 | deposit_accounting | Deposit Accounting Prep | B | 4 | 3 | 4 | 3 | 2 | 4 | 1 | 3 | approval | 8 | Financial |
| 27 | contractor_dispatch | Contractor Dispatch Agent | B | 4 | 4 | 4 | 3 | 3 | 3 | 3 | 3 | approval | 6 | Outbound action |
| 28 | maintenance_status | Maintenance Status Tracker | B | 3 | 3 | 3 | 2 | 2 | 2 | 2 | 4 | auto | 7 | |
| 33 | amazon_split | Amazon Split Agent | C | 3 | 4 | 2 | 3 | 3 | 3 | 3 | 3 | draft | 3 | Needs order data |
| 39 | refund_chase | Refund Chase Agent | C | 4 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | approval | 4 | Outbound action |
| 40 | duplicate_charge | Duplicate Charge Detector | C | 4 | 3 | 3 | 3 | 2 | 4 | 3 | 3 | auto | 5 | |
| 42 | budget_drift | Budget Drift Agent | C | 4 | 3 | 3 | 3 | 2 | 3 | 2 | 3 | auto | 6 | |
| 44 | return_pickup_scheduler | Return Pickup Scheduler | D | 3 | 3 | 2 | 3 | 3 | 2 | 3 | 3 | draft | 2 | |
| 45 | warranty_eligibility | Warranty Eligibility Agent | D | 3 | 3 | 2 | 2 | 2 | 2 | 2 | 4 | auto | 6 | |
| 47 | warranty_status | Warranty Status Agent | D | 3 | 2 | 2 | 2 | 2 | 2 | 2 | 3 | auto | 4 | |
| 48 | recall_checker | Recall Checker | D | 4 | 2 | 3 | 3 | 3 | 2 | 3 | 3 | auto | 4 | |
| 49 | protection_plan_use | Protection Plan Use Agent | D | 3 | 3 | 2 | 2 | 2 | 2 | 2 | 3 | auto | 5 | |
| 51-57 | schedulers | All Scheduler Agents | E | 3 | 3 | 3 | 4 | 4 | 4 | 4 | 2 | approval | -1 | Portal scraping, fragile |
| 58 | reschedule_negotiator | Reschedule Negotiator | E | 3 | 3 | 2 | 4 | 3 | 3 | 4 | 2 | approval | -2 | |
| 59 | pre_visit_instruction | Pre-Visit Instruction Agent | E | 3 | 3 | 3 | 2 | 2 | 3 | 2 | 3 | auto | 6 | |
| 60 | waiting_room_packet | Waiting Room Packet Agent | E | 3 | 3 | 2 | 3 | 2 | 4 | 2 | 3 | auto | 4 | |
| 65 | credentialing_packet | Credentialing Packet Agent | F | 4 | 3 | 4 | 3 | 2 | 3 | 2 | 3 | draft | 7 | |
| 66 | employment_doc_tracker | Employment Document Tracker | F | 3 | 2 | 3 | 2 | 2 | 3 | 1 | 3 | auto | 6 | |
| 67 | malpractice_review | Malpractice Coverage Review | F | 3 | 2 | 3 | 2 | 1 | 3 | 1 | 3 | auto | 7 | |
| 68 | state_req_change | State/Federal Requirement Change | F | 3 | 2 | 4 | 3 | 3 | 2 | 3 | 3 | manual_only | 4 | |
| 70 | recruiter_reply | Recruiter Reply Agent | G | 3 | 3 | 3 | 3 | 2 | 3 | 3 | 3 | draft | 4 | Outbound |
| 71 | compensation_comparator | Compensation Comparator | G | 4 | 2 | 4 | 3 | 2 | 3 | 3 | 3 | manual_only | 5 | |
| 72 | contract_review_prep | Contract Review Prep | G | 4 | 2 | 4 | 3 | 2 | 4 | 1 | 3 | draft | 7 | |
| 73 | tax_comp_idea | Tax-Advantaged Comp Ideas | G | 4 | 2 | 4 | 3 | 2 | 3 | 2 | 3 | manual_only | 6 | |
| 74 | moonlighting | Moonlighting Opportunity Watcher | G | 4 | 2 | 4 | 3 | 3 | 3 | 3 | 3 | draft | 4 | |
| 76 | small_biz_strategy | Small Business Strategy Watcher | G | 3 | 2 | 4 | 3 | 3 | 2 | 3 | 3 | manual_only | 4 | |
| 78 | legislative_impact | Legislative Impact Interpreter | H | 3 | 2 | 4 | 4 | 3 | 2 | 3 | 2 | manual_only | 2 | Needs NLP |
| 80 | property_law_change | Property Law Change Watcher | H | 4 | 2 | 5 | 3 | 3 | 2 | 3 | 3 | manual_only | 6 | |
| 82 | evidence_pack_builder | Evidence Pack Builder | H | 4 | 3 | 4 | 3 | 2 | 4 | 2 | 3 | draft | 7 | |
| 84 | water_drainage | Water Drainage Concern Tracker | I | 3 | 2 | 3 | 2 | 2 | 1 | 1 | 3 | auto | 6 | |
| 85 | remodel_phase | Remodel Phase Manager | I | 4 | 3 | 4 | 3 | 3 | 2 | 2 | 3 | draft | 6 | |
| 86 | materials_batch | Materials Batch Planner | I | 3 | 3 | 3 | 3 | 2 | 1 | 2 | 3 | draft | 5 | |
| 88 | appliance_manual_lib | Appliance/Fixture Manual Librarian | I | 3 | 3 | 2 | 2 | 1 | 1 | 1 | 4 | auto | 8 | |
| 89 | smart_home_routine | Smart Home Routine Agent | I | 3 | 3 | 2 | 3 | 3 | 2 | 4 | 4 | auto | 3 | Needs HA |
| 91 | seekerpro_listener | SeekerPro Listener | J | 4 | 3 | 3 | 3 | 4 | 2 | 4 | 3 | auto | 2 | Fragile |
| 92 | clearance_value | Clearance Value Filter | J | 3 | 2 | 3 | 3 | 3 | 1 | 3 | 3 | auto | 2 | |
| 93 | fb_marketplace | Facebook Marketplace Watcher | J | 4 | 3 | 3 | 3 | 4 | 2 | 4 | 3 | auto | 2 | FB scraping fragile |
| 94 | resale_margin | Resale Margin Estimator | J | 4 | 3 | 3 | 3 | 2 | 1 | 3 | 3 | auto | 5 | |
| 95 | pickup_decision | Pickup Decision Agent | J | 3 | 3 | 2 | 2 | 2 | 1 | 2 | 3 | draft | 5 | |
| 96 | flip_listing_builder | Flip Listing Builder | J | 3 | 3 | 3 | 3 | 2 | 1 | 2 | 3 | draft | 5 | |
| 97 | competitive_resale | Competitive Resale Scanner | J | 3 | 2 | 3 | 3 | 3 | 1 | 3 | 3 | auto | 2 | |
| 98 | inventory_hold_time | Inventory Hold Time Tracker | J | 3 | 2 | 2 | 2 | 1 | 1 | 1 | 4 | auto | 7 | |
| 99 | tesla_readiness | Tesla Readiness Agent | K | 3 | 2 | 2 | 3 | 3 | 2 | 4 | 3 | auto | -1 | Tesla API |
| 100 | award_trip | Award Trip Opportunity Agent | K | 4 | 2 | 3 | 4 | 3 | 3 | 4 | 3 | draft | 1 | Complex |
| 105 | market_thesis | Market Moving Thesis Agent | L | 4 | 2 | 4 | 4 | 3 | 4 | 3 | 2 | manual_only | 2 | High risk |

---

## Top 10 Quick Wins (Build First)

Ranked by quick_win_score, then by lowest build_difficulty:

1. **promo_apr_deadline_agent** (QW: 16) — Pure date tracking, prevents real $ loss
2. **filing_deadline_tracker** (QW: 16) — Critical dates, zero API dependency
3. **np_license_tracker** (QW: 15) — Career-critical dates, zero API
4. **amazon_return_window_agent** (QW: 15) — Prevents lost money, manual entry OK
5. **dea_tracker** (QW: 14) — Credential date, minimal effort
6. **rent_reminder_agent** (QW: 13) — Simple scheduled notifications
7. **home_maintenance_calendar** (QW: 13) — Seasonal reminders
8. **bls_acls_renewal_agent** (QW: 13) — Credential dates
9. **installment_tracker** (QW: 13) — Payment date tracking
10. **maintenance_intake_agent** (QW: 12) — Telegram-triggered, property income protection

---

## Phase Allocation Summary

| Phase | Count | Theme |
|-------|-------|-------|
| Phase 1 | 17 | Quick wins + core value workflows |
| Phase 2 | 27 | High value, moderate effort |
| Phase 3 | 61 | Complex, high-dependency, or niche |

---

## Structured Data

See `docs/workflow_prioritization.yaml` for machine-readable version.
