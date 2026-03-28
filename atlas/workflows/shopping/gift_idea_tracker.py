"""Workflow #95: Gift Idea Tracker — Phase 3 Priority.
Tracks gift ideas for contacts; reminds before birthdays and holidays.
Recommended phase: 3 (quick_win_score: 9) | Trust level: suggest | Category: shopping
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class OccasionType(str, Enum):
	BIRTHDAY = "birthday"
	ANNIVERSARY = "anniversary"
	HOLIDAY = "holiday"
	GRADUATION = "graduation"
	OTHER = "other"


class GiftIdeaStatus(str, Enum):
	IDEA = "idea"
	PURCHASED = "purchased"
	GIFTED = "gifted"
	ARCHIVED = "archived"


@dataclass(slots=True)
class GiftIdea:
	idea_id: str
	contact_name: str
	occasion: OccasionType
	occasion_date: date
	idea: str
	estimated_cost: float
	status: GiftIdeaStatus = GiftIdeaStatus.IDEA

	def days_until_occasion(self) -> int:
		return (self.occasion_date - date.today()).days


@dataclass(frozen=True, slots=True)
class GiftIdeaSummary:
	total_ideas: int
	pending: int
	occasions_soon: int
	purchased: int


class GiftIdeaTrackerService(PersistenceMixin):
	OCCASION_SOON_DAYS = 21

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._ideas: dict[str, GiftIdea] = {}

	def add_idea(
		self,
		idea_id: str,
		contact_name: str,
		occasion: OccasionType,
		occasion_date: date,
		idea: str,
		estimated_cost: float,
	) -> GiftIdea:
		gift = GiftIdea(
			idea_id=idea_id,
			contact_name=contact_name,
			occasion=occasion,
			occasion_date=occasion_date,
			idea=idea,
			estimated_cost=estimated_cost,
		)
		self._ideas[idea_id] = gift
		return gift

	def mark_purchased(self, idea_id: str) -> bool:
		if idea_id not in self._ideas:
			return False
		self._ideas[idea_id].status = GiftIdeaStatus.PURCHASED
		return True

	def mark_gifted(self, idea_id: str) -> bool:
		if idea_id not in self._ideas:
			return False
		self._ideas[idea_id].status = GiftIdeaStatus.GIFTED
		return True

	def get_occasions_soon(self) -> list[GiftIdea]:
		return [
			i for i in self._ideas.values()
			if i.status == GiftIdeaStatus.IDEA and 0 <= i.days_until_occasion() <= self.OCCASION_SOON_DAYS
		]

	def get_summary(self) -> GiftIdeaSummary:
		vals = list(self._ideas.values())
		return GiftIdeaSummary(
			total_ideas=len(vals),
			pending=len([i for i in vals if i.status == GiftIdeaStatus.IDEA]),
			occasions_soon=len(self.get_occasions_soon()),
			purchased=len([i for i in vals if i.status == GiftIdeaStatus.PURCHASED]),
		)


class GiftIdeaTrackerWorkflow(BaseWorkflow):
	workflow_id = "gift_idea_tracker"
	name = "Gift Idea Tracker"
	category = "shopping"
	trust_level = TrustLevel.DRAFT

	def __init__(
		self,
		service: GiftIdeaTrackerService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or GiftIdeaTrackerService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		summary = self.service.get_summary()
		return ActionPlan(
			action_type="review_gift_ideas",
			confidence=0.8,
			context={
				"pending": summary.pending,
				"occasions_soon": summary.occasions_soon,
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
			f"gift idea tracker: {plan.context.get('occasions_soon', 0)} occasion(s) soon",
			{**plan.context, "policy": decision.reason},
		)
