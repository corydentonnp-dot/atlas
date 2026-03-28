"""Workflow #92: Coupon Aggregator — Phase 2 Priority.
Collects and organizes available coupons and promo codes for upcoming purchases.
Recommended phase: 2 (quick_win_score: 10) | Trust level: auto | Category: shopping
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class CouponSource(str, Enum):
	EMAIL = "email"
	WEB = "web"
	APP = "app"
	CARD_OFFER = "card_offer"
	STORE = "store"


class CouponStatus(str, Enum):
	ACTIVE = "active"
	APPLIED = "applied"
	EXPIRED = "expired"


@dataclass(slots=True)
class Coupon:
	coupon_id: str
	merchant: str
	code: str
	discount_pct: float
	expires_on: date
	source: CouponSource
	min_spend: float = 0.0
	status: CouponStatus = CouponStatus.ACTIVE

	def is_active(self) -> bool:
		return self.status == CouponStatus.ACTIVE and self.expires_on >= date.today()


@dataclass(frozen=True, slots=True)
class CouponSummary:
	total_tracked: int
	active: int
	expiring_soon: int
	applied: int


class CouponAggregatorService(PersistenceMixin):
	EXPIRING_SOON_DAYS = 7

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._coupons: dict[str, Coupon] = {}

	def add_coupon(
		self,
		coupon_id: str,
		merchant: str,
		code: str,
		discount_pct: float,
		expires_on: date,
		source: CouponSource,
		min_spend: float = 0.0,
	) -> Coupon:
		coupon = Coupon(
			coupon_id=coupon_id,
			merchant=merchant,
			code=code,
			discount_pct=discount_pct,
			expires_on=expires_on,
			source=source,
			min_spend=min_spend,
		)
		if coupon.expires_on < date.today():
			coupon.status = CouponStatus.EXPIRED
		self._coupons[coupon_id] = coupon
		return coupon

	def mark_applied(self, coupon_id: str) -> bool:
		if coupon_id not in self._coupons:
			return False
		self._coupons[coupon_id].status = CouponStatus.APPLIED
		return True

	def get_active(self) -> list[Coupon]:
		self._refresh_statuses()
		return [c for c in self._coupons.values() if c.status == CouponStatus.ACTIVE]

	def get_best_for_merchant(self, merchant: str, subtotal: float) -> Coupon | None:
		eligible = [
			c for c in self.get_active()
			if c.merchant.lower() == merchant.lower() and subtotal >= c.min_spend
		]
		return max(eligible, key=lambda c: c.discount_pct, default=None)

	def get_summary(self) -> CouponSummary:
		self._refresh_statuses()
		vals = list(self._coupons.values())
		return CouponSummary(
			total_tracked=len(vals),
			active=len([c for c in vals if c.status == CouponStatus.ACTIVE]),
			expiring_soon=len([c for c in vals if c.status == CouponStatus.ACTIVE and 0 <= (c.expires_on - date.today()).days <= self.EXPIRING_SOON_DAYS]),
			applied=len([c for c in vals if c.status == CouponStatus.APPLIED]),
		)

	def _refresh_statuses(self) -> None:
		for coupon in self._coupons.values():
			if coupon.status == CouponStatus.ACTIVE and coupon.expires_on < date.today():
				coupon.status = CouponStatus.EXPIRED


class CouponAggregatorWorkflow(BaseWorkflow):
	workflow_id = "coupon_aggregator"
	name = "Coupon Aggregator"
	category = "shopping"
	trust_level = TrustLevel.AUTO

	def __init__(
		self,
		service: CouponAggregatorService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or CouponAggregatorService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		summary = self.service.get_summary()
		return ActionPlan(
			action_type="surface_best_coupons",
			confidence=0.93,
			context={
				"total_tracked": summary.total_tracked,
				"active": summary.active,
				"expiring_soon": summary.expiring_soon,
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})
		return ActionResult(
			True,
			f"coupon aggregator: {plan.context.get('active', 0)} active coupon(s)",
			{**plan.context, "policy": decision.reason},
		)
