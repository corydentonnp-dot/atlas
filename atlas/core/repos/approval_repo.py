"""Repository for Approval model persistence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.models.approval import Approval, ApprovalStatus


class ApprovalRepository:
	"""Async repository for Approval records."""

	def __init__(self, session: AsyncSession) -> None:
		self.session = session

	async def create(
		self,
		workflow_id: str,
		action_type: str,
		context: dict[str, object],
		ttl_minutes: int = 1440,  # 24 hours default
	) -> Approval:
		"""Create a new approval request."""
		approval = Approval(
			id=uuid4(),
			workflow_id=workflow_id,
			action_type=action_type,
			status=ApprovalStatus.PENDING,
			context=context,
			expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
			created_at=datetime.now(timezone.utc),
			updated_at=datetime.now(timezone.utc),
		)
		self.session.add(approval)
		await self.session.flush()
		return approval

	async def get_by_id(self, approval_id: UUID) -> Approval | None:
		"""Retrieve an approval by ID."""
		stmt = select(Approval).where(Approval.id == approval_id)
		result = await self.session.execute(stmt)
		return result.scalar_one_or_none()

	async def list_pending(self, workflow_id: str | None = None) -> list[Approval]:
		"""List all pending approvals, optionally filtered by workflow."""
		stmt = select(Approval).where(Approval.status == ApprovalStatus.PENDING)
		if workflow_id:
			stmt = stmt.where(Approval.workflow_id == workflow_id)
		result = await self.session.execute(stmt)
		return result.scalars().all()

	async def resolve(
		self,
		approval_id: UUID,
		approved: bool,
		resolved_by: str = "system",
	) -> Approval | None:
		"""Resolve an approval (approve or reject)."""
		approval = await self.get_by_id(approval_id)
		if not approval:
			return None

		approval.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
		approval.resolved_by = resolved_by
		approval.resolved_at = datetime.now(timezone.utc)
		approval.updated_at = datetime.now(timezone.utc)
		await self.session.flush()
		return approval

	async def expire_stale(self) -> int:
		"""Expire all overdue approvals. Returns count of expired."""
		stmt = select(Approval).where(
			Approval.status == ApprovalStatus.PENDING,
			Approval.expires_at <= datetime.now(timezone.utc),
		)
		result = await self.session.execute(stmt)
		expired = result.scalars().all()

		for approval in expired:
			approval.status = ApprovalStatus.EXPIRED
			approval.updated_at = datetime.now(timezone.utc)

		await self.session.flush()
		return len(expired)

	async def delete(self, approval_id: UUID) -> bool:
		"""Delete an approval by ID."""
		approval = await self.get_by_id(approval_id)
		if not approval:
			return False
		await self.session.delete(approval)
		await self.session.flush()
		return True
