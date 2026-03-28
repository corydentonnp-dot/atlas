"""Workflow #62: DEA Tracker — tracks DEA registration expirations.

Monitors DEA license registration expiry and renewal requirements.
Critical for prescribing practitioners; missing renewal prevents prescribing.
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


class DEAStatus(str, Enum):
	"""DEA registration status."""

	ACTIVE = "active"
	RENEWAL_WINDOW_OPEN = "renewal_window_open"
	RENEWAL_DUE = "renewal_due"
	RENEWED = "renewed"
	EXPIRED = "expired"


@dataclass(slots=True)
class DEARegistration:
	"""DEA license registration tracking."""

	registration_id: str
	dea_number: str
	expiry_date: date
	practitioner_name: str = ""
	registration_type: str = "individual"  # or institutional
	status: DEAStatus = DEAStatus.ACTIVE
	notes: str = ""


@dataclass(frozen=True, slots=True)
class DEAAlert:
	"""Alert for approaching DEA registration expiration."""

	registration_id: str
	days_remaining: int
	expiry_date: date
	dea_number: str
	renewal_fee_estimate: float = 731.00  # 2024 fee


class DEATrackerService(PersistenceMixin):
	"""Service for tracking DEA registrations."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._registrations: dict[str, DEARegistration] = {}
		self._renewal_history: dict[str, list[date]] = {}

	def add_registration(self, registration: DEARegistration) -> DEARegistration:
		"""Track a new DEA registration."""
		self._registrations[registration.registration_id] = registration
		self._renewal_history[registration.registration_id] = []
		return registration

	def check_expiring(self, days_ahead: int, today: date) -> list[DEARegistration]:
		"""Find DEA registrations expiring within specified days."""
		results: list[DEARegistration] = []
		for reg in self._registrations.values():
			days_remaining = (reg.expiry_date - today).days
			if 0 <= days_remaining <= days_ahead and reg.status == DEAStatus.ACTIVE:
				results.append(reg)
		results.sort(key=lambda r: (r.expiry_date - today).days)
		return results

	def get_renewal_instructions(self) -> list[str]:
		"""Get renewal instructions for DEA registration."""
		return [
			"Log into CSOS (Central System for Services and Online Registration)",
			"Complete DEA Form 106 (Application for Renewal of Registration)",
			"Verify current state medical/nursing license status",
			"Pay renewal fee (~$731 per year)",
			"Submit application 60 days before expiration if possible",
			"Maintain certifications: NPI, state license, PTIN (if applicable)",
		]

	def mark_renewed(self, registration_id: str, new_expiry: date) -> bool:
		"""Mark a DEA registration as renewed."""
		if registration_id in self._registrations:
			reg = self._registrations[registration_id]
			reg.status = DEAStatus.RENEWED
			self._renewal_history[registration_id].append(date.today())
			reg.expiry_date = new_expiry
			reg.status = DEAStatus.ACTIVE
			return True
		return False

	def get_dea_alert(self, registration: DEARegistration, today: date) -> DEAAlert | None:
		"""Generate alert if DEA registration expiring soon."""
		if registration.status != DEAStatus.ACTIVE:
			return None
		days_remaining = (registration.expiry_date - today).days
		if days_remaining < 0:
			registration.status = DEAStatus.EXPIRED
			return None
		if days_remaining <= 120:  # Alert 120 days out (4 months)
			return DEAAlert(
				registration_id=registration.registration_id,
				days_remaining=days_remaining,
				expiry_date=registration.expiry_date,
				dea_number=registration.dea_number,
			)
		return None


class DEATrackerAgent(BaseWorkflow):
	"""Workflow for tracking DEA registration renewals."""

	name = "dea_tracker"
	description = "Track DEA registration expirations; alert on renewal requirements"
	category = "licensure"
	version = "1.0.0"

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = DEATrackerService(session)
		self.policy = PolicyEngine()

	def trigger(self, event: WorkflowEvent) -> bool:
		"""Triggered by daily check or registration addition."""
		return event.event_type in {"dea.added", "dea.check_due"}

	def process(self, run: WorkflowRun) -> ActionPlan:
		"""Identify DEA registrations approaching renewal."""
		if not run.input_data:
			# Daily check mode
			today = date.today()
			expiring = self.service.check_expiring(days_ahead=180, today=today)
			if not expiring:
				return ActionPlan(
					action="wait",
					rationale="No DEA registrations approaching expiration",
					next_scheduled=date.today().isoformat(),
				)
			run.add_output("registrations_expiring_count", len(expiring))
			run.add_output("registrations", [
				{
					"dea_number": r.dea_number,
					"expiry_date": r.expiry_date.isoformat(),
					"days_left": (r.expiry_date - today).days,
				}
				for r in expiring
			])
			return ActionPlan(
				action="notify",
				rationale=f"Found {len(expiring)} DEA registration(s) approaching renewal",
				target_audience="user",
				next_scheduled=date.today().isoformat(),
			)
		else:
			# New registration added
			reg_data = run.input_data
			registration = DEARegistration(
				registration_id=reg_data.get("registration_id", str(uuid4())),
				dea_number=reg_data.get("dea_number"),
				expiry_date=date.fromisoformat(reg_data.get("expiry_date")),
				practitioner_name=reg_data.get("practitioner_name", ""),
			)
			added = self.service.add_registration(registration)
			run.add_output("registration_id", added.registration_id)
			run.add_output("days_until_expiry", (added.expiry_date - date.today()).days)
			return ActionPlan(
				action="track",
				rationale=f"Tracking DEA registration {added.dea_number}",
				next_scheduled=date.today().isoformat(),
			)

	def act(self, plan: ActionPlan, run: WorkflowRun) -> ActionResult:
		"""Send renewal alert with instructions."""
		if plan.action == "notify":
			registrations = run.output_data.get("registrations", [])
			instructions = self.service.get_renewal_instructions()
			message = f"⚠️  DEA Registration Renewal Required:\n"
			message += f"{len(registrations)} registration(s) need renewal\n\n"
			for reg in registrations[:2]:
				message += f"- DEA #{reg['dea_number']}: expires {reg['expiry_date']} ({reg['days_left']} days)\n"
			if len(registrations) > 2:
				message += f"- ... and {len(registrations) - 2} more\n"
			message += "\n📋 Renewal Steps:\n"
			for step in instructions[:4]:
				message += f"1. {step}\n"
			return ActionResult(
				success=True,
				action_taken="renewal_alert_sent",
				summary=message,
				details={"registration_count": len(registrations)},
			)
		elif plan.action == "track":
			return ActionResult(
				success=True,
				action_taken="registration_tracked",
				summary="DEA registration tracked",
			)
		else:
			return ActionResult(
				success=True,
				action_taken="wait",
				summary="No DEA registrations requiring immediate renewal",
			)

	def close(self, result: ActionResult, run: WorkflowRun) -> None:
		"""Log final status."""
		run.add_output("final_status", "completed")
		run.add_output("action", result.action_taken)
