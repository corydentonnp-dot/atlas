"""Workflow #61: NP License Tracker — tracks NP license expirations and renewals.

Monitors NP license expiration dates and renewal requirements across states.
Career-critical workflow for healthcare professionals with state-specific tracking.
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


class LicenseStatus(str, Enum):
	"""License status."""

	ACTIVE = "active"
	RENEWAL_WINDOW_OPEN = "renewal_window_open"
	RENEWAL_DUE = "renewal_due"
	RENEWED = "renewed"
	EXPIRED = "expired"


@dataclass(slots=True)
class NPLicense:
	"""NP license with expiration and renewal tracking."""

	license_id: str
	state: str
	license_number: str
	expiry_date: date
	ce_requirements: int  # hours required
	status: LicenseStatus = LicenseStatus.ACTIVE
	notes: str = ""


@dataclass(frozen=True, slots=True)
class LicenseAlert:
	"""Alert for approaching license expiration."""

	license_id: str
	state: str
	days_remaining: int
	expiry_date: date
	ce_hours_required: int
	renewal_deadline_date: date


class NPLicenseService(PersistenceMixin):
	"""Service for tracking NP licenses across states."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._licenses: dict[str, NPLicense] = {}
		self._renewal_history: dict[str, list[date]] = {}
		# Common state-specific CE requirements
		self.state_ce_map: dict[str, int] = {
			"AL": 30, "AK": 30, "AZ": 25, "AR": 40, "CA": 30,
			"CO": 30, "CT": 30, "DE": 30, "FL": 30, "GA": 30,
			"HI": 30, "ID": 30, "IL": 30, "IN": 30, "IA": 30,
			"KS": 30, "KY": 30, "LA": 30, "ME": 30, "MD": 30,
			"MA": 30, "MI": 30, "MN": 30, "MS": 30, "MO": 30,
			"MT": 30, "NE": 30, "NV": 30, "NH": 30, "NJ": 30,
			"NM": 30, "NY": 30, "NC": 30, "ND": 30, "OH": 30,
			"OK": 30, "OR": 30, "PA": 30, "RI": 30, "SC": 30,
			"SD": 30, "TN": 30, "TX": 30, "UT": 30, "VT": 30,
			"VA": 30, "WA": 30, "WV": 30, "WI": 30, "WY": 30,
		}

	def add_license(self, license: NPLicense) -> NPLicense:
		"""Track a new NP license."""
		self._licenses[license.license_id] = license
		self._renewal_history[license.license_id] = []
		return license

	def check_expiring(self, days_ahead: int, today: date) -> list[NPLicense]:
		"""Find licenses expiring within specified days."""
		results: list[NPLicense] = []
		for license in self._licenses.values():
			days_remaining = (license.expiry_date - today).days
			if 0 <= days_remaining <= days_ahead and license.status == LicenseStatus.ACTIVE:
				results.append(license)
		results.sort(key=lambda l: (l.expiry_date - today).days)
		return results

	def get_renewal_checklist(self, license_id: str) -> list[str]:
		"""Get renewal checklist for a license."""
		if license_id not in self._licenses:
			return []
		license = self._licenses[license_id]
		ce_required = license.ce_requirements or self.state_ce_map.get(license.state, 30)
		return [
			f"Complete {ce_required} hours of continuing education",
			f"Verify active RN license in {license.state}",
			"Pay renewal fee",
			f"Complete renewal application for {license.state} Board of Nursing",
			"Submit verification of practice hours",
			"Verify malpractice insurance current",
		]

	def mark_renewed(self, license_id: str, new_expiry: date) -> bool:
		"""Mark a license as renewed."""
		if license_id in self._licenses:
			license = self._licenses[license_id]
			license.status = LicenseStatus.RENEWED
			self._renewal_history[license_id].append(date.today())
			license.expiry_date = new_expiry
			license.status = LicenseStatus.ACTIVE
			return True
		return False

	def get_license_alert(self, license: NPLicense, today: date) -> LicenseAlert | None:
		"""Generate alert for license if expiring soon."""
		if license.status != LicenseStatus.ACTIVE:
			return None
		days_remaining = (license.expiry_date - today).days
		if days_remaining < 0:
			license.status = LicenseStatus.EXPIRED
			return None
		if days_remaining <= 90:  # Renewal window opens 90 days before
			return LicenseAlert(
				license_id=license.license_id,
				state=license.state,
				days_remaining=days_remaining,
				expiry_date=license.expiry_date,
				ce_hours_required=license.ce_requirements,
				renewal_deadline_date=license.expiry_date,
			)
		return None

	def list_all(self) -> list[NPLicense]:
		"""List all tracked licenses."""
		return list(self._licenses.values())


class NPLicenseTrackerAgent(BaseWorkflow):
	"""Workflow for tracking NP license renewals."""

	name = "np_license_tracker"
	description = "Track NP license expirations; alert on renewal requirements"
	category = "licensure"
	version = "1.0.0"

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = NPLicenseService(session)
		self.policy = PolicyEngine()

	def trigger(self, event: WorkflowEvent) -> bool:
		"""Triggered by daily check or license addition."""
		return event.event_type in {"license.added", "renewal.check_due"}

	def process(self, run: WorkflowRun) -> ActionPlan:
		"""Identify licenses approaching renewal windows."""
		if not run.input_data:
			# Daily check mode
			today = date.today()
			expiring = self.service.check_expiring(days_ahead=180, today=today)
			if not expiring:
				return ActionPlan(
					action="wait",
					rationale="No licenses approaching renewal in next 6 months",
					next_scheduled=date.today().isoformat(),
				)
			run.add_output("licenses_expiring_count", len(expiring))
			run.add_output("licenses", [
				{
					"state": l.state,
					"license_number": l.license_number,
					"expiry_date": l.expiry_date.isoformat(),
					"days_left": (l.expiry_date - today).days,
				}
				for l in expiring
			])
			return ActionPlan(
				action="notify",
				rationale=f"Found {len(expiring)} licenses approaching renewal",
				target_audience="user",
				next_scheduled=date.today().isoformat(),
			)
		else:
			# New license added
			lic_data = run.input_data
			license = NPLicense(
				license_id=lic_data.get("license_id", str(uuid4())),
				state=lic_data.get("state"),
				license_number=lic_data.get("license_number"),
				expiry_date=date.fromisoformat(lic_data.get("expiry_date")),
				ce_requirements=int(lic_data.get("ce_requirements", 30)),
			)
			added = self.service.add_license(license)
			run.add_output("license_id", added.license_id)
			run.add_output("days_until_expiry", (added.expiry_date - date.today()).days)
			return ActionPlan(
				action="track",
				rationale=f"Tracking NP license in {added.state}",
				next_scheduled=date.today().isoformat(),
			)

	def act(self, plan: ActionPlan, run: WorkflowRun) -> ActionResult:
		"""Send notification with renewal checklist."""
		if plan.action == "notify":
			licenses = run.output_data.get("licenses", [])
			checklist = []
			if licenses:
				sample_license_id = self.service.list_all()[0].license_id
				checklist = self.service.get_renewal_checklist(sample_license_id)
			message = f"📋 {len(licenses)} NP licenses approaching renewal:\n"
			for lic in licenses[:3]:  # Show top 3
				message += f"- {lic['state']} ({lic['days_left']} days left)\n"
			if len(licenses) > 3:
				message += f"- ... and {len(licenses) - 3} more\n"
			message += "\n✅ Renewal Checklist:\n"
			for item in checklist[:3]:
				message += f"- {item}\n"
			return ActionResult(
				success=True,
				action_taken="renewal_checklist_sent",
				summary=message,
				details={"license_count": len(licenses), "checklist_items": len(checklist)},
			)
		elif plan.action == "track":
			return ActionResult(
				success=True,
				action_taken="license_tracked",
				summary=f"Tracking license in {run.input_data.get('state')}",
			)
		else:
			return ActionResult(
				success=True,
				action_taken="wait",
				summary="No licenses requiring immediate attention",
			)

	def close(self, result: ActionResult, run: WorkflowRun) -> None:
		"""Log final status."""
		run.add_output("final_status", "completed")
		run.add_output("action", result.action_taken)
