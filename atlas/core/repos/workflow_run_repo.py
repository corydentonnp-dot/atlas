"""Repository for WorkflowRun model persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.models.workflow_run import WorkflowRun, WorkflowRunStatus


class WorkflowRunRepository:
	"""Async repository for WorkflowRun records."""

	def __init__(self, session: AsyncSession) -> None:
		self.session = session

	async def create(
		self,
		workflow_id: str,
		event_type: str,
		status: WorkflowRunStatus = WorkflowRunStatus.STARTED,
		input_data: dict[str, object] | None = None,
	) -> WorkflowRun:
		"""Create a new workflow run."""
		run = WorkflowRun(
			id=uuid4(),
			workflow_id=workflow_id,
			event_type=event_type,
			status=status,
			input_data=input_data or {},
			output_data={},
			error_message=None,
			tags=[],
			created_at=datetime.now(timezone.utc),
			updated_at=datetime.now(timezone.utc),
		)
		self.session.add(run)
		await self.session.flush()
		return run

	async def get_by_id(self, run_id: str) -> WorkflowRun | None:
		"""Retrieve a workflow run by ID."""
		stmt = select(WorkflowRun).where(WorkflowRun.id == run_id)
		result = await self.session.execute(stmt)
		return result.scalar_one_or_none()

	async def list_by_workflow(self, workflow_id: str, limit: int = 100) -> list[WorkflowRun]:
		"""List runs for a workflow."""
		stmt = (
			select(WorkflowRun)
			.where(WorkflowRun.workflow_id == workflow_id)
			.order_by(WorkflowRun.created_at.desc())
			.limit(limit)
		)
		result = await self.session.execute(stmt)
		return result.scalars().all()

	async def list_by_status(self, status: WorkflowRunStatus, limit: int = 100) -> list[WorkflowRun]:
		"""List runs by status."""
		stmt = (
			select(WorkflowRun)
			.where(WorkflowRun.status == status)
			.order_by(WorkflowRun.created_at.desc())
			.limit(limit)
		)
		result = await self.session.execute(stmt)
		return result.scalars().all()

	async def list_terminal_runs(self, limit: int = 100) -> list[WorkflowRun]:
		"""List completed or failed runs."""
		stmt = (
			select(WorkflowRun)
			.where(
				(WorkflowRun.status == WorkflowRunStatus.COMPLETED) | (WorkflowRun.status == WorkflowRunStatus.FAILED)
			)
			.order_by(WorkflowRun.created_at.desc())
			.limit(limit)
		)
		result = await self.session.execute(stmt)
		return result.scalars().all()

	async def update_status(
		self,
		run_id: str,
		status: WorkflowRunStatus,
		output_data: dict[str, object] | None = None,
		error_message: str | None = None,
	) -> WorkflowRun | None:
		"""Update a run's status and optionally output."""
		run = await self.get_by_id(run_id)
		if not run:
			return None

		run.status = status
		if output_data:
			run.output_data = output_data
		if error_message:
			run.error_message = error_message
		run.updated_at = datetime.now(timezone.utc)
		await self.session.flush()
		return run

	async def add_tag(self, run_id: str, tag: str) -> WorkflowRun | None:
		"""Add a tag to a run."""
		run = await self.get_by_id(run_id)
		if not run:
			return None
		if tag not in run.tags:
			run.tags.append(tag)
			run.updated_at = datetime.now(timezone.utc)
			await self.session.flush()
		return run

	async def list_by_tag(self, tag: str, limit: int = 100) -> list[WorkflowRun]:
		"""List runs with a specific tag."""
		# Note: This is a text-based filter since tags are stored as list in JSON
		# In production, would want a normalized tags table
		stmt = select(WorkflowRun).limit(limit)
		result = await self.session.execute(stmt)
		runs = result.scalars().all()
		return [r for r in runs if tag in r.tags]

	async def count_by_status(self, status: WorkflowRunStatus) -> int:
		"""Count runs by status."""
		stmt = select(WorkflowRun).where(WorkflowRun.status == status)
		result = await self.session.execute(stmt)
		return len(result.scalars().all())
