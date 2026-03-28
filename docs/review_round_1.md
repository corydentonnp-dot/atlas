# Atlas Review Round 1

Last updated: 2026-03-26

## Executive Verdict

The repository has strong scaffolding discipline and clear intent, but it was previously over-documented relative to implementation depth. This pass converted core primitives from placeholders into working, testable components and delivered five real workflow vertical slices.

Current recommendation: keep the stack unchanged (FastAPI + SQLAlchemy + Redis + arq), reduce broad scaffolding growth, and deepen a narrow set of high-ROI workflows.

## Audit Snapshot

- Workflow python files present: 118
- Scaffold marker count (TODO: Implement after scaffolding is approved): 158
- Core declaration count before this pass was very low (10 class/def hits across key areas)
- Test suite status after this pass: 22 passed

## 1) What Exists And Is Actually Wired

- Typed settings and logging are implemented:
  - atlas/core/config.py
  - atlas/core/logging.py
- Async DB session/health infrastructure exists:
  - atlas/core/database.py
- Core runtime primitives implemented in-memory and test-backed:
  - Event bus: atlas/core/events/bus.py
  - State machine: atlas/core/state/machine.py
  - Workflow base + registry: atlas/core/workflow/base.py, atlas/core/workflow/registry.py
  - Policy engine: atlas/core/policy/engine.py
  - Approval queue: atlas/core/approval/service.py
  - Audit log service: atlas/core/audit/service.py
  - Notification routing + digest queueing: atlas/core/notifications/service.py
- FastAPI app now starts and registers selected workflows:
  - atlas/api/main.py
  - atlas/api/routes.py
- Five phase-1 workflows now run end-to-end skeleton logic:
  - promo_apr_deadline
  - filing_deadline_tracker
  - maintenance_intake
  - shared_expense_classifier
  - rent_reminder
- Tests now cover core primitives and selected workflows:
  - tests/core/*
  - tests/workflows/test_registration.py

## 2) What Exists Only As Stub

- Most workflow modules remain stubs with docstring-level contracts only.
- Most integration adapters are stubs.
- Memory service, scoring service, secrets manager, task worker remain stub-level.
- DB domain models beyond base mixins are not implemented.
- Alembic migrations are not wired to metadata and no versions exist.

## 3) What Is Missing But Implied By Docs

- Durable persistence for approvals/audit/workflow runs (currently in-memory only).
- Redis task queue execution paths beyond placeholders.
- End-to-end integration contracts with external services.
- API coverage for notifications and richer audit filters implied by docs.
- Honest execution status in some docs still lagged prior to this review.

## 4) Architectural Strengths

- Clear package boundaries and category organization.
- Good local-first bias and privacy-first defaults.
- Strong decomposition of platform concerns.
- Good testability of new primitives due to explicit dataclasses/services.
- Workflow-first orientation gives good long-term extension path.

## 5) Architectural Weaknesses

- Documentation had outrun implementation (overclaim risk).
- Large scaffold surface with low executable density.
- In-memory implementations not yet persistence-backed.
- Workflow roster breadth creates maintenance drag for a solo novice.
- Migration and model layer not yet connected.

## 6) Dimension Scores (1-5)

| Dimension | Score | Rationale | Improvement Actions |
|---|---:|---|---|
| local dev experience | 3 | Good docs and Makefile, but no running DB models/migrations yet | Wire first migration + seed command; add one-command smoke run |
| architecture clarity | 4 | Structure is clear and consistent | Add single source of truth for runtime status in docs |
| modularity | 4 | Good separations in core subsystems | Replace direct internal field access with service methods |
| workflow registration consistency | 3 | Registry exists, but only 3 workflows real | Add explicit metadata contract for all workflows |
| state model quality | 3 | Generic machine is now real but simple | Add typed workflow state enums and persistence hooks |
| approval/policy design | 3 | Core logic works, no persistence yet | Persist approvals; add SLA expiry worker task |
| audit logging completeness | 3 | Query/export exists but in-memory only | Add DB-backed audit repository and API pagination |
| notification abstraction quality | 3 | Channels + digest exist, quiet-hours works | Add channel retries, batching windows, and dead-letter logging |
| memory abstraction quality | 1 | Still stub | Implement minimal KV + entity memory backend |
| config/secrets hygiene | 3 | Typed settings and SecretStr good | Implement secrets manager and secret source precedence |
| testability | 4 | Core now unit-tested and deterministic | Add API tests + persistence integration tests |
| docs quality | 3 | Comprehensive but historically over-optimistic | Keep docs synchronized with executable status table |
| ease of future extension | 4 | Registry/base patterns support growth | Add template generator for new workflow skeletons |
| likelihood of solo maintenance success | 3 | Strong structure but too much surface area | Freeze low-ROI stubs and focus on 5 core workflows |
| speed-to-value | 3 | Better after this pass, still many placeholders | Build durable core + 5 deep workflows before expansion |
| overengineering risk | 4 | High due to 100+ stubs early | Enforce vertical-slice policy before new modules |
| under-modeling risk | 2 | Some areas under-modeled (DB, memory) | Implement minimum domain models for approvals/audit/workflow runs |
| external dependency risk | 3 | Many workflows rely on credentials/APIs | Keep manual-input variants for phase-1 value |
| privacy posture | 4 | Local-first design and trust levels are good | Add explicit data retention + export/delete policies |

## 7) Top 10 Improvements By ROI

1. Persist approvals, audit entries, and workflow runs in Postgres.
2. Implement first migration and connect Alembic target metadata.
3. Add API integration tests for health, ready, workflows, approvals.
4. Harden notification batching (windowing + idempotency key).
5. Implement memory service MVP used by shared_expense_classifier.
6. Add worker tasks for approval expiry and digest flush.
7. Add workflow metadata validation CI test for all workflow files.
8. Add honest implementation status matrix in README.
9. Introduce integration contract protocols for adapters.
10. Reduce docs duplication and move phase tracking to one canonical page.

## 8) Top 10 Risks If Left Unchanged

1. Stubs continue to outnumber executable code by large margin.
2. In-memory services lose state across restarts.
3. Docs drift leads to false confidence.
4. Approval queue lacks durability and traceability.
5. No migration path blocks production-like validation.
6. Integration stubs encourage brittle assumptions.
7. Too many workflow stubs overwhelm solo maintenance.
8. No worker scheduling means time-based automation remains partial.
9. Privacy promises are not fully enforceable without retention controls.
10. New development may continue breadth-first instead of value-first.

## 9) Recommended Next Implementation Tranche

Focus next on durability + five workflow deepening:

- Platform hardening:
  - Postgres models for approvals, audits, workflow runs
  - Alembic initial migration
  - Worker tasks for digest flush and stale approval expiration
- Workflow deepening:
  - promo_apr_deadline
  - filing_deadline_tracker
  - maintenance_intake
  - shared_expense_classifier
  - rent_reminder

## 10) Priority Movement (Up/Down)

Moved up:
- shared_expense_classifier (now directly enabled by policy/notification primitives)
- rent_reminder (cheap, independent, immediate value)
- installment_tracker (cheap, date math, low external dependency)

Moved down:
- message_triage_agent (requires NLP + account integrations)
- furnished_finder_lead_responder (higher integration fragility early)
- listing_refresh_agent (browser fragility)

## 11) Should The Stack Change?

No. Keep the current stack unchanged.

Reasoning:
- Current bottlenecks are implementation depth and durability, not framework limits.
- Changing stack now would reduce speed-to-value.
- Existing choices are appropriate for single-user local-first execution.
