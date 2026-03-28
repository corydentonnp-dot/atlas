"""Workflow #86: Seasonal Prep Agent — Phase 2 Priority.
Generates seasonal checklists (winterize, spring prep, hurricane season, etc.).
Recommended phase: 2 (quick_win_score: 11) | Trust level: auto | Category: home
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class Season(str, Enum):
	"""Season for prep checklist."""

	SPRING = "spring"
	SUMMER = "summer"
	FALL = "fall"
	WINTER = "winter"


class ChecklistItemStatus(str, Enum):
	"""Status of a checklist item."""

	PENDING = "pending"
	IN_PROGRESS = "in_progress"
	COMPLETED = "completed"
	SKIPPED = "skipped"


@dataclass(slots=True)
class ChecklistItem:
	"""An item in a seasonal prep checklist."""

	item_id: str
	title: str
	category: str
	priority: int  # 1=high, 2=medium, 3=low
	estimated_hours: float
	status: ChecklistItemStatus = ChecklistItemStatus.PENDING
	notes: str = ""


@dataclass(frozen=True, slots=True)
class SeasonalChecklist:
	"""Complete seasonal prep checklist."""

	checklist_id: str
	season: Season
	year: int
	items: list[ChecklistItem]
	total_items: int
	completed_items: int
	estimated_total_hours: float
	progress_percentage: float


SEASONAL_ITEMS: dict[Season, list[tuple[str, str, int, float]]] = {
	Season.SPRING: [
		("Inspect roof for winter damage", "exterior", 1, 2.0),
		("Clean gutters and downspouts", "exterior", 1, 2.0),
		("Service HVAC for cooling season", "hvac", 1, 1.0),
		("Test smoke and CO detectors", "safety", 1, 0.5),
		("Check window and door seals", "exterior", 2, 1.0),
		("Start lawn fertilization program", "landscaping", 2, 1.5),
		("Flush water heater", "plumbing", 2, 1.0),
		("Deep clean interior", "interior", 3, 4.0),
	],
	Season.SUMMER: [
		("Check AC performance and filters", "hvac", 1, 0.5),
		("Inspect deck/patio for damage", "exterior", 1, 1.0),
		("Test irrigation system", "landscaping", 2, 1.0),
		("Clean dryer vent", "safety", 1, 0.5),
		("Seal driveway cracks", "exterior", 3, 2.0),
		("Check attic ventilation", "hvac", 2, 0.5),
	],
	Season.FALL: [
		("Service furnace before heating season", "hvac", 1, 1.0),
		("Clean and store outdoor furniture", "exterior", 2, 2.0),
		("Drain and winterize irrigation", "plumbing", 1, 1.5),
		("Caulk gaps around windows/doors", "weatherization", 1, 2.0),
		("Clean gutters after leaf fall", "exterior", 1, 2.0),
		("Check chimney and fireplace", "safety", 1, 0.5),
		("Stock emergency winter supplies", "safety", 2, 1.0),
		("Aerate and overseed lawn", "landscaping", 3, 2.0),
	],
	Season.WINTER: [
		("Insulate exposed pipes", "plumbing", 1, 2.0),
		("Test sump pump", "plumbing", 1, 0.5),
		("Reverse ceiling fans for heat distribution", "hvac", 2, 0.25),
		("Check weatherstripping on all doors", "weatherization", 2, 1.0),
		("Test smoke/CO detectors", "safety", 1, 0.5),
		("Inspect attic insulation", "hvac", 2, 1.0),
		("Stock generator fuel", "safety", 2, 0.5),
	],
}


class SeasonalPrepService(PersistenceMixin):
	"""Service for generating and tracking seasonal prep checklists."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._checklists: dict[str, SeasonalChecklist] = {}
		self._item_status: dict[str, dict[str, ChecklistItemStatus]] = {}

	def generate_checklist(self, checklist_id: str, season: Season) -> SeasonalChecklist:
		"""Generate a seasonal prep checklist."""
		item_templates = SEASONAL_ITEMS.get(season, [])
		items = [
			ChecklistItem(
				item_id=f"{checklist_id}_{i}",
				title=title,
				category=category,
				priority=priority,
				estimated_hours=hours,
			)
			for i, (title, category, priority, hours) in enumerate(item_templates)
		]
		checklist = SeasonalChecklist(
			checklist_id=checklist_id,
			season=season,
			year=date.today().year,
			items=items,
			total_items=len(items),
			completed_items=0,
			estimated_total_hours=sum(i.estimated_hours for i in items),
			progress_percentage=0.0,
		)
		self._checklists[checklist_id] = checklist
		self._item_status[checklist_id] = {item.item_id: ChecklistItemStatus.PENDING for item in items}
		return checklist

	def complete_item(self, checklist_id: str, item_id: str) -> bool:
		"""Mark a checklist item as completed."""
		if checklist_id not in self._item_status:
			return False
		if item_id not in self._item_status[checklist_id]:
			return False
		self._item_status[checklist_id][item_id] = ChecklistItemStatus.COMPLETED
		return True

	def get_high_priority_items(self, checklist_id: str) -> list[ChecklistItem]:
		"""Get pending high-priority items from a checklist."""
		if checklist_id not in self._checklists:
			return []
		return [
			item for item in self._checklists[checklist_id].items
			if item.priority == 1 and self._item_status[checklist_id].get(item.item_id) == ChecklistItemStatus.PENDING
		]

	def get_progress(self, checklist_id: str) -> tuple[int, int, float]:
		"""Return (completed, total, percentage) for a checklist."""
		if checklist_id not in self._checklists:
			return (0, 0, 0.0)
		statuses = self._item_status[checklist_id]
		completed = sum(1 for s in statuses.values() if s == ChecklistItemStatus.COMPLETED)
		total = len(statuses)
		pct = (completed / total * 100) if total > 0 else 0.0
		return (completed, total, round(pct, 1))

	def infer_current_season(self) -> Season:
		"""Infer the current season from today's date."""
		month = date.today().month
		if month in (3, 4, 5):
			return Season.SPRING
		if month in (6, 7, 8):
			return Season.SUMMER
		if month in (9, 10, 11):
			return Season.FALL
		return Season.WINTER


class SeasonalPrepAgent(BaseWorkflow):
	"""Workflow for generating and tracking seasonal home prep checklists."""

	workflow_id = "seasonal_prep"
	name = "Seasonal Prep"
	category = "home"
	trust_level = TrustLevel.AUTO

	def __init__(
		self,
		service: SeasonalPrepService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or SeasonalPrepService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle seasonal prep requests."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Generate or assess seasonal checklist."""
		payload = run.event.payload or {}
		season_str = str(payload.get("season", ""))
		checklist_id = str(payload.get("checklist_id", "seasonal_current"))

		try:
			season = Season(season_str)
		except ValueError:
			season = self.service.infer_current_season()

		if checklist_id not in self.service._checklists:
			checklist = self.service.generate_checklist(checklist_id, season)
		else:
			checklist = self.service._checklists[checklist_id]

		completed, total, pct = self.service.get_progress(checklist_id)
		high_priority = self.service.get_high_priority_items(checklist_id)

		return ActionPlan(
			action_type="generate_seasonal_checklist",
			confidence=0.88,
			context={
				"season": season.value,
				"checklist_id": checklist_id,
				"total_items": total,
				"completed_items": completed,
				"progress_percentage": pct,
				"high_priority_remaining": len(high_priority),
				"estimated_hours": checklist.estimated_total_hours,
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Emit seasonal checklist result."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})
		season = plan.context.get("season", "current")
		total = plan.context.get("total_items", 0)
		pct = plan.context.get("progress_percentage", 0.0)
		high = plan.context.get("high_priority_remaining", 0)
		return ActionResult(
			True,
			f"{season.capitalize()} prep checklist: {total} items, {pct:.0f}% complete, {high} high-priority remaining",
			{**plan.context, "policy": decision.reason},
		)
