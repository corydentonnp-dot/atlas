"""Workflow #96: Product Research Agent — Phase 3 Priority.
Gathers reviews, comparisons, and specs for products under consideration.
Recommended phase: 3 (quick_win_score: 8) | Trust level: suggest | Category: shopping
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class ResearchStatus(str, Enum):
	RESEARCHING = "researching"
	SHORTLISTED = "shortlisted"
	REJECTED = "rejected"
	SELECTED = "selected"


@dataclass(slots=True)
class ProductCandidate:
	product_id: str
	name: str
	category: str
	price: float
	rating: float
	review_count: int
	status: ResearchStatus = ResearchStatus.RESEARCHING

	def score(self) -> float:
		return (self.rating * 20.0) + min(self.review_count / 10.0, 20.0) - (self.price / 100.0)


@dataclass(frozen=True, slots=True)
class ProductResearchSummary:
	total_candidates: int
	shortlisted: int
	best_candidate: str


class ProductResearchService(PersistenceMixin):
	SHORTLIST_SCORE = 90.0

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._candidates: dict[str, ProductCandidate] = {}

	def add_candidate(
		self,
		product_id: str,
		name: str,
		category: str,
		price: float,
		rating: float,
		review_count: int,
	) -> ProductCandidate:
		candidate = ProductCandidate(
			product_id=product_id,
			name=name,
			category=category,
			price=price,
			rating=rating,
			review_count=review_count,
		)
		if candidate.score() >= self.SHORTLIST_SCORE:
			candidate.status = ResearchStatus.SHORTLISTED
		self._candidates[product_id] = candidate
		return candidate

	def mark_selected(self, product_id: str) -> bool:
		if product_id not in self._candidates:
			return False
		self._candidates[product_id].status = ResearchStatus.SELECTED
		return True

	def get_shortlist(self) -> list[ProductCandidate]:
		return [c for c in self._candidates.values() if c.status == ResearchStatus.SHORTLISTED]

	def get_summary(self) -> ProductResearchSummary:
		vals = list(self._candidates.values())
		best = max(vals, key=lambda c: c.score(), default=None)
		return ProductResearchSummary(
			total_candidates=len(vals),
			shortlisted=len([c for c in vals if c.status == ResearchStatus.SHORTLISTED]),
			best_candidate=best.name if best else "",
		)


class ProductResearchAgent(BaseWorkflow):
	workflow_id = "product_research"
	name = "Product Research Agent"
	category = "shopping"
	trust_level = TrustLevel.DRAFT

	def __init__(
		self,
		service: ProductResearchService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or ProductResearchService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		summary = self.service.get_summary()
		return ActionPlan(
			action_type="present_product_research",
			confidence=0.77,
			context={
				"total_candidates": summary.total_candidates,
				"shortlisted": summary.shortlisted,
				"best_candidate": summary.best_candidate,
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
			f"product research: {plan.context.get('shortlisted', 0)} shortlisted candidate(s)",
			{**plan.context, "policy": decision.reason},
		)
