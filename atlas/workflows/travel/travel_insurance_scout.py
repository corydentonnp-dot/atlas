"""Workflow #53: Travel Insurance Scout — identifies and compares travel insurance options.

Analyzes trip characteristics and recommendations suitable travel insurance products,
compares coverage levels, and identifies best value options.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class CoverageType(str, Enum):
	"""Travel insurance coverage type."""

	MEDICAL_EMERGENCY = "medical_emergency"
	TRIP_CANCELLATION = "trip_cancellation"
	BAGGAGE = "baggage"
	FLIGHT_DELAY = "flight_delay"
	COVID = "covid"
	ADVENTURE_SPORTS = "adventure_sports"


@dataclass(slots=True)
class InsuranceProduct:
	"""Travel insurance policy offering."""

	product_id: str
	provider: str
	name: str
	coverage_types: list[CoverageType]
	premium_per_day: float
	annual_limit: float  # If annual plan
	deductible: float
	cancellation_coverage: float
	medical_emergency_coverage: float
	baggage_coverage: float
	review_rating: float  # 1-5


@dataclass(frozen=True, slots=True)
class InsuranceRecommendation:
	"""Recommended insurance product."""

	product_id: str
	provider: str
	name: str
	total_premium: float
	coverage_score: float  # 0-100
	value_ratio: float  # Coverage/Cost
	recommended_for: str  # Trip description
	risk_level: str  # "low", "medium", "high"

	def to_dict(self) -> dict:
		"""Convert to dictionary."""
		return {
			"product_id": self.product_id,
			"provider": self.provider,
			"name": self.name,
			"total_premium": self.total_premium,
			"coverage_score": self.coverage_score,
			"value_ratio": self.value_ratio,
		}


class TravelInsuranceService(PersistenceMixin):
	"""Service for travel insurance recommendations."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._products: dict[str, InsuranceProduct] = {}
		self._initialize_standard_products()

	def _initialize_standard_products(self) -> None:
		"""Create standard travel insurance products."""
		products = [
			InsuranceProduct(
				product_id="basic-travel-1",
				provider="TravelGuard",
				name="Basic Travel Protection",
				coverage_types=[CoverageType.MEDICAL_EMERGENCY, CoverageType.BAGGAGE, CoverageType.FLIGHT_DELAY],
				premium_per_day=1.50,
				annual_limit=0,
				deductible=100,
				cancellation_coverage=0,
				medical_emergency_coverage=100000,
				baggage_coverage=2500,
				review_rating=4.2,
			),
			InsuranceProduct(
				product_id="comprehensive-travel-1",
				provider="AXA",
				name="Comprehensive Travel Plus",
				coverage_types=[
					CoverageType.MEDICAL_EMERGENCY,
					CoverageType.TRIP_CANCELLATION,
					CoverageType.BAGGAGE,
					CoverageType.FLIGHT_DELAY,
					CoverageType.COVID,
				],
				premium_per_day=3.50,
				annual_limit=0,
				deductible=250,
				cancellation_coverage=5000,
				medical_emergency_coverage=250000,
				baggage_coverage=5000,
				review_rating=4.5,
			),
			InsuranceProduct(
				product_id="adventure-travel-1",
				provider="World Nomads",
				name="Adventure Sports Coverage",
				coverage_types=[
					CoverageType.MEDICAL_EMERGENCY,
					CoverageType.ADVENTURE_SPORTS,
					CoverageType.BAGGAGE,
					CoverageType.COVID,
				],
				premium_per_day=4.00,
				annual_limit=0,
				deductible=150,
				cancellation_coverage=0,
				medical_emergency_coverage=300000,
				baggage_coverage=3000,
				review_rating=4.4,
			),
		]

		for product in products:
			self._products[product.product_id] = product

	def recommend_insurance(self, trip_duration_days: int, trip_cost: float, risk_level: str) -> list[InsuranceRecommendation]:
		"""Recommend insurance based on trip profile."""
		recommendations: list[InsuranceRecommendation] = []

		for product in self._products.values():
			# Calculate premium
			total_premium = product.premium_per_day * trip_duration_days

			# Score coverage based on risk level
			coverage_score = 0
			if risk_level == "high" and CoverageType.MEDICAL_EMERGENCY in product.coverage_types:
				coverage_score += 25
			if trip_cost > 5000 and CoverageType.TRIP_CANCELLATION in product.coverage_types:
				coverage_score += 25
			if CoverageType.BAGGAGE in product.coverage_types:
				coverage_score += 15
			if CoverageType.FLIGHT_DELAY in product.coverage_types:
				coverage_score += 10
			if risk_level == "high" and CoverageType.COVID in product.coverage_types:
				coverage_score += 15

			value_ratio = coverage_score / total_premium if total_premium > 0 else 0

			recommendations.append(
				InsuranceRecommendation(
					product_id=product.product_id,
					provider=product.provider,
					name=product.name,
					total_premium=total_premium,
					coverage_score=coverage_score,
					value_ratio=value_ratio,
					recommended_for=f"{trip_duration_days}-day trip costing ${trip_cost:,.0f}",
					risk_level=risk_level,
				)
			)

		# Sort by value ratio (coverage per dollar)
		return sorted(recommendations, key=lambda r: r.value_ratio, reverse=True)


class TravelInsuranceScoutAgent(BaseWorkflow):
	"""Workflow for travel insurance product recommendations."""

	workflow_id = "travel_insurance_scout"
	name = "Travel Insurance Scout"
	category = "travel"
	trust_level = TrustLevel.DRAFT

	def __init__(self, service: TravelInsuranceService | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = service or TravelInsuranceService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle insurance query events."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Recommend insurance products."""
		payload = run.event.payload

		trip_duration = int(cast(int, payload.get("trip_duration_days") or 7)) if payload else 7
		trip_cost = float(cast(float, payload.get("trip_cost") or 5000)) if payload else 5000
		risk_level = cast(str, payload.get("risk_level") or "medium") if payload else "medium"

		recommendations = self.service.recommend_insurance(trip_duration, trip_cost, risk_level)

		return ActionPlan(
			action_type="recommend_travel_insurance",
			confidence=0.85,
			context={
				"trip_duration": trip_duration,
				"trip_cost": trip_cost,
				"risk_level": risk_level,
				"recommendations_count": len(recommendations),
				"best_value": recommendations[0].to_dict() if recommendations else {},
				"options": [
					{
						"provider": r.provider,
						"name": r.name,
						"total_premium": r.total_premium,
						"coverage_score": r.coverage_score,
						"value_ratio": r.value_ratio,
					}
					for r in recommendations[:3]
				],
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute insurance recommendation."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})

		duration = plan.context.get("trip_duration", 0)
		options = plan.context.get("recommendations_count", 0)
		summary = f"Found {options} travel insurance options for {duration}-day trip"
		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
