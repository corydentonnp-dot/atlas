# Atlas — Architecture Overview

## System Architecture

Atlas is a **local-first, single-user workflow orchestration engine** that automates personal
and professional operations through a pipeline of watchers, interpreters, planners, actors,
closers, and approval gates.

### Core Principles

1. **Local-first**: All data stored locally (Postgres + filesystem). No cloud dependency for core ops.
2. **Privacy by design**: Sensitive data never leaves the local machine unless explicitly approved.
3. **Stateful process ownership**: Every workflow owns its state machine and lifecycle.
4. **Graduated trust**: Workflows operate at `auto`, `suggest`, or `approve` trust levels.
5. **Single-user optimized**: No multi-tenancy overhead. arq over Celery. Simple auth model.

### High-Level Data Flow

```
External Signals (Gmail, Calendar, HA, Scrapers)
        │
        ▼
   ┌─────────────┐
   │   Watchers   │  ← Poll / webhook listeners
   └──────┬──────┘
          │ raw events
          ▼
   ┌──────────────┐
   │ Interpreters  │  ← Parse, classify, extract
   └──────┬───────┘
          │ structured signals
          ▼
   ┌──────────────┐
   │   Planners    │  ← Decide actions, check policy
   └──────┬───────┘
          │ action plans
          ▼
   ┌──────────────┐
   │    Actors     │  ← Execute actions (send, file, create)
   └──────┬───────┘
          │ results
          ▼
   ┌──────────────┐
   │   Closers     │  ← Verify, log, advance state
   └──────┬───────┘
          │
          ▼
   Audit Log + Notification Digest
```

### Component Map

| Layer           | Technology         | Purpose                                    |
|-----------------|--------------------|--------------------------------------------|
| API             | FastAPI + Uvicorn  | REST endpoints, Telegram webhook receiver  |
| Task Queue      | arq + Redis        | Async job execution, scheduling            |
| Database        | PostgreSQL 16      | State, audit logs, workflow data, memory    |
| Cache / Broker  | Redis 7            | arq broker, caching, pub/sub               |
| ORM             | SQLAlchemy 2.0     | Async database access                      |
| Migrations      | Alembic            | Schema versioning                          |
| Config          | Pydantic Settings  | Type-safe .env configuration               |
| Logging         | structlog          | Structured JSON logging                    |
| Browser         | Playwright         | Web scraping, portal automation            |
| Telegram        | python-telegram-bot| Primary user interface                     |

### Directory Structure

```
atlas/
├── atlas/
│   ├── api/              # FastAPI routes
│   ├── core/             # Platform subsystems
│   │   ├── approval/     # Human-in-the-loop gates
│   │   ├── audit/        # Immutable audit trail
│   │   ├── events/       # Internal event bus
│   │   ├── memory/       # Preferences & knowledge store
│   │   ├── notifications/# Multi-channel delivery
│   │   ├── policy/       # Trust level enforcement
│   │   ├── scoring/      # Signal/opportunity scoring
│   │   ├── secrets/      # Credential management
│   │   ├── state/        # Workflow state machines
│   │   ├── tasks/        # arq worker configuration
│   │   └── workflow/     # Registry + base class
│   ├── integrations/     # External service adapters (14)
│   ├── models/           # SQLAlchemy models
│   └── workflows/        # 105 workflow modules (12 categories)
├── tests/                # Pytest test suite
├── docs/                 # Project documentation
├── migrations/           # Alembic migrations
└── scripts/              # Utility scripts
```

## TODO

- [ ] Add sequence diagrams for key workflow patterns
- [ ] Document database schema after models are defined
- [ ] Add integration adapter interface specification
- [ ] Document event bus topic conventions
