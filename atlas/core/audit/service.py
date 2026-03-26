"""Audit service — write and query the audit log.

TODO: Implement after scaffolding is approved.
- log_action(actor, action, workflow_id, context, result) -> AuditEntry
- query(filters, pagination) -> list[AuditEntry]
- count_by_workflow(workflow_id, time_range) -> int
- export(format, time_range) -> bytes
"""
