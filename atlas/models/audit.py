"""SQLAlchemy model for audit log entries."""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from atlas.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AuditEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
	"""Audit log entry — records all actions for compliance and visibility."""

	__tablename__ = "audit_entries"

	actor: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
	action: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
	workflow_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
	context: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-serialized context
	result: Mapped[str] = mapped_column(String(50), nullable=False)  # 'success', 'error', etc.
	error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

	def __repr__(self) -> str:
		return (
			f"<AuditEntry id={self.id} actor={self.actor} action={self.action} "
			f"workflow={self.workflow_id} result={self.result}>"
		)
