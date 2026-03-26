# Atlas — Open Questions

> Items requiring user input, policy decisions, or external credentials.
> Last updated: 2026-03-26

---

## Blocking Questions (Need Answer Before Full Implementation)

### Q1: Telegram Bot Token
- **Status**: BLOCKING for notification delivery
- **What**: Need a Telegram bot token and your chat ID for the command/control interface
- **How to get**: Talk to @BotFather on Telegram, create a bot, get the token
- **Impact**: Without this, notifications are logged but not delivered
- **Workaround**: System logs all notifications; can be viewed via API until Telegram is connected

### Q2: Gmail / Google OAuth Credentials
- **Status**: BLOCKING for email workflows
- **What**: OAuth 2.0 client credentials for Gmail, Calendar, Drive access
- **How to get**: Google Cloud Console → APIs & Services → Credentials
- **Impact**: Email-dependent workflows (overdue_text_resurfacer, thread_closer, etc.) need this
- **Workaround**: These workflows are stubbed; data can be manually entered initially

### Q3: PostgreSQL Connection
- **Status**: NOT BLOCKING (Docker Compose provides this)
- **What**: Will use Docker Compose Postgres by default
- **Decision needed**: Do you want to use an existing Postgres instance instead?
- **Default**: Docker Compose local instance, no action needed

### Q4: Home Assistant URL and Token
- **Status**: BLOCKING for presence/home automation workflows
- **What**: Home Assistant base URL + long-lived access token
- **Impact**: dual_departure_presence_automation, smart_home_routine_agent
- **Workaround**: Stubbed; manual triggers available

### Q5: Tesla API Access
- **Status**: DEFERRED (low priority for phase 1)
- **What**: Tesla account credentials or token for vehicle API
- **Impact**: tesla_readiness_agent only

---

## Non-Blocking Decisions (Have Reasonable Defaults)

### D1: Project Name
- **Default chosen**: "Atlas"
- **Rationale**: Short, memorable, conveys "carrying the world" metaphor
- **Change cost**: Low — rename package and a few configs
- **User can override at any time**

### D2: Task Queue Choice
- **Default chosen**: arq (async Redis-based)
- **Alternative**: Celery (heavier, more features)
- **Rationale**: arq is simpler, async-native, perfect for single-user local system
- **Change cost**: Medium — swap out task decorators and worker config

### D3: Notification Priority
- **Default chosen**: Telegram first, then email digest as secondary
- **Rationale**: Telegram is push, mobile, low-friction, already personal
- **Change cost**: Low — notification system is abstracted

### D4: Database Naming
- **Default chosen**: `atlas_dev` for development, `atlas` for production
- **Change cost**: Trivial — .env file change

### D5: Quiet Hours Default
- **Default chosen**: 22:00–07:00 local time, batch non-urgent into morning digest
- **User can customize via preferences**

---

## Assumptions Made (Will Verify Later)

### A1: Single User System
- The entire system serves exactly one user
- No multi-tenancy, no user auth beyond API key/Telegram chat ID
- If this changes, significant rework needed

### A2: Local-First Execution
- All data stays on local machine / local Docker
- No cloud services for core platform (cloud APIs for integrations only)
- User controls all data

### A3: Fiancée Shared Logistics
- Some workflows involve shared data (expenses, scheduling, presence)
- Fiancée does NOT have direct system access (user relays via approval)
- No separate fiancée account needed initially

### A4: Property Portfolio Size
- Assumed small portfolio (1-5 properties)
- Data model supports more, but UI/workflow optimized for small scale
- If 50+ units, would need different query patterns

### A5: Browser Automation Fragility
- Playwright automations are inherently fragile
- Will stub them but mark as higher-maintenance
- Prefer API integrations where available

### A6: No Autonomous Financial Transactions
- System will NEVER execute financial transactions without explicit approval
- Even "auto" trust level workflows cannot move money
- This is a hard policy, not configurable

---

## Architecture Questions to Revisit

### R1: Event Bus Implementation
- Starting with simple in-process async event bus
- If scale demands it, can move to Redis Pub/Sub or dedicated message broker
- Decision point: when we have >20 concurrent watchers

### R2: Workflow State Persistence
- Storing workflow state in Postgres JSON columns initially
- May want dedicated state tables per workflow category later
- Decision point: when state queries become complex

### R3: Memory System Depth
- Starting with key-value preference storage + entity tagging
- Full semantic memory (embeddings, RAG) is Phase 3+
- Decision point: when user feedback indicates memory gaps

### R4: Multi-Device Presence
- Starting with manual presence toggle or Home Assistant integration
- Phone location tracking is privacy-sensitive; deferred
- Decision point: when dual_departure workflow is actively used

---

## Items Punted to Later Phases

- Voice / wakeword interface (Phase 3+)
- Full autonomous trading signals (Phase 3+, with heavy approval gates)
- Multi-user / fiancée direct access (maybe never)
- Mobile app (Telegram is the mobile interface)
- Web dashboard beyond API docs (Phase 2+)
- Semantic search / RAG over personal data (Phase 3+)
- SMS/MMS integration (Telegram first)
