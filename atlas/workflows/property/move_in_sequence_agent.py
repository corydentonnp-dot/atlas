"""Workflow #23: Move-In Sequence Agent.

Manages move-in checklist with walkthrough, documentation, and utility setup coordination.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class ChecklistItemStatus(str, Enum):
	"""Checklist item status."""

	PENDING = "pending"
	IN_PROGRESS = "in_progress"
	COMPLETED = "completed"
	FAILED = "failed"


@dataclass(slots=True)
class MoveInChecklistItem:
	"""Single move-in task."""

	item_id: str
	category: str
	description: str
	due_date: date
	status: ChecklistItemStatus = ChecklistItemStatus.PENDING
	notes: str = ""
	assigned_to: str = ""


class MoveInSequenceService(PersistenceMixin):
	"""Service for move-in sequence management."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._checklists: dict[str, list[MoveInChecklistItem]] = {}

	DEFAULT_CATEGORIES = {
		"keys": ["Collect all keys from property manager", "Label all keys"],
		"utilities": ["Confirm electricity transfer", "Confirm gas transfer", "Confirm water transfer"],
		"walkthrough": ["Take photos of all rooms", "Document existing damage", "Verify appliance function"],
		"setup": ["Arrange furniture", "Set up internet/phone", "Locate circuit breaker and water shut-off"],
		"paperwork": ["Review lease thoroughly", "Provide renter insurance proof", "Register as occupant if applicable"],
	}

	def create_checklist(self, tenant_id: str, move_in_date: date) -> list[MoveInChecklistItem]:
		"""Create a standard move-in checklist."""
		items: list[MoveInChecklistItem] = []
		for category, descriptions in self.DEFAULT_CATEGORIES.items():
			for idx, desc in enumerate(descriptions):
				item = MoveInChecklistItem(
					item_id=f"{tenant_id}-{category}-{idx}",
					category=category,
					description=desc,
					due_date=move_in_date,
				)
				items.append(item)
		self._checklists[tenant_id] = items
		return items

	def complete_item(self, tenant_id: str, item_id: str, notes: str = "") -> bool:
		"""Mark a checklist item as completed."""
		items = self._checklists.get(tenant_id, [])
		for item in items:
			if item.item_id == item_id:
				item.status = ChecklistItemStatus.COMPLETED
				item.notes = notes
				return True
		return False

	def completion_rate(self, tenant_id: str) -> float:
		"""Return percent of items completed."""
		items = self._checklists.get(tenant_id, [])
		if not items:
			return 0.0
		completed = sum(1 for item in items if item.status == ChecklistItemStatus.COMPLETED)
		return completed / len(items)

	def pending_by_category(self, tenant_id: str) -> dict[str, int]:
		"""Return count of pending items by category."""
		items = self._checklists.get(tenant_id, [])
		result: dict[str, int] = {}
		for item in items:
			if item.status != ChecklistItemStatus.COMPLETED:
				result[item.category] = result.get(item.category, 0) + 1
		return result


class MoveInSequenceAgent(BaseWorkflow):
	"""Workflow for managing move-in sequence."""

	workflow_id = "move_in_sequence_agent"
	name = "move_in_sequence_agent"
	category = "property"
	trust_level = TrustLevel.DRAFT

	def __init__(self, service: MoveInSequenceService | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = service or MoveInSequenceService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		if event.event_type == "move_in_scheduled":
			payload = event.payload
			tenant_id = str(payload.get("tenant_id", ""))
			move_in_date = date.fromisoformat(str(payload.get("move_in_date", date.today().isoformat())))
			self.service.create_checklist(tenant_id, move_in_date)
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		tenant_id = str(run.event.payload.get("tenant_id", ""))
		completion = self.service.completion_rate(tenant_id)
		pending = self.service.pending_by_category(tenant_id)
		return ActionPlan(
			action_type="manage_move_in_sequence",
			confidence=0.88,
			context={
				"tenant_id": tenant_id,
				"completion_rate": completion,
				"pending_by_category": pending,
				"checklist_size": len(self.service._checklists.get(tenant_id, [])),
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
		completion = float(plan.context.get("completion_rate", 0.0))
		pending = plan.context.get("pending_by_category", {})
		pending_count = sum(pending.values())
		summary = f"Move-in sequence tracked: {int(completion*100)}% complete, {pending_count} items pending"
		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
