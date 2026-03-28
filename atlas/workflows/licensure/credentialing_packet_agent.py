"""Workflow #65: Credentialing Packet Agent — Phase 2 Priority.
Assembles and tracks credentialing packet documents for employer or payer enrollment.
Recommended phase: 2 (quick_win_score: 10) | Trust level: approve | Category: licensure
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class CredentialDocType(str, Enum):
	LICENSE = "license"
	DEA = "dea"
	BOARD_CERT = "board_cert"
	MALPRACTICE = "malpractice"
	CV = "cv"
	IMMUNIZATION = "immunization"
	BACKGROUND_CHECK = "background_check"
	OTHER = "other"


class CredentialStatus(str, Enum):
	MISSING = "missing"
	SUBMITTED = "submitted"
	VERIFIED = "verified"
	EXPIRED = "expired"


@dataclass(slots=True)
class CredentialRequirement:
	doc_id: str
	packet_id: str
	name: str
	doc_type: CredentialDocType
	due_date: date
	expires_on: date | None = None
	status: CredentialStatus = CredentialStatus.MISSING

	def days_until_due(self) -> int:
		return (self.due_date - date.today()).days


@dataclass(frozen=True, slots=True)
class CredentialingSummary:
	total_requirements: int
	missing: int
	due_soon: int
	verified: int
	expired: int


class CredentialingPacketService(PersistenceMixin):
	DUE_SOON_DAYS = 10

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._requirements: dict[str, CredentialRequirement] = {}

	def add_requirement(
		self,
		doc_id: str,
		packet_id: str,
		name: str,
		doc_type: CredentialDocType,
		due_date: date,
		expires_on: date | None = None,
	) -> CredentialRequirement:
		req = CredentialRequirement(
			doc_id=doc_id,
			packet_id=packet_id,
			name=name,
			doc_type=doc_type,
			due_date=due_date,
			expires_on=expires_on,
		)
		self._requirements[doc_id] = req
		self._refresh_status(req)
		return req

	def mark_submitted(self, doc_id: str) -> bool:
		if doc_id not in self._requirements:
			return False
		self._requirements[doc_id].status = CredentialStatus.SUBMITTED
		return True

	def mark_verified(self, doc_id: str) -> bool:
		if doc_id not in self._requirements:
			return False
		self._requirements[doc_id].status = CredentialStatus.VERIFIED
		return True

	def get_missing(self) -> list[CredentialRequirement]:
		self._refresh_all()
		return [r for r in self._requirements.values() if r.status == CredentialStatus.MISSING]

	def get_due_soon(self) -> list[CredentialRequirement]:
		self._refresh_all()
		return [
			r for r in self._requirements.values()
			if r.status == CredentialStatus.MISSING and 0 <= r.days_until_due() <= self.DUE_SOON_DAYS
		]

	def get_summary(self) -> CredentialingSummary:
		self._refresh_all()
		vals = list(self._requirements.values())
		return CredentialingSummary(
			total_requirements=len(vals),
			missing=len([r for r in vals if r.status == CredentialStatus.MISSING]),
			due_soon=len(self.get_due_soon()),
			verified=len([r for r in vals if r.status == CredentialStatus.VERIFIED]),
			expired=len([r for r in vals if r.status == CredentialStatus.EXPIRED]),
		)

	def _refresh_status(self, req: CredentialRequirement) -> None:
		if req.status in (CredentialStatus.SUBMITTED, CredentialStatus.VERIFIED):
			return
		if req.expires_on is not None and req.expires_on < date.today():
			req.status = CredentialStatus.EXPIRED
		elif req.due_date < date.today():
			req.status = CredentialStatus.EXPIRED
		else:
			req.status = CredentialStatus.MISSING

	def _refresh_all(self) -> None:
		for req in self._requirements.values():
			self._refresh_status(req)


class CredentialingPacketAgent(BaseWorkflow):
	workflow_id = "credentialing_packet"
	name = "Credentialing Packet Agent"
	category = "licensure"
	trust_level = TrustLevel.APPROVAL

	def __init__(
		self,
		service: CredentialingPacketService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or CredentialingPacketService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		summary = self.service.get_summary()
		return ActionPlan(
			action_type="review_credential_packet",
			confidence=0.9,
			context={
				"total_requirements": summary.total_requirements,
				"missing": summary.missing,
				"due_soon": summary.due_soon,
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
		return ActionResult(
			True,
			f"credentialing packet: {plan.context.get('missing', 0)} missing requirement(s)",
			{**plan.context, "policy": decision.reason},
		)
