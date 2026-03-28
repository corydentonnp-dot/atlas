"""Workflow #80: Document Vault Organizer — Phase 2 Priority.
Organizes and indexes important legal/financial documents in Google Drive.
Recommended phase: 2 (quick_win_score: 10) | Trust level: approve | Category: tax_legal
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun

_EXPIRING_SOON_DAYS = 90


class DocumentCategory(str, Enum):
	"""Category of a tracked document."""

	TAX_RETURN = "tax_return"
	BUSINESS_LICENSE = "business_license"
	INSURANCE_POLICY = "insurance_policy"
	CONTRACT = "contract"
	LEASE = "lease"
	WILL_TRUST = "will_trust"
	IDENTIFICATION = "identification"
	MEDICAL = "medical"
	FINANCIAL = "financial"
	OTHER = "other"


class VaultStatus(str, Enum):
	"""Storage status of document vault records."""

	LOGGED = "logged"
	UPLOADED = "uploaded"
	VERIFIED = "verified"
	ARCHIVED = "archived"
	MISSING = "missing"


@dataclass(slots=True)
class VaultDocument:
	"""A document tracked in the digital vault."""

	doc_id: str
	title: str
	category: DocumentCategory
	issue_date: date
	source: str
	expiry_date: date | None = None
	tags: list[str] = field(default_factory=list)
	status: VaultStatus = VaultStatus.LOGGED
	drive_link: str = ""
	notes: str = ""

	def is_expiring_soon(self) -> bool:
		"""Whether the document expires within 90 days."""
		if self.expiry_date is None:
			return False
		return 0 <= (self.expiry_date - date.today()).days <= _EXPIRING_SOON_DAYS


@dataclass(frozen=True, slots=True)
class VaultSummary:
	"""Summary of the document vault."""

	total_logged: int
	uploaded: int
	verified: int
	missing: int
	expiring_soon: int


class DocumentVaultService(PersistenceMixin):
	"""Service for indexing and tracking important documents."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._docs: dict[str, VaultDocument] = {}

	def log_document(
		self,
		doc_id: str,
		title: str,
		category: DocumentCategory,
		issue_date: date,
		source: str,
		expiry_date: date | None = None,
		tags: list[str] | None = None,
		notes: str = "",
	) -> VaultDocument:
		"""Log a document to the vault index."""
		doc = VaultDocument(
			doc_id=doc_id,
			title=title,
			category=category,
			issue_date=issue_date,
			source=source,
			expiry_date=expiry_date,
			tags=tags or [],
			notes=notes,
		)
		self._docs[doc_id] = doc
		return doc

	def mark_uploaded(self, doc_id: str, drive_link: str = "") -> bool:
		"""Mark a document as uploaded to cloud storage."""
		if doc_id not in self._docs:
			return False
		self._docs[doc_id].status = VaultStatus.UPLOADED
		if drive_link:
			self._docs[doc_id].drive_link = drive_link
		return True

	def mark_verified(self, doc_id: str) -> bool:
		"""Mark a document as verified accessible."""
		if doc_id not in self._docs:
			return False
		self._docs[doc_id].status = VaultStatus.VERIFIED
		return True

	def get_expiring_soon(self) -> list[VaultDocument]:
		"""Return documents expiring within 90 days."""
		return [d for d in self._docs.values() if d.is_expiring_soon()]

	def get_by_category(self, category: DocumentCategory) -> list[VaultDocument]:
		"""Return all documents in a given category."""
		return [d for d in self._docs.values() if d.category == category]

	def get_summary(self) -> VaultSummary:
		"""Return a summary of the vault."""
		return VaultSummary(
			total_logged=len(self._docs),
			uploaded=len([d for d in self._docs.values() if d.status in (VaultStatus.UPLOADED, VaultStatus.VERIFIED)]),
			verified=len([d for d in self._docs.values() if d.status == VaultStatus.VERIFIED]),
			missing=len([d for d in self._docs.values() if d.status == VaultStatus.MISSING]),
			expiring_soon=len(self.get_expiring_soon()),
		)


class DocumentVaultOrganizerWorkflow(BaseWorkflow):
	"""Workflow for organizing and indexing important documents."""

	workflow_id = "document_vault_organizer"
	name = "Document Vault Organizer"
	category = "tax_legal"
	trust_level = TrustLevel.APPROVAL

	def __init__(
		self,
		service: DocumentVaultService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or DocumentVaultService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Accept a vault audit request."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Audit vault completeness and flag expiring documents."""
		summary = self.service.get_summary()
		return ActionPlan(
			action_type="audit_document_vault",
			confidence=0.90,
			context={
				"total_logged": summary.total_logged,
				"uploaded": summary.uploaded,
				"missing": summary.missing,
				"expiring_soon": summary.expiring_soon,
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Produce audit report of vault health."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})
		expiring = plan.context.get("expiring_soon", 0)
		return ActionResult(
			True,
			f"document vault: {plan.context.get('total_logged', 0)} logged, {expiring} expiring soon",
			{**plan.context, "policy": decision.reason},
		)
