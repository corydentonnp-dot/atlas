"""SQLAlchemy model for approval requests."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from atlas.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ApprovalStatus(str, Enum):
	"""Approval status enumeration."""

	PENDING = "pending"
	APPROVED = "approved"
	REJECTED = "rejected"
	EXPIRED = "expired"


class Approval(Base, UUIDPrimaryKeyMixin, TimestampMixin):
	"""Approval request record — pending human review or automatic resolution."""

	__tablename__ = "approvals"

	workflow_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
	action_type: Mapped[str] = mapped_column(String(255), nullable=False)
	requester: Mapped[str] = mapped_column(String(255), nullable=False)
	status: Mapped[ApprovalStatus] = mapped_column(String(20), default=ApprovalStatus.PENDING, index=True)
	context: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-serialized context
	expires_at: Mapped[datetime | None] = mapped_column(nullable=True, index=True)
	resolved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
	resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)

	def __repr__(self) -> str:
		return (
			f"<Approval id={self.id} workflow={self.workflow_id} "
			f"action={self.action_type} status={self.status}>"
		)

	@property
	def is_expired(self) -> bool:
		"""Check if approval has expired."""
		if self.expires_at is None:
			return False
		return datetime.utcnow() > self.expires_at

	@property
	def is_pending(self) -> bool:
		"""Check if approval is still pending."""
		return self.status == ApprovalStatus.PENDING and not self.is_expired
