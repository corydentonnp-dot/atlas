"""Workflow #63: BLS/ACLS Renewal Agent — tracks healthcare certifications.

Monitors BLS and ACLS certification renewal dates.
Alert on renewal deadlines and training scheduling.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from uuid import uuid4

from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class CertificationStatus(str, Enum):
	"""Certification status."""

	ACTIVE = "active"
	COMING_DUE = "coming_due"
	EXPIRED = "expired"
	RENEWED = "renewed"


@dataclass(slots=True)
class Certification:
	"""BLS or ACLS certification."""

	cert_id: str
	cert_type: str  # "BLS" or "ACLS"
	issue_date: date
	expiry_date: date
	certification_body: str = ""  # AHA, etc.
	status: CertificationStatus = CertificationStatus.ACTIVE
	card_number: str = ""


@dataclass(frozen=True, slots=True)
class CertAlert:
	"""Alert for approaching certification expiration."""

	cert_id: str
	cert_type: str
	days_remaining: int
	expiry_date: date
	training_providers: list[str] = None


class BLSACLSService:
	"""Service for tracking BLS and ACLS certifications."""

	def __init__(self) -> None:
		self._certifications: dict[str, Certification] = {}
		self._renewal_history: dict[str, list[date]] = {}
		self.training_providers = ["American Heart Association", "Red Cross", "ProTrainings", "ACLS.com"]

	def add_certification(self, cert: Certification) -> Certification:
		"""Track a new BLS/ACLS certification."""
		self._certifications[cert.cert_id] = cert
		self._renewal_history[cert.cert_id] = []
		return cert

	def check_expiring(self, days_ahead: int, today: date) -> list[Certification]:
		"""Find certifications expiring within specified days."""
		results: list[Certification] = []
		for cert in self._certifications.values():
			days_remaining = (cert.expiry_date - today).days
			if 0 <= days_remaining <= days_ahead and cert.status == CertificationStatus.ACTIVE:
				results.append(cert)
		results.sort(key=lambda c: (c.expiry_date - today).days)
		return results

	def get_training_providers(self) -> list[str]:
		"""Get list of BLS/ACLS training providers."""
		return self.training_providers

	def mark_renewed(self, cert_id: str, new_expiry: date) -> bool:
		"""Mark a certification as renewed."""
		if cert_id in self._certifications:
			cert = self._certifications[cert_id]
			cert.status = CertificationStatus.RENEWED
			self._renewal_history[cert_id].append(date.today())
			cert.expiry_date = new_expiry
			cert.status = CertificationStatus.ACTIVE
			return True
		return False



class BLSACLSRenewalAgent(BaseWorkflow):
	"""Workflow for tracking BLS and ACLS certification renewals."""

	name = "bls_acls_renewal_agent"
	description = "Track BLS/ACLS certifications; alert on renewal deadlines"
	category = "licensure"
	version = "1.0.0"

	def __init__(self) -> None:
		super().__init__()
		self.service = BLSACLSService()
		self.policy = PolicyEngine()

	def trigger(self, event: WorkflowEvent) -> bool:
		"""Triggered by daily check or cert addition."""
		return event.event_type in {"cert.added", "cert.check_due"}

	def process(self, run: WorkflowRun) -> ActionPlan:
		"""Identify certifications approaching expiration."""
		if not run.input_data:
			# Daily check mode
			today = date.today()
			expiring = self.service.check_expiring(days_ahead=180, today=today)
			if not expiring:
				return ActionPlan(
					action="wait",
					rationale="No BLS/ACLS certifications expiring soon",
					next_scheduled=date.today().isoformat(),
				)
			run.add_output("certs_expiring_count", len(expiring))
			run.add_output("certifications", [
				{
					"cert_type": c.cert_type,
					"expiry_date": c.expiry_date.isoformat(),
					"days_left": (c.expiry_date - today).days,
				}
				for c in expiring
			])
			return ActionPlan(
				action="notify",
				rationale=f"Found {len(expiring)} certification(s) approaching renewal",
				target_audience="user",
				next_scheduled=date.today().isoformat(),
			)
		else:
			# New cert added
			cert_data = run.input_data
			cert = Certification(
				cert_id=cert_data.get("cert_id", str(uuid4())),
				cert_type=cert_data.get("cert_type", "BLS"),
				issue_date=date.fromisoformat(cert_data.get("issue_date", date.today().isoformat())),
				expiry_date=date.fromisoformat(cert_data.get("expiry_date")),
				certification_body=cert_data.get("certification_body", "AHA"),
				card_number=cert_data.get("card_number", ""),
			)
			added = self.service.add_certification(cert)
			run.add_output("cert_id", added.cert_id)
			run.add_output("days_until_expiry", (added.expiry_date - date.today()).days)
			return ActionPlan(
				action="track",
				rationale=f"Tracking {added.cert_type} certification",
				next_scheduled=date.today().isoformat(),
			)

	def act(self, plan: ActionPlan, run: WorkflowRun) -> ActionResult:
		"""Send renewal alert with training options."""
		if plan.action == "notify":
			certs = run.output_data.get("certifications", [])
			providers = self.service.get_training_providers()
			message = f"🏥 BLS/ACLS Renewal Required:\n"
			message += f"{len(certs)} certification(s) need renewal\n\n"
			for cert in certs[:2]:
				message += f"- {cert['cert_type']}: expires {cert['expiry_date']} ({cert['days_left']} days)\n"
			if len(certs) > 2:
				message += f"- ... and {len(certs) - 2} more\n"
			message += "\n📚 Training Providers:\n"
			for provider in providers[:3]:
				message += f"- {provider}\n"
			return ActionResult(
				success=True,
				action_taken="renewal_alert_sent",
				summary=message,
				details={"cert_count": len(certs)},
			)
		elif plan.action == "track":
			return ActionResult(
				success=True,
				action_taken="cert_tracked",
				summary=f"Tracking {run.input_data.get('cert_type')} certification",
			)
		else:
			return ActionResult(
				success=True,
				action_taken="wait",
				summary="No BLS/ACLS certifications need immediate renewal",
			)

	def close(self, result: ActionResult, run: WorkflowRun) -> None:
		"""Log final status."""
		run.add_output("final_status", "completed")
		run.add_output("action", result.action_taken)
