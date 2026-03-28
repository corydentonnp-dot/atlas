"""Workflow #33: Amazon Split Agent — splits Amazon orders for shared expense settlement.

Analyzes Amazon orders and categorizes items as personal, shared household, or business,
then calculates settlement amounts for shared expenses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class ItemCategory(str, Enum):
	"""Item categorization."""

	PERSONAL = "personal"
	HOUSEHOLD_SHARED = "household_shared"
	BUSINESS = "business"


class SettlementStatus(str, Enum):
	"""Settlement tracking status."""

	PENDING = "pending"
	REQUESTED = "requested"
	PAID = "paid"
	DISPUTED = "disputed"


@dataclass(slots=True)
class AmazonItem:
	"""Individual item from Amazon order."""

	item_id: str
	sku: str
	title: str
	price: float
	quantity: int
	category: ItemCategory = ItemCategory.PERSONAL


@dataclass(slots=True)
class AmazonOrder:
	"""Amazon order record."""

	order_id: str
	order_date: date
	total_amount: float
	items: list[AmazonItem]


@dataclass(frozen=True, slots=True)
class ExpenseSettlement:
	"""Calculated settlement for shared expenses."""

	order_id: str
	shared_amount: float
	your_share: float
	roommate_share: float
	settlement_status: SettlementStatus
	notes: str


class AmazonSplitService(PersistenceMixin):
	"""Service for Amazon order splitting and settlement."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._orders: dict[str, AmazonOrder] = {}
		self._settlements: dict[str, ExpenseSettlement] = {}

	def add_order(self, order: AmazonOrder) -> AmazonOrder:
		"""Register an Amazon order for splitting."""
		self._orders[order.order_id] = order
		return order

	def categorize_items(self, order_id: str, item_categories: dict[str, ItemCategory]) -> AmazonOrder | None:
		"""Update item categorization for an order."""
		order = self._orders.get(order_id)
		if not order:
			return None

		for item in order.items:
			if item.item_id in item_categories:
				item.category = item_categories[item.item_id]

		return order

	def calculate_settlement(self, order_id: str, split_percent: float = 0.5) -> ExpenseSettlement | None:
		"""Calculate settlement for shared items."""
		order = self._orders.get(order_id)
		if not order:
			return None

		shared_amount = sum(item.price * item.quantity for item in order.items if item.category == ItemCategory.HOUSEHOLD_SHARED)
		your_share = shared_amount * split_percent
		roommate_share = shared_amount * (1 - split_percent)

		settlement = ExpenseSettlement(
			order_id=order_id,
			shared_amount=shared_amount,
			your_share=your_share,
			roommate_share=roommate_share,
			settlement_status=SettlementStatus.PENDING,
			notes=f"Split {len([i for i in order.items if i.category == ItemCategory.HOUSEHOLD_SHARED])} shared items",
		)

		self._settlements[order_id] = settlement
		return settlement

	def get_pending_settlements(self) -> list[ExpenseSettlement]:
		"""Get all pending settlements."""
		return [s for s in self._settlements.values() if s.settlement_status == SettlementStatus.PENDING]


class AmazonSplitWorkflow(BaseWorkflow):
	"""Workflow for Amazon order splitting and settlement."""

	workflow_id = "amazon_split"
	name = "Amazon Split Agent"
	category = "budget"
	trust_level = TrustLevel.DRAFT

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = AmazonSplitService(session)

	def describe(self) -> str:
		return "Split Amazon orders and calculate expense settlements for shared items."

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle order events."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Plan order splitting."""
		pending = self.service.get_pending_settlements()

		return ActionPlan(
			action_type="split_orders",
			confidence=0.85,
			context={
				"pending_settlements": len(pending),
				"total_orders": len(self.service._orders),
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute order splitting."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		self.state_machine.transition("completed", {"reason": "splitting_complete"})

		return ActionResult(
			success=True,
			summary=f"Processed {plan.context.get('total_orders', 0)} orders",
			metadata=plan.context,
		)
