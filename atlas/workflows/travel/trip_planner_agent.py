"""Workflow #100: Trip Planner Agent — Phase 3 Priority.
Assembles itineraries, checklists, and booking research for upcoming trips.
Recommended phase: 3 (quick_win_score: 8) | Trust level: approve | Category: travel
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class TripStatus(str, Enum):
	PLANNING = "planning"
	BOOKED = "booked"
	COMPLETED = "completed"
	CANCELLED = "cancelled"


@dataclass(slots=True)
class TripPlan:
	trip_id: str
	destination: str
	start_date: date
	end_date: date
	budget: float
	status: TripStatus = TripStatus.PLANNING
	checklist: list[str] = field(default_factory=list)
	itinerary: list[str] = field(default_factory=list)

	def duration_days(self) -> int:
		return max((self.end_date - self.start_date).days, 0)


@dataclass(frozen=True, slots=True)
class TripPlannerSummary:
	total_trips: int
	planning: int
	booked: int
	upcoming: int


class TripPlannerService(PersistenceMixin):
	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._trips: dict[str, TripPlan] = {}

	def add_trip(
		self,
		trip_id: str,
		destination: str,
		start_date: date,
		end_date: date,
		budget: float,
	) -> TripPlan:
		trip = TripPlan(
			trip_id=trip_id,
			destination=destination,
			start_date=start_date,
			end_date=end_date,
			budget=budget,
			checklist=["flight", "lodging", "transport", "documents"],
		)
		self._trips[trip_id] = trip
		return trip

	def add_itinerary_item(self, trip_id: str, item: str) -> bool:
		if trip_id not in self._trips:
			return False
		self._trips[trip_id].itinerary.append(item)
		return True

	def mark_booked(self, trip_id: str) -> bool:
		if trip_id not in self._trips:
			return False
		self._trips[trip_id].status = TripStatus.BOOKED
		return True

	def get_upcoming(self) -> list[TripPlan]:
		return [t for t in self._trips.values() if t.start_date >= date.today() and t.status in (TripStatus.PLANNING, TripStatus.BOOKED)]

	def get_summary(self) -> TripPlannerSummary:
		vals = list(self._trips.values())
		return TripPlannerSummary(
			total_trips=len(vals),
			planning=len([t for t in vals if t.status == TripStatus.PLANNING]),
			booked=len([t for t in vals if t.status == TripStatus.BOOKED]),
			upcoming=len(self.get_upcoming()),
		)


class TripPlannerAgent(BaseWorkflow):
	workflow_id = "trip_planner"
	name = "Trip Planner Agent"
	category = "travel"
	trust_level = TrustLevel.APPROVAL

	def __init__(
		self,
		service: TripPlannerService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or TripPlannerService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		summary = self.service.get_summary()
		return ActionPlan(
			action_type="prepare_trip_plan",
			confidence=0.83,
			context={
				"planning": summary.planning,
				"booked": summary.booked,
				"upcoming": summary.upcoming,
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
			f"trip planner: {plan.context.get('upcoming', 0)} upcoming trip(s)",
			{**plan.context, "policy": decision.reason},
		)
