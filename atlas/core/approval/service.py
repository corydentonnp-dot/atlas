"""Approval service — manages the approval queue lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.repos.approval_repo import ApprovalRepository


class ApprovalStatus(StrEnum):
	PENDING = "pending"
	APPROVED = "approved"
	REJECTED = "rejected"
	EXPIRED = "expired"


@dataclass(slots=True)
class ApprovalRequest:
	workflow_id: str
	action_type: str
	context: dict[str, object]
	trust_level: str
	approval_id: str = field(default_factory=lambda: str(uuid4()))
	created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
	expires_at: datetime | None = None
	status: ApprovalStatus = ApprovalStatus.PENDING
	decision_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ApprovalResult:
	approval_id: str
	status: ApprovalStatus
	decided_at: datetime
	reason: str | None = None


class ApprovalService:
	"""Approval queue supporting both in-memory and async repository modes."""

	def __init__(self, ttl_hours: int = 24, session: AsyncSession | None = None) -> None:
		self._approvals: dict[str, ApprovalRequest] = {}
		self._ttl = timedelta(hours=ttl_hours)
		self._repo: ApprovalRepository | None = ApprovalRepository(session) if session else None

	def create_approval(
		self,
		workflow_id: str,
		action_type: str,
		context: dict[str, object],
		trust_level: str,
		expires_at: datetime | None = None,
	) -> ApprovalRequest:
		"""Create an approval (in-memory mode — use create_approval_async for persistence)."""
		approval = ApprovalRequest(
			workflow_id=workflow_id,
			action_type=action_type,
			context=context,
			trust_level=trust_level,
			expires_at=expires_at or datetime.now(timezone.utc) + self._ttl,
		)
		self._approvals[approval.approval_id] = approval
		return approval

	async def create_approval_async(
		self,
		workflow_id: str,
		action_type: str,
		context: dict[str, object],
		ttl_minutes: int = 1440,
	) -> dict[str, object]:
		"""Create an approval using repository (persisted)."""
		if not self._repo:
			raise RuntimeError("Repository not configured for async operations")
		approval = await self._repo.create(workflow_id, action_type, context, ttl_minutes)
		return {
			"approval_id": str(approval.id),
			"status": approval.status.value,
			"created_at": approval.created_at.isoformat(),
		}

	def resolve_approval(self, approval_id: str, decision: str, reason: str | None = None) -> ApprovalResult:
		approval = self._approvals.get(approval_id)
		if approval is None:
			raise KeyError(f"Unknown approval_id: {approval_id}")

		if approval.status != ApprovalStatus.PENDING:
			return ApprovalResult(
				approval_id=approval_id,
				status=approval.status,
				decided_at=datetime.now(timezone.utc),
				reason=approval.decision_reason,
			)

		resolved = decision.strip().lower()
		if resolved not in {"approve", "approved", "reject", "rejected"}:
			raise ValueError("Decision must be approve/approved/reject/rejected.")

		approval.status = (
			ApprovalStatus.APPROVED if resolved.startswith("approve") else ApprovalStatus.REJECTED
		)
		approval.decision_reason = reason
		return ApprovalResult(
			approval_id=approval_id,
			status=approval.status,
			decided_at=datetime.now(timezone.utc),
			reason=reason,
		)

	async def resolve_approval_async(
		self,
		approval_id: UUID | str,
		approved: bool,
		resolved_by: str = "system",
	) -> dict[str, object]:
		"""Resolve an approval using repository (persisted)."""
		if not self._repo:
			raise RuntimeError("Repository not configured for async operations")
		if isinstance(approval_id, str):
			approval_id = UUID(approval_id)
		approval = await self._repo.resolve(approval_id, approved, resolved_by)
		if not approval:
			raise KeyError(f"Unknown approval_id: {approval_id}")
		return {
			"approval_id": str(approval.id),
			"status": approval.status.value,
			"resolved_at": approval.resolved_at.isoformat() if approval.resolved_at else None,
		}

	def list_pending(self, workflow_id: str | None = None) -> list[ApprovalRequest]:
		pending = [approval for approval in self._approvals.values() if approval.status == ApprovalStatus.PENDING]
		if workflow_id is None:
			return pending
		return [approval for approval in pending if approval.workflow_id == workflow_id]

	async def list_pending_async(self, workflow_id: str | None = None) -> list[dict[str, object]]:
		"""List pending approvals using repository."""
		if not self._repo:
			raise RuntimeError("Repository not configured for async operations")
		approvals = await self._repo.list_pending(workflow_id)
		return [
			{
				"approval_id": str(a.id),
				"workflow_id": a.workflow_id,
				"status": a.status.value,
				"created_at": a.created_at.isoformat(),
			}
			for a in approvals
		]

	def batch_approve(self, approval_ids: list[str], reason: str | None = None) -> list[ApprovalResult]:
		return [self.resolve_approval(approval_id, "approved", reason) for approval_id in approval_ids]

	def auto_approve_if_policy_allows(self, trust_level: str, confidence: float) -> bool:
		if trust_level == "auto" and confidence >= 0.75:
			return True
		return False

	def expire_stale_approvals(self, now: datetime | None = None) -> int:
		resolved_now = now or datetime.now(timezone.utc)
		expired_count = 0
		for approval in self._approvals.values():
			if approval.status != ApprovalStatus.PENDING or approval.expires_at is None:
				continue
			if approval.expires_at <= resolved_now:
				approval.status = ApprovalStatus.EXPIRED
				expired_count += 1
		return expired_count

	async def expire_stale_approvals_async(self) -> int:
		"""Expire stale approvals using repository."""
		if not self._repo:
			raise RuntimeError("Repository not configured for async operations")
		return await self._repo.expire_stale()

		approval.status = (
			ApprovalStatus.APPROVED if resolved.startswith("approve") else ApprovalStatus.REJECTED
		)
		approval.decision_reason = reason
		return ApprovalResult(
			approval_id=approval_id,
			status=approval.status,
			decided_at=datetime.now(timezone.utc),
			reason=reason,
		)

	def list_pending(self, workflow_id: str | None = None) -> list[ApprovalRequest]:
		pending = [approval for approval in self._approvals.values() if approval.status == ApprovalStatus.PENDING]
		if workflow_id is None:
			return pending
		return [approval for approval in pending if approval.workflow_id == workflow_id]

	def batch_approve(self, approval_ids: list[str], reason: str | None = None) -> list[ApprovalResult]:
		return [self.resolve_approval(approval_id, "approved", reason) for approval_id in approval_ids]

	def auto_approve_if_policy_allows(self, trust_level: str, confidence: float) -> bool:
		if trust_level == "auto" and confidence >= 0.75:
			return True
		return False

	def expire_stale_approvals(self, now: datetime | None = None) -> int:
		resolved_now = now or datetime.now(timezone.utc)
		expired_count = 0
		for approval in self._approvals.values():
			if approval.status != ApprovalStatus.PENDING or approval.expires_at is None:
				continue
			if approval.expires_at <= resolved_now:
				approval.status = ApprovalStatus.EXPIRED
				expired_count += 1
		return expired_count
