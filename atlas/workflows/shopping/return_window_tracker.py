"""Workflow #97: Return Window Tracker — Phase 1 Priority.
Tracks return/exchange deadlines for recent purchases.
Recommended phase: 1 (quick_win_score: 13) | Trust level: auto | Category: shopping
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class ReturnStatus(str, Enum):
	"""Status of a return window."""

	ACTIVE = "active"
	DUE_SOON = "due_soon"
	EXPIRED = "expired"
	RETURNED = "returned"
	KEPT = "kept"


@dataclass(slots=True)
class ReturnWindow:
	"""A tracked return window for a purchase."""

	item_id: str
	item_name: str
	retailer: str
	purchase_date: date
	return_deadline: date
	price: float
	condition_notes: str = ""
	status: ReturnStatus = ReturnStatus.ACTIVE

	@property
	def days_remaining(self) -> int:
		"""Days until return deadline (negative = expired)."""
		return (self.return_deadline - date.today()).days


@dataclass(frozen=True, slots=True)
class ReturnWindowSummary:
	"""Summary of tracked return windows."""

	total_tracked: int
	active: int
	due_soon: int
	expired: int
	total_value_at_risk: float


class ReturnWindowTrackerService(PersistenceMixin):
	"""Service for tracking return/exchange deadlines."""

	DUE_SOON_DAYS: int = 5

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._windows: dict[str, ReturnWindow] = {}

	def add_return_window(
		self,
		item_id: str,
		item_name: str,
		retailer: str,
		purchase_date: date,
		return_window_days: int,
		price: float,
		condition_notes: str = "",
	) -> ReturnWindow:
		"""Add a new purchase to return window tracking."""
		deadline = purchase_date + timedelta(days=return_window_days)
		rw = ReturnWindow(
			item_id=item_id,
			item_name=item_name,
			retailer=retailer,
			purchase_date=purchase_date,
			return_deadline=deadline,
			price=price,
			condition_notes=condition_notes,
		)
		rw.status = self._compute_status(rw)
		self._windows[item_id] = rw
		return rw

	def mark_returned(self, item_id: str) -> bool:
		"""Mark an item as returned."""
		if item_id not in self._windows:
			return False
		self._windows[item_id].status = ReturnStatus.RETURNED
		return True

	def mark_kept(self, item_id: str) -> bool:
		"""Mark an item as kept (no return needed)."""
		if item_id not in self._windows:
			return False
		self._windows[item_id].status = ReturnStatus.KEPT
		return True

	def get_due_soon(self) -> list[ReturnWindow]:
		"""Return windows expiring within the alert threshold."""
		self._refresh_statuses()
		return [w for w in self._windows.values() if w.status == ReturnStatus.DUE_SOON]

	def get_summary(self) -> ReturnWindowSummary:
		"""Return a summary of all return windows."""
		self._refresh_statuses()
		active = [w for w in self._windows.values() if w.status in (ReturnStatus.ACTIVE, ReturnStatus.DUE_SOON)]
		due_soon = [w for w in self._windows.values() if w.status == ReturnStatus.DUE_SOON]
		expired = [w for w in self._windows.values() if w.status == ReturnStatus.EXPIRED]
		return ReturnWindowSummary(
			total_tracked=len(self._windows),
			active=len(active),
			due_soon=len(due_soon),
			expired=len(expired),
			total_value_at_risk=sum(w.price for w in active),
		)

	def _compute_status(self, w: ReturnWindow) -> ReturnStatus:
		days = w.days_remaining
		if days < 0:
			return ReturnStatus.EXPIRED
		if days <= self.DUE_SOON_DAYS:
			return ReturnStatus.DUE_SOON
		return ReturnStatus.ACTIVE

	def _refresh_statuses(self) -> None:
		for w in self._windows.values():
			if w.status not in (ReturnStatus.RETURNED, ReturnStatus.KEPT):
				w.status = self._compute_status(w)


class ReturnWindowTrackerAgent(BaseWorkflow):
	"""Workflow for tracking return deadlines on recent purchases."""

	workflow_id = "return_window_tracker"
	name = "Return Window Tracker"
	category = "shopping"
	trust_level = TrustLevel.AUTO

	def __init__(
		self,
		service: ReturnWindowTrackerService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or ReturnWindowTrackerService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Accept a return window check."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Identify windows expiring soon."""
		due_soon = self.service.get_due_soon()
		summary = self.service.get_summary()
		return ActionPlan(
			action_type="alert_return_windows",
			confidence=0.95,
			context={
				"due_soon": len(due_soon),
				"total_active": summary.active,
				"value_at_risk": summary.total_value_at_risk,
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Emit return deadline alerts."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})
		due = plan.context.get("due_soon", 0)
		return ActionResult(
			True,
			f"return window tracker: {due} window(s) expiring soon",
			{**plan.context, "policy": decision.reason},
		)
