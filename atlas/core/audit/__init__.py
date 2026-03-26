"""Atlas audit log — immutable record of all system actions.

TODO: Implement after scaffolding is approved.
Components:
- AuditEntry model (timestamp, actor, action, workflow, context, result)
- AuditLog service for writing and querying entries
- Structured context capture
- Retention policy support
- Query/filter by workflow, time range, action type
"""
