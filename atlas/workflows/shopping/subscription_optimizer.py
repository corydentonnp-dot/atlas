"""Workflow #93: Subscription Optimizer — Phase 2 Priority.
Tracks all active subscriptions; identifies unused, redundant, or cancellable services.
Recommended phase: 2 (quick_win_score: 12) | Trust level: suggest | Category: shopping
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class BillingCycle(str, Enum):
	"""Subscription billing cycle."""

	MONTHLY = "monthly"
	ANNUAL = "annual"
	QUARTERLY = "quarterly"
	WEEKLY = "weekly"


class SubStatus(str, Enum):
	"""Status of a subscription."""

	ACTIVE = "active"
	CANCEL_CANDIDATE = "cancel_candidate"
	CANCELLED = "cancelled"
	PAUSED = "paused"


@dataclass(slots=True)
class Subscription:
	"""A tracked subscription."""

	sub_id: str
	name: str
	monthly_cost: float
	billing_cycle: BillingCycle
	next_renewal: date
	category: str
	used_in_last_30_days: bool = True
	have_duplicate: bool = False
	status: SubStatus = SubStatus.ACTIVE
	notes: str = ""

	@property
	def annual_cost(self) -> float:
		"""Annualized cost of the subscription."""
		if self.billing_cycle == BillingCycle.MONTHLY:
			return self.monthly_cost * 12
		if self.billing_cycle == BillingCycle.ANNUAL:
			return self.monthly_cost
		if self.billing_cycle == BillingCycle.QUARTERLY:
			return self.monthly_cost * 4
		return self.monthly_cost * 52

	@property
	def days_until_renewal(self) -> int:
		"""Days until subscription renews."""
		return (self.next_renewal - date.today()).days


@dataclass(frozen=True, slots=True)
class SubscriptionSummary:
	"""Summary of subscription audit."""

	total_active: int
	total_monthly_spend: float
	total_annual_spend: float
	cancel_candidates: int
	annual_savings_if_cancelled: float
	renewing_this_week: int


class SubscriptionOptimizerService(PersistenceMixin):
	"""Service for tracking and optimizing subscription spend."""

	RENEWING_SOON_DAYS: int = 7

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._subs: dict[str, Subscription] = {}

	def add_subscription(
		self,
		sub_id: str,
		name: str,
		monthly_cost: float,
		billing_cycle: BillingCycle,
		next_renewal: date,
		category: str,
		used_in_last_30_days: bool = True,
		have_duplicate: bool = False,
		notes: str = "",
	) -> Subscription:
		"""Add a subscription to tracking."""
		sub = Subscription(
			sub_id=sub_id,
			name=name,
			monthly_cost=monthly_cost,
			billing_cycle=billing_cycle,
			next_renewal=next_renewal,
			category=category,
			used_in_last_30_days=used_in_last_30_days,
			have_duplicate=have_duplicate,
			notes=notes,
		)
		if not sub.used_in_last_30_days or sub.have_duplicate:
			sub.status = SubStatus.CANCEL_CANDIDATE
		self._subs[sub_id] = sub
		return sub

	def mark_cancelled(self, sub_id: str) -> bool:
		"""Mark a subscription as cancelled."""
		if sub_id not in self._subs:
			return False
		self._subs[sub_id].status = SubStatus.CANCELLED
		return True

	def get_cancel_candidates(self) -> list[Subscription]:
		"""Return subscriptions flagged for potential cancellation."""
		return [s for s in self._subs.values() if s.status == SubStatus.CANCEL_CANDIDATE]

	def get_renewing_soon(self) -> list[Subscription]:
		"""Return subscriptions renewing within RENEWING_SOON_DAYS."""
		return [
			s for s in self._subs.values()
			if s.status == SubStatus.ACTIVE and 0 <= s.days_until_renewal <= self.RENEWING_SOON_DAYS
		]

	def get_summary(self) -> SubscriptionSummary:
		"""Return summary of subscription audit."""
		active = [s for s in self._subs.values() if s.status in (SubStatus.ACTIVE, SubStatus.CANCEL_CANDIDATE)]
		candidates = self.get_cancel_candidates()
		renewing = self.get_renewing_soon()
		return SubscriptionSummary(
			total_active=len(active),
			total_monthly_spend=sum(s.monthly_cost for s in active),
			total_annual_spend=sum(s.annual_cost for s in active),
			cancel_candidates=len(candidates),
			annual_savings_if_cancelled=sum(s.annual_cost for s in candidates),
			renewing_this_week=len(renewing),
		)


class SubscriptionOptimizerAgent(BaseWorkflow):
	"""Workflow for tracking and optimizing subscription spend."""

	workflow_id = "subscription_optimizer"
	name = "Subscription Optimizer"
	category = "shopping"
	trust_level = TrustLevel.DRAFT

	def __init__(
		self,
		service: SubscriptionOptimizerService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or SubscriptionOptimizerService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Accept a subscription audit request."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Identify cancellation candidates and renewing subscriptions."""
		summary = self.service.get_summary()
		return ActionPlan(
			action_type="optimize_subscriptions",
			confidence=0.85,
			context={
				"cancel_candidates": summary.cancel_candidates,
				"monthly_spend": summary.total_monthly_spend,
				"annual_savings": summary.annual_savings_if_cancelled,
				"renewing_soon": summary.renewing_this_week,
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Surface optimization recommendations."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})
		candidates = plan.context.get("cancel_candidates", 0)
		savings = plan.context.get("annual_savings", 0.0)
		return ActionResult(
			True,
			f"subscription optimizer: {candidates} cancel candidate(s), ${savings:.0f}/yr potential savings",
			{**plan.context, "policy": decision.reason},
		)
