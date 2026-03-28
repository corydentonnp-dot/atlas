"""Workflow #81: Legal Document Review Agent — Phase 3 Priority.
Flags key dates and terms in leases, contracts, and legal agreements.
Recommended phase: 3 (quick_win_score: 8) | Trust level: approve | Category: tax_legal
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class LegalDocumentType(str, Enum):
	LEASE = "lease"
	CONTRACT = "contract"
	NDA = "nda"
	SERVICE_AGREEMENT = "service_agreement"
	OTHER = "other"


class LegalReviewStatus(str, Enum):
	PENDING = "pending"
	REVIEWED = "reviewed"
	FLAGGED = "flagged"
	ARCHIVED = "archived"


@dataclass(slots=True)
class LegalDocument:
	doc_id: str
	title: str
	doc_type: LegalDocumentType
	effective_date: date
	renewal_date: date | None = None
	terms: list[str] = field(default_factory=list)
	flags: list[str] = field(default_factory=list)
	status: LegalReviewStatus = LegalReviewStatus.PENDING


@dataclass(frozen=True, slots=True)
class LegalReviewSummary:
	total_docs: int
	pending: int
	flagged: int
	renewing_soon: int


class LegalDocumentReviewService(PersistenceMixin):
	RENEWING_SOON_DAYS = 45

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._docs: dict[str, LegalDocument] = {}

	def add_document(
		self,
		doc_id: str,
		title: str,
		doc_type: LegalDocumentType,
		effective_date: date,
		renewal_date: date | None = None,
		terms: list[str] | None = None,
	) -> LegalDocument:
		doc = LegalDocument(
			doc_id=doc_id,
			title=title,
			doc_type=doc_type,
			effective_date=effective_date,
			renewal_date=renewal_date,
			terms=terms or [],
		)
		self._docs[doc_id] = doc
		return doc

	def review_document(self, doc_id: str, flags: list[str] | None = None) -> bool:
		if doc_id not in self._docs:
			return False
		doc = self._docs[doc_id]
		doc.flags = flags or []
		doc.status = LegalReviewStatus.FLAGGED if doc.flags else LegalReviewStatus.REVIEWED
		return True

	def get_flagged(self) -> list[LegalDocument]:
		return [d for d in self._docs.values() if d.status == LegalReviewStatus.FLAGGED]

	def get_renewing_soon(self) -> list[LegalDocument]:
		results: list[LegalDocument] = []
		for doc in self._docs.values():
			if doc.renewal_date is None:
				continue
			days = (doc.renewal_date - date.today()).days
			if 0 <= days <= self.RENEWING_SOON_DAYS:
				results.append(doc)
		return results

	def get_summary(self) -> LegalReviewSummary:
		vals = list(self._docs.values())
		return LegalReviewSummary(
			total_docs=len(vals),
			pending=len([d for d in vals if d.status == LegalReviewStatus.PENDING]),
			flagged=len([d for d in vals if d.status == LegalReviewStatus.FLAGGED]),
			renewing_soon=len(self.get_renewing_soon()),
		)


class LegalDocumentReviewAgent(BaseWorkflow):
	workflow_id = "legal_document_review"
	name = "Legal Document Review Agent"
	category = "tax_legal"
	trust_level = TrustLevel.APPROVAL

	def __init__(
		self,
		service: LegalDocumentReviewService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or LegalDocumentReviewService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		summary = self.service.get_summary()
		return ActionPlan(
			action_type="review_legal_documents",
			confidence=0.85,
			context={
				"pending": summary.pending,
				"flagged": summary.flagged,
				"renewing_soon": summary.renewing_soon,
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
			f"legal document review: {plan.context.get('flagged', 0)} flagged document(s)",
			{**plan.context, "policy": decision.reason},
		)
