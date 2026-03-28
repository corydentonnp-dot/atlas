"""Workflow #39: Refund Chase Agent — tracks and follows up on pending refunds.

Monitors expected refunds from returns, tax filings, or disputes and sends reminders
when refunds are overdue. Requires approval for outbound contact.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class RefundSource(str, Enum):
	"""Source of expected refund."""

	PRODUCT_RETURN = "product_return"
	TAX_RETURN = "tax_return"
	BILLING_DISPUTE = "billing_dispute"
	INSURANCE_CLAIM = "insurance_claim"
	OVERPAYMENT = "overpayment"


class RefundStatus(str, Enum):
	"""Refund status."""

	PENDING = "pending"
	IN_PROGRESS = "in_progress"
	RECEIVED = "received"
	DISPUTED = "disputed"
	ABANDONED = "abandoned"


@dataclass(slots=True)
class Refund:
	"""Expected refund."""

	refund_id: str
	source: RefundSource
	amount: float
	date_initiated: date
	expected_date: date
	from_party: str
	status: RefundStatus = RefundStatus.PENDING
	notes: str = ""


@dataclass(frozen=True, slots=True)
class RefundReminder:
	"""Reminder about overdue refund."""

	refund_id: str
	from_party: str
	source: RefundSource
	amount: float
	days_overdue: int
	reminder_count: int
	recommended_action: str


class RefundChaseService(PersistenceMixin):
	"""Service for refund tracking and follow-up."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._refunds: dict[str, Refund] = {}
		self._reminders_sent: dict[str, int] = {}  # refund_id -> count

	def add_refund(self, refund: Refund) -> Refund:
		"""Register an expected refund."""
		self._refunds[refund.refund_id] = refund
		return refund

	def check_overdue_refunds(self, today: date | None = None) -> list[RefundReminder]:
		"""Find refunds that are overdue."""
		if today is None:
			today = date.today()

		reminders: list[RefundReminder] = []

		for refund in self._refunds.values():
			if refund.status in (RefundStatus.RECEIVED, RefundStatus.ABANDONED):
				continue

			days_since_expected = (today - refund.expected_date).days

			if days_since_expected > 0:
				reminder_count = self._reminders_sent.get(refund.refund_id, 0)

				# Escalate action based on how overdue
				if days_since_expected > 90:
					action = "File formal dispute or chargeback"
				elif days_since_expected > 60:
					action = "Send final demand letter"
				elif days_since_expected > 30:
					action = "Send formal follow-up email"
				elif days_since_expected > 14:
					action = "Send reminder phone call"
				else:
					action = "Send friendly reminder email"

				reminders.append(
					RefundReminder(
						refund_id=refund.refund_id,
						from_party=refund.from_party,
						source=refund.source,
						amount=refund.amount,
						days_overdue=days_since_expected,
						reminder_count=reminder_count,
						recommended_action=action,
					)
				)

		return reminders

	def mark_refund_received(self, refund_id: str) -> Refund | None:
		"""Mark a refund as received."""
		refund = self._refunds.get(refund_id)
		if refund:
			self._refunds[refund_id].status = RefundStatus.RECEIVED
		return refund

	def get_refund_summary(self) -> dict:
		"""Get summary of refund status."""
		pending = [r for r in self._refunds.values() if r.status == RefundStatus.PENDING]
		return {
			"total_refunds": len(self._refunds),
			"pending_refunds": len(pending),
			"pending_amount": sum(r.amount for r in pending),
		}


class RefundChaseWorkflow(BaseWorkflow):
	"""Workflow for refund tracking and follow-up."""

	workflow_id = "refund_chase"
	name = "Refund Chase Agent"
	category = "budget"
	trust_level = TrustLevel.APPROVAL

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = RefundChaseService(session)

	def describe(self) -> str:
		return "Track expected refunds and follow up when overdue."

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle refund events."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Plan refund chase."""
		reminders = self.service.check_overdue_refunds()

		return ActionPlan(
			action_type="chase_refunds",
			confidence=0.85,
			context={
				"overdue_refunds": len(reminders),
				"total_tracked": len(self.service._refunds),
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute refund chase."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		self.state_machine.transition("completed", {"reason": "chase_complete"})

		return ActionResult(
			success=True,
			summary=f"Found {plan.context.get('overdue_refunds', 0)} overdue refunds to follow up on",
			metadata=plan.context,
		)
