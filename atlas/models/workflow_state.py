"""Workflow state model for persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, String, Text, Index, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from atlas.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class WorkflowState(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
	"""Persisted state record for any workflow."""

	__tablename__ = "workflow_states"

	workflow_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
	workflow_category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
	operation_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
	state_type: Mapped[str] = mapped_column(String(100), nullable=False)  # 'plan', 'result', 'decision'
	context: Mapped[dict[str, Any]] = mapped_column(
		JSON,
		nullable=False,
		default=dict,
	)
	status: Mapped[str] = mapped_column(String(50), nullable=False, index=True, default="pending")
	result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
	confidence: Mapped[float] = mapped_column(nullable=False, default=0.5)
	expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

	__table_args__ = (
		Index("ix_workflow_states_workflow_operation", "workflow_id", "operation_id"),
		Index("ix_workflow_states_category_status", "workflow_category", "status"),
		Index("ix_workflow_states_expires", "expires_at"),
	)

	def __repr__(self) -> str:
		return f"WorkflowState(workflow_id={self.workflow_id}, state_type={self.state_type}, status={self.status})"
