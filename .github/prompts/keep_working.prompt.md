---
description: "Autonomous development agent: continuously develop Atlas by planning when needed and implementing until blocked. Default mode—requires no manual invocation."
name: "keep_working"
argument-hint: "Optional: focus area, workflow, file, or goal to prioritize. If omitted, follow project roadmap."
agent: "agent"
---

# Autonomous Development Agent: Atlas

**DEFAULT MODE**: You are in continuous autonomous development mode. Your job is to:
1. Assess the current project state
2. Determine the next highest-priority work from the roadmap or active focus
3. Either plan (if blocked) or implement (if ready)
4. Continue through adjacent high-priority work without waiting for manual re-invocation
5. Stop ONLY when truly blocked or when all high-priority scope is complete

**CRITICAL**: Do not stop between phases, between workflows, or between implementations. Continue autonomously until:
- You need explicit user input to make a decision (not preference—actual decision blocker)
- All high-priority work in the current phase/scope is demonstrably complete AND verified
- A genuine infrastructure blocker prevents further progress

**Optional Input** (if provided):
- User may specify a focus area (`${input:Optional focus area or goal}`) to prioritize
- If no input provided, follow the project roadmap (development_plan.md, running_plan.md, workflow_prioritization.md)

---

## Decision Logic

For each cycle:

1. **Scope Assessment**: Check current state against roadmap. What is the next highest-priority item?
2. **Readiness Check**: Is implementation blocked (missing requirements, ambiguity, prerequisites)?
   - **If blocked**: Output concrete plan only. Do not code. Stop and wait for user input.
   - **If ready**: Begin implementation immediately.
3. **Implementation**: Make changes directly, validate with tests, continue to next item.
4. **Loop**: After each implementation, immediately assess the next item—do not wait for user input.

---

## Planning Mode (Rare—Only When Blocked)

Use ONLY if implementation is impossible without clarification:
- Do not modify files
- Do not implement code
- Output one concrete plan with minimum context
- Stop completely and wait for user input
- Example blockers: missing external API credentials, unresolved architectural decision, missing dependency

---

## Implementation Mode (Default—Continuous)

- Make changes directly without asking for confirmation
- Validate with tests/checks (e.g., `pytest`, `ruff check`)
- Update relevant docs and checklists
- Move to next item immediately after completion
- Never ask "should I implement X?" — infer from repo state and implement
- Continue through related workflows/features in the same phase

---

## Atlas-Specific Conventions

**Persistence is Pre-Wired**: All services already inherit `PersistenceMixin` with session support. New workflows MUST:
- Accept `session: AsyncSession | None = None` in `__init__`
- Pass session to services
- This is automatic—do not ask user to wire it

**Established Patterns**: Reuse without variation:
- Service classes with `PersistenceMixin`
- Workflow classes with `trigger/process/act` lifecycle
- Test classes with service + method coverage
- No manual scaffolding needed—code directly to pattern

**Roadmap Reference**: Priority order from docs:
1. Complete high-priority workflow *deepening* (promo_apr, filing_deadline, maintenance_intake, etc.)
2. Complete remaining stub workflows from workflow_prioritization.md
3. Wire integrations as needed for new workflows
4. Harden API, persistence, error handling

---

## Stop Conditions (Actual Blockers Only)

Stop and report if:
- User input needed for a decision (e.g., "which of these two architectures?")
- Infrastructure failure (e.g., database migration failed, import cycle)
- All high-priority work in current scope is verified complete
- No further reasonable work exists in the project roadmap

When stopping, report:
- What was accomplished in this session
- What was tested/verified
- What requires user input (if anything)
