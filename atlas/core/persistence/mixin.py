"""Persistence layer mixin for workflow services.

This mixin allows workflow services to optionally use async persistence
without requiring code changes to the core service logic.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.repos.workflow_state_repo import WorkflowStateRepository

T = TypeVar("T")


class PersistenceMixin:
	"""Mixin adding async persistence to workflow services."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		"""Initialize with optional async session for persistence."""
		self._session = session
		self._repo = WorkflowStateRepository(session) if session else None

	@property
	def has_persistence(self) -> bool:
		"""Check if persistence is enabled."""
		return self._repo is not None

	async def persist_plan(
		self,
		workflow_id: str,
		workflow_category: str,
		operation_id: str,
		context: dict[str, Any],
		confidence: float = 0.5,
	) -> str:
		"""Persist a workflow decision plan. Returns state ID."""
		if not self.has_persistence:
			return operation_id  # Return operation ID if no persistence

		state = await self._repo.create_state(
			workflow_id=workflow_id,
			workflow_category=workflow_category,
			operation_id=operation_id,
			state_type="plan",
			context=context,
			status="pending",
			confidence=confidence,
			ttl_minutes=1440,  # 24 hour TTL
		)
		return str(state.id)

	async def persist_result(
		self,
		workflow_id: str,
		workflow_category: str,
		operation_id: str,
		context: dict[str, Any],
		result_summary: str,
		success: bool = True,
	) -> str:
		"""Persist a workflow execution result. Returns state ID."""
		if not self.has_persistence:
			return operation_id

		state = await self._repo.create_state(
			workflow_id=workflow_id,
			workflow_category=workflow_category,
			operation_id=operation_id,
			state_type="result",
			context=context,
			status="completed" if success else "failed",
			result_summary=result_summary,
			confidence=1.0 if success else 0.0,
			ttl_minutes=2880,  # 48 hour TTL
		)
		return str(state.id)

	async def persist_decision(
		self,
		workflow_id: str,
		workflow_category: str,
		operation_id: str,
		context: dict[str, Any],
		decision_reason: str,
		approved: bool = True,
	) -> str:
		"""Persist a workflow decision/approval. Returns state ID."""
		if not self.has_persistence:
			return operation_id

		state = await self._repo.create_state(
			workflow_id=workflow_id,
			workflow_category=workflow_category,
			operation_id=operation_id,
			state_type="decision",
			context=context,
			status="approved" if approved else "rejected",
			result_summary=decision_reason,
			confidence=1.0 if approved else 0.5,
			ttl_minutes=10080,  # 7 day TTL
		)
		return str(state.id)

	async def get_recent_state(self, workflow_id: str, operation_id: str) -> dict[str, Any] | None:
		"""Retrieve the most recent state for a workflow operation."""
		if not self.has_persistence:
			return None

		state = await self._repo.get_by_operation(workflow_id, operation_id)
		return {
			"id": str(state.id),
			"workflow_id": state.workflow_id,
			"operation_id": state.operation_id,
			"state_type": state.state_type,
			"status": state.status,
			"context": state.context,
			"result_summary": state.result_summary,
			"confidence": state.confidence,
			"created_at": state.created_at.isoformat(),
		} if state else None

	async def get_workflow_history(self, workflow_id: str, limit: int = 50) -> list[dict[str, Any]]:
		"""Retrieve all states for a workflow."""
		if not self.has_persistence:
			return []

		states = await self._repo.list_by_workflow(workflow_id, limit=limit)
		return [
			{
				"id": str(state.id),
				"workflow_id": state.workflow_id,
				"operation_id": state.operation_id,
				"state_type": state.state_type,
				"status": state.status,
				"context": state.context,
				"created_at": state.created_at.isoformat(),
			}
			for state in states
		]
