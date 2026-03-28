"""Workflow #51: Trip Cost Analyzer — budgets and forecasts travel expenses.

Breaks down trip costs across categories (flights, hotels, activities, dining) and
compares itineraries for cost-effectiveness, identifies savings opportunities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class ExpenseCategory(str, Enum):
	"""Travel expense category."""

	FLIGHTS = "flights"
	LODGING = "lodging"
	ACTIVITIES = "activities"
	DINING = "dining"
	GROUND_TRANSPORT = "ground_transport"
	TRAVEL_INSURANCE = "travel_insurance"
	MISCELLANEOUS = "miscellaneous"


@dataclass(slots=True)
class TripExpense:
	"""Individual trip expense item."""

	expense_id: str
	category: ExpenseCategory
	description: str
	estimated_cost: float
	actual_cost: float = 0.0
	trip_id: str = ""
	notes: str = ""


@dataclass(slots=True)
class TripItinerary:
	"""Travel trip itinerary and budget."""

	trip_id: str
	destination: str
	start_date: date
	end_date: date
	travelers: int = 1
	expenses: list[TripExpense] = field(default_factory=list)
	budget_limit: float = 0.0


@dataclass(frozen=True, slots=True)
class CostAnalysis:
	"""Trip cost analysis."""

	trip_id: str
	destination: str
	duration_days: int
	total_estimated_cost: float
	cost_per_day: float
	cost_per_person_total: float
	breakdown_by_category: dict[str, float]
	over_under_budget: float  # Positive = under budget
	budget_percentage_used: float


class TripCostService(PersistenceMixin):
	"""Service for trip cost planning and analysis."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._trips: dict[str, TripItinerary] = {}

	def create_trip(self, trip: TripItinerary) -> TripItinerary:
		"""Create a new trip itinerary."""
		self._trips[trip.trip_id] = trip
		return trip

	def add_expense(self, trip_id: str, expense: TripExpense) -> bool:
		"""Add an expense to a trip."""
		if trip_id in self._trips:
			self._trips[trip_id].expenses.append(expense)
			return True
		return False

	def analyze_trip_cost(self, trip_id: str) -> CostAnalysis | None:
		"""Analyze total cost for a trip."""
		trip = self._trips.get(trip_id)
		if not trip:
			return None

		# Calculate totals
		total_estimated = sum(e.estimated_cost for e in trip.expenses)

		# Breakdown by category
		breakdown: dict[str, float] = {}
		for expense in trip.expenses:
			category = expense.category.value
			breakdown[category] = breakdown.get(category, 0) + expense.estimated_cost

		# Duration
		duration = (trip.end_date - trip.start_date).days + 1

		# Per-day and per-person
		cost_per_day = total_estimated / duration if duration > 0 else 0
		cost_per_person = total_estimated / trip.travelers if trip.travelers > 0 else 0

		# Budget analysis
		budget_used_pct = (total_estimated / trip.budget_limit * 100) if trip.budget_limit > 0 else 0
		over_under = trip.budget_limit - total_estimated if trip.budget_limit > 0 else 0

		return CostAnalysis(
			trip_id=trip_id,
			destination=trip.destination,
			duration_days=duration,
			total_estimated_cost=total_estimated,
			cost_per_day=cost_per_day,
			cost_per_person_total=cost_per_person,
			breakdown_by_category=breakdown,
			over_under_budget=over_under,
			budget_percentage_used=budget_used_pct,
		)

	def find_savings_opportunities(self, trip_id: str) -> list[str]:
		"""Identify cost reduction opportunities."""
		trip = self._trips.get(trip_id)
		if not trip:
			return []

		opportunities = []
		analysis = self.analyze_trip_cost(trip_id)
		if not analysis:
			return []

		# Check for expensive categories
		if analysis.breakdown_by_category.get("flights", 0) > analysis.total_estimated_cost * 0.5:
			opportunities.append("Consider alternative flights or dates to reduce flight costs")
		if analysis.breakdown_by_category.get("lodging", 0) > analysis.total_estimated_cost * 0.4:
			opportunities.append("Consider budget lodging or house-sharing alternatives")
		if analysis.breakdown_by_category.get("dining", 0) > analysis.total_estimated_cost * 0.2:
			opportunities.append("Reduce dining frequency or choose less expensive restaurants")
		if analysis.breakdown_by_category.get("activities", 0) > analysis.total_estimated_cost * 0.15:
			opportunities.append("Look for free or low-cost activities in destination")

		return opportunities


class TripCostAnalyzerAgent(BaseWorkflow):
	"""Workflow for trip cost planning and analysis."""

	workflow_id = "trip_cost_analyzer"
	name = "Trip Cost Analyzer"
	category = "travel"
	trust_level = TrustLevel.DRAFT

	def __init__(self, service: TripCostService | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = service or TripCostService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle trip events."""
		self.state_machine.transition("planning", {"event_type": event.event_type})

		if event.event_type == "trip_created":
			payload = event.payload
			trip = TripItinerary(
				trip_id=str(payload.get("trip_id", "")),
				destination=str(payload.get("destination", "")),
				start_date=date.fromisoformat(str(payload.get("start_date", date.today().isoformat()))),
				end_date=date.fromisoformat(str(payload.get("end_date", (date.today() + timedelta(days=7)).isoformat()))),
				travelers=int(payload.get("travelers", 1)),
				budget_limit=float(payload.get("budget_limit", 0)),
			)
			self.service.create_trip(trip)

		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Analyze trip costs."""
		trip_id = str(run.event.payload.get("trip_id", ""))
		analysis = self.service.analyze_trip_cost(trip_id)

		if not analysis:
			return ActionPlan(action_type="analyze_trip_cost", confidence=0.0, context={"error": "Trip not found"})

		opportunities = self.service.find_savings_opportunities(trip_id)

		return ActionPlan(
			action_type="analyze_trip_cost",
			confidence=0.85,
			context={
				"destination": analysis.destination,
				"duration_days": analysis.duration_days,
				"total_cost": analysis.total_estimated_cost,
				"cost_per_day": analysis.cost_per_day,
				"cost_per_person": analysis.cost_per_person_total,
				"budget_used": analysis.budget_percentage_used,
				"over_budget": analysis.over_under_budget < 0,
				"savings_opportunities": opportunities,
				"breakdown": {k: v for k, v in analysis.breakdown_by_category.items() if v > 0},
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute trip cost analysis."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})

		destination = plan.context.get("destination", "")
		total = plan.context.get("total_cost", 0)
		per_day = plan.context.get("cost_per_day", 0)
		summary = f"Trip to {destination}: ${total:,.0f} total (${per_day:,.0f}/day)"
		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
