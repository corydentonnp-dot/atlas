# Atlas — Personal AI Operations Platform

> A local-first, privacy-conscious workflow orchestration engine for managing
> communications, property operations, finances, scheduling, and life admin.

**This is not a chatbot.** It is a system of watchers, interpreters, planners, actors,
closers, and approval gates — all auditable, stateful, and modular.

## Quick Start

```bash
# 1. Clone and enter the project
cd atlas

# 2. Copy environment config
cp .env.example .env

# 3. Start infrastructure (Postgres + Redis)
docker-compose up -d

# 4. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# 5. Install dependencies
pip install -e ".[dev]"

# 6. Run database migrations
alembic upgrade head

# 7. Start the API server
uvicorn atlas.api.main:app --reload

# 8. Open API docs
# http://localhost:8000/docs
```

## Architecture

See [docs/architecture.md](docs/architecture.md) for full system design.

**Core Components:**
- **Watchers** — observe external sources for signals
- **Interpreters** — parse and classify signals
- **Planners** — decide what actions to take
- **Actors** — execute approved actions
- **Closers** — finalize workflows and clean up
- **Approval Gates** — human-in-the-loop for risky actions
- **Audit Log** — every action is recorded
- **Memory** — preferences, decisions, entity knowledge

**Tech Stack:**
- Python 3.11 + FastAPI + Pydantic
- PostgreSQL + SQLAlchemy + Alembic
- Redis + arq (async task queue)
- Telegram Bot (command/control interface)
- Docker Compose (local development)
- structlog (structured logging)
- Playwright (browser automation stubs)

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

**Current Phase:** Phase 0 — Planning & Scaffolding complete. Awaiting approval to begin implementation.

## License

Private — single-user personal system.
