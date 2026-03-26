# Atlas — Development Plan

## Phased Implementation

### Phase 0: Planning & Scaffolding ✅
- Project specification and scoring matrix
- Directory structure and stub files
- Planning documents and open questions

### Phase 1: Foundation (Current Target)
- [ ] Database models (SQLAlchemy) and initial Alembic migration
- [ ] Configuration loading (Pydantic Settings + .env)
- [ ] Structured logging setup (structlog)
- [ ] Event bus (in-process pub/sub)
- [ ] State machine (generic workflow state transitions)
- [ ] Workflow base class and registry
- [ ] arq worker bootstrap
- [ ] FastAPI app skeleton with health endpoint
- [ ] Telegram bot — basic command interface

### Phase 2: Core Subsystems
- [ ] Approval queue (Telegram-based approve/reject)
- [ ] Audit logging service
- [ ] Notification service (Telegram channel + digest batching)
- [ ] Policy engine (trust level evaluation)
- [ ] Memory / preferences service
- [ ] Scoring service (signal evaluation)
- [ ] Secrets manager (encrypted credential access)

### Phase 3: First Integrations
- [ ] Gmail adapter (OAuth2 + watch/send)
- [ ] Google Calendar adapter (read/write events)
- [ ] Google Drive adapter (file operations)
- [ ] Telegram adapter (full bot interface)

### Phase 4: Quick-Win Workflows
Deploy the top-10 highest-scoring workflows:
1. `#17` promo_apr_deadline_agent (QW: 16)
2. `#77` filing_deadline_tracker (QW: 16)
3. `#101` daily_briefing_agent (QW: 15)
4. `#105` system_health_monitor (QW: 15)
5. `#61` np_license_tracker (QW: 15)
6. `#83` home_maintenance_scheduler (QW: 14)
7. `#102` weekly_review_agent (QW: 14)
8. `#91` price_drop_agent (QW: 14)
9. `#62` dea_tracker (QW: 14)
10. `#51` appointment_scheduler (QW: 14)

### Phase 5: Remaining Workflows
- Deploy Phase 1 and Phase 2 workflows by priority score
- Integration adapters as needed per workflow dependencies

### Phase 6: Browser Automation
- [ ] Playwright adapter for card portals
- [ ] Event scraper workflows
- [ ] Marketplace listing automation

### Phase 7: Advanced Integrations
- [ ] Home Assistant adapter
- [ ] Tesla adapter
- [ ] Speech/presence adapters
- [ ] Pricing feed adapter

### Phase 8: Polish & Hardening
- [ ] Comprehensive test coverage (>80%)
- [ ] Error recovery and retry strategies
- [ ] Performance profiling
- [ ] Monitoring and alerting

### Phase 9: Documentation & Handoff
- [ ] Final architecture documentation
- [ ] Workflow registry reference
- [ ] Integration adapter specs
- [ ] Runbooks and troubleshooting guides

## Development Conventions

- **Branch strategy**: `main` (stable) + feature branches
- **Commit style**: Conventional commits (`feat:`, `fix:`, `docs:`, `chore:`)
- **Testing**: Every subsystem gets unit tests; workflows get integration tests
- **Code quality**: Ruff + Black + MyPy enforced via `make check`
