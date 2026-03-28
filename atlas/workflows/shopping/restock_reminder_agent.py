"""Workflow #98: Restock Reminder Agent — Phase 2 Priority.
Reminds when consumables (filters, medications, household supplies) need reordering.
Recommended phase: 2 (quick_win_score: 11) | Trust level: auto | Category: shopping
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class RestockCategory(str, Enum):
	"""Category of consumable item."""

	MEDICATION = "medication"
	HVAC_FILTER = "hvac_filter"
	HOUSEHOLD = "household"
	PET = "pet"
	PRODUCE = "produce"
	PERSONAL_CARE = "personal_care"
	OFFICE = "office"
	OTHER = "other"


class RestockStatus(str, Enum):
	"""Status of a restock item."""

	IN_STOCK = "in_stock"
	DUE_SOON = "due_soon"
	OVERDUE = "overdue"
	ORDERED = "ordered"


@dataclass(slots=True)
class RestockItem:
	"""A tracked consumable item."""

	item_id: str
	name: str
	category: RestockCategory
	last_restocked: date
	restock_interval_days: int  # how often to reorder
	quantity_on_hand: int = 1
	notes: str = ""
	status: RestockStatus = RestockStatus.IN_STOCK

	@property
	def next_due_date(self) -> date:
		"""Date when restock is due."""
		return self.last_restocked + timedelta(days=self.restock_interval_days)

	@property
	def days_until_due(self) -> int:
		"""Days until restock is due (negative = overdue)."""
		return (self.next_due_date - date.today()).days


@dataclass(frozen=True, slots=True)
class RestockSummary:
	"""Summary of restock tracking."""

	total_tracked: int
	due_soon: int
	overdue: int
	in_stock: int
	most_urgent_item: str


class RestockReminderService(PersistenceMixin):
	"""Service for tracking and reminding about consumable restocks."""

	DUE_SOON_DAYS: int = 7  # alert when within 7 days

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._items: dict[str, RestockItem] = {}

	def add_item(
		self,
		item_id: str,
		name: str,
		category: RestockCategory,
		last_restocked: date,
		restock_interval_days: int,
		quantity_on_hand: int = 1,
		notes: str = "",
	) -> RestockItem:
		"""Add a consumable item to track."""
		item = RestockItem(
			item_id=item_id,
			name=name,
			category=category,
			last_restocked=last_restocked,
			restock_interval_days=restock_interval_days,
			quantity_on_hand=quantity_on_hand,
			notes=notes,
		)
		item.status = self._compute_status(item)
		self._items[item_id] = item
		return item

	def record_restock(self, item_id: str, new_quantity: int = 1) -> bool:
		"""Record a restock event, resetting the interval clock."""
		if item_id not in self._items:
			return False
		item = self._items[item_id]
		item.last_restocked = date.today()
		item.quantity_on_hand = new_quantity
		item.status = RestockStatus.IN_STOCK
		return True

	def mark_ordered(self, item_id: str) -> bool:
		"""Mark an item as ordered (in transit)."""
		if item_id not in self._items:
			return False
		self._items[item_id].status = RestockStatus.ORDERED
		return True

	def get_due_items(self) -> list[RestockItem]:
		"""Return items that are due soon or overdue."""
		self._refresh_statuses()
		return [
			i for i in self._items.values()
			if i.status in (RestockStatus.DUE_SOON, RestockStatus.OVERDUE)
		]

	def get_summary(self) -> RestockSummary:
		"""Return a summary of all tracked consumables."""
		self._refresh_statuses()
		overdue = [i for i in self._items.values() if i.status == RestockStatus.OVERDUE]
		due_soon = [i for i in self._items.values() if i.status == RestockStatus.DUE_SOON]
		in_stock = [i for i in self._items.values() if i.status == RestockStatus.IN_STOCK]
		urgent = min(overdue + due_soon, key=lambda i: i.days_until_due, default=None)
		return RestockSummary(
			total_tracked=len(self._items),
			due_soon=len(due_soon),
			overdue=len(overdue),
			in_stock=len(in_stock),
			most_urgent_item=urgent.name if urgent else "",
		)

	def _compute_status(self, item: RestockItem) -> RestockStatus:
		"""Compute the current status of an item based on dates."""
		days = item.days_until_due
		if days < 0:
			return RestockStatus.OVERDUE
		if days <= self.DUE_SOON_DAYS:
			return RestockStatus.DUE_SOON
		return RestockStatus.IN_STOCK

	def _refresh_statuses(self) -> None:
		"""Recompute statuses for all non-ordered items."""
		for item in self._items.values():
			if item.status != RestockStatus.ORDERED:
				item.status = self._compute_status(item)


class RestockReminderAgent(BaseWorkflow):
	"""Workflow for reminding about consumable restock deadlines."""

	workflow_id = "restock_reminder"
	name = "Restock Reminder Agent"
	category = "shopping"
	trust_level = TrustLevel.AUTO

	def __init__(
		self,
		service: RestockReminderService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or RestockReminderService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Accept a restock-check request."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Identify items due for restocking."""
		due = self.service.get_due_items()
		summary = self.service.get_summary()
		return ActionPlan(
			action_type="send_restock_reminders",
			confidence=0.90,
			context={
				"due_count": len(due),
				"overdue": summary.overdue,
				"due_soon": summary.due_soon,
				"most_urgent": summary.most_urgent_item,
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Surface restock reminders."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})
		due_soon = plan.context.get("due_soon", 0)
		overdue = plan.context.get("overdue", 0)
		return ActionResult(
			True,
			f"restock reminder: {due_soon} due soon, {overdue} overdue",
			{**plan.context, "policy": decision.reason},
		)
