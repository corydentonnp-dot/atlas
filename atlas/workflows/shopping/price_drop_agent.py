"""Workflow #91: Price Drop Agent — Phase 1 Priority.
Monitors product prices and alerts when items drop below target thresholds.
Recommended phase: 1 (quick_win_score: 14) | Trust level: auto | Category: shopping
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class DropStatus(str, Enum):
	"""Status of a tracked price item."""

	WATCHING = "watching"
	DROP_DETECTED = "drop_detected"
	ALERTED = "alerted"
	PURCHASED = "purchased"
	EXPIRED = "expired"


@dataclass(slots=True)
class TrackedProduct:
	"""A product being price-monitored."""

	product_id: str
	name: str
	url: str
	target_price: float
	baseline_price: float
	current_price: float
	category: str = ""
	status: DropStatus = DropStatus.WATCHING
	notes: str = ""
	last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

	@property
	def savings(self) -> float:
		"""Dollar savings vs baseline."""
		return max(self.baseline_price - self.current_price, 0.0)

	@property
	def is_at_target(self) -> bool:
		"""Whether current price is at or below target."""
		return self.current_price <= self.target_price


@dataclass(frozen=True, slots=True)
class PriceDropSummary:
	"""Summary of price monitoring activity."""

	total_watching: int
	drops_detected: int
	at_or_below_target: int
	total_potential_savings: float
	best_deal_name: str
	best_deal_savings: float


class PriceDropService(PersistenceMixin):
	"""Service for tracking product prices and detecting drops."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._products: dict[str, TrackedProduct] = {}

	def add_product(
		self,
		product_id: str,
		name: str,
		url: str,
		target_price: float,
		baseline_price: float,
		category: str = "",
		notes: str = "",
	) -> TrackedProduct:
		"""Add a product to price monitoring."""
		product = TrackedProduct(
			product_id=product_id,
			name=name,
			url=url,
			target_price=target_price,
			baseline_price=baseline_price,
			current_price=baseline_price,
			category=category,
			notes=notes,
		)
		self._products[product_id] = product
		return product

	def update_price(self, product_id: str, new_price: float) -> TrackedProduct | None:
		"""Update current price; flag if at/below target."""
		if product_id not in self._products:
			return None
		p = self._products[product_id]
		p.current_price = new_price
		p.last_updated = datetime.now(timezone.utc)
		if p.is_at_target and p.status == DropStatus.WATCHING:
			p.status = DropStatus.DROP_DETECTED
		return p

	def mark_purchased(self, product_id: str) -> bool:
		"""Mark a product as purchased."""
		if product_id not in self._products:
			return False
		self._products[product_id].status = DropStatus.PURCHASED
		return True

	def get_deals(self) -> list[TrackedProduct]:
		"""Return products currently at or below target price."""
		return [p for p in self._products.values() if p.status in (DropStatus.DROP_DETECTED, DropStatus.ALERTED)]

	def get_summary(self) -> PriceDropSummary:
		"""Return a summary of all price monitoring."""
		watching = [p for p in self._products.values() if p.status != DropStatus.EXPIRED]
		drops = self.get_deals()
		at_target = [p for p in watching if p.is_at_target]
		best = max(drops, key=lambda p: p.savings, default=None)
		return PriceDropSummary(
			total_watching=len(watching),
			drops_detected=len(drops),
			at_or_below_target=len(at_target),
			total_potential_savings=sum(p.savings for p in at_target),
			best_deal_name=best.name if best else "",
			best_deal_savings=best.savings if best else 0.0,
		)


class PriceDropAgent(BaseWorkflow):
	"""Workflow for monitoring product prices and alerting on drops."""

	workflow_id = "price_drop"
	name = "Price Drop Agent"
	category = "shopping"
	trust_level = TrustLevel.AUTO

	def __init__(
		self,
		service: PriceDropService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or PriceDropService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Accept a price-check request."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Identify products currently at or below target price."""
		deals = self.service.get_deals()
		summary = self.service.get_summary()
		return ActionPlan(
			action_type="alert_price_drops",
			confidence=0.92,
			context={
				"drops_detected": len(deals),
				"total_savings": summary.total_potential_savings,
				"best_deal": summary.best_deal_name,
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Emit price drop alerts."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})
		drops = plan.context.get("drops_detected", 0)
		return ActionResult(
			True,
			f"price drop agent: {drops} deal(s) at or below target price",
			{**plan.context, "policy": decision.reason},
		)
