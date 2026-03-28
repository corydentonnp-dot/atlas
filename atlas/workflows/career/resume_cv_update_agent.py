"""Workflow #69: Resume/CV Update Agent — Phase 2 Priority.
Prompts periodic resume/CV updates; tracks new skills, certifications, and accomplishments.
Recommended phase: 2 (quick_win_score: 10) | Trust level: suggest | Category: career
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class UpdateType(str, Enum):
	SKILL = "skill"
	CERTIFICATION = "certification"
	PROJECT = "project"
	PUBLICATION = "publication"
	AWARD = "award"
	ROLE_CHANGE = "role_change"
	OTHER = "other"


class ResumeUpdateStatus(str, Enum):
	CAPTURED = "captured"
	ADDED_TO_RESUME = "added_to_resume"
	DISMISSED = "dismissed"


@dataclass(slots=True)
class ResumeUpdateItem:
	item_id: str
	title: str
	update_type: UpdateType
	impact: str
	occurred_on: date
	status: ResumeUpdateStatus = ResumeUpdateStatus.CAPTURED


@dataclass(frozen=True, slots=True)
class ResumeUpdateSummary:
	total_items: int
	pending_items: int
	added_to_resume: int


class ResumeCvUpdateService(PersistenceMixin):
	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._items: dict[str, ResumeUpdateItem] = {}

	def add_item(
		self,
		item_id: str,
		title: str,
		update_type: UpdateType,
		impact: str,
		occurred_on: date,
	) -> ResumeUpdateItem:
		item = ResumeUpdateItem(
			item_id=item_id,
			title=title,
			update_type=update_type,
			impact=impact,
			occurred_on=occurred_on,
		)
		self._items[item_id] = item
		return item

	def mark_added(self, item_id: str) -> bool:
		if item_id not in self._items:
			return False
		self._items[item_id].status = ResumeUpdateStatus.ADDED_TO_RESUME
		return True

	def dismiss(self, item_id: str) -> bool:
		if item_id not in self._items:
			return False
		self._items[item_id].status = ResumeUpdateStatus.DISMISSED
		return True

	def get_pending(self) -> list[ResumeUpdateItem]:
		return [i for i in self._items.values() if i.status == ResumeUpdateStatus.CAPTURED]

	def get_summary(self) -> ResumeUpdateSummary:
		vals = list(self._items.values())
		return ResumeUpdateSummary(
			total_items=len(vals),
			pending_items=len(self.get_pending()),
			added_to_resume=len([i for i in vals if i.status == ResumeUpdateStatus.ADDED_TO_RESUME]),
		)


class ResumeCvUpdateAgent(BaseWorkflow):
	workflow_id = "resume_cv_update"
	name = "Resume/CV Update Agent"
	category = "career"
	trust_level = TrustLevel.DRAFT

	def __init__(
		self,
		service: ResumeCvUpdateService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or ResumeCvUpdateService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		summary = self.service.get_summary()
		return ActionPlan(
			action_type="review_resume_updates",
			confidence=0.84,
			context={
				"total_items": summary.total_items,
				"pending_items": summary.pending_items,
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
			f"resume/cv update: {plan.context.get('pending_items', 0)} item(s) pending",
			{**plan.context, "policy": decision.reason},
		)
