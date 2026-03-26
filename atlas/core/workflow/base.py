"""Base workflow class — abstract interface for all workflows.

TODO: Implement after scaffolding is approved.
- BaseWorkflow ABC:
  - workflow_id: str
  - name: str
  - category: str
  - trust_level: TrustLevel
  - required_credentials: list[str]
  - state_machine: StateMachine
  - async trigger(event) -> WorkflowRun
  - async process(run) -> ActionPlan
  - async act(plan, approval) -> ActionResult
  - async close(run) -> None
  - get_status() -> WorkflowStatus
"""
