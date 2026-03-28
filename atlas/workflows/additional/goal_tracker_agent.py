"""Workflow #103: Goal Tracker Agent — Phase 2 Priority.
Tracks personal and professional goals; measures progress and suggests adjustments.
Recommended phase: 2 (quick_win_score: 10) | Trust level: suggest | Category: additional
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class GoalStatus(str, Enum):
	"""Status of a goal."""

	NOT_STARTED = "not_started"
	ON_TRACK = "on_track"
	AT_RISK = "at_risk"
	BLOCKED = "blocked"
	COMPLETED = "completed"
	ABANDONED = "abandoned"


class GoalType(str, Enum):
	"""Type of goal."""

	PERSONAL = "personal"
	PROFESSIONAL = "professional"
	WELLNESS = "wellness"
	FINANCIAL = "financial"


@dataclass(frozen=True, slots=True)
class Goal:
	"""Personal or professional goal."""

	goal_id: str
	title: str
	description: str
	goal_type: GoalType
	progress_percentage: float
	status: GoalStatus
	target_date: date
	created_at: datetime = datetime.now(timezone.utc)
	category: str = ""
	key_results: list[str] | None = None


@dataclass(frozen=True, slots=True)
class GoalAdjustment:
	"""Recommended adjustment for a goal."""

	goal_id: str
	title: str
	current_status: GoalStatus
	suggested_action: str
	priority_change: str
	risk_level: str


@dataclass(frozen=True, slots=True)
class GoalProgress:
	"""Progress summary for goals."""

	total_goals: int
	on_track: int
	at_risk: int
	blocked: int
	completed: int
	abandoned: int
	average_progress: float
	adjustments_needed: int


class GoalTrackerService(PersistenceMixin):
	"""Service for tracking personal and professional goals."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._goals: dict[str, Goal] = {}
		self._adjustments: dict[str, list[GoalAdjustment]] = {}

	def create_goal(
		self,
		goal_id: str,
		title: str,
		description: str,
		goal_type: GoalType,
		target_date: date,
		category: str = "",
		key_results: list[str] | None = None,
	) -> Goal:
		"""Create a new goal."""
		goal = Goal(
			goal_id=goal_id,
			title=title,
			description=description,
			goal_type=goal_type,
			progress_percentage=0.0,
			status=GoalStatus.NOT_STARTED,
			target_date=target_date,
			category=category,
			key_results=key_results,
		)
		self._goals[goal_id] = goal
		return goal

	def update_progress(self, goal_id: str, progress_percentage: float) -> Goal | None:
		"""Update goal progress percentage."""
		if goal_id not in self._goals:
			return None
		goal = self._goals[goal_id]
		status = self._infer_status(goal, progress_percentage)
		updated = Goal(
			goal_id=goal.goal_id,
			title=goal.title,
			description=goal.description,
			goal_type=goal.goal_type,
			progress_percentage=min(100.0, max(0.0, progress_percentage)),
			status=status,
			target_date=goal.target_date,
			created_at=goal.created_at,
			category=goal.category,
			key_results=goal.key_results,
		)
		self._goals[goal_id] = updated
		return updated

	def get_goal_summary(self) -> GoalProgress:
		"""Get overall goal progress summary."""
		if not self._goals:
			return GoalProgress(0, 0, 0, 0, 0, 0, 0.0, 0)

		on_track = sum(1 for g in self._goals.values() if g.status == GoalStatus.ON_TRACK)
		at_risk = sum(1 for g in self._goals.values() if g.status == GoalStatus.AT_RISK)
		blocked = sum(1 for g in self._goals.values() if g.status == GoalStatus.BLOCKED)
		completed = sum(1 for g in self._goals.values() if g.status == GoalStatus.COMPLETED)
		abandoned = sum(1 for g in self._goals.values() if g.status == GoalStatus.ABANDONED)

		total = len(self._goals)
		avg_progress = sum(g.progress_percentage for g in self._goals.values()) / total if total > 0 else 0.0
		adjustments_needed = at_risk + blocked

		return GoalProgress(
			total_goals=total,
			on_track=on_track,
			at_risk=at_risk,
			blocked=blocked,
			completed=completed,
			abandoned=abandoned,
			average_progress=avg_progress,
			adjustments_needed=adjustments_needed,
		)

	def suggest_adjustments(self) -> list[GoalAdjustment]:
		"""Suggest adjustments for at-risk or blocked goals."""
		adjustments = []
		for goal in self._goals.values():
			if goal.status in (GoalStatus.AT_RISK, GoalStatus.BLOCKED):
				risk_level = "high" if goal.status == GoalStatus.BLOCKED else "medium"
				suggested_action = self._suggest_action(goal)
				adjustment = GoalAdjustment(
					goal_id=goal.goal_id,
					title=goal.title,
					current_status=goal.status,
					suggested_action=suggested_action,
					priority_change="consider_deprioritizing" if goal.status == GoalStatus.BLOCKED else "increase_engagement",
					risk_level=risk_level,
				)
				adjustments.append(adjustment)
		return adjustments

	def get_goals_by_status(self, status: GoalStatus) -> list[Goal]:
		"""Get all goals with a specific status."""
		return [g for g in self._goals.values() if g.status == status]

	def get_all_goals(self) -> list[Goal]:
		"""Get all goals."""
		return list(self._goals.values())

	def _infer_status(self, goal: Goal, progress: float) -> GoalStatus:
		"""Infer goal status based on progress and target date."""
		if progress >= 100.0:
			return GoalStatus.COMPLETED
		if progress == 0.0 and goal.status == GoalStatus.NOT_STARTED:
			return GoalStatus.NOT_STARTED
		if progress >= 75.0:
			return GoalStatus.ON_TRACK
		if progress >= 50.0:
			return GoalStatus.ON_TRACK
		if progress >= 25.0:
			return GoalStatus.AT_RISK
		return GoalStatus.AT_RISK

	def _suggest_action(self, goal: Goal) -> str:
		"""Suggest an action for an at-risk or blocked goal."""
		if goal.status == GoalStatus.BLOCKED:
			return f"Unblock '{goal.title}' by identifying and resolving key blockers"
		if goal.progress_percentage < 25.0:
			return f"Create concrete milestones for '{goal.title}' and establish weekly check-ins"
		return f"Increase momentum on '{goal.title}' with focused effort or adjust target date"


class GoalTrackerAgent(BaseWorkflow):
	"""Workflow for tracking goals and suggesting adjustments."""

	workflow_id = "goal_tracker"
	name = "Goal Tracker"
	category = "additional"
	trust_level = TrustLevel.DRAFT

	def __init__(
		self,
		service: GoalTrackerService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or GoalTrackerService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle goal tracking requests."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Process goal tracking and analysis."""
		payload = run.event.payload or {}

		# Get current goals summary
		summary = self.service.get_goal_summary()
		adjustments = self.service.suggest_adjustments()

		return ActionPlan(
			action_type="track_goals",
			confidence=0.85,
			context={
				"total_goals": summary.total_goals,
				"on_track_count": summary.on_track,
				"at_risk_count": summary.at_risk,
				"blocked_count": summary.blocked,
				"completed_count": summary.completed,
				"average_progress": summary.average_progress,
				"adjustments_suggested": len(adjustments),
				"update_request": payload.get("update_request", "summary"),
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute goal tracking action."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})

		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)

		self.state_machine.transition("completed", {"reason": decision.reason})

		summary = self.service.get_goal_summary()
		if summary.total_goals == 0:
			summary_text = "No goals tracked yet"
		else:
			summary_text = f"{summary.on_track} on track, {summary.at_risk} at risk, {summary.blocked} blocked, {summary.completed} completed"

		return ActionResult(
			True,
			f"Goal tracking complete: {summary_text}",
			{**plan.context, "policy": decision.reason},
		)
