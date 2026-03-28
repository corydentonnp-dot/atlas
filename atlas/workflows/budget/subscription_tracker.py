"""Workflow #37: Subscription Tracker.

Tracks recurring subscriptions, renewal dates, cancellation timing, and monthly burn.
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
	"""Subscription cadence."""

	MONTHLY = "monthly"
	QUARTERLY = "quarterly"
	ANNUAL = "annual"


class SubscriptionStatus(str, Enum):
	"""Lifecycle state for a subscription."""

	ACTIVE = "active"
	CANCEL_SCHEDULED = "cancel_scheduled"
	CANCELLED = "cancelled"
	EXPIRED = "expired"


@dataclass(slots=True)
class Subscription:
	"""Recurring subscription record."""

	subscription_id: str
	vendor: str
	service_name: str
	amount: float
	billing_cycle: BillingCycle
	renewal_date: date
	auto_renews: bool = True
	status: SubscriptionStatus = SubscriptionStatus.ACTIVE
	category: str = "general"
	notes: str = ""


@dataclass(frozen=True, slots=True)
class SubscriptionAlert:
	"""Alert for upcoming renewal or cancellation deadline."""

	subscription_id: str
	vendor: str
	service_name: str
	days_remaining: int
	auto_renews: bool
	status: SubscriptionStatus


class SubscriptionTrackerService(PersistenceMixin):
	"""Service for recurring subscription monitoring."""

	CYCLE_TO_MONTHS: dict[BillingCycle, int] = {
		BillingCycle.MONTHLY: 1,
		BillingCycle.QUARTERLY: 3,
		BillingCycle.ANNUAL: 12,
	}

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._subscriptions: dict[str, Subscription] = {}

	def add_subscription(self, subscription: Subscription) -> Subscription:
		"""Track a subscription."""
		self._subscriptions[subscription.subscription_id] = subscription
		return subscription

	def upcoming_renewals(self, today: date, days_ahead: int = 30) -> list[SubscriptionAlert]:
		"""Find subscriptions renewing soon."""
		alerts: list[SubscriptionAlert] = []
		for subscription in self._subscriptions.values():
			if subscription.status in {SubscriptionStatus.CANCELLED, SubscriptionStatus.EXPIRED}:
				continue
			days_remaining = (subscription.renewal_date - today).days
			if days_remaining < 0:
				subscription.status = SubscriptionStatus.EXPIRED
				continue
			if days_remaining <= days_ahead:
				alerts.append(
					SubscriptionAlert(
						subscription_id=subscription.subscription_id,
						vendor=subscription.vendor,
						service_name=subscription.service_name,
						days_remaining=days_remaining,
						auto_renews=subscription.auto_renews,
						status=subscription.status,
					)
				)
		alerts.sort(key=lambda alert: alert.days_remaining)
		return alerts

	def estimate_monthly_spend(self) -> float:
		"""Normalize all active subscriptions to a monthly burn rate."""
		total = 0.0
		for subscription in self._subscriptions.values():
			if subscription.status in {SubscriptionStatus.CANCELLED, SubscriptionStatus.EXPIRED}:
				continue
			months = self.CYCLE_TO_MONTHS[subscription.billing_cycle]
			total += subscription.amount / months
		return round(total, 2)

	def mark_cancel_scheduled(self, subscription_id: str) -> bool:
		"""Mark a subscription for cancellation."""
		subscription = self._subscriptions.get(subscription_id)
		if subscription is None:
			return False
		subscription.status = SubscriptionStatus.CANCEL_SCHEDULED
		return True


class SubscriptionTrackerWorkflow(BaseWorkflow):
	"""Workflow for subscription renewal warnings."""

	workflow_id = "subscription_tracker"
	name = "subscription_tracker"
	category = "budget"
	trust_level = TrustLevel.AUTO

	def __init__(self, service: SubscriptionTrackerService | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = service or SubscriptionTrackerService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		if event.event_type == "subscription_added":
			payload = event.payload
			self.service.add_subscription(
				Subscription(
					subscription_id=str(payload.get("subscription_id", "")),
					vendor=str(payload.get("vendor", "")),
					service_name=str(payload.get("service_name", "")),
					amount=float(payload.get("amount", 0)),
					billing_cycle=BillingCycle(str(payload.get("billing_cycle", "monthly"))),
					renewal_date=date.fromisoformat(str(payload.get("renewal_date", date.today().isoformat()))),
					auto_renews=bool(payload.get("auto_renews", True)),
					category=str(payload.get("category", "general")),
				)
			)
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		today = date.fromisoformat(str(run.event.payload.get("today", date.today().isoformat())))
		alerts = self.service.upcoming_renewals(today=today)
		return ActionPlan(
			action_type="review_subscriptions",
			confidence=0.9 if alerts else 0.72,
			context={
				"alert_count": len(alerts),
				"monthly_burn": self.service.estimate_monthly_spend(),
				"alerts": [
					{
						"vendor": alert.vendor,
						"service_name": alert.service_name,
						"days_remaining": alert.days_remaining,
						"status": alert.status.value,
						"auto_renews": alert.auto_renews,
					}
					for alert in alerts
				],
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
		count = int(plan.context.get("alert_count", 0))
		summary = f"Prepared {count} subscription renewal reminder(s)" if count else "No subscription renewals due"
		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
