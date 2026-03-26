"""Policy engine — evaluate actions against trust levels and rules.

TODO: Implement after scaffolding is approved.
- get_trust_level(workflow_id, action_type) -> TrustLevel
- evaluate_action(workflow_id, action, context, confidence) -> PolicyDecision
- set_workflow_policy(workflow_id, trust_level) -> None
- set_action_policy(workflow_id, action_type, trust_level) -> None
- add_user_override(workflow_id, action_pattern, decision) -> None
- get_domain_defaults(domain) -> dict[str, TrustLevel]
"""
