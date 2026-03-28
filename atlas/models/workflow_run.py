"""SQLAlchemy model for workflow run records."""

from __future__ import annotations

from enum import Enum

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from atlas.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WorkflowRunStatus(str, Enum):
	"""Workflow run status enumeration."""

	STARTED = "started"
	PLANNING = "planning"
	ACTING = "acting"
	COMPLETED = "completed"
	FAILED = "failed"


class WorkflowRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
	"""Workflow run record — tracks execution of a workflow instance."""

	__tablename__ = "workflow_runs"

	workflow_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
	event_type: Mapped[str] = mapped_column(String(255), nullable=False)
	status: Mapped[WorkflowRunStatus] = mapped_column(String(20), default=WorkflowRunStatus.STARTED, index=True)
	input_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-serialized input
	output_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON-serialized output
	error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
	tags: Mapped[str | None] = mapped_column(String(500), nullable=True)  # Space-separated tags for filtering

	def __repr__(self) -> str:
		return (
			f"<WorkflowRun id={self.id} workflow={self.workflow_id} "
			f"status={self.status} created={self.created_at}>"
		)

	@property
	def is_terminal(self) -> bool:
		"""Check if run is in a terminal state."""
		return self.status in (WorkflowRunStatus.COMPLETED, WorkflowRunStatus.FAILED)
