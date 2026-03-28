"""Workflow #1: Overdue Text Resurfacer — Phase 1 Priority.

Surfaces stale unanswered messages that need follow-up.
Scans message history for threads where the other party is waiting
for a reply, or where you said you'd do something and haven't.

Recommended phase: 1 (quick_win_score: 11)
Trust level: draft
Category: communication
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class ThreadUrgency(str, Enum):
	"""Urgency level of an overdue thread."""

	LOW = "low"
	MEDIUM = "medium"
	HIGH = "high"
	CRITICAL = "critical"


class ThreadStatus(str, Enum):
	"""Status of an overdue thread."""

	PENDING = "pending"
	DRAFTED = "drafted"
	REPLIED = "replied"
	DISMISSED = "dismissed"


@dataclass(slots=True)
class OverdueThread:
	"""A message thread that needs follow-up."""

	thread_id: str
	contact: str
	last_message_snippet: str
	last_message_date: date
	waiting_on_me: bool  # True = they're waiting on my reply
	urgency: ThreadUrgency
	days_overdue: int
	status: ThreadStatus = ThreadStatus.PENDING
	notes: str = ""


@dataclass(slots=True)
class DraftReply:
	"""A drafted reply for an overdue thread."""

	draft_id: str
	thread_id: str
	suggested_text: str
	confidence: float  # 0.0 - 1.0
	created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class ResurfacerSummary:
	"""Summary of overdue thread scanning."""

	total_scanned: int
	waiting_on_me: int
	waiting_on_them: int
	high_urgency: int
	drafts_ready: int


class OverdueTextResurfacerService(PersistenceMixin):
	"""Service for surfacing stale message threads needing follow-up."""

	DEFAULT_OVERDUE_DAYS: int = 3  # threads >3 days old without reply

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._threads: dict[str, OverdueThread] = {}
		self._drafts: dict[str, DraftReply] = {}

	def add_thread(
		self,
		thread_id: str,
		contact: str,
		last_message_snippet: str,
		last_message_date: date,
		waiting_on_me: bool,
		urgency: ThreadUrgency = ThreadUrgency.MEDIUM,
		notes: str = "",
	) -> OverdueThread:
		"""Add a thread to the overdue tracking list."""
		days_overdue = (date.today() - last_message_date).days
		thread = OverdueThread(
			thread_id=thread_id,
			contact=contact,
			last_message_snippet=last_message_snippet,
			last_message_date=last_message_date,
			waiting_on_me=waiting_on_me,
			urgency=urgency,
			days_overdue=days_overdue,
			notes=notes,
		)
		self._threads[thread_id] = thread
		return thread

	def create_draft(self, thread_id: str, suggested_text: str, confidence: float = 0.7) -> DraftReply | None:
		"""Create a draft reply for an overdue thread."""
		if thread_id not in self._threads:
			return None
		draft_id = f"draft_{thread_id}"
		draft = DraftReply(
			draft_id=draft_id,
			thread_id=thread_id,
			suggested_text=suggested_text,
			confidence=min(max(confidence, 0.0), 1.0),
		)
		self._drafts[draft_id] = draft
		self._threads[thread_id].status = ThreadStatus.DRAFTED
		return draft

	def mark_replied(self, thread_id: str) -> bool:
		"""Mark a thread as replied to."""
		if thread_id not in self._threads:
			return False
		self._threads[thread_id].status = ThreadStatus.REPLIED
		return True

	def dismiss(self, thread_id: str) -> bool:
		"""Dismiss a thread from follow-up tracking."""
		if thread_id not in self._threads:
			return False
		self._threads[thread_id].status = ThreadStatus.DISMISSED
		return True

	def get_pending_threads(self) -> list[OverdueThread]:
		"""Return threads still waiting for action."""
		return [
			t for t in self._threads.values()
			if t.status in (ThreadStatus.PENDING, ThreadStatus.DRAFTED)
		]

	def get_summary(self) -> ResurfacerSummary:
		"""Return summary of thread scan results."""
		active = [t for t in self._threads.values() if t.status not in (ThreadStatus.REPLIED, ThreadStatus.DISMISSED)]
		return ResurfacerSummary(
			total_scanned=len(self._threads),
			waiting_on_me=len([t for t in active if t.waiting_on_me]),
			waiting_on_them=len([t for t in active if not t.waiting_on_me]),
			high_urgency=len([t for t in active if t.urgency in (ThreadUrgency.HIGH, ThreadUrgency.CRITICAL)]),
			drafts_ready=len(self._drafts),
		)


class OverdueTextResurfacerWorkflow(BaseWorkflow):
	"""Workflow for surfacing stale message threads needing follow-up."""

	workflow_id = "overdue_text_resurfacer"
	name = "Overdue Text Resurfacer"
	category = "communication"
	trust_level = TrustLevel.DRAFT

	def __init__(
		self,
		service: OverdueTextResurfacerService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or OverdueTextResurfacerService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Accept a thread-scan request."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Identify threads needing follow-up."""
		pending = self.service.get_pending_threads()
		summary = self.service.get_summary()
		return ActionPlan(
			action_type="resurface_overdue_threads",
			confidence=0.80,
			context={
				"pending": len(pending),
				"waiting_on_me": summary.waiting_on_me,
				"waiting_on_them": summary.waiting_on_them,
				"high_urgency": summary.high_urgency,
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Surface overdue threads for user action."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})
		waiting = plan.context.get("waiting_on_me", 0)
		high = plan.context.get("high_urgency", 0)
		return ActionResult(
			True,
			f"overdue text resurfacer: {waiting} waiting on me, {high} high urgency",
			{**plan.context, "policy": decision.reason},
		)
