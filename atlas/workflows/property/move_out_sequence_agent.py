"""Workflow #24: Move-Out Sequence Agent.

Manages move-out checklist: final walkthrough, inspection, cleaning, and key return.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class InspectionStatus(str, Enum):
	"""Move-out inspection status."""

	SCHEDULED = "scheduled"
	IN_PROGRESS = "in_progress"
	COMPLETED = "completed"
	ISSUES_FOUND = "issues_found"


@dataclass(slots=True)
class MoveOutTask:
	"""Task in move-out sequence."""

	task_id: str
	task_name: str
	category: str
	target_date: date
	completed: bool = False
	notes: str = ""


class MoveOutSequenceService(PersistenceMixin):
	"""Move-out checklist and inspection management."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._sequences: dict[str, list[MoveOutTask]] = {}

	STANDARD_TASKS = [
		("final_walkthrough", "walkthrough", "Conduct final walkthrough with tenant"),
		("take_photos", "documentation", "Photograph condition of all rooms"),
		("note_damages", "documentation", "Document any damage or wear"),
		("cleaning_verification", "cleaning", "Verify cleaning completed to standard"),
		("key_return", "logistics", "Collect all keys and access devices"),
		("mail_forwarding", "logistics", "Verify mail forwarding is set up"),
		("utility_disconnect", "utilities", "Schedule utility disconnections"),
		("final_meter_reading", "utilities", "Record final meter readings"),
	]

	def create_sequence(self, tenant_id: str, move_out_date: date) -> list[MoveOutTask]:
		"""Create standard move-out sequence."""
		tasks: list[MoveOutTask] = []
		for task_id, category, name in self.STANDARD_TASKS:
			task = MoveOutTask(
				task_id=f"{tenant_id}-{task_id}",
				task_name=name,
				category=category,
				target_date=move_out_date,
			)
			tasks.append(task)
		self._sequences[tenant_id] = tasks
		return tasks

	def mark_task_complete(self, tenant_id: str, task_id: str, notes: str = "") -> bool:
		"""Mark a task as completed."""
		tasks = self._sequences.get(tenant_id, [])
		for task in tasks:
			if task.task_id == task_id:
				task.completed = True
				task.notes = notes
				return True
		return False

	def completion_status(self, tenant_id: str) -> dict[str, object]:
		"""Get move-out completion status."""
		tasks = self._sequences.get(tenant_id, [])
		completed = sum(1 for task in tasks if task.completed)
		by_category = {}
		for task in tasks:
			if task.category not in by_category:
				by_category[task.category] = {"total": 0, "completed": 0}
			by_category[task.category]["total"] += 1
			if task.completed:
				by_category[task.category]["completed"] += 1
		return {
			"total_tasks": len(tasks),
			"completed_tasks": completed,
			"completion_percent": int((completed / len(tasks) * 100) if tasks else 0),
			"by_category": by_category,
		}

	def all_complete(self, tenant_id: str) -> bool:
		"""Check if all move-out tasks complete."""
		tasks = self._sequences.get(tenant_id, [])
		return all(task.completed for task in tasks) if tasks else False


class MoveOutSequenceAgent(BaseWorkflow):
	"""Workflow for move-out sequence management."""

	workflow_id = "move_out_sequence_agent"
	name = "move_out_sequence_agent"
	category = "property"
	trust_level = TrustLevel.DRAFT

	def __init__(self, service: MoveOutSequenceService | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = service or MoveOutSequenceService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		if event.event_type == "move_out_initiated":
			payload = event.payload
			tenant_id = str(payload.get("tenant_id", ""))
			move_out_date = date.fromisoformat(str(payload.get("move_out_date", date.today().isoformat())))
			self.service.create_sequence(tenant_id, move_out_date)
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		tenant_id = str(run.event.payload.get("tenant_id", ""))
		status = self.service.completion_status(tenant_id)
		complete = self.service.all_complete(tenant_id)
		return ActionPlan(
			action_type="manage_move_out_sequence",
			confidence=0.90 if complete else 0.75,
			context={
				"tenant_id": tenant_id,
				"status": status,
				"all_complete": complete,
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
		status = plan.context.get("status", {})
		completion = status.get("completion_percent", 0)
		summary = f"Move-out sequence tracked: {completion}% complete"
		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
