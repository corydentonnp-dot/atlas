"""Workflow #66: Employment Document Tracker — Phase 2 Priority.
Tracks employment-related document renewals (contracts, privileges, etc.).
Recommended phase: 2 (quick_win_score: 9) | Trust level: suggest | Category: licensure
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class EmploymentDocType(str, Enum):
	CONTRACT = "contract"
	PRIVILEGES = "privileges"
	ONBOARDING = "onboarding"
	COMPLIANCE = "compliance"
	OTHER = "other"


class EmploymentDocStatus(str, Enum):
	ACTIVE = "active"
	RENEWAL_DUE = "renewal_due"
	EXPIRED = "expired"
	ARCHIVED = "archived"


@dataclass(slots=True)
class EmploymentDocument:
	doc_id: str
	title: str
	doc_type: EmploymentDocType
	employer: str
	issue_date: date
	renewal_date: date
	status: EmploymentDocStatus = EmploymentDocStatus.ACTIVE

	def days_until_renewal(self) -> int:
		return (self.renewal_date - date.today()).days


@dataclass(frozen=True, slots=True)
class EmploymentDocumentSummary:
	total_docs: int
	active: int
	renewal_due: int
	expired: int


class EmploymentDocumentTrackerService(PersistenceMixin):
	RENEWAL_DUE_DAYS = 30

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._docs: dict[str, EmploymentDocument] = {}

	def add_document(
		self,
		doc_id: str,
		title: str,
		doc_type: EmploymentDocType,
		employer: str,
		issue_date: date,
		renewal_date: date,
	) -> EmploymentDocument:
		doc = EmploymentDocument(
			doc_id=doc_id,
			title=title,
			doc_type=doc_type,
			employer=employer,
			issue_date=issue_date,
			renewal_date=renewal_date,
		)
		self._docs[doc_id] = doc
		self._refresh_status(doc)
		return doc

	def archive_document(self, doc_id: str) -> bool:
		if doc_id not in self._docs:
			return False
		self._docs[doc_id].status = EmploymentDocStatus.ARCHIVED
		return True

	def get_renewal_due(self) -> list[EmploymentDocument]:
		self._refresh_all()
		return [d for d in self._docs.values() if d.status == EmploymentDocStatus.RENEWAL_DUE]

	def get_summary(self) -> EmploymentDocumentSummary:
		self._refresh_all()
		vals = list(self._docs.values())
		return EmploymentDocumentSummary(
			total_docs=len(vals),
			active=len([d for d in vals if d.status == EmploymentDocStatus.ACTIVE]),
			renewal_due=len([d for d in vals if d.status == EmploymentDocStatus.RENEWAL_DUE]),
			expired=len([d for d in vals if d.status == EmploymentDocStatus.EXPIRED]),
		)

	def _refresh_status(self, doc: EmploymentDocument) -> None:
		if doc.status == EmploymentDocStatus.ARCHIVED:
			return
		days = doc.days_until_renewal()
		if days < 0:
			doc.status = EmploymentDocStatus.EXPIRED
		elif days <= self.RENEWAL_DUE_DAYS:
			doc.status = EmploymentDocStatus.RENEWAL_DUE
		else:
			doc.status = EmploymentDocStatus.ACTIVE

	def _refresh_all(self) -> None:
		for doc in self._docs.values():
			self._refresh_status(doc)


class EmploymentDocumentTrackerWorkflow(BaseWorkflow):
	workflow_id = "employment_document_tracker"
	name = "Employment Document Tracker"
	category = "licensure"
	trust_level = TrustLevel.DRAFT

	def __init__(
		self,
		service: EmploymentDocumentTrackerService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or EmploymentDocumentTrackerService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		summary = self.service.get_summary()
		return ActionPlan(
			action_type="review_employment_documents",
			confidence=0.82,
			context={
				"total_docs": summary.total_docs,
				"renewal_due": summary.renewal_due,
				"expired": summary.expired,
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
			f"employment document tracker: {plan.context.get('renewal_due', 0)} renewal(s) due",
			{**plan.context, "policy": decision.reason},
		)
