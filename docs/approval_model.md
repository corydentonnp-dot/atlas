# Atlas — Approval Model

## Overview

The approval system is Atlas's **human-in-the-loop** mechanism. It ensures that workflows
requiring user judgment pause execution, present context, and wait for explicit approval
before proceeding.

## Trust Levels & Approval Requirements

| Trust Level | Requires Approval? | Notification | Auto-Execute |
|-------------|-------------------|--------------|--------------|
| `auto`      | No                | Digest only  | Yes          |
| `suggest`   | Soft (nudge)      | Immediate    | After timeout (configurable) |
| `approve`   | Hard (blocking)   | Immediate    | Never        |

## Approval Flow

```
Workflow reaches action phase
        │
        ▼
   ┌──────────────────────┐
   │ Policy Engine Check   │
   │ (trust_level lookup)  │
   └──────────┬───────────┘
              │
    ┌─────────┼─────────┐
    ▼         ▼         ▼
  auto     suggest    approve
    │         │         │
    │    ┌────┴────┐    │
    │    │ Notify  │    │
    │    │ + Timer │    │
    │    └────┬────┘    │
    │         │         │
    │    timeout?───┐   │
    │    │yes  │no  │   │
    │    │     ▼    │   │
    │    │  wait... │   │
    │    ▼         ▼    │
    │  execute  rejected│
    │              │    │
    ▼              ▼    ▼
  execute       abort  Telegram prompt
    │              │    │
    │              │    ├── ✅ Approve → execute
    │              │    └── ❌ Reject  → abort
    ▼              ▼                      ▼
  Closer        Closer                 Closer
```

## Approval Interface (Telegram)

Approval prompts are delivered via Telegram with inline keyboards:

```
🔔 Approval Required: Workflow #17 — Promo APR Deadline
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Action: Send balance transfer reminder email
Details: Chase Sapphire 0% APR expires 2025-03-15
Amount: $4,200 remaining balance

[✅ Approve]  [❌ Reject]  [⏸️ Defer 1hr]
```

## Approval Queue

Pending approvals are stored in the database with:
- Workflow ID and instance
- Action description and context payload
- Requested timestamp
- Expiry/timeout (for `suggest` level)
- Resolution (approved / rejected / expired / deferred)
- Resolved-by and resolved-at timestamps

## Escalation Rules

- `suggest` workflows auto-execute after configurable timeout (default: 4 hours)
- `approve` workflows never auto-execute; they expire after 48 hours
- Expired approvals trigger a "missed approval" notification in the next digest
- Users can bulk-approve/reject from a Telegram summary command

## TODO

- [ ] Define approval database schema
- [ ] Implement Telegram inline keyboard handler
- [ ] Add approval delegation (e.g., auto-approve during work hours)
- [ ] Define approval audit trail format
