"""Atlas API route definitions — stub.

TODO: Implement after scaffolding is approved.
Routes to create:
- GET  /health           — health check
- GET  /ready            — readiness check (DB + Redis)
- GET  /workflows        — list registered workflows
- GET  /workflows/{id}   — workflow detail + state
- POST /workflows/{id}/trigger — manually trigger a workflow
- GET  /approvals        — pending approval queue
- POST /approvals/{id}/approve — approve an action
- POST /approvals/{id}/reject  — reject an action
- GET  /audit            — query audit log
- GET  /notifications    — recent notifications
- POST /intents          — capture a user intent
"""
