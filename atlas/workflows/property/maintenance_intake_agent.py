"""Workflow #26: Maintenance Intake Agent — Phase 1 Priority.

Intakes maintenance requests from tenants (via Telegram or form),
classifies urgency, and queues for dispatch.

Recommended phase: 1 (quick_win_score: 12)
Trust level: draft
Required credentials: Telegram bot
Category: property

TODO: Implement after scaffolding is approved.

Workflow states:
- idle -> request_received -> classified -> dispatch_ready -> dispatched -> resolved

Service interface:
- intake_request(source, message) -> MaintenanceRequest
- classify_urgency(request) -> UrgencyLevel
- suggest_contractor(request) -> Contractor | None
- dispatch(request, contractor, approval) -> None

Schemas needed:
- MaintenanceRequest(tenant, property, unit, description, urgency, photos)
- UrgencyLevel enum (emergency, urgent, routine, cosmetic)
"""

# TODO: Implement BaseWorkflow subclass
# TODO: Implement intake parsing
# TODO: Add urgency classification rules
# TODO: Add contractor matching
# TODO: Add schemas and tests
