"""Workflow #22: Utility Setup Reminder Agent.

Tracks utility setup tasks tied to move-in dates and reminds when accounts are not yet connected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class UtilityStatus(str, Enum):
	"""Utility connection status."""

	PENDING = "pending"
	SCHEDULED = "scheduled"
	CONNECTED = "connected"
	OVERDUE = "overdue"


@dataclass(slots=True)
class UtilityTask:
	"""Single utility setup item for a move-in."""

	task_id: str
	tenant_id: str
	tenant_name: str
	property_name: str
	unit: str
	utility_type: str
	due_date: date
	provider_hint: str = ""
	status: UtilityStatus = UtilityStatus.PENDING
	confirmation_number: str = ""


@dataclass(slots=True)
class MoveInUtilityPlan:
	"""Collection of utility tasks for a tenant move-in."""

	plan_id: str
	tenant_id: str
	tenant_name: str
	property_name: str
	unit: str
	move_in_date: date
	tasks: list[UtilityTask] = field(default_factory=list)


class UtilitySetupService:
	"""Service for scheduling and tracking utility setup reminders."""

	DEFAULT_UTILITIES: tuple[tuple[str, str], ...] = (
		("electric", "Electric provider"),
		("water", "Water utility"),
		("internet", "Internet provider"),
		("gas", "Gas provider"),
		("trash", "Trash service"),
	)

	def __init__(self) -> None:
		self._plans: dict[str, MoveInUtilityPlan] = {}

	def create_plan(self, plan: MoveInUtilityPlan) -> MoveInUtilityPlan:
		"""Create a move-in plan and populate default utilities when absent."""
		if not plan.tasks:
			for utility_type, provider_hint in self.DEFAULT_UTILITIES:
				plan.tasks.append(
					UtilityTask(
						task_id=f"{plan.plan_id}-{utility_type}",
						tenant_id=plan.tenant_id,
						tenant_name=plan.tenant_name,
						property_name=plan.property_name,
						unit=plan.unit,
						utility_type=utility_type,
						due_date=plan.move_in_date,
						provider_hint=provider_hint,
					)
				)
		self._plans[plan.plan_id] = plan
		return plan

	def pending_tasks(self, today: date, days_ahead: int = 14) -> list[UtilityTask]:
		"""Return utility tasks due soon or overdue."""
		results: list[UtilityTask] = []
		for plan in self._plans.values():
			for task in plan.tasks:
				if task.status == UtilityStatus.CONNECTED:
					continue
				days_remaining = (task.due_date - today).days
				if days_remaining < 0:
					task.status = UtilityStatus.OVERDUE
				if days_remaining <= days_ahead:
					results.append(task)
		results.sort(key=lambda task: task.due_date)
		return results

	def mark_connected(self, task_id: str, confirmation_number: str = "") -> bool:
		"""Mark a utility account as connected."""
		for plan in self._plans.values():
			for task in plan.tasks:
				if task.task_id == task_id:
					task.status = UtilityStatus.CONNECTED
					task.confirmation_number = confirmation_number
					return True
		return False

	def completion_rate(self) -> float:
		"""Return percent of utility tasks marked connected."""
		all_tasks = [task for plan in self._plans.values() for task in plan.tasks]
		if not all_tasks:
			return 0.0
		completed = sum(1 for task in all_tasks if task.status == UtilityStatus.CONNECTED)
		return completed / len(all_tasks)


class UtilitySetupReminderAgent(BaseWorkflow):
	"""Workflow for move-in utility setup reminders."""

	workflow_id = "utility_setup_reminder_agent"
	name = "utility_setup_reminder_agent"
	category = "property"
	trust_level = TrustLevel.AUTO

	def __init__(self, service: UtilitySetupService | None = None, policy_engine: PolicyEngine | None = None) -> None:
		super().__init__()
		self.service = service or UtilitySetupService()
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		if event.event_type == "move_in_scheduled":
			payload = event.payload
			self.service.create_plan(
				MoveInUtilityPlan(
					plan_id=str(payload.get("plan_id", "")),
					tenant_id=str(payload.get("tenant_id", "")),
					tenant_name=str(payload.get("tenant_name", "")),
					property_name=str(payload.get("property_name", "")),
					unit=str(payload.get("unit", "")),
					move_in_date=date.fromisoformat(str(payload.get("move_in_date", date.today().isoformat()))),
				)
			)
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		today = date.fromisoformat(str(run.event.payload.get("today", date.today().isoformat())))
		pending = self.service.pending_tasks(today=today)
		return ActionPlan(
			action_type="send_utility_reminders",
			confidence=0.92 if pending else 0.7,
			context={
				"task_count": len(pending),
				"tasks": [
					{
						"tenant_name": task.tenant_name,
						"property_unit": f"{task.property_name}/{task.unit}",
						"utility_type": task.utility_type,
						"due_date": task.due_date.isoformat(),
						"status": task.status.value,
					}
					for task in pending
				],
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
		count = int(plan.context.get("task_count", 0))
		summary = f"Prepared {count} utility reminder(s)" if count else "No pending utility reminders"
		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
