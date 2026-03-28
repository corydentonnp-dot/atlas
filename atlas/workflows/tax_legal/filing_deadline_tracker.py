"""Workflow #77: Filing Deadline Tracker — tracks tax and legal filing deadlines with recurring support.

This workflow manages deadline tracking for tax filings, license renewals, and legal compliance deadlines.
It supports recurring deadlines, extension tracking, and priority-based escalation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class Criticality(str, Enum):
	"""Criticality level for filing deadlines."""

	CRITICAL = "critical"  # Financial penalties or legal action if missed
	HIGH = "high"  # Significant penalties or renewal impacts
	MEDIUM = "medium"  # Fee penalties or reduced coverage
	LOW = "low"  # Informational or advisory


class DeadlineStatus(str, Enum):
	"""Status of a filing deadline."""

	ACTIVE = "active"
	EXTENDED = "extended"
	COMPLETED = "completed"
	MISSED = "missed"
	WAIVED = "waived"


@dataclass(slots=True)
class FilingDeadline:
	"""Filing deadline with recurring and extension support."""

	deadline_id: str
	label: str
	jurisdiction: str
	due_date: date
	criticality: Criticality = Criticality.HIGH
	status: DeadlineStatus = DeadlineStatus.ACTIVE
	is_recurring: bool = False
	recurring_months: int | None = None  # Months between recurrences (e.g., 12 for annual)
	notes: str | None = None
	parent_deadline_id: str | None = None  # For tracking extensions


@dataclass(slots=True)
class FilingAlert:
	"""Alert for an approaching filing deadline."""

	deadline_id: str
	label: str
	days_remaining: int
	criticality: Criticality
	is_overdue: bool
	message: str
	next_deadline: date | None = None  # If recurring
	required_documents: list[str] | None = None


@dataclass(slots=True)
class FilingTemplate:
	"""Reusable deadline template for recurring filings."""

	template_id: str
	filing_type: str  # e.g., "1040", "1099", "LLC_ANNUAL_REPORT"
	label_template: str
	jurisdiction: str
	due_month: int
	due_day: int
	criticality: Criticality
	recurring_months: int
	required_documents: list[str]
	instructions_url: str | None = None


class FilingDeadlineService(PersistenceMixin):
	"""Service for managing filing deadlines and recurring schedules."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._deadlines: dict[str, FilingDeadline] = {}
		self._alerts_sent: dict[str, set[int]] = {}  # deadline_id -> set of alert thresholds sent
		self._templates: dict[str, FilingTemplate] = {}
		self._init_default_templates()

	def _init_default_templates(self) -> None:
		"""Initialize common deadline templates for tax and legal filings."""
		templates = [
			FilingTemplate(
				template_id="form_1040",
				filing_type="1040",
				label_template="Federal Individual Income Tax Return",
				jurisdiction="USA",
				due_month=4,
				due_day=15,
				criticality=Criticality.CRITICAL,
				recurring_months=12,
				required_documents=["W2s", "1099s", "Investment income statements", "Charitable contributions records", "Medical expense receipts"],
				instructions_url="https://www.irs.gov/forms/about-form-1040",
			),
			FilingTemplate(
				template_id="form_1099",
				filing_type="1099",
				label_template="Miscellaneous Information Return",
				jurisdiction="USA",
				due_month=1,
				due_day=31,
				criticality=Criticality.HIGH,
				recurring_months=12,
				required_documents=["Payment records", "Contractor/vendor details", "Payment amounts"],
				instructions_url="https://www.irs.gov/forms/about-form-1099-misc",
			),
			FilingTemplate(
				template_id="state_income_tax",
				filing_type="STATE_INCOME_TAX",
				label_template="State Income Tax Return",
				jurisdiction="STATE",
				due_month=4,
				due_day=15,
				criticality=Criticality.HIGH,
				recurring_months=12,
				required_documents=["State W2s", "State 1099s", "Out-of-state income documentation", "Tax credits documentation"],
				instructions_url=None,
			),
			FilingTemplate(
				template_id="estimated_tax_q1",
				filing_type="ESTIMATED_TAX_Q1",
				label_template="Quarterly Estimated Tax Payment (Q1)",
				jurisdiction="USA",
				due_month=4,
				due_day=15,
				criticality=Criticality.MEDIUM,
				recurring_months=3,
				required_documents=["Prior year tax return", "YTD income estimate", "Expense estimates"],
				instructions_url="https://www.irs.gov/forms/about-form-1040-es",
			),
		]

		for template in templates:
			self._templates[template.template_id] = template

	def get_template(self, template_id: str) -> FilingTemplate | None:
		"""Retrieve a deadline template."""
		return self._templates.get(template_id)

	def create_from_template(self, template_id: str, deadline_id: str, due_date: date | None = None) -> FilingDeadline | None:
		"""Create a new deadline from a template."""
		template = self.get_template(template_id)
		if not template:
			return None

		# If no due_date provided, calculate it from template (this year)
		if due_date is None:
			today = date.today()
			due_date = date(today.year, template.due_month, template.due_day)
			# If deadline already passed this year, schedule for next year
			if due_date < today:
				due_date = date(today.year + 1, template.due_month, template.due_day)

		deadline = FilingDeadline(
			deadline_id=deadline_id,
			label=template.label_template,
			jurisdiction=template.jurisdiction,
			due_date=due_date,
			criticality=template.criticality,
			is_recurring=True,
			recurring_months=template.recurring_months,
		)

		return self.add_deadline(deadline)

	def get_required_documents(self, deadline_id: str) -> list[str]:
		"""Get required documents list for a deadline (if tracked)."""
		deadline = self._deadlines.get(deadline_id)
		if not deadline:
			return []

		# Try to match against templates to find required documents
		for template in self._templates.values():
			if template.label_template == deadline.label:
				return template.required_documents

		return []

	def add_deadline(self, deadline: FilingDeadline) -> FilingDeadline:
		"""Add a new deadline to track."""
		self._deadlines[deadline.deadline_id] = deadline
		self._alerts_sent[deadline.deadline_id] = set()
		return deadline

	def extend_deadline(self, deadline_id: str, new_due_date: date) -> FilingDeadline | None:
		"""Create an extension of an existing deadline."""
		if deadline_id not in self._deadlines:
			return None

		original = self._deadlines[deadline_id]
		original.status = DeadlineStatus.EXTENDED

		# Create extension record
		extension = FilingDeadline(
			deadline_id=f"{deadline_id}_ext",
			label=f"{original.label} (Extended)",
			jurisdiction=original.jurisdiction,
			due_date=new_due_date,
			criticality=original.criticality,
			status=DeadlineStatus.ACTIVE,
			is_recurring=original.is_recurring,
			recurring_months=original.recurring_months,
			parent_deadline_id=deadline_id,
		)
		self._deadlines[extension.deadline_id] = extension
		return extension

	def mark_completed(self, deadline_id: str) -> bool:
		"""Mark a deadline as completed."""
		if deadline_id in self._deadlines:
			self._deadlines[deadline_id].status = DeadlineStatus.COMPLETED
			return True
		return False

	def due_within(self, days: int, today: date) -> list[FilingDeadline]:
		"""Find deadlines due within specified days."""
		results: list[FilingDeadline] = []
		for deadline in self._deadlines.values():
			remaining = (deadline.due_date - today).days
			if remaining <= days and deadline.status in (DeadlineStatus.ACTIVE, DeadlineStatus.EXTENDED):
				results.append(deadline)
		return sorted(results, key=lambda d: d.due_date)

	def is_overdue(self, deadline: FilingDeadline, today: date) -> bool:
		"""Check if deadline is overdue."""
		return (deadline.due_date - today).days < 0 and deadline.status != DeadlineStatus.COMPLETED

	def get_alert_threshold(self, criticality: Criticality) -> list[int]:
		"""Get alert thresholds (in days) for criticality level."""
		thresholds = {
			Criticality.CRITICAL: [60, 30, 14, 7, 3, 1, 0],  # Almost every day for critical
			Criticality.HIGH: [45, 30, 14, 7, 3],
			Criticality.MEDIUM: [30, 14, 7],
			Criticality.LOW: [14, 7],
		}
		return thresholds.get(criticality, [])

	def should_alert(self, deadline_id: str, days_remaining: int, criticality: Criticality) -> bool:
		"""Determine if we should alert for this deadline at this time."""
		thresholds = self.get_alert_threshold(criticality)

		# Alert if we haven't sent alert at this threshold yet
		if days_remaining in thresholds:
			if days_remaining not in self._alerts_sent.get(deadline_id, set()):
				self._alerts_sent.setdefault(deadline_id, set()).add(days_remaining)
				return True

		# Always alert if overdue
		if days_remaining < 0:
			return True

		return False

	def generate_alert(self, deadline: FilingDeadline, today: date) -> FilingAlert | None:
		"""Generate alert for a deadline if needed."""
		days_remaining = (deadline.due_date - today).days
		is_overdue = self.is_overdue(deadline, today)

		if deadline.status not in (DeadlineStatus.ACTIVE, DeadlineStatus.EXTENDED):
			return None

		if not (days_remaining <= 60 or is_overdue):  # Only alert if within 60 days or overdue
			return None

		if not self.should_alert(deadline.deadline_id, days_remaining, deadline.criticality):
			return None

		severity_emoji = {
			Criticality.CRITICAL: "🚨",
			Criticality.HIGH: "⚠️",
			Criticality.MEDIUM: "ℹ️",
			Criticality.LOW: "📋",
		}

		emoji = severity_emoji.get(deadline.criticality, "")

		if is_overdue:
			message = f"{emoji} OVERDUE: {deadline.label} (due {abs(days_remaining)} days ago, {deadline.jurisdiction})"
		elif days_remaining == 0:
			message = f"{emoji} DUE TODAY: {deadline.label} ({deadline.jurisdiction})"
		elif days_remaining < 0:
			message = f"{emoji} {days_remaining:d} days overdue: {deadline.label}"
		else:
			message = f"{emoji} {days_remaining} days until: {deadline.label} ({deadline.jurisdiction})"

		next_deadline = None
		if deadline.is_recurring and deadline.recurring_months:
			next_deadline = date(
				deadline.due_date.year + (deadline.due_date.month + deadline.recurring_months - 1) // 12,
				(deadline.due_date.month + deadline.recurring_months - 1) % 12 + 1,
				deadline.due_date.day,
			)

		required_docs = self.get_required_documents(deadline.deadline_id)

		return FilingAlert(
			deadline_id=deadline.deadline_id,
			label=deadline.label,
			days_remaining=days_remaining,
			criticality=deadline.criticality,
			is_overdue=is_overdue,
			message=message,
			next_deadline=next_deadline,
			required_documents=required_docs if required_docs else None,
		)


class FilingDeadlineTrackerWorkflow(BaseWorkflow):
	"""Workflow for tracking and escalating filing deadlines."""

	workflow_id = "filing_deadline_tracker"
	name = "Filing Deadline Tracker"
	category = "tax_legal"
	trust_level = TrustLevel.AUTO

	def __init__(
		self,
		service: FilingDeadlineService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or FilingDeadlineService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Initialize workflow from deadline event."""
		self.state_machine.transition("planning", {"event_type": event.event_type})

		if event.event_type == "deadline_added":
			payload = event.payload
			self.service.add_deadline(
				FilingDeadline(
					deadline_id=str(payload["deadline_id"]),
					label=str(payload["label"]),
					jurisdiction=str(payload.get("jurisdiction", "Unknown")),
					due_date=date.fromisoformat(str(payload["due_date"])),
					criticality=Criticality(payload.get("criticality", "high")),
					is_recurring=bool(payload.get("is_recurring", False)),
					recurring_months=int(payload.get("recurring_months", 12)) if payload.get("is_recurring") else None,
				)
			)
		elif event.event_type == "deadline_extended":
			deadline_id = str(event.payload.get("deadline_id"))
			new_due = date.fromisoformat(str(event.payload.get("new_due_date")))
			self.service.extend_deadline(deadline_id, new_due)
		elif event.event_type == "deadline_completed":
			self.service.mark_completed(str(event.payload.get("deadline_id")))

		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Generate action plan by checking for approaching/overdue deadlines."""
		today = date.fromisoformat(str(run.event.payload.get("today", date.today().isoformat())))
		days_ahead = int(run.event.payload.get("days_ahead", 60))

		relevant = self.service.due_within(days_ahead, today)
		alerts = []

		for deadline in relevant:
			alert = self.service.generate_alert(deadline, today)
			if alert:
				alerts.append(alert)

		# Increase confidence if there are overdue items
		overdue_count = sum(1 for a in alerts if a.is_overdue)
		confidence = min(0.98, 0.8 + (0.05 * len(alerts)) + (0.10 * overdue_count))

		return ActionPlan(
			action_type="escalate_filing_deadlines",
			confidence=confidence,
			context={
				"today": today.isoformat(),
				"alert_count": len(alerts),
				"overdue_count": overdue_count,
				"alert_details": [
					{
						"label": a.label,
						"criticality": a.criticality.value,
						"days_remaining": a.days_remaining,
						"is_overdue": a.is_overdue,
						"message": a.message,
					}
					for a in alerts
				],
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute action plan via policy engine."""
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

		self.state_machine.transition("completed", {"reason": decision.reason})
		overdue = plan.context.get("overdue_count", 0)
		return ActionResult(
			True,
			f"Tracked {plan.context['alert_count']} deadlines ({overdue} overdue).",
			{**plan.context, "policy_decision": decision.reason},
		)
