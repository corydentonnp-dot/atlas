"""Workflow registry — discover, register, and manage workflows.

TODO: Implement after scaffolding is approved.
- register(workflow_cls) -> None
- get(workflow_id) -> BaseWorkflow
- list_all() -> list[WorkflowInfo]
- list_by_category(category) -> list[WorkflowInfo]
- list_active() -> list[WorkflowInfo]
- get_status(workflow_id) -> WorkflowStatus
- trigger(workflow_id, event) -> WorkflowRun
- auto_discover(package) -> int  (scan for BaseWorkflow subclasses)
"""
