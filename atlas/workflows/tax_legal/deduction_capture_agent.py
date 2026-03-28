"""Workflow #79: Deduction Capture Agent — Phase 2 Priority.
Monitors spending and flags potential tax deductions; prompts receipt/documentation capture.
Recommended phase: 2 (quick_win_score: 12) | Trust level: suggest | Category: tax_legal
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class DeductionCategory(str, Enum):
	"""Tax deduction category."""

	HOME_OFFICE = "home_office"
	MEDICAL = "medical"
	CHARITABLE = "charitable"
	BUSINESS_EXPENSE = "business_expense"
	EDUCATION = "education"
	VEHICLE = "vehicle"
	INVESTMENT = "investment"
	OTHER = "other"


class DeductionStatus(str, Enum):
	"""Status of a flagged deduction."""

	FLAGGED = "flagged"
	DOCUMENTED = "documented"
	CONFIRMED = "confirmed"
	DISMISSED = "dismissed"


@dataclass(frozen=True, slots=True)
class SpendingItem:
	"""A spending item that may qualify as a deduction."""

	item_id: str
	description: str
	amount: float
	spend_date: date
	merchant: str
	category_hint: str = ""


@dataclass(slots=True)
class DeductionRecord:
	"""A flagged tax deduction."""

	deduction_id: str
	item_id: str
	description: str
	amount: float
	deduction_category: DeductionCategory
	status: DeductionStatus
	reason: str
	document_required: bool
	spend_date: date
	created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class DeductionSummary:
	"""Summary of captured deductions."""

	total_flagged: int
	total_documented: int
	total_confirmed: int
	total_amount_flagged: float
	total_amount_confirmed: float
	by_category: dict[str, float]


class DeductionCaptureService(PersistenceMixin):
	"""Service for identifying and tracking potential tax deductions."""

	DEDUCTION_KEYWORDS: dict[DeductionCategory, tuple[str, ...]] = {
		DeductionCategory.MEDICAL: ("pharmacy", "doctor", "hospital", "medical", "dental", "vision", "clinic", "health"),
		DeductionCategory.CHARITABLE: ("donate", "charity", "foundation", "nonprofit", "church", "red cross", "goodwill"),
		DeductionCategory.HOME_OFFICE: ("office depot", "staples", "desk", "monitor", "keyboard", "printer", "internet", "at&t", "comcast"),
		DeductionCategory.BUSINESS_EXPENSE: ("conference", "seminar", "workshop", "linkedin", "software", "subscription"),
		DeductionCategory.EDUCATION: ("tuition", "udemy", "coursera", "textbook", "university", "college", "school"),
		DeductionCategory.VEHICLE: ("auto repair", "car wash", "fuel", "gas station", "parking", "toll"),
		DeductionCategory.INVESTMENT: ("brokerage", "advisor", "fidelity", "vanguard", "schwab", "investment"),
	}

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._deductions: dict[str, DeductionRecord] = {}

	def flag_item(self, item: SpendingItem) -> DeductionRecord | None:
		"""Analyze a spending item and flag it as a potential deduction."""
		category, reason, doc_required = self._classify_item(item)
		if category is None:
			return None

		deduction_id = f"ded_{item.item_id}"
		record = DeductionRecord(
			deduction_id=deduction_id,
			item_id=item.item_id,
			description=item.description,
			amount=item.amount,
			deduction_category=category,
			status=DeductionStatus.FLAGGED,
			reason=reason,
			document_required=doc_required,
			spend_date=item.spend_date,
		)
		self._deductions[deduction_id] = record
		return record

	def mark_documented(self, deduction_id: str) -> bool:
		"""Mark a deduction as having receipt/documentation captured."""
		if deduction_id not in self._deductions:
			return False
		self._deductions[deduction_id].status = DeductionStatus.DOCUMENTED
		return True

	def confirm_deduction(self, deduction_id: str) -> bool:
		"""Confirm a deduction is valid and will be claimed."""
		if deduction_id not in self._deductions:
			return False
		self._deductions[deduction_id].status = DeductionStatus.CONFIRMED
		return True

	def dismiss_deduction(self, deduction_id: str) -> bool:
		"""Dismiss a flagged deduction as not qualifying."""
		if deduction_id not in self._deductions:
			return False
		self._deductions[deduction_id].status = DeductionStatus.DISMISSED
		return True

	def get_flagged_deductions(self) -> list[DeductionRecord]:
		"""Return all flagged (unreviewed) deductions."""
		return [d for d in self._deductions.values() if d.status == DeductionStatus.FLAGGED]

	def get_summary(self) -> DeductionSummary:
		"""Return an aggregate summary of captured deductions."""
		flagged = [d for d in self._deductions.values() if d.status == DeductionStatus.FLAGGED]
		documented = [d for d in self._deductions.values() if d.status == DeductionStatus.DOCUMENTED]
		confirmed = [d for d in self._deductions.values() if d.status == DeductionStatus.CONFIRMED]

		by_category: dict[str, float] = {}
		for d in confirmed:
			key = d.deduction_category.value
			by_category[key] = by_category.get(key, 0.0) + d.amount

		return DeductionSummary(
			total_flagged=len(flagged),
			total_documented=len(documented),
			total_confirmed=len(confirmed),
			total_amount_flagged=sum(d.amount for d in flagged),
			total_amount_confirmed=sum(d.amount for d in confirmed),
			by_category=by_category,
		)

	def _classify_item(self, item: SpendingItem) -> tuple[DeductionCategory | None, str, bool]:
		"""Classify a spending item into a deduction category."""
		text = f"{item.description} {item.merchant} {item.category_hint}".lower()
		for category, keywords in self.DEDUCTION_KEYWORDS.items():
			for keyword in keywords:
				if keyword in text:
					return category, f"Matched keyword '{keyword}' for {category.value}", True
		return None, "", False


class DeductionCaptureAgent(BaseWorkflow):
	"""Workflow for flagging and tracking potential tax deductions."""

	workflow_id = "deduction_capture"
	name = "Deduction Capture"
	category = "tax_legal"
	trust_level = TrustLevel.DRAFT

	def __init__(
		self,
		service: DeductionCaptureService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or DeductionCaptureService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle spending review requests."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		if event.event_type == "spending_item_recorded":
			p = event.payload
			item = SpendingItem(
				item_id=str(p.get("item_id", "")),
				description=str(p.get("description", "")),
				amount=float(p.get("amount", 0.0)),  # type: ignore[arg-type]
				spend_date=date.fromisoformat(str(p.get("spend_date", date.today().isoformat()))),
				merchant=str(p.get("merchant", "")),
				category_hint=str(p.get("category_hint", "")),
			)
			self.service.flag_item(item)
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Summarize flagged deductions for review."""
		summary = self.service.get_summary()
		flagged = self.service.get_flagged_deductions()
		return ActionPlan(
			action_type="review_deductions",
			confidence=0.80,
			context={
				"total_flagged": summary.total_flagged,
				"total_confirmed": summary.total_confirmed,
				"amount_flagged": summary.total_amount_flagged,
				"amount_confirmed": summary.total_amount_confirmed,
				"needs_documentation": sum(1 for d in flagged if d.document_required),
				"by_category": summary.by_category,
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Emit deduction review result."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})
		flagged = plan.context.get("total_flagged", 0)
		amount = plan.context.get("amount_flagged", 0.0)
		return ActionResult(
			True,
			f"Deduction scan complete: {flagged} potential deductions totalling ${amount:.2f}",
			{**plan.context, "policy": decision.reason},
		)
