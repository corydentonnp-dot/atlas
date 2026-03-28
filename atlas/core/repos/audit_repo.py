"""Repository for AuditEntry model persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.models.audit import AuditEntry


class AuditRepository:
	"""Async repository for AuditEntry records."""

	def __init__(self, session: AsyncSession) -> None:
		self.session = session

	async def create(
		self,
		actor: str,
		action: str,
		workflow_id: str | None = None,
		context: dict[str, object] | None = None,
		result: str = "pending",
		error_message: str | None = None,
	) -> AuditEntry:
		"""Create a new audit entry."""
		entry = AuditEntry(
			id=uuid4(),
			actor=actor,
			action=action,
			workflow_id=workflow_id,
			context=context or {},
			result=result,
			error_message=error_message,
			created_at=datetime.now(timezone.utc),
			updated_at=datetime.now(timezone.utc),
		)
		self.session.add(entry)
		await self.session.flush()
		return entry

	async def get_by_id(self, entry_id: str) -> AuditEntry | None:
		"""Retrieve an audit entry by ID."""
		stmt = select(AuditEntry).where(AuditEntry.id == entry_id)
		result = await self.session.execute(stmt)
		return result.scalar_one_or_none()

	async def list_by_actor(self, actor: str, limit: int = 100) -> list[AuditEntry]:
		"""List audit entries by actor."""
		stmt = select(AuditEntry).where(AuditEntry.actor == actor).order_by(AuditEntry.created_at.desc()).limit(limit)
		result = await self.session.execute(stmt)
		return result.scalars().all()

	async def list_by_action(self, action: str, limit: int = 100) -> list[AuditEntry]:
		"""List audit entries by action type."""
		stmt = select(AuditEntry).where(AuditEntry.action == action).order_by(AuditEntry.created_at.desc()).limit(limit)
		result = await self.session.execute(stmt)
		return result.scalars().all()

	async def list_by_workflow(self, workflow_id: str, limit: int = 100) -> list[AuditEntry]:
		"""List audit entries for a workflow."""
		stmt = (
			select(AuditEntry)
			.where(AuditEntry.workflow_id == workflow_id)
			.order_by(AuditEntry.created_at.desc())
			.limit(limit)
		)
		result = await self.session.execute(stmt)
		return result.scalars().all()

	async def list_by_actor_and_action(
		self,
		actor: str,
		action: str,
		limit: int = 100,
	) -> list[AuditEntry]:
		"""List audit entries by actor AND action."""
		stmt = (
			select(AuditEntry)
			.where(and_(AuditEntry.actor == actor, AuditEntry.action == action))
			.order_by(AuditEntry.created_at.desc())
			.limit(limit)
		)
		result = await self.session.execute(stmt)
		return result.scalars().all()

	async def export_all(self, limit: int = 10000) -> list[AuditEntry]:
		"""Export all audit entries."""
		stmt = select(AuditEntry).order_by(AuditEntry.created_at.desc()).limit(limit)
		result = await self.session.execute(stmt)
		return result.scalars().all()

	async def count(self) -> int:
		"""Count total audit entries."""
		stmt = select(AuditEntry)
		result = await self.session.execute(stmt)
		return len(result.scalars().all())
