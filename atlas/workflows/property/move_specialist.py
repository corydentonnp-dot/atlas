"""Workflow #47: Move Specialist — coordinates comprehensive relocation activities.

Manages multi-phase move orchestration including pre-move planning, moving day coordination,
post-move setup, and utility/service transitions with task tracking and deadline management.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class MovePhase(str, Enum):
	"""Relocation phase."""

	PLANNING = "planning"
	PRE_MOVE = "pre_move"
	MOVING_DAY = "moving_day"
	POST_MOVE = "post_move"
	COMPLETED = "completed"


class TaskStatus(str, Enum):
	"""Task completion status."""

	PENDING = "pending"
	IN_PROGRESS = "in_progress"
	COMPLETED = "completed"
	SKIPPED = "skipped"


@dataclass(slots=True)
class MoveTask:
	"""Individual relocation task."""

	task_id: str
	title: str
	phase: MovePhase
	deadline: date
	priority: int  # 1-5, 5 is highest
	status: TaskStatus = TaskStatus.PENDING
	assigned_to: str = ""
	notes: str = ""


@dataclass(frozen=True, slots=True)
class MovePhaseStatus:
	"""Status of a move phase."""

	phase: MovePhase
	total_tasks: int
	completed_tasks: int
	pending_tasks: int
	completion_percentage: float


class MoveSpecialistService(PersistenceMixin):
	"""Service for move coordination and task management."""

	PHASE_TASKS = {
		MovePhase.PLANNING: [
			"Establish moving budget",
			"Research movers and get quotes",
			"Decide on moving date",
			"Notify current landlord/employer",
			"Start decluttering",
		],
		MovePhase.PRE_MOVE: [
			"Confirm moving company details",
			"Arrange utilities at new address",
			"Update address with institutions",
			"Book movers and confirm",
			"Pack non-essential items",
			"Arrange childcare/pet care",
		],
		MovePhase.MOVING_DAY: [
			"Final walkthrough (current property)",
			"Supervise moving crew",
			"Do final utilities check",
			"Transfer keys/access",
			"Take photos of empty property",
		],
		MovePhase.POST_MOVE: [
			"Unpack essentials boxes",
			"Verify utilities working",
			"Address change with final institutions",
			"Return moving equipment",
			"Unpack and organize remaining items",
			"Update insurance address",
		],
	}

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._tasks: dict[str, MoveTask] = {}
		self._current_phase = MovePhase.PLANNING

	def initialize_move(self, move_date: date) -> list[MoveTask]:
		"""Create task checklist for a move."""
		self._tasks.clear()
		tasks: list[MoveTask] = []
		days_until_move = (move_date - date.today()).days

		for phase_enum, phase_tasks in self.PHASE_TASKS.items():
			# Distribute phases based on move date
			if phase_enum == MovePhase.PLANNING:
				phase_start = date.today()
			elif phase_enum == MovePhase.PRE_MOVE:
				phase_start = move_date - timedelta(days=30)
			elif phase_enum == MovePhase.MOVING_DAY:
				phase_start = move_date
			else:
				phase_start = move_date + timedelta(days=1)

			for i, task_title in enumerate(phase_tasks):
				task = MoveTask(
					task_id=f"move-{phase_enum.value}-{i}",
					title=task_title,
					phase=phase_enum,
					deadline=phase_start + timedelta(days=i),
					priority=5 if phase_enum == MovePhase.MOVING_DAY else (4 if phase_enum == MovePhase.PRE_MOVE else 3),
				)
				self._tasks[task.task_id] = task
				tasks.append(task)

		return tasks

	def get_phase_status(self, phase: MovePhase) -> MovePhaseStatus:
		"""Get completion status for a phase."""
		phase_tasks = [t for t in self._tasks.values() if t.phase == phase]
		completed = len([t for t in phase_tasks if t.status == TaskStatus.COMPLETED])
		total = len(phase_tasks)

		return MovePhaseStatus(
			phase=phase,
			total_tasks=total,
			completed_tasks=completed,
			pending_tasks=total - completed,
			completion_percentage=(completed / total * 100) if total > 0 else 0,
		)

	def complete_task(self, task_id: str) -> bool:
		"""Mark a task as completed."""
		if task_id in self._tasks:
			self._tasks[task_id].status = TaskStatus.COMPLETED
			return True
		return False

	def get_urgent_tasks(self) -> list[MoveTask]:
		"""Get high-priority pending tasks approaching deadlines."""
		today = date.today()
		return [
			t
			for t in self._tasks.values()
			if t.status == TaskStatus.PENDING and t.priority >= 4 and (t.deadline - today).days <= 14
		]

	def overall_completion_percentage(self) -> float:
		"""Get overall move completion rate."""
		total = len(self._tasks)
		if total == 0:
			return 0.0
		completed = len([t for t in self._tasks.values() if t.status == TaskStatus.COMPLETED])
		return (completed / total) * 100


class MoveSpecialistAgent(BaseWorkflow):
	"""Workflow for comprehensive move coordination."""

	workflow_id = "move_specialist"
	name = "Move Specialist"
	category = "property"
	trust_level = TrustLevel.DRAFT

	def __init__(self, service: MoveSpecialistService | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = service or MoveSpecialistService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle move events."""
		self.state_machine.transition("planning", {"event_type": event.event_type})

		if event.event_type == "move_scheduled":
			move_date = date.fromisoformat(str(event.payload.get("move_date", date.today().isoformat())))
			self.service.initialize_move(move_date)

		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Generate move coordination plan."""
		urgent = self.service.get_urgent_tasks()
		overall = self.service.overall_completion_percentage()

		return ActionPlan(
			action_type="coordinate_move",
			confidence=0.9,
			context={
				"overall_completion": overall,
				"urgent_tasks_count": len(urgent),
				"planning_status": self.service.get_phase_status(MovePhase.PLANNING).completion_percentage,
				"pre_move_status": self.service.get_phase_status(MovePhase.PRE_MOVE).completion_percentage,
				"moving_day_ready": self.service.get_phase_status(MovePhase.MOVING_DAY).completed_tasks == 0,
				"urgent_tasks": [
					{
						"title": t.title,
						"deadline": t.deadline.isoformat(),
						"priority": t.priority,
						"phase": t.phase.value,
					}
					for t in urgent[:5]
				],
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute move coordination."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})

		completion = plan.context.get("overall_completion", 0)
		urgent_count = plan.context.get("urgent_tasks_count", 0)
		summary = f"Move {completion:.0f}% complete with {urgent_count} urgent tasks due soon" if urgent_count else f"Move {completion:.0f}% complete; on track"
		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
