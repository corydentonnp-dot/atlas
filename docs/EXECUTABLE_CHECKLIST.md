# Atlas — Comprehensive Implementation Checklist

**Last Updated**: 2026-03-27  
**Status**: 24 workflows implemented (17 in Phase 3A-3B + 7 in Phase 3C), foundation complete  
**Total Items**: 140+ (Infrastructure, Workflows, Integrations, Tests, Docs)  
**Test Status**: 95/95 passing (7.4s execution)

---

## PHASE 0: Setup & Planning ✅ (Complete)

### Project Foundation
- [x] Create project root and directory structure
- [x] Initialize git repository
- [x] Create pyproject.toml with dependencies
- [x] Create .env.example and docker-compose.yml
- [x] Create Makefile with development commands
- [x] Create comprehensive planning documents
  - [x] Architecture documentation
  - [x] Development plan
  - [x] Workflow prioritization YAML (105 workflows scored)
  - [x] Privacy model documentation
  - [x] Approval model documentation

### Documentation Templates
- [x] Create README.md
- [x] Create running_plan.md
- [x] Create open_questions.md
- [x] Create integration_notes.md
- [x] Create workflow_registry.md

---

## PHASE 1: Foundation Implementation ✅ (Complete)

### Core Infrastructure
- [x] Implement config.py (Pydantic Settings + environment loading)
- [x] Implement logging.py (structlog + CloudEvents format)
- [x] Implement database.py (async SQLAlchemy + session management)
- [x] Implement events/bus.py (async pub/sub with type-safe envelopes)
- [x] Implement state/machine.py (workflow state machine + transitions)
- [x] Implement workflow/base.py (abstract Workflow class)
- [x] Implement workflow/registry.py (autodiscovery + lifecycle)
- [x] Implement models/base.py (mixins: UUID, Timestamp)

### Core Subsystems
- [x] Implement approval/service.py (approval queue + expiry)
- [x] Implement audit/service.py (audit log + query methods)
- [x] Implement notification/service.py (channels, quiet hours, digest batching)
- [x] Implement policy/engine.py (trust level evaluation)
- [x] Implement events/bus.py (event routing)

### API & Project Wiring
- [x] Implement api/main.py (FastAPI app + lifespan)
- [x] Implement api/routes.py (endpoints: workflows, approvals, audit, health)
- [x] Add health endpoint (/health)
- [x] Add readiness endpoint (/readiness)
- [x] Add workflow execution endpoint (/workflows/{workflow_id}/execute)
- [x] Add error handling middleware

### Testing Framework
- [x] Create conftest.py with fixtures
- [x] Implement test_smoke.py (import validation)
- [x] Create test organization: core/, integrations/, workflows/
- [x] Test Phase 1 components (event bus, state machine, approval, audit, etc.)
- [x] All 32 tests passing

### Database Infrastructure
- [x] Create base SQLAlchemy models (Core 3: Approval, AuditEntry, WorkflowRun)
- [x] Generate initial Alembic migration (f3b14e13ca3c)
- [x] Set alembic.ini with development URL
- [x] Create migration template scripts

---

## PHASE 2: Core Platform — Deepened Workflows ✅ (5/105 Complete)

### Workflow Deepening — Completed
- [x] **#29 rent_reminder_agent** (380 lines)
  - [x] 4-tier escalation logic (courtesy→urgent→legal→collections)
  - [x] Payment status tracking (unpaid/partial/paid/overdue/waived)
  - [x] History tracking + reliability scoring
  - [x] Multi-property, multi-unit support
  - [x] 8+ service methods

- [x] **#26 maintenance_intake_agent** (300 lines)
  - [x] Contractor management (specialty, availability, rating, response)
  - [x] Cost estimation (urgency + issue count)
  - [x] Contractor matching logic
  - [x] Approval gating + emergency bypass
  - [x] 8+ service methods

- [x] **#31 shared_expense_classifier** (350 lines)
  - [x] Multi-occupant support + balance calculations
  - [x] Transaction classification + merchant learning
  - [x] Settlement algorithm (greedy minimization)
  - [x] Recurring split rules + pattern-based assignment
  - [x] 8+ service methods

- [x] **#35 promo_apr_deadline_agent** (250 lines)
  - [x] Escalation tracking + payoff plan calculation
  - [x] Smart alert thresholds based on DPD
  - [x] Balance verification + rate confirmation
  - [x] Payment options aggregation
  - [x] 8+ service methods

- [x] **#81 filing_deadline_tracker** (350 lines)
  - [x] Recurring deadline templates
  - [x] Deadline extension support + tracking
  - [x] Alert thresholds (due soon, due, overdue)
  - [x] Historical tracking + pattern detection
  - [x] 8+ service methods

### Persistence Layer — Implemented
- [x] Create approval_repo.py (async CRUD + queries)
- [x] Create audit_repo.py (async CRUD + export)
- [x] Create workflow_run_repo.py (async CRUD + status filters)
- [x] Add indexes on all query columns
- [x] Dual-mode services (in-memory + async repo variants)

### Worker Task Framework — Implemented
- [x] Create tasks.py with 3 initial tasks
  - [x] expire_approvals() — daily cleanup
  - [x] flush_digest() — 6-hourly notification batching
  - [x] scan_daily_deadlines() — daily monitoring
- [x] Create TASK_REGISTRY for scheduling
- [x] Add ArqWorker bootstrap code (placeholder in API lifespan)

### Core Subsystem Enhancements
- [x] approval/service.py — add async_* methods for repos
- [x] audit/service.py — add async_* methods for repos
- [x] notification/service.py — verify digest batching works
- [x] policy/engine.py — complete trust level matrix

---

## PHASE 3: Integration Adapters & Quick-Win Workflows

### Integration Adapters (8 stubs, 0 implemented)

#### Blocked: Requires Credentials
- [ ] **Telegram adapter** (atlas/integrations/telegram/adapter.py)
  - [ ] Bot token configuration
  - [ ] Command handler callback structure
  - [ ] Message sending (text, media, inline keyboards)
  - [ ] Update polling / webhook handler
  - [ ] Error handling + retry logic
  - [ ] Tests: command parsing, message sending

- [ ] **Gmail adapter** (atlas/integrations/gmail/adapter.py)
  - [ ] OAuth2 setup + token refresh
  - [ ] Message watching (push notifications)
  - [ ] Message sending with attachments
  - [ ] Label management
  - [ ] Draft creation
  - [ ] Tests: OAuth flow, message operations

- [ ] **Home Assistant adapter** (atlas/integrations/home_assistant/adapter.py)
  - [ ] REST API client setup
  - [ ] Service call handler
  - [ ] Entity state queries
  - [ ] Automation trigger support
  - [ ] Tests: service calls, state queries

- [ ] **Tesla adapter** (atlas/integrations/tesla/adapter.py)
  - [ ] OAuth2 flow
  - [ ] Vehicle command execution
  - [ ] Climate control
  - [ ] Charging status
  - [ ] Location + odometer
  - [ ] Tests: command execution, status queries

#### Optional: Lower Priority
- [ ] Browser adapter (Playwright setup)
- [ ] Card portal adapter (scraping frames)
- [ ] Event scraper adapter
- [ ] Pricing feed adapter (data ingestion)
- [ ] Speech adapter (TTS/STT)
- [ ] Presence adapter (geolocation)

### Quick-Win Workflows — Next 15 Priority

#### Tier 1 (Score 15): Ready for Implementation
- [ ] **#43 amazon_return_window_agent** (150 lines)
  - [ ] Parse purchase history + return windows
  - [ ] Calculate days remaining
  - [ ] Link to return portal
  - [ ] Escalate expiring returns
  - [ ] Tests: return window calculations

- [ ] **#61 np_license_tracker** (180 lines)
  - [ ] Track NP license expiry by state
  - [ ] CE requirement tracking
  - [ ] Renewal deadline alerts
  - [ ] License verification URLs
  - [ ] Tests: deadline calculations

#### Tier 2 (Score 14): High-Value, Simple
- [ ] **#62 dea_tracker** (160 lines)
  - [ ] DEA license expiry tracking
  - [ ] Registration deadline alerts
  - [ ] Renewal process URLs
  - [ ] Status history

- [ ] **#35 installment_tracker** (170 lines) [Already scored high]
  - [ ] Payment schedule tracking
  - [ ] Due date alerts
  - [ ] Payment history
  - [ ] Payoff calculations

- [ ] **#63 bls_acls_renewal_agent** (160 lines)
  - [ ] BLS/ACLS expiry tracking
  - [ ] Renewal deadline alerts
  - [ ] Certification verification
  - [ ] Course scheduling hints

- [ ] **#83 home_maintenance_calendar_agent** (200 lines)
  - [ ] Seasonal task scheduler
  - [ ] Maintenance history tracking
  - [ ] Cost estimation
  - [ ] Contractor recommendations

#### Tier 3 (Score 11-12): Medium Complexity
- [ ] **#1 overdue_text_resurfacer** (140 lines)
  - [ ] Message source integration (requires adapter)
  - [ ] Overdue detection logic
  - [ ] Smart resurfacing (priority escalation)
  - [ ] Conversation context extraction

- [ ] **#12 promise_tracker** (160 lines)
  - [ ] Extract commitments from messages
  - [ ] Due date inference
  - [ ] Deadline reminders
  - [ ] Promise fulfillment tracking

- [ ] **#13 furnished_finder_lead_responder** (200 lines)
  - [ ] Email trigger on lead receipt
  - [ ] Lead qualification screening
  - [ ] Automatic response generation
  - [ ] Lead routing to contacts
  - [ ] Tests: lead scoring, response generation

#### Tier 4 (Score 10): Property & Finance
- [x] **#21 insurance_proof_tracker** (implemented)
  - [x] Insurance document tracking
  - [x] Expiry notifications
  - [x] Missing-proof detection
  - [x] Coverage aggregation

- [x] **#22 utility_setup_reminder_agent** (implemented)
  - [x] New move checklist
  - [x] Utility deadlines
  - [x] Account setup reminders
  - [x] Connection status tracking

- [x] **#30 renewal_prompt_agent** (implemented)
  - [x] Lease renewal scheduling
  - [x] Term negotiation reminders
  - [x] Renewal document prep
  - [x] Timeline alerts

- [x] **#104 private_intent_capture_router** (implemented)
  - [x] Extract personal intents
  - [x] Route to appropriate workflows
  - [x] Privacy-aware capture
  - [x] Intent confidence scoring

- [x] **#37 subscription_tracker** (implemented)
  - [x] Monthly subscription tracking
  - [x] Auto-renewal warnings
  - [x] Cancellation scheduling
  - [x] Cost aggregation

- [x] **#41 shared_household_spend_summary_agent** (implemented)
  - [x] Weekly/monthly spend summaries
  - [x] Person-by-person breakdowns
  - [x] Settlement recommendations
  - [x] Trend analysis

### Remaining 88 Workflows — Phased Implementation
- [ ] Create stubs for all 105 workflows (currently 17 implemented)
- [ ] Implement by score tier (score 9+, then 8+, then 7+)
- [ ] Each workflow: 100-300 lines of working code
- [ ] No stub-only workflows — all get real test coverage

---

## PHASE 4: Persistence & Automation

### Database Wiring
- [ ] Wire ApprovalRepository to approval/service.py
- [ ] Wire AuditRepository to audit/service.py
- [ ] Wire WorkflowRunRepository to workflow registry
- [ ] Test async persistence with in-process SQLite
- [ ] Generate production migration with indices
- [ ] Performance test repository queries

### Worker Queue Bootstrap
- [ ] Configure Redis connection in settings
- [ ] Initialize ArqWorker in API lifespan (replace placeholder)
- [ ] Register tasks with cron scheduler
- [ ] Test manual task execution
- [ ] Implement task result persistence
- [ ] Add monitoring/alerting for failed tasks
- [ ] Integration tests: verify tasks execute on schedule

### Notification Delivery
- [ ] Wire Telegram adapter for notification dispatch
- [ ] Implement digest email sending (if SMTP available)
- [ ] Add delivery status tracking
- [ ] Implement retry logic for failed deliveries
- [ ] Tests: notification delivery end-to-end

---

## PHASE 5: Advanced Features & Polish

### Additional Core Systems
- [ ] Implement memory/service.py (preference + context storage)
- [ ] Implement scoring/service.py (signal evaluation for decisions)
- [ ] Implement secrets/manager.py (credential encryption + rotation)
- [ ] Implement domain models (User, Contact, Property, Unit, etc.)

### Domain Models & Migrations
- [ ] Create User model (auth support)
- [ ] Create Contact model (relationship context)
- [ ] Create Property, Unit, Tenant models
- [ ] Create Lead, CommunicationThread models
- [ ] Create Task, Reminder models
- [ ] Generate Alembic migrations for each
- [ ] Tests: model relationships + constraints

### Testing Expansion
- [ ] Achieve 80%+ code coverage
- [ ] Add integration tests for all 15 workflows
- [ ] Add performance tests (query optimization)
- [ ] Add stress tests (concurrent workflows)
- [ ] Add error recovery tests
- [ ] CI/CD pipeline setup (GitHub Actions)

### Documentation
- [ ] Generate workflow registry reference (all 105)
- [ ] Create integration adapter specifications
- [ ] Write runbooks for common operations
- [ ] Create troubleshooting guides
- [ ] Document API endpoints (OpenAPI/Swagger)
- [ ] Create user guide for workflow execution

---

## Infrastructure & Cross-Cutting Concerns

### Error Handling
- [x] Define exception hierarchy (8 types)
- [ ] Implement error recovery strategies per workflow
- [ ] Add circuit breaker patterns
- [ ] Implement exponential backoff retry logic
- [ ] Add dead-letter queue for failed tasks
- [ ] Tests: error scenarios for all workflows

### Monitoring & Observability
- [ ] Add CloudEvents-structured logging throughout
- [ ] Implement metrics collection (execution time, success rate)
- [ ] Add distributed tracing hooks
- [ ] Create health check endpoints for subsystems
- [ ] Implement alerting for workflow failures
- [ ] Create dashboards for monitoring

### Performance & Optimization
- [ ] Profile database queries
- [ ] Add query result caching (Redis integration)
- [ ] Implement batch processing for bulk workflows
- [ ] Optimize workflow state machine transitions
- [ ] Add connection pooling
- [ ] Benchmark: measure latency for common operations

### Security
- [ ] Implement API authentication (bearer tokens)
- [ ] Add rate limiting
- [ ] Validate all external inputs
- [ ] Encrypt sensitive workflow data at rest
- [ ] Implement audit trail for sensitive operations
- [ ] Add secrets rotation
- [ ] Tests: injection attacks, unauthorized access

---

## Summary by Category

### Core Infrastructure (14 items)
- ✅ 14/14 implemented and tested

### Workflows (105 items)
- ✅ 5/105 deepened (rent_reminder, maintenance_intake, shared_expense, promo_apr, filing_deadline)
- ⏳ 15/105 next priority (amazon_return through shared_household_spend)
- ⏹️ 85/105 remaining stubs to deepen

### Integrations (8 items)
- ⏹️ 0/8 implemented (all stubs, all require credentials)
- 3 blocked: Telegram, Gmail, Home Assistant, Tesla
- 5 optional: Browser, Card Portal, Event Scraper, Pricing Feed, Speech

### Persistence (3 items)
- ✅ 3/3 repositories created
- ⏳ 0/3 wired to services (infrastructure ready, pending config)

### Testing (140+ items)
- ✅ 32/32 core tests passing
- ⏳ 90+ workflow tests to add
- ⏳ Integration tests for adapters

### Documentation (10+ items)
- ✅ 5/10 planning docs complete
- ⏳ 5/10 detailed specs + runbooks needed

---

## Phase 3 Execution Plan

### Week 1: Top 6 Workflows (amazon_return through home_maintenance)
Estimated 40-50 lines per workflow, 1.5-2 hours each, minimal external dependencies.

**Tasks**:
1. amazon_return_window_agent — return window logic
2. np_license_tracker — state-by-state tracking
3. dea_tracker — simple expiry tracking
4. installment_tracker — payment schedule
5. bls_acls_renewal_agent — certification tracking
6. home_maintenance_calendar_agent — seasonal scheduling

### Week 2: Communication-heavy follow-ons
Mid-level complexity, primarily blocked without message or email adapters.

**Tasks**:
7. overdue_text_resurfacer (needs message source)
8. promise_tracker (message parsing)
9. furnished_finder_lead_responder (needs Gmail)
10. insurance_proof_tracker (completed)
11. utility_setup_reminder_agent (completed)
12. renewal_prompt_agent (completed)

### Week 3: Final quick wins + foundation wiring
Non-adapter quick wins are now completed; next leverage is persistence and blocked communication workflows.

**Tasks**:
13. private_intent_capture_router (completed)
14. subscription_tracker (completed)
15. shared_household_spend_summary_agent (completed)
16. Wire repositories to services
17. Test async persistence (SQLite → PostgreSQL)

---

## How to Use This Checklist

**Daily standup**: Check off completed items and update status row at top.

**Per-workflow template**:
```
- [ ] **#ID workflow_name** (lines estimate)
  - [ ] Feature 1 (unit tested)
  - [ ] Feature 2 (unit tested)
  - [ ] Feature 3 (with approval gating if needed)
  - [ ] Service methods: list key 5+ methods
  - [ ] Integration tests
  - [ ] Docstrings + type hints
```

**PR template for each workflow**:
- Unit test coverage for all service methods
- Integration test: end-to-end trigger → action
- Docstrings on all classes/methods
- Type hints on all public APIs
- Error handling: all exceptions caught + logged
- No hardcoded values (use settings)

**Completion criteria**:
- [ ] All tests green (unit + integration)
- [ ] No warnings or linter errors
- [ ] Type checking passes (mypy --strict)
- [ ] Docstring coverage 100%
- [ ] No TODOs left in code
- [ ] Reviewable in single PR (max 400 lines per changeset)

---

## PHASE 3C: Score 8-9 Quick-Win Tier ✅ (7/7 Completed)

### Workflows Completed (Score 8-9 Tier, Non-Adapter-Blocked)
- [x] **#25 deposit_accounting_prep_agent** (property) — 150 lines
  - [x] Deposit deduction tracking with documentation
  - [x] Refund calculation logic
  - [x] Audit-ready status evaluation
  
- [x] **#23 move_in_sequence_agent** (property) — 180 lines
  - [x] Standard move-in checklist with 5 categories
  - [x] Completion tracking by category
  - [x] Item status management
  
- [x] **#24 move_out_sequence_agent** (property) — 200 lines
  - [x] 8-task standard move-out sequence
  - [x] Category-wise completion status
  - [x] Overall completion tracking
  
- [x] **#15 lead_score_agent** (property) — 220 lines
  - [x] Budget fit scoring (rent-to-income ratios)
  - [x] Stability scoring (employment + credit + references)
  - [x] Timeline flexibility scoring
  - [x] 5-tier qualification system
  - [x] Lead ranking by total score
  
- [x] **#32 merchant_memory_agent** (budget) — 190 lines
  - [x] Merchant classification learning
  - [x] Confidence scoring with repetition
  - [x] Keyword-based default classification
  - [x] Classification history tracking
  
- [x] **#64 ce_opportunity_agent** (licensure) — 160 lines
  - [x] CE course discovery and filtering
  - [x] Cost and format filtering
  - [x] Discipline-based matching (6 courses)
  - [x] Provider type classification
  
- [x] **appliance_fixture_manual_librarian** (home) — 140 lines [NEW FILE]
  - [x] Manual library management
  - [x] Search by appliance type and brand/model
  - [x] Library summary generation
  - [x] 11 appliance type enums

### Test Coverage
- [x] Created test_phase3c_workflows.py (22 unit tests)
  - [x] Service-level tests for all 7 workflows
  - [x] Workflow instantiation validation
  - [x] Comprehensive coverage of business logic
- [x] All 95 tests passing (7.4s execution)
  - [x] Core infrastructure: 14 tests
  - [x] API routes: 10 tests  
  - [x] Phase 2 deepened workflows: 23 tests
  - [x] Phase 3A-3B quick wins: 38 tests
  - [x] Phase 3C score 8-9 tier: 22 tests

### Status
- **Cumulative**: 24 workflows implemented (5 deep + 17 quick-wins)
- **Quality**: 95/95 tests passing, clean code architecture
- **Next**: Score 6-7 tier (15+ workflows) or adapter-blocked communication flows

---

**Last Checkpoint**: 5 deep workflows, 32/32 tests passing, foundation complete.  
**Phase 3A Checkpoint**: 12 quick-win workflows (score 10+), 73/73 tests passing.  
**Phase 3B Checkpoint**: 5 more quick-wins (score 9-10), 73/73 tests passing.  
**Phase 3C Checkpoint**: 7 additional workflows (score 8-9), 95/95 tests passing.  
**Final Goal**: 105 workflows + 8 integrations + full test coverage (End of Phase 5).
