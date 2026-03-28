"""Workflow #12: Promise Tracker — Phase 1 Priority.

Extracts commitments/promises made in messages and tracks them
so nothing falls through the cracks.

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


class PromiseStatus(str, Enum):
	"""Status of a tracked promise."""

	PENDING = "pending"
	IN_PROGRESS = "in_progress"
	OVERDUE = "overdue"
	RESOLVED = "resolved"
	DISMISSED = "dismissed"


class PromiseDirection(str, Enum):
	"""Direction of the promise (who owes whom)."""

	I_PROMISED = "i_promised"     # user made the commitment
	THEY_PROMISED = "they_promised"  # other party made the commitment


@dataclass(slots=True)
class Promise:
	"""A tracked commitment extracted from a message."""

	promise_id: str
	text: str  # the promise text
	made_by: str  # contact name or 'me'
	made_to: str  # recipient
	direction: PromiseDirection
	due_date: date | None
	source_context: str  # e.g. 'SMS thread with Mom'
	status: PromiseStatus = PromiseStatus.PENDING
	created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# Keywords that suggest a promise was made
_PROMISE_KEYWORDS = (
	"i will", "i'll", "i can", "i'll get", "i'll send", "i'll do",
	"i promise", "i'll make sure", "i'll follow up", "i'll check",
	"let me", "don't worry", "i've got", "count on me",
)
_THEY_KEYWORDS = (
	"they said", "he said", "she said", "they'll", "he'll", "she'll",
	"they will", "they promised", "confirmed",
)


@dataclass(frozen=True, slots=True)
class PromiseSummary:
	"""Summary of tracked promises."""

	total: int
	pending: int
	overdue: int
	resolved: int
	my_promises: int
	their_promises: int


class PromiseTrackerService(PersistenceMixin):
	"""Service for capturing and tracking commitments."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._promises: dict[str, Promise] = {}

	def capture_promise(
		self,
		promise_id: str,
		text: str,
		made_by: str,
		made_to: str,
		source_context: str,
		due_date: date | None = None,
	) -> Promise:
		"""Manually capture a promise from a message or conversation."""
		direction = PromiseDirection.I_PROMISED if made_by.lower() in ("me", "cory", "user") else PromiseDirection.THEY_PROMISED
		promise = Promise(
			promise_id=promise_id,
			text=text,
			made_by=made_by,
			made_to=made_to,
			direction=direction,
			due_date=due_date,
			source_context=source_context,
		)
		self._promises[promise_id] = promise
		return promise

	def extract_from_text(self, promise_id: str, message: str, contact: str, source_context: str) -> Promise | None:
		"""Detect a promise from free-form message text using keyword matching."""
		lower = message.lower()
		for kw in _PROMISE_KEYWORDS:
			if kw in lower:
				return self.capture_promise(promise_id, message[:200], "me", contact, source_context)
		for kw in _THEY_KEYWORDS:
			if kw in lower:
				return self.capture_promise(promise_id, message[:200], contact, "me", source_context)
		return None

	def mark_resolved(self, promise_id: str) -> bool:
		"""Mark a promise as fulfilled."""
		if promise_id not in self._promises:
			return False
		self._promises[promise_id].status = PromiseStatus.RESOLVED
		return True

	def dismiss(self, promise_id: str) -> bool:
		"""Dismiss a promise as not relevant."""
		if promise_id not in self._promises:
			return False
		self._promises[promise_id].status = PromiseStatus.DISMISSED
		return True

	def get_overdue(self) -> list[Promise]:
		"""Return promises that are past due date and still pending."""
		today = date.today()
		overdue = []
		for p in self._promises.values():
			if p.status == PromiseStatus.PENDING and p.due_date and p.due_date < today:
				p.status = PromiseStatus.OVERDUE
				overdue.append(p)
			elif p.status == PromiseStatus.OVERDUE:
				overdue.append(p)
		return overdue

	def get_pending(self) -> list[Promise]:
		"""Return all pending (non-resolved) promises."""
		return [p for p in self._promises.values() if p.status in (PromiseStatus.PENDING, PromiseStatus.IN_PROGRESS)]

	def get_summary(self) -> PromiseSummary:
		"""Return aggregate summary of promise tracking."""
		overdue = self.get_overdue()
		return PromiseSummary(
			total=len(self._promises),
			pending=len([p for p in self._promises.values() if p.status == PromiseStatus.PENDING]),
			overdue=len(overdue),
			resolved=len([p for p in self._promises.values() if p.status == PromiseStatus.RESOLVED]),
			my_promises=len([p for p in self._promises.values() if p.direction == PromiseDirection.I_PROMISED]),
			their_promises=len([p for p in self._promises.values() if p.direction == PromiseDirection.THEY_PROMISED]),
		)


class PromiseTrackerWorkflow(BaseWorkflow):
	"""Workflow for extracting and tracking commitments from messages."""

	workflow_id = "promise_tracker"
	name = "Promise Tracker"
	category = "communication"
	trust_level = TrustLevel.DRAFT

	def __init__(
		self,
		service: PromiseTrackerService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or PromiseTrackerService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Accept a promise-tracking scan request."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Check for overdue promises."""
		overdue = self.service.get_overdue()
		summary = self.service.get_summary()
		return ActionPlan(
			action_type="surface_overdue_promises",
			confidence=0.80,
			context={
				"overdue": len(overdue),
				"pending": summary.pending,
				"my_promises": summary.my_promises,
				"their_promises": summary.their_promises,
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Surface overdue promises for user review."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})
		pending = plan.context.get("pending", 0)
		overdue = plan.context.get("overdue", 0)
		return ActionResult(
			True,
			f"promise tracker: {pending} pending, {overdue} overdue",
			{**plan.context, "policy": decision.reason},
		)
