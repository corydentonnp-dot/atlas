"""Workflow #94: Grocery List Builder — Phase 2 Priority.
Builds grocery lists from meal plans, recipes, and pantry inventory tracking.
Recommended phase: 2 (quick_win_score: 10) | Trust level: suggest | Category: shopping
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class GrocerySection(str, Enum):
	"""Grocery store section."""

	PRODUCE = "produce"
	MEAT_SEAFOOD = "meat_seafood"
	DAIRY = "dairy"
	FROZEN = "frozen"
	PANTRY = "pantry"
	BEVERAGES = "beverages"
	BREAD_BAKERY = "bread_bakery"
	PERSONAL_CARE = "personal_care"
	HOUSEHOLD = "household"
	OTHER = "other"


class ItemStatus(str, Enum):
	"""Status of a grocery list item."""

	NEEDED = "needed"
	IN_CART = "in_cart"
	PURCHASED = "purchased"
	SKIPPED = "skipped"


@dataclass(slots=True)
class GroceryItem:
	"""An item on the grocery list."""

	item_id: str
	name: str
	section: GrocerySection
	quantity: float
	unit: str
	price_estimate: float = 0.0
	recipe_source: str = ""
	status: ItemStatus = ItemStatus.NEEDED
	notes: str = ""


@dataclass(frozen=True, slots=True)
class CompiledList:
	"""A compiled grocery shopping list."""

	list_id: str
	store: str
	total_items: int
	estimated_total: float
	sections: list[str]


@dataclass(slots=True)
class PantryItem:
	"""An item tracked as on-hand in the pantry."""

	name: str
	quantity: float
	unit: str


class GroceryListBuilderService(PersistenceMixin):
	"""Service for building and managing grocery lists."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._items: dict[str, GroceryItem] = {}
		self._pantry: dict[str, PantryItem] = {}

	def add_item(
		self,
		item_id: str,
		name: str,
		section: GrocerySection,
		quantity: float,
		unit: str,
		price_estimate: float = 0.0,
		recipe_source: str = "",
		notes: str = "",
	) -> GroceryItem:
		"""Add an item to the current grocery list."""
		item = GroceryItem(
			item_id=item_id,
			name=name,
			section=section,
			quantity=quantity,
			unit=unit,
			price_estimate=price_estimate,
			recipe_source=recipe_source,
			notes=notes,
		)
		self._items[item_id] = item
		return item

	def update_pantry(self, name: str, quantity: float, unit: str) -> None:
		"""Update pantry stock for an item."""
		self._pantry[name.lower()] = PantryItem(name=name, quantity=quantity, unit=unit)

	def check_pantry(self, name: str) -> PantryItem | None:
		"""Check if an item is in the pantry."""
		return self._pantry.get(name.lower())

	def mark_in_cart(self, item_id: str) -> bool:
		"""Mark an item as in the cart."""
		if item_id not in self._items:
			return False
		self._items[item_id].status = ItemStatus.IN_CART
		return True

	def mark_purchased(self, item_id: str) -> bool:
		"""Mark an item as purchased and update pantry."""
		if item_id not in self._items:
			return False
		item = self._items[item_id]
		item.status = ItemStatus.PURCHASED
		self.update_pantry(item.name, item.quantity, item.unit)
		return True

	def compile_list(self, list_id: str, store: str = "Grocery") -> CompiledList:
		"""Compile the current needed items into a grocery list."""
		needed = [i for i in self._items.values() if i.status == ItemStatus.NEEDED]
		sections = list({i.section.value for i in needed})
		return CompiledList(
			list_id=list_id,
			store=store,
			total_items=len(needed),
			estimated_total=sum(i.price_estimate for i in needed),
			sections=sections,
		)


class GroceryListBuilderAgent(BaseWorkflow):
	"""Workflow for compiling grocery lists from meal plans and pantry state."""

	workflow_id = "grocery_list_builder"
	name = "Grocery List Builder"
	category = "shopping"
	trust_level = TrustLevel.DRAFT

	def __init__(
		self,
		service: GroceryListBuilderService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or GroceryListBuilderService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Accept a grocery list build request."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Compile the grocery list."""
		grocery_list = self.service.compile_list("current_list")
		return ActionPlan(
			action_type="present_grocery_list",
			confidence=0.88,
			context={
				"item_count": grocery_list.total_items,
				"estimated_total": grocery_list.estimated_total,
				"sections": grocery_list.sections,
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Deliver the grocery list for review."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})
		items = plan.context.get("item_count", 0)
		return ActionResult(
			True,
			f"grocery list builder: {items} item(s) compiled",
			{**plan.context, "policy": decision.reason},
		)
