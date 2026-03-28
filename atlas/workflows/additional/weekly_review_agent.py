"""Workflow #102: Weekly Review Agent.

Generates weekly progress summaries with wins, blockers, and next priorities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class ReviewPriority(str, Enum):
	"""Priority level for weekly items."""

	LOW = "low"
	MEDIUM = "medium"
	HIGH = "high"


@dataclass(slots=True)
class WeeklyItem:
	"""A completed or pending weekly work item."""

	item_id: str
	title: str
	category: str
	priority: ReviewPriority = ReviewPriority.MEDIUM
	completed: bool = False


@dataclass(slots=True)
class WeeklyReview:
	"""Compiled weekly review output."""

	review_id: str
	week_of: date
	completed_count: int
	pending_count: int
	wins: list[str] = field(default_factory=list)
	blockers: list[str] = field(default_factory=list)
	next_priorities: list[WeeklyItem] = field(default_factory=list)
	generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class WeeklyReviewService(PersistenceMixin):
	"""Service for building weekly review summaries."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._items: dict[str, WeeklyItem] = {}
		self._wins: list[str] = []
		self._blockers: list[str] = []

	def add_item(self, item: WeeklyItem) -> WeeklyItem:
		"""Add or update a weekly item."""
		self._items[item.item_id] = item
		return item

	def add_win(self, win: str) -> None:
		"""Record a weekly win."""
		if win.strip():
			self._wins.append(win.strip())

	def add_blocker(self, blocker: str) -> None:
		"""Record a weekly blocker."""
		if blocker.strip():
			self._blockers.append(blocker.strip())

	def get_next_priorities(self, limit: int = 5) -> list[WeeklyItem]:
		"""Return pending items sorted by priority."""
		rank = {
			ReviewPriority.HIGH: 2,
			ReviewPriority.MEDIUM: 1,
			ReviewPriority.LOW: 0,
		}
		pending = [item for item in self._items.values() if not item.completed]
		pending.sort(key=lambda item: (-rank[item.priority], item.title.lower()))
		return pending[:limit]

	def build_review(self, week_of: date) -> WeeklyReview:
		"""Compile weekly review output."""
		completed_count = sum(1 for item in self._items.values() if item.completed)
		pending_count = sum(1 for item in self._items.values() if not item.completed)
		return WeeklyReview(
			review_id=f"weekly_review_{week_of.isoformat()}",
			week_of=week_of,
			completed_count=completed_count,
			pending_count=pending_count,
			wins=list(self._wins),
			blockers=list(self._blockers),
			next_priorities=self.get_next_priorities(),
		)


class WeeklyReviewAgent(BaseWorkflow):
	"""Workflow for generating weekly reviews."""

	workflow_id = "weekly_review"
	name = "Weekly Review Agent"
	category = "additional"
	trust_level = TrustLevel.AUTO

	def __init__(
		self,
		service: WeeklyReviewService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or WeeklyReviewService(session=session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Initialize a weekly review run."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Compile review context for action execution."""
		payload = run.event.payload
		week_of = date.fromisoformat(cast(str, payload.get("week_of", date.today().isoformat())))
		review = self.service.build_review(week_of=week_of)

		return ActionPlan(
			action_type="publish_weekly_review",
			confidence=0.9,
			context={
				"review_id": review.review_id,
				"week_of": review.week_of.isoformat(),
				"completed_count": review.completed_count,
				"pending_count": review.pending_count,
				"wins_count": len(review.wins),
				"blockers_count": len(review.blockers),
				"next_priorities_count": len(review.next_priorities),
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Evaluate policy and publish review summary."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})

		summary = (
			f"Weekly review {plan.context.get('review_id')} ready: "
			f"completed={plan.context.get('completed_count')} "
			f"pending={plan.context.get('pending_count')}"
		)
		return ActionResult(
			success=True,
			summary=summary,
			metadata={**plan.context, "policy": decision.reason},
		)
