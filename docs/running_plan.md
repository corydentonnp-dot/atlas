# Atlas — Running Plan

> Personal AI Operations Platform
> Last updated: 2026-03-26

## Project Name: Atlas

Atlas is a local-first, privacy-conscious workflow orchestration engine for one user.
It is NOT a chatbot. It is a system of watchers, interpreters, planners, actors, closers,
and approval gates — all auditable, stateful, and modular.

---

## Current Phase: Phase 0 — Planning & Scaffolding

All planning documents, stubs, folder structures, and prioritization matrices are being
created before any implementation code is written. User will approve before coding begins.

---

## Architecture Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python 3.11 | Already installed, user is learning, AI-assistable |
| API Framework | FastAPI | Async, modern, auto-docs, Pydantic-native |
| Database | PostgreSQL | Durable, relational, good for workflows/state |
| Cache / Queue | Redis | Event coordination, task queues, caching |
| ORM | SQLAlchemy 2.0 + Alembic | Standard, well-documented, migration support |
| Config | Pydantic Settings | Type-safe, .env-friendly |
| Task Queue | arq (Redis-based) | Lightweight, async-native, Python-only |
| Browser Automation | Playwright | Modern, reliable, Python bindings |
| Command Interface | Telegram Bot | Low friction, mobile, push notifications |
| Containerization | Docker Compose | Local dev reproducibility |
| Testing | Pytest + pytest-asyncio | Standard, async support |
| Linting | Ruff + Black + MyPy | Fast, comprehensive |
| Logging | structlog | Structured JSON logs, context-rich |
| Project Layout | Single repo, `atlas/` package | Simple, greppable, one virtualenv |

### Why arq over Celery?
- Celery is heavyweight, complex config, overkill for single-user local system
- arq is async-native, Redis-only, minimal config, perfect for this scale
- If we outgrow arq, migration to Celery/Dramatiq is straightforward

---

## Phased Roadmap

### Phase 0 — Planning & Scaffolding (NOW)
- [x] Inspect environment
- [x] Create directory structure
- [ ] Create all planning docs
- [ ] Create workflow prioritization matrix (docs + YAML)
- [ ] Create all stub files and __init__.py files
- [ ] Create .env.example, Docker Compose, pyproject.toml
- [ ] Ask user for permission to begin coding

### Phase 1 — Project Foundation
- README, architecture docs, dev guide
- Docker Compose for Postgres + Redis
- pyproject.toml / dependency management
- Ruff, Black, MyPy, Pytest configs
- Makefile with common commands
- structlog + config infrastructure
- Base error handling patterns
- Health/readiness endpoints

### Phase 2 — Core Platform
- Event bus / workflow trigger layer
- Workflow registry + agent registry
- Approval queue system
- Audit log
- Notification abstraction (Telegram first)
- Memory abstraction
- Secrets/config abstraction
- Task/job execution layer (arq)
- State machine pattern
- Policy / trust level framework
- Source adapters interface
- Actor/action interface
- Watcher/observer interface
- Digest / batching framework
- Scoring framework

### Phase 3 — Domain Models
- All SQLAlchemy models per spec
- Alembic initial migration
- Pydantic schemas for API layer

### Phase 4 — Priority Workflows (Deep Implementation)
- ~10 highest-value workflows with full schemas, services, states, tests
- See workflow_prioritization.md for selection

### Phase 5 — Full Workflow Stub Catalog
- 105 workflows scaffolded with interfaces, schemas, TODOs

### Phase 6 — Integration Adapters
- 14 integration stubs with contracts

### Phase 7 — Approval / Policy System
- Trust levels, per-workflow/per-action policies, quiet hours, digests

### Phase 8 — Memory / Personalization
- Preference storage, decision memory, entity memory, feedback loops

### Phase 9 — Documentation
- Continuously maintained docs suite

---

## Quick Win Strategy

The first "minimum useful platform" should:
1. Run locally (FastAPI + Postgres + Redis in Docker)
2. Expose health/status endpoints
3. Persist state via SQLAlchemy
4. Register workflows in a registry
5. Queue approvals
6. Log all actions to audit table
7. Stub Telegram notifications
8. Run at least 3 workflows in skeleton form

Target quick-win workflows (pending prioritization analysis):
- `promo_apr_deadline_agent` — deadline tracker, pure data, no external API
- `amazon_return_window_agent` — deadline tracker, manual data entry
- `filing_deadline_tracker` — dates + reminders
- `maintenance_intake_agent` — form → dispatch, Telegram trigger
- `shared_expense_classifier` — categorize transactions
- `overdue_text_resurfacer` — scan message history, surface stale threads

---

## Open Issues
See docs/open_questions.md for full list.

---

## File Organization

```
atlas/                     # Project root
├── atlas/                 # Python package
│   ├── api/              # FastAPI routes
│   ├── core/             # Platform primitives
│   │   ├── approval/     # Approval queue system
│   │   ├── audit/        # Audit logging
│   │   ├── events/       # Event bus
│   │   ├── memory/       # Memory abstraction
│   │   ├── notifications/# Notification system
│   │   ├── policy/       # Trust & policy framework
│   │   ├── scoring/      # Opportunity scoring
│   │   ├── secrets/      # Secrets/config abstraction
│   │   ├── state/        # State machine
│   │   ├── tasks/        # Task/job queue
│   │   └── workflow/     # Workflow registry & base
│   ├── models/           # SQLAlchemy models
│   ├── integrations/     # External service adapters
│   │   ├── gmail/
│   │   ├── google_calendar/
│   │   ├── google_drive/
│   │   ├── telegram/
│   │   ├── home_assistant/
│   │   ├── browser/
│   │   ├── card_portal/
│   │   ├── event_scraper/
│   │   ├── marketplace/
│   │   ├── speech/
│   │   ├── presence/
│   │   ├── tesla/
│   │   └── pricing_feed/
│   └── workflows/        # All workflow modules
│       ├── communication/
│       ├── property/
│       ├── budget/
│       ├── returns/
│       ├── scheduling/
│       ├── licensure/
│       ├── career/
│       ├── tax_legal/
│       ├── home/
│       ├── shopping/
│       ├── travel/
│       └── additional/
├── tests/                # Pytest test suite
├── migrations/           # Alembic migrations
├── docs/                 # Documentation
├── scripts/              # Utility scripts
├── docker-compose.yml
├── pyproject.toml
├── Makefile
├── .env.example
└── README.md
```
