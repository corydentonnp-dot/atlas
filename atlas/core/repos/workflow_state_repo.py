"""Repository for WorkflowState persistence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import and_, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.models.workflow_state import WorkflowState


class WorkflowStateRepository:
	"""Async repository for WorkflowState records."""

	def __init__(self, session: AsyncSession) -> None:
		self.session = session

	async def create_state(
		self,
		workflow_id: str,
		workflow_category: str,
		operation_id: str,
		state_type: str,
		context: dict,
		status: str = "pending",
		confidence: float = 0.5,
		ttl_minutes: int | None = None,
	) -> WorkflowState:
		"""Create a new workflow state record."""
		expires_at = None
		if ttl_minutes:
			expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)

		state = WorkflowState(
			id=uuid4(),
			workflow_id=workflow_id,
			workflow_category=workflow_category,
			operation_id=operation_id,
			state_type=state_type,
			context=context,
			status=status,
			confidence=confidence,
			expires_at=expires_at,
			created_at=datetime.now(timezone.utc),
			updated_at=datetime.now(timezone.utc),
		)
		self.session.add(state)
		await self.session.flush()
		return state

	async def get_by_id(self, state_id: UUID) -> WorkflowState | None:
		"""Retrieve a state by ID."""
		stmt = select(WorkflowState).where(WorkflowState.id == state_id)
		result = await self.session.execute(stmt)
		return result.scalar_one_or_none()

	async def get_by_operation(self, workflow_id: str, operation_id: str) -> WorkflowState | None:
		"""Get the latest state for a workflow operation."""
		stmt = (
			select(WorkflowState)
			.where(
				and_(
					WorkflowState.workflow_id == workflow_id,
					WorkflowState.operation_id == operation_id,
					WorkflowState.deleted_at.is_(None),
				)
			)
			.order_by(desc(WorkflowState.created_at))
			.limit(1)
		)
		result = await self.session.execute(stmt)
		return result.scalar_one_or_none()

	async def list_by_workflow(self, workflow_id: str, limit: int = 100) -> list[WorkflowState]:
		"""List all states for a workflow."""
		stmt = (
			select(WorkflowState)
			.where(
				and_(
					WorkflowState.workflow_id == workflow_id,
					WorkflowState.deleted_at.is_(None),
				)
			)
			.order_by(desc(WorkflowState.created_at))
			.limit(limit)
		)
		result = await self.session.execute(stmt)
		return result.scalars().all()

	async def list_by_category(self, category: str, status: str | None = None, limit: int = 100) -> list[WorkflowState]:
		"""List states by workflow category, optionally filtered by status."""
		conditions = [
			WorkflowState.workflow_category == category,
			WorkflowState.deleted_at.is_(None),
		]
		if status:
			conditions.append(WorkflowState.status == status)

		stmt = (
			select(WorkflowState)
			.where(and_(*conditions))
			.order_by(desc(WorkflowState.created_at))
			.limit(limit)
		)
		result = await self.session.execute(stmt)
		return result.scalars().all()

	async def list_pending(self, workflow_id: str | None = None, limit: int = 100) -> list[WorkflowState]:
		"""List pending state records."""
		conditions = [
			WorkflowState.status == "pending",
			WorkflowState.deleted_at.is_(None),
		]
		if workflow_id:
			conditions.append(WorkflowState.workflow_id == workflow_id)

		stmt = (
			select(WorkflowState)
			.where(and_(*conditions))
			.order_by(desc(WorkflowState.created_at))
			.limit(limit)
		)
		result = await self.session.execute(stmt)
		return result.scalars().all()

	async def update_status(self, state_id: UUID, status: str, result_summary: str | None = None) -> WorkflowState | None:
		"""Update the status of a state record."""
		state = await self.get_by_id(state_id)
		if state:
			state.status = status
			if result_summary:
				state.result_summary = result_summary
			state.processed_at = datetime.now(timezone.utc)
			state.updated_at = datetime.now(timezone.utc)
			await self.session.flush()
		return state

	async def cleanup_expired(self) -> int:
		"""Delete expired state records. Returns count deleted."""
		stmt = select(WorkflowState).where(
			and_(
				WorkflowState.expires_at <= datetime.now(timezone.utc),
				WorkflowState.deleted_at.is_(None),
			)
		)
		result = await self.session.execute(stmt)
		states = result.scalars().all()

		for state in states:
			state.deleted_at = datetime.now(timezone.utc)

		await self.session.flush()
		return len(states)
