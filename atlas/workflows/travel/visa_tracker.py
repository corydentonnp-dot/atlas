"""Workflow #52: Visa Tracker — monitors visa expiration and renewal deadlines.

Tracks passport and visa expiration dates across multiple countries, alerts on renewal
windows, and provides checklists for renewal processes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class VisaStatus(str, Enum):
	"""Visa or passport status."""

	VALID = "valid"
	EXPIRING_SOON = "expiring_soon"  # < 6 months
	EXPIRED = "expired"
	RENEWAL_IN_PROGRESS = "renewal_in_progress"
	CANCELLED = "cancelled"


@dataclass(slots=True)
class Visa:
	"""Visa or passport record."""

	visa_id: str
	country: str
	visa_type: str  # "tourist", "work", "student", "residence", "passport"
	issue_date: date
	expiry_date: date
	status: VisaStatus = VisaStatus.VALID
	renewal_eligible_date: date | None = None
	notes: str = ""


@dataclass(frozen=True, slots=True)
class VisaAlert:
	"""Alert for visa expiration or renewal window."""

	visa_id: str
	country: str
	vis_type: str
	days_until_expiry: int
	expiry_date: date
	action_required: str  # "renew", "contact embassy", "travel before expiry"


class VisaTrackerService(PersistenceMixin):
	"""Service for visa and passport tracking."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._visas: dict[str, Visa] = {}

	def add_visa(self, visa: Visa) -> Visa:
		"""Register a visa or passport."""
		self._visas[visa.visa_id] = visa
		return visa

	def check_status(self, today: date = date.today()) -> list[VisaAlert]:
		"""Check all visas for alerts."""
		alerts: list[VisaAlert] = []

		for visa in self._visas.values():
			days_remaining = (visa.expiry_date - today).days

			# Update status
			if days_remaining < 0:
				visa.status = VisaStatus.EXPIRED
			elif days_remaining < 180:
				visa.status = VisaStatus.EXPIRING_SOON
			else:
				visa.status = VisaStatus.VALID

			# Generate alert if necessary
			if visa.status in {VisaStatus.EXPIRING_SOON, VisaStatus.EXPIRED}:
				if days_remaining < 0:
					action = "Contact embassy for extension or renewal"
				elif days_remaining < 30:
					action = "Begin renewal process immediately"
				elif days_remaining < 90:
					action = "Schedule renewal appointment"
				else:
					action = "Start gathering renewal documents"

				alerts.append(
					VisaAlert(
						visa_id=visa.visa_id,
						country=visa.country,
						vis_type=visa.visa_type,
						days_until_expiry=max(days_remaining, 0),
						expiry_date=visa.expiry_date,
						action_required=action,
					)
				)

		return sorted(alerts, key=lambda a: a.days_until_expiry)

	def get_renewal_requirements(self, country: str, visa_type: str) -> list[str]:
		"""Get standard renewal documentation for a visa."""
		base_docs = ["Completed visa application form", "Valid passport", "Passport photos", "Fee payment"]

		country_specific: dict[str, list[str]] = {
			"USA": ["I-129 or I-140 form", "Labor certification (if applicable)", "Proof of employment", "Medical exam (I-693)"],
			"Canada": ["Express Entry profile", "Police certificate", "Medical exam", "Language test results"],
			"UK": ["Financial proof", "English language test", "Tuberculosis test", "Accommodation confirmation"],
			"Japan": ["Certificate of eligibility", "Financial proof", "Health certificate", "Accommodation details"],
		}

		docs = base_docs + country_specific.get(country, ["Check embassy website for specific requirements"])
		return docs

	def upcoming_renewals(self, days_ahead: int = 180, today: date = date.today()) -> list[Visa]:
		"""Find visas needing renewal soon."""
		renewals = []
		for visa in self._visas.values():
			days_remaining = (visa.expiry_date - today).days
			if 0 < days_remaining <= days_ahead:
				renewals.append(visa)
		return sorted(renewals, key=lambda v: v.expiry_date)


class VisaTrackerAgent(BaseWorkflow):
	"""Workflow for visa and passport tracking."""

	workflow_id = "visa_tracker"
	name = "Visa Tracker"
	category = "travel"
	trust_level = TrustLevel.DRAFT

	def __init__(self, service: VisaTrackerService | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = service or VisaTrackerService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle visa events."""
		self.state_machine.transition("planning", {"event_type": event.event_type})

		if event.event_type == "visa_added":
			payload = event.payload
			self.service.add_visa(
				Visa(
					visa_id=str(payload.get("visa_id", "")),
					country=str(payload.get("country", "")),
					visa_type=str(payload.get("visa_type", "tourist")),
					issue_date=date.fromisoformat(str(payload.get("issue_date", date.today().isoformat()))),
					expiry_date=date.fromisoformat(str(payload.get("expiry_date", (date.today() + timedelta(days=365)).isoformat()))),
				)
			)

		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Check visa status and identify alerts."""
		alerts = self.service.check_status()
		urgent_alerts = [a for a in alerts if a.days_until_expiry < 90]

		return ActionPlan(
			action_type="check_visa_status",
			confidence=0.9,
			context={
				"total_visas": len(self.service._visas),
				"alerts_count": len(alerts),
				"urgent_alerts": len(urgent_alerts),
				"alerts": [
					{
						"country": a.country,
						"type": a.vis_type,
						"days_until_expiry": a.days_until_expiry,
						"action": a.action_required,
					}
					for a in alerts[:5]
				],
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute visa status check."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})

		total = plan.context.get("total_visas", 0)
		alerts = plan.context.get("alerts_count", 0)
		urgent = plan.context.get("urgent_alerts", 0)

		if urgent > 0:
			summary = f"Tracking {total} visas; {urgent} need immediate renewal attention"
		elif alerts > 0:
			summary = f"Tracking {total} visas; {alerts} approaching expiry"
		else:
			summary = f"Tracking {total} visas; all current"

		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
