"""Workflow #21: Insurance Proof Tracker.

Tracks renter's insurance proof collection, renewal windows, and missing policy coverage.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class InsuranceStatus(str, Enum):
	"""Insurance proof state."""

	MISSING = "missing"
	ACTIVE = "active"
	EXPIRING = "expiring"
	EXPIRED = "expired"
	CANCELLED = "cancelled"


@dataclass(slots=True)
class InsuranceProof:
	"""Tenant insurance proof record."""

	proof_id: str
	tenant_id: str
	tenant_name: str
	property_name: str
	unit: str
	provider: str
	policy_number: str
	coverage_amount: float
	expiry_date: date
	received_date: date | None = None
	document_reference: str = ""
	status: InsuranceStatus = InsuranceStatus.ACTIVE


@dataclass(frozen=True, slots=True)
class InsuranceAlert:
	"""Alert for expiring or missing insurance proof."""

	proof_id: str
	tenant_name: str
	property_unit: str
	days_remaining: int
	status: InsuranceStatus


class InsuranceProofService(PersistenceMixin):
	"""Service for tracking renter's insurance proof and expiry."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._proofs: dict[str, InsuranceProof] = {}

	def add_proof(self, proof: InsuranceProof) -> InsuranceProof:
		"""Track a tenant insurance proof."""
		if proof.received_date is None:
			proof.received_date = date.today()
		self._proofs[proof.proof_id] = proof
		return proof

	def check_expiring(self, days_ahead: int, today: date) -> list[InsuranceAlert]:
		"""Find policies that are missing, expired, or near expiry."""
		alerts: list[InsuranceAlert] = []
		for proof in self._proofs.values():
			if proof.status == InsuranceStatus.CANCELLED:
				continue

			days_remaining = (proof.expiry_date - today).days
			status = proof.status
			if days_remaining < 0:
				proof.status = InsuranceStatus.EXPIRED
				status = InsuranceStatus.EXPIRED
			elif days_remaining <= days_ahead:
				proof.status = InsuranceStatus.EXPIRING
				status = InsuranceStatus.EXPIRING

			if status in {InsuranceStatus.EXPIRING, InsuranceStatus.EXPIRED, InsuranceStatus.MISSING}:
				alerts.append(
					InsuranceAlert(
						proof_id=proof.proof_id,
						tenant_name=proof.tenant_name,
						property_unit=f"{proof.property_name}/{proof.unit}",
						days_remaining=days_remaining,
						status=status,
					)
				)

		alerts.sort(key=lambda alert: alert.days_remaining)
		return alerts

	def missing_for_tenants(self, required_tenants: list[dict[str, str]]) -> list[InsuranceProof]:
		"""Build placeholder records for tenants with no policy on file."""
		tracked_tenants = {proof.tenant_id for proof in self._proofs.values()}
		missing: list[InsuranceProof] = []
		for tenant in required_tenants:
			tenant_id = tenant.get("tenant_id", "")
			if tenant_id and tenant_id not in tracked_tenants:
				missing.append(
					InsuranceProof(
						proof_id=f"missing-{tenant_id}",
						tenant_id=tenant_id,
						tenant_name=tenant.get("tenant_name", "Unknown"),
						property_name=tenant.get("property_name", "Unknown"),
						unit=tenant.get("unit", ""),
						provider="",
						policy_number="",
						coverage_amount=0.0,
						expiry_date=date.today() - timedelta(days=1),
						status=InsuranceStatus.MISSING,
					)
				)
		return missing

	def mark_received(self, proof_id: str, document_reference: str, expiry_date: date) -> bool:
		"""Mark a proof as updated and active."""
		proof = self._proofs.get(proof_id)
		if proof is None:
			return False
		proof.document_reference = document_reference
		proof.expiry_date = expiry_date
		proof.received_date = date.today()
		proof.status = InsuranceStatus.ACTIVE
		return True

	def total_coverage(self) -> float:
		"""Return total active coverage tracked."""
		return sum(proof.coverage_amount for proof in self._proofs.values() if proof.status != InsuranceStatus.CANCELLED)


class InsuranceProofTrackerWorkflow(BaseWorkflow):
	"""Workflow for insurance proof reminders and renewal tracking."""

	workflow_id = "insurance_proof_tracker"
	name = "insurance_proof_tracker"
	category = "property"
	trust_level = TrustLevel.AUTO

	def __init__(self, service: InsuranceProofService | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = service or InsuranceProofService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		if event.event_type == "insurance_proof_received":
			payload = event.payload
			self.service.add_proof(
				InsuranceProof(
					proof_id=str(payload.get("proof_id", "")),
					tenant_id=str(payload.get("tenant_id", "")),
					tenant_name=str(payload.get("tenant_name", "")),
					property_name=str(payload.get("property_name", "")),
					unit=str(payload.get("unit", "")),
					provider=str(payload.get("provider", "")),
					policy_number=str(payload.get("policy_number", "")),
					coverage_amount=float(payload.get("coverage_amount", 0)),
					expiry_date=date.fromisoformat(str(payload.get("expiry_date", date.today().isoformat()))),
					document_reference=str(payload.get("document_reference", "")),
				)
			)
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		today = date.fromisoformat(str(run.event.payload.get("today", date.today().isoformat())))
		alerts = self.service.check_expiring(days_ahead=45, today=today)
		context = {
			"alert_count": len(alerts),
			"alerts": [
				{
					"tenant_name": alert.tenant_name,
					"property_unit": alert.property_unit,
					"days_remaining": alert.days_remaining,
					"status": alert.status.value,
				}
				for alert in alerts
			],
		}
		return ActionPlan(action_type="review_insurance_proofs", confidence=0.9 if alerts else 0.7, context=context)

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
		summary = f"Prepared {count} insurance proof reminder(s)" if count else "No insurance proof follow-up needed"
		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
