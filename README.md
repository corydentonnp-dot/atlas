# Atlas — Personal AI Operations Platform

> A local-first, privacy-conscious workflow orchestration engine for managing
> communications, property operations, finances, scheduling, and life admin.

**Status**: Hardened foundation with 5 working workflows. See [docs/hardening_pass.md](docs/hardening_pass.md) for what's real vs. stubbed.

**Not yet**: Persistent state, real integrations (Telegram/Gmail/HA/Tesla need credentials), UI, 100 workflows still stubbed.

## What Works Now

- ✅ **5 executable workflows** (promo APR deadlines, tax filing deadlines, maintenance intake, shared expenses, rent reminders)
- ✅ **Event → Action** pipeline (trigger, analyze, plan, execute/gate, audit)
- ✅ **Policy engine** (trust levels, approval gating, confidence escalation)
- ✅ **Approval queue** (human review before risky actions)
- ✅ **Audit log** (all actions recorded)
- ✅ **32 passing tests** (core primitives + API routes)
- ✅ **Health/readiness endpoints** (dependency checks)
- ✅ **Async architecture** (FastAPI, asyncpg, pytest-asyncio)

## Quick Start (In-Memory Mode)

```bash
# 1. Clone and enter the project
cd atlas

# 2. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Run tests to verify setup
pytest -v

# 5. Start the API server
uvicorn atlas.api.main:app --reload --host 0.0.0.0 --port 8000

# 6. Test an endpoint
curl http://localhost:8000/health

# 7. List workflows
curl http://localhost:8000/workflows

# 8. Trigger a workflow
curl -X POST http://localhost:8000/workflows/promo_apr_deadline/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "promo_added",
    "promo_id": "DEMO-001",
    "card_name": "Chase Sapphire",
    "promo_rate": 0,
    "regular_rate": 21,
    "balance": 5000,
    "end_date": "2026-04-26"
  }'
```

**Note**: All data is in-memory; restarts clear state. Next phase will add persistence.

## Architecture

See [docs/architecture.md](docs/architecture.md) for full system design.  
See [docs/minimum_useful_platform.md](docs/minimum_useful_platform.md) for current capabilities.

**Core Components (All Implemented):**
- **Event Bus** — type-safe async publish/subscribe
- **State Machine** — explicit transitions with callbacks and history
- **Workflow Registry** — discover, register, and trigger workflows
- **Policy Engine** — trust levels, approval gating, confidence escalation
- **Approval Service** — in-memory queue with TTL expiry
- **Audit Service** — record all actions with context
- **Notification Service** — multi-channel with quiet hours and digest batching
- **Workflow Base** — abstract `trigger/process/act/close` lifecycle

**Components (Planned for Next Tranche):**
- Database persistence (models created, not yet wired)
- Worker queue (arq bootstrap pending)
- Real integrations (stub-only until credentials available)
- Memory/KV backend (stub-only)

**Tech Stack:**
- Python 3.11 + FastAPI + Pydantic
- PostgreSQL + SQLAlchemy + Alembic (infrastructure ready, not yet integrated)
- Redis + arq (infrastructure ready, not yet integrated)
- structlog (structured logging configured)
- pytest + pytest-asyncio (32 passing tests)

## Project Layout

```
atlas/                     # Project root
├── atlas/                 # Python package
│   ├── api/              # FastAPI routes & endpoints
│   ├── core/             # Platform primitives (events, state, approval, etc.)
│   ├── models/           # SQLAlchemy domain models
│   ├── integrations/     # External service adapters
│   └── workflows/        # All workflow modules (105 workflows)
├── tests/                # Pytest test suite
├── migrations/           # Alembic database migrations
├── docs/                 # Documentation
├── scripts/              # Utility scripts
└── docker-compose.yml    # Local dev infrastructure
```

## Workflow Categories

| Category | Count | Examples |
|----------|-------|---------|
| Communication & Follow-Through | 12 | overdue_text_resurfacer, promise_tracker |
| Property & Leasing | 18 | maintenance_intake, rent_reminder |
| Budget & Spending | 12 | shared_expense_classifier, promo_apr_deadline |
| Returns & Warranties | 8 | amazon_return_window, warranty_claim_builder |
| Scheduling & Appointments | 10 | dentist_scheduler, car_service_scheduler |
| Licensure & Credentialing | 8 | np_license_tracker, dea_tracker |
| Career & Income | 8 | better_job_watcher, rent_raise_strategy |
| Tax & Legal | 6 | filing_deadline_tracker, deduction_opportunity |
| Home & Environment | 8 | home_maintenance_calendar, price_drop_watcher |
| Shopping & Resale | 8 | seekerpro_listener, resale_margin_estimator |
| Travel & Mobility | 2 | tesla_readiness, award_trip_opportunity |
| Additional High-Value | 5 | date_night_planner, intent_capture_router |

## Documentation

- [Architecture](docs/architecture.md)
- [Running Plan](docs/running_plan.md)
- [Workflow Prioritization](docs/workflow_prioritization.md)
- [Development Plan](docs/development_plan.md)
- [Privacy Model](docs/privacy_model.md)
- [Approval Model](docs/approval_model.md)
- [Integration Notes](docs/integration_notes.md)
- [Open Questions](docs/open_questions.md)

## Development

```bash
# Run tests
pytest

# Lint and format
ruff check atlas/ tests/
black atlas/ tests/

# Type checking
mypy atlas/

# All checks
make check
```

## Status

**Current Phase:** Phase 1.5 — Foundation hardening and first workflow vertical slices.

Implemented now:
- Core event/state/workflow/policy/approval/audit/notification primitives
- FastAPI health/readiness + workflow/approval/audit routes
- Five runnable workflows: promo APR deadline, filing deadline tracker, maintenance intake, shared expense classifier, rent reminder
- Core test suite expanded (22 passing tests)

## License

Private — single-user personal system.
