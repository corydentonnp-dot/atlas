# Atlas — Phase 1 Bootstrap Guide

## Prerequisites

1. **Python 3.11+** installed
2. **Docker Desktop** running (for Postgres + Redis)
3. **Git** installed

## Quick Start

```bash
# 1. Clone / navigate to the project
cd C:\Users\coryd\atlas

# 2. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Copy environment config
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux

# 5. Edit .env with your actual values
# At minimum, set:
#   TELEGRAM_BOT_TOKEN=<your bot token>
#   DATABASE_URL=postgresql+asyncpg://atlas:atlas_dev@localhost:5432/atlas
#   REDIS_URL=redis://localhost:6379/0

# 6. Start infrastructure
docker compose up -d

# 7. Run database migrations
alembic upgrade head

# 8. Verify
make test
```

## What to Build First

Phase 1 implementation order (each builds on the previous):

1. **`atlas/core/config.py`** — Load settings from `.env` via Pydantic Settings
2. **`atlas/core/logging.py`** — Configure structlog with JSON output
3. **`atlas/core/database.py`** — Async SQLAlchemy engine + session factory
4. **`atlas/models/`** — Base model + initial schema (workflows, audit_logs, approvals)
5. **`atlas/core/events/bus.py`** — In-process async event bus
6. **`atlas/core/state/machine.py`** — Generic state machine for workflow lifecycle
7. **`atlas/core/workflow/base.py`** — Abstract base workflow class
8. **`atlas/core/workflow/registry.py`** — Auto-discovery and registration
9. **`atlas/core/tasks/worker.py`** — arq worker configuration
10. **`atlas/api/`** — FastAPI app with `/health` endpoint
11. **`atlas/integrations/telegram/adapter.py`** — Basic Telegram bot (start, help)

## Validation Checklist

After Phase 1 implementation, verify:

- [ ] `docker compose up -d` → Postgres and Redis healthy
- [ ] `alembic upgrade head` → Tables created
- [ ] `make test` → Smoke tests pass
- [ ] `make dev` → FastAPI starts, `/health` returns 200
- [ ] `make worker` → arq worker connects to Redis
- [ ] Telegram bot responds to `/start` and `/help`

## Common Issues

| Issue | Solution |
|-------|----------|
| Port 5432 in use | Stop other Postgres instances or change port in docker-compose.yml |
| Redis connection refused | Ensure Docker Desktop is running: `docker compose ps` |
| Alembic can't connect | Check DATABASE_URL in .env matches docker-compose.yml credentials |
| Telegram bot not responding | Verify TELEGRAM_BOT_TOKEN is set correctly in .env |
