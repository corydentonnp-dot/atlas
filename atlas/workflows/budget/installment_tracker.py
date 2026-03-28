"""Workflow #35: Installment Tracker — tracks BNPL and installment payment deadlines.

Monitors installment payment plans (Buy Now Pay Later) and sends alerts before payments due.
Helps prevent missed payments and late fee penalties.
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


class PaymentStatus(str, Enum):
	"""Payment status in installment plan."""

	UPCOMING = "upcoming"
	DUE = "due"
	OVERDUE = "overdue"
	PAID = "paid"
	MISSED = "missed"


@dataclass(slots=True)
class InstallmentPayment:
	"""Single payment in an installment plan."""

	payment_id: str
	plan_id: str
	due_date: date
	amount: float
	status: PaymentStatus = PaymentStatus.UPCOMING
	missed_warning_sent: bool = False


@dataclass(slots=True)
class InstallmentPlan:
	"""Buy Now Pay Later installment plan."""

	plan_id: str
	merchant: str
	total_amount: float
	total_payments: int
	payments: list[InstallmentPayment]
	created_date: date = None
	status: str = "active"


@dataclass(frozen=True, slots=True)
class PaymentAlert:
	"""Alert for upcoming installment payment."""

	payment_id: str
	merchant: str
	amount: float
	days_until_due: int
	due_date: date


class InstallmentService(PersistenceMixin):
	"""Service for tracking installment payment plans."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._plans: dict[str, InstallmentPlan] = {}
		self._payments_by_due_date: dict[date, list[InstallmentPayment]] = {}

	def add_plan(self, plan: InstallmentPlan) -> InstallmentPlan:
		"""Track a new installment plan."""
		if plan.created_date is None:
			plan.created_date = date.today()
		self._plans[plan.plan_id] = plan
		for payment in plan.payments:
			if payment.due_date not in self._payments_by_due_date:
				self._payments_by_due_date[payment.due_date] = []
			self._payments_by_due_date[payment.due_date].append(payment)
		return plan

	def check_upcoming(self, days_ahead: int, today: date) -> list[InstallmentPayment]:
		"""Find payments due within specified days."""
		results: list[InstallmentPayment] = []
		for payment in self._get_all_payments():
			days_until_due = (payment.due_date - today).days
			if 0 <= days_until_due <= days_ahead and payment.status in {PaymentStatus.UPCOMING, PaymentStatus.DUE}:
				results.append(payment)
		results.sort(key=lambda p: (p.due_date - today).days)
		return results

	def _get_all_payments(self) -> list[InstallmentPayment]:
		"""Get all payments across all plans."""
		payments = []
		for plan in self._plans.values():
			payments.extend(plan.payments)
		return payments

	def mark_paid(self, payment_id: str) -> bool:
		"""Mark a payment as paid."""
		for plan in self._plans.values():
			for payment in plan.payments:
				if payment.payment_id == payment_id:
					payment.status = PaymentStatus.PAID
					return True
		return False

	def get_payment_total_due(self, today: date) -> float:
		"""Get total of all overdue payments."""
		total = 0.0
		for plan in self._plans.values():
			for payment in plan.payments:
				if payment.due_date < today and payment.status != PaymentStatus.PAID:
					total += payment.amount
		return total



class InstallmentTrackerAgent(BaseWorkflow):
	"""Workflow for tracking installment payment deadlines."""

	name = "installment_tracker"
	description = "Track installment payment plans; alert before due dates"
	category = "budget"
	version = "1.0.0"

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = InstallmentService(session)
		self.policy = PolicyEngine()

	def trigger(self, event: WorkflowEvent) -> bool:
		"""Triggered by daily check or plan addition."""
		return event.event_type in {"plan.added", "payment.check_due"}

	def process(self, run: WorkflowRun) -> ActionPlan:
		"""Identify upcoming installment payments."""
		if not run.input_data:
			# Daily check mode
			today = date.today()
			upcoming = self.service.check_upcoming(days_ahead=30, today=today)
			if not upcoming:
				return ActionPlan(
					action="wait",
					rationale="No installment payments due in next 30 days",
					next_scheduled=date.today().isoformat(),
				)
			run.add_output("payments_count", len(upcoming))
			run.add_output("total_due", sum(p.amount for p in upcoming))
			run.add_output("payments", [
				{
					"merchant": next((plan.merchant for plan in self.service._plans.values() if p in plan.payments), "Unknown"),
					"amount": p.amount,
					"due_date": p.due_date.isoformat(),
					"days_left": (p.due_date - today).days,
				}
				for p in upcoming[:5]
			])
			return ActionPlan(
				action="notify",
				rationale=f"Found {len(upcoming)} payments due soon",
				target_audience="user",
				next_scheduled=date.today().isoformat(),
			)
		else:
			# New plan added
			plan_data = run.input_data
			payments = [
				InstallmentPayment(
					payment_id=str(uuid4()),
					plan_id=plan_data.get("plan_id", str(uuid4())),
					due_date=date.fromisoformat(d),
					amount=float(plan_data.get("total_amount", 0)) / int(plan_data.get("total_payments", 1)),
				)
				for d in plan_data.get("payment_dates", [])
			]
			plan = InstallmentPlan(
				plan_id=plan_data.get("plan_id", str(uuid4())),
				merchant=plan_data.get("merchant", "Unknown"),
				total_amount=float(plan_data.get("total_amount", 0)),
				total_payments=len(payments),
				payments=payments,
			)
			added = self.service.add_plan(plan)
			run.add_output("plan_id", added.plan_id)
			run.add_output("payments_count", len(payments))
			return ActionPlan(
				action="track",
				rationale=f"Tracking {len(payments)} payments for {added.merchant}",
				next_scheduled=date.today().isoformat(),
			)

	def act(self, plan: ActionPlan, run: WorkflowRun) -> ActionResult:
		"""Send payment reminders."""
		if plan.action == "notify":
			payments = run.output_data.get("payments", [])
			message = f"💳 Installment Payments Due Soon:\n"
			message += f"Total: ${run.output_data.get('total_due', 0):.2f}\n\n"
			for p in payments[:3]:
				message += f"- {p['merchant']}: ${p['amount']:.2f} due {p['due_date']} ({p['days_left']} days)\n"
			return ActionResult(
				success=True,
				action_taken="payment_reminders_sent",
				summary=message,
				details={"payment_count": len(payments)},
			)
		elif plan.action == "track":
			return ActionResult(
				success=True,
				action_taken="plan_tracked",
				summary=f"Tracking {run.output_data.get('payments_count')} payments",
			)
		else:
			return ActionResult(
				success=True,
				action_taken="wait",
				summary="No payments due this month",
			)

	def close(self, result: ActionResult, run: WorkflowRun) -> None:
		"""Log final status."""
		run.add_output("final_status", "completed")
		run.add_output("action", result.action_taken)
