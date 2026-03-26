# Atlas — Workflow Registry Reference

## Overview

Atlas manages **105 workflows** across **12 categories** (A–L). Each workflow is a Python
module under `atlas/workflows/<category>/` that will subclass `BaseWorkflow` and register
with the workflow registry.

## Category Index

| Cat | Name           | Count | Workflow IDs | Directory              |
|-----|----------------|-------|--------------|------------------------|
| A   | Communication  | 12    | #1–#12       | `workflows/communication/` |
| B   | Property       | 18    | #13–#30      | `workflows/property/`      |
| C   | Budget         | 12    | #31–#42      | `workflows/budget/`        |
| D   | Returns        | 8     | #43–#50      | `workflows/returns/`       |
| E   | Scheduling     | 10    | #51–#60      | `workflows/scheduling/`    |
| F   | Licensure      | 8     | #61–#68      | `workflows/licensure/`     |
| G   | Career         | 8     | #69–#76      | `workflows/career/`        |
| H   | Tax & Legal    | 6     | #77–#82      | `workflows/tax_legal/`     |
| I   | Home           | 8     | #83–#90      | `workflows/home/`          |
| J   | Shopping       | 8     | #91–#98      | `workflows/shopping/`      |
| K   | Travel         | 2     | #99–#100     | `workflows/travel/`        |
| L   | Additional     | 5     | #101–#105    | `workflows/additional/`    |

## Trust Levels

Each workflow operates at one of three trust levels:

- **auto**: Executes without human approval. Used for read-only or low-risk actions.
- **suggest**: Presents recommendations to the user; does not act without confirmation.
- **approve**: Requires explicit approval before any action is taken.

Trust levels are configurable per-workflow and can be overridden at runtime via the policy engine.

## Lifecycle States

All workflows follow a common state machine:

```
idle → watching → interpreting → planning → [approval_pending] → acting → closing → idle
                                                    ↓
                                                 rejected → idle
```

The `approval_pending` state is only entered when the workflow's trust level requires it
(i.e., `suggest` or `approve` modes).

## Quick-Win Scores

Workflows are prioritized by a composite quick-win score (0–20) based on:
- User value (1–5)
- Friction reduction (1–5)
- Build difficulty (inverted, 1–5)
- Automation potential (1–5)

See `docs/workflow_prioritization.md` and `docs/workflow_prioritization.yaml` for the full
scored matrix.

## TODO

- [ ] Generate this reference automatically from workflow module docstrings
- [ ] Add per-workflow dependency graph (which integrations each workflow requires)
- [ ] Document trigger types (cron, event, manual) per workflow
