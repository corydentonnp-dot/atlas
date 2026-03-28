"""Atlas API route definitions."""

from __future__ import annotations

from datetime import datetime, timezone

import redis
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from atlas.core.approval.service import ApprovalService
from atlas.core.audit.service import AuditService
from atlas.core.config import get_settings
from atlas.core.database import database_healthcheck
from atlas.core.exceptions import AtlasError, NotFoundError
from atlas.core.workflow.base import WorkflowEvent
from atlas.core.workflow.registry import default_workflow_registry

router = APIRouter()
approval_service = ApprovalService()
audit_service = AuditService()


class ErrorResponse(BaseModel):
	"""Standard error response."""

	code: str
	message: str
	timestamp: str


class HealthResponse(BaseModel):
	"""Health check response."""

	status: str
	timestamp: str


class ReadyResponse(BaseModel):
	"""Readiness check response."""

	status: str
	database: bool
	redis: bool


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
	"""Verify service is alive."""
	return HealthResponse(
		status="ok",
		timestamp=datetime.now(timezone.utc).isoformat(),
	)


@router.get("/ready", response_model=ReadyResponse)
async def ready() -> ReadyResponse:
	"""Verify all critical dependencies are available."""
	settings = get_settings()
	database_ok = False
	redis_ok = False

	try:
		database_ok = await database_healthcheck(settings)
	except Exception as e:
		database_ok = False

	try:
		client = redis.from_url(settings.redis_url, socket_timeout=1.0)
		redis_ok = bool(client.ping())
	except Exception as e:
		redis_ok = False

	status_code = "ready" if database_ok and redis_ok else "degraded"
	return ReadyResponse(status=status_code, database=database_ok, redis=redis_ok)


@router.get("/workflows")
async def list_workflows() -> list[dict[str, object]]:
	"""List all registered workflows."""
	try:
		return [status.__dict__ for status in default_workflow_registry.list_all()]
	except Exception as e:
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail="Failed to list workflows",
		) from e


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str) -> dict[str, object]:
	"""Get a specific workflow's status."""
	try:
		status_obj = default_workflow_registry.get_status(workflow_id)
		return status_obj.__dict__
	except KeyError as exc:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"Workflow '{workflow_id}' not found",
		) from exc
	except Exception as e:
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail="Failed to get workflow status",
		) from e


@router.post("/workflows/{workflow_id}/trigger")
async def trigger_workflow(workflow_id: str, event: dict[str, object]) -> dict[str, object]:
	"""Trigger a workflow with provided event data."""
	try:
		# Validate event structure
		if not event:
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail="Event payload cannot be empty",
			)

		workflow_event = WorkflowEvent(
			event_type=str(event.get("event_type", "manual_trigger")),
			payload=event,
		)

		result = await default_workflow_registry.trigger(workflow_id, workflow_event)
		audit_service.log_action("api", "workflow_trigger", workflow_id, event, "success")
		return result.__dict__

	except KeyError as exc:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"Workflow '{workflow_id}' not found",
		) from exc
	except Exception as e:
		audit_service.log_action("api", "workflow_trigger", workflow_id, event, "error")
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail="Failed to trigger workflow",
		) from e


@router.get("/approvals")
async def list_pending_approvals() -> list[dict[str, object]]:
	"""List all pending approval requests."""
	try:
		return [approval.__dict__ for approval in approval_service.list_pending()]
	except Exception as e:
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail="Failed to list approvals",
		) from e


@router.post("/approvals/{approval_id}/approve")
async def approve(approval_id: str) -> dict[str, object]:
	"""Approve a pending request."""
	try:
		result = approval_service.resolve_approval(approval_id, "approved")
		audit_service.log_action("api", "approval_approve", "approval", {"approval_id": approval_id}, "success")
		return result.__dict__
	except KeyError as exc:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"Approval '{approval_id}' not found",
		) from exc
	except Exception as e:
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail="Failed to approve request",
		) from e


@router.post("/approvals/{approval_id}/reject")
async def reject(approval_id: str) -> dict[str, object]:
	"""Reject a pending request."""
	try:
		result = approval_service.resolve_approval(approval_id, "rejected")
		audit_service.log_action("api", "approval_reject", "approval", {"approval_id": approval_id}, "success")
		return result.__dict__
	except KeyError as exc:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"Approval '{approval_id}' not found",
		) from exc
	except Exception as e:
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail="Failed to reject request",
		) from e


@router.get("/audit")
async def audit(workflow_id: str | None = None, action: str | None = None) -> list[dict[str, object]]:
	"""Query audit log with optional filters."""
	try:
		entries = audit_service.query(workflow_id=workflow_id, action=action)
		return [entry.__dict__ for entry in entries]
	except Exception as e:
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail="Failed to query audit log",
		) from e
