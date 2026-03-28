"""Workflow #29: Rent Reminder Agent — rent payment reminders with escalation and tracking.

This workflow sends rent payment reminders to tenants on a configurable schedule,
tracks payment status, escalates overdue payments, and supports multi-property
management with payment method tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class PaymentStatus(str, Enum):
	"""Payment status tracking."""

	UNPAID = "unpaid"
	PARTIAL = "partial"
	PAID = "paid"
	OVERDUE = "overdue"
	WAIVED = "waived"


class EscalationTier(str, Enum):
	"""Reminder escalation levels."""

	COURTESY = "courtesy"  # Initial reminder, friendly tone
	URGENT = "urgent"  # Payment overdue, firm tone
	LEGAL = "legal"  # Multiple days overdue, formal notice
	COLLECTIONS = "collections"  # Severe delinquency, legal action

@dataclass(slots=True)
class ReminderHistory:
	"""Record of a sent reminder."""

	history_id: str
	reminder_id: str
	rent_due_id: str
	tenant_id: str
	sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
	delivery_confirmed: bool = False
	confirmed_at: datetime | None = None
	delivery_method: str = "email"  # email, sms, portal_notification
	notes: str = ""

@dataclass(slots=True)
class ReminderDigest:
	"""Grouped reminders for a tenant (for digest delivery)."""

	digest_id: str
	tenant_id: str
	property_name: str
	reminder_count: int
	total_amount_due: float
	reminders: list[RentReminder] = field(default_factory=list)
	created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class RentPayment:
	"""A rent payment record."""

	payment_id: str
	tenant_id: str
	amount: float
	paid_date: date | None
	payment_method: str = "unknown"  # ACH, check, cash, etc.


@dataclass(slots=True)
class RentDue:
	"""Rent due for a tenant in a month."""

	rent_due_id: str
	tenant_id: str
	tenant_name: str
	property_name: str
	unit: str
	amount_due: float
	due_date: date
	status: PaymentStatus = PaymentStatus.UNPAID
	amount_paid: float = 0.0
	last_reminder_date: date | None = None
	escalation_tier: EscalationTier = EscalationTier.COURTESY
	payment_method: str = "unknown"
	notes: str = ""


@dataclass(slots=True)
class RentSchedule:
	"""Rent schedule for a property unit."""

	schedule_id: str
	unit: str
	tenant_id: str
	monthly_amount: float
	due_day_of_month: int = 1  # 1-28 to avoid month-end issues
	reminder_days_before: int = 3  # Send reminder N days before due date
	escalation_days: list[int] = field(default_factory=lambda: [0, 7, 14, 21])  # Days for each tier


@dataclass(frozen=True, slots=True)
class RentReminder:
	"""A reminder to send to a tenant."""

	reminder_id: str
	rent_due_id: str
	tenant_id: str
	tenant_name: str
	property_unit: str
	amount_due: float
	days_overdue: int
	escalation_tier: EscalationTier
	payment_method: str


class RentReminderService(PersistenceMixin):
	"""Service for managing rent reminders and payment tracking."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._rent_items: dict[str, RentDue] = {}
		self._schedules: dict[str, RentSchedule] = {}
		self._payments: dict[str, RentPayment] = {}
		self._reminder_history: dict[str, ReminderHistory] = {}
		self._property_portfolio: set[str] = set()

	def add_schedule(self, schedule: RentSchedule) -> None:
		"""Register a rent schedule for a unit."""
		self._schedules[schedule.schedule_id] = schedule

	def add_rent_due(self, item: RentDue) -> None:
		"""Record a rent due item."""
		self._rent_items[item.rent_due_id] = item

	def record_payment(self, payment: RentPayment) -> None:
		"""Record a rent payment."""
		self._payments[payment.payment_id] = payment

		# Update rent due status
		for rent_due in self._rent_items.values():
			if rent_due.tenant_id == payment.tenant_id and rent_due.status != PaymentStatus.PAID:
				rent_due.amount_paid += payment.amount
				if rent_due.amount_paid >= rent_due.amount_due:
					rent_due.status = PaymentStatus.PAID
					rent_due.amount_paid = rent_due.amount_due
				elif rent_due.amount_paid > 0:
					rent_due.status = PaymentStatus.PARTIAL

	def get_escalation_tier(self, rent_due: RentDue, today: date) -> EscalationTier:
		"""Determine escalation tier based on days overdue."""
		days_overdue = (today - rent_due.due_date).days

		if days_overdue < 0:
			return EscalationTier.COURTESY
		if days_overdue < 7:
			return EscalationTier.COURTESY
		if days_overdue < 14:
			return EscalationTier.URGENT
		if days_overdue < 21:
			return EscalationTier.LEGAL
		return EscalationTier.COLLECTIONS

	def check_due_rents(self, today: date) -> list[RentReminder]:
		"""Check which rents are due for reminder."""
		reminders: list[RentReminder] = []

		for rent_due in self._rent_items.values():
			# Skip already paid
			if rent_due.status == PaymentStatus.PAID or rent_due.status == PaymentStatus.WAIVED:
				continue

			days_until_due = (rent_due.due_date - today).days
			days_overdue = (today - rent_due.due_date).days

			# Send courtesy reminder 3 days before
			if -3 <= days_until_due <= 0 and rent_due.escalation_tier == EscalationTier.COURTESY:
				escalation = self.get_escalation_tier(rent_due, today)
				reminder = RentReminder(
					reminder_id=f"reminder_{rent_due.rent_due_id}_{today.isoformat()}",
					rent_due_id=rent_due.rent_due_id,
					tenant_id=rent_due.tenant_id,
					tenant_name=rent_due.tenant_name,
					property_unit=f"{rent_due.property_name}/{rent_due.unit}",
					amount_due=rent_due.amount_due - rent_due.amount_paid,
					days_overdue=max(days_overdue, 0),
					escalation_tier=escalation,
					payment_method=rent_due.payment_method,
				)
				reminders.append(reminder)
				rent_due.last_reminder_date = today

			# Escalate if overdue
			elif days_overdue > 7:
				escalation = self.get_escalation_tier(rent_due, today)
				if escalation.value > rent_due.escalation_tier.value:
					rent_due.escalation_tier = escalation
					reminder = RentReminder(
						reminder_id=f"reminder_{rent_due.rent_due_id}_{today.isoformat()}",
						rent_due_id=rent_due.rent_due_id,
						tenant_id=rent_due.tenant_id,
						tenant_name=rent_due.tenant_name,
						property_unit=f"{rent_due.property_name}/{rent_due.unit}",
						amount_due=rent_due.amount_due - rent_due.amount_paid,
						days_overdue=days_overdue,
						escalation_tier=escalation,
						payment_method=rent_due.payment_method,
					)
					reminders.append(reminder)

		return reminders

	def get_tenant_payment_history(self, tenant_id: str, months: int = 12) -> dict[str, object]:
		"""Get payment history for a tenant."""
		relevant_payments = [p for p in self._payments.values() if p.tenant_id == tenant_id]
		
		on_time = sum(1 for p in relevant_payments if p.paid_date and p.paid_date <= date.today())
		late = sum(1 for p in relevant_payments if p.paid_date and p.paid_date > date.today())

		return {
			"tenant_id": tenant_id,
			"total_payments": len(relevant_payments),
			"on_time_payments": on_time,
			"late_payments": late,
			"reliability": on_time / len(relevant_payments) if relevant_payments else 0.0,
		}

	def record_reminder_sent(self, reminder: RentReminder, delivery_method: str = "email") -> ReminderHistory:
		"""Record that a reminder was sent."""
		history_id = f"hist_{reminder.reminder_id}_{datetime.now(timezone.utc).timestamp()}"
		record = ReminderHistory(
			history_id=history_id,
			reminder_id=reminder.reminder_id,
			rent_due_id=reminder.rent_due_id,
			tenant_id=reminder.tenant_id,
			delivery_method=delivery_method,
		)
		self._reminder_history[history_id] = record
		return record

	def confirm_delivery(self, history_id: str) -> bool:
		"""Mark a reminder as delivered/confirmed."""
		if history_id not in self._reminder_history:
			return False
		record = self._reminder_history[history_id]
		record.delivery_confirmed = True
		record.confirmed_at = datetime.now(timezone.utc)
		return True

	def get_unconfirmed_reminders(self) -> list[ReminderHistory]:
		"""Get all reminders that haven't been confirmed as delivered."""
		return [r for r in self._reminder_history.values() if not r.delivery_confirmed]

	def add_property(self, property_name: str) -> None:
		"""Register a property in the portfolio."""
		self._property_portfolio.add(property_name)

	def get_properties(self) -> list[str]:
		"""Get all managed properties."""
		return sorted(list(self._property_portfolio))

	def group_reminders_by_property(self, reminders: list[RentReminder]) -> dict[str, ReminderDigest]:
		"""Group reminders by property for digest delivery."""
		digests: dict[str, ReminderDigest] = {}
        
		for reminder in reminders:
			# Extract property name from unit string (e.g., "Main St/2B" -> "Main St")
			property_name = reminder.property_unit.split("/")[0] if "/" in reminder.property_unit else "Unknown"
            
			if property_name not in digests:
				digest_id = f"digest_{property_name}_{datetime.now(timezone.utc).timestamp()}"
				digests[property_name] = ReminderDigest(
					digest_id=digest_id,
					tenant_id=reminder.tenant_id,
					property_name=property_name,
					reminder_count=0,
					total_amount_due=0.0,
				)
            
			digests[property_name].reminders.append(reminder)
			digests[property_name].reminder_count += 1
			digests[property_name].total_amount_due += reminder.amount_due
        
		return digests

	def get_reminder_history(self, tenant_id: str = "") -> list[ReminderHistory]:
		"""Get reminder history, optionally filtered by tenant."""
		if not tenant_id:
			return list(self._reminder_history.values())
		return [r for r in self._reminder_history.values() if r.tenant_id == tenant_id]


class RentReminderWorkflow(BaseWorkflow):
	"""Workflow for rent reminders and payment tracking."""

	workflow_id = "rent_reminder"
	name = "Rent Reminder Agent"
	category = "property"
	trust_level = TrustLevel.AUTO

	def __init__(self, service: RentReminderService | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = service or RentReminderService(session=session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle rent-related events (due, paid, etc.)."""
		self.state_machine.transition("planning", {"event_type": event.event_type})

		if event.event_type == "rent_due_added":
			payload = event.payload
			self.service.add_rent_due(
				RentDue(
					rent_due_id=str(payload.get("rent_due_id", "")),
					tenant_id=str(payload.get("tenant_id", "")),
					tenant_name=str(payload.get("tenant_name", "")),
					property_name=str(payload.get("property_name", "")),
					unit=str(payload.get("unit", "")),
					amount_due=float(payload.get("amount_due", 0)),
					due_date=date.fromisoformat(str(payload.get("due_date", date.today().isoformat()))),
					payment_method=str(payload.get("payment_method", "unknown")),
				)
			)

		elif event.event_type == "rent_payment_received":
			payload = event.payload
			self.service.record_payment(
				RentPayment(
					payment_id=str(payload.get("payment_id", "")),
					tenant_id=str(payload.get("tenant_id", "")),
					amount=float(payload.get("amount", 0)),
					paid_date=date.fromisoformat(str(payload.get("paid_date", date.today().isoformat()))),
					payment_method=str(payload.get("payment_method", "unknown")),
				)
			)

		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Check which rents need reminders."""
		today = date.fromisoformat(str(run.event.payload.get("today", date.today().isoformat())))
		due_reminders = self.service.check_due_rents(today)

		# Build context with reminder details
		reminders_context = [
			{
				"tenant_name": r.tenant_name,
				"unit": r.property_unit,
				"amount": r.amount_due,
				"overdue_days": r.days_overdue,
				"escalation": r.escalation_tier.value,
			}
			for r in due_reminders
		]

		confidence = 0.95 if len(due_reminders) > 0 else 0.70

		return ActionPlan(
			action_type="send_rent_reminders",
			confidence=confidence,
			context={
				"reminder_count": len(due_reminders),
				"today": today.isoformat(),
				"reminders": reminders_context,
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute reminder dispatch with policy gating."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})

		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)

		if not decision.allowed:
			self.state_machine.transition("failed", {"reason": decision.reason})
			return ActionResult(False, decision.reason, plan.context)

		reminder_count = plan.context.get("reminder_count", 0)
		summary = f"Sent {reminder_count} rent reminder(s)" if reminder_count > 0 else "No reminders due today"

		self.state_machine.transition("completed", {"reason": decision.reason})

		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
