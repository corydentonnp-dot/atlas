"""Workflow #48: Portfolio Overview — summarizes real estate portfolio performance.

Aggregates metrics across multiple properties (owned/managed) to provide portfolio-level
insights on occupancy, cash flow, equity, and maintenance needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class PropertyType(str, Enum):
	"""Real estate property type."""

	SINGLE_FAMILY = "single_family"
	MULTI_UNIT = "multi_unit"
	COMMERCIAL = "commercial"
	VACATION_RENTAL = "vacation_rental"


class PropertyStatus(str, Enum):
	"""Property operational status."""

	OWNED = "owned"
	MANAGED = "managed"
	FOR_SALE = "for_sale"
	VACANT = "vacant"


@dataclass(slots=True)
class RealEstateProperty:
	"""Real estate property record."""

	property_id: str
	address: str
	property_type: PropertyType
	acquisition_date: date
	purchase_price: float
	current_value: float
	status: PropertyStatus = PropertyStatus.OWNED
	units: int = 1
	occupancy_rate: float = 1.0
	monthly_revenue: float = 0.0
	monthly_expenses: float = 0.0
	mortgage_balance: float = 0.0
	notes: str = ""


@dataclass(frozen=True, slots=True)
class PortfolioMetrics:
	"""Portfolio-level performance metrics."""

	total_properties: int
	total_value: float
	total_equity: float
	total_debt: float
	monthly_cash_flow: float
	occupancy_rate: float
	expense_ratio: float  # Expenses / Revenue
	cap_rate: float  # Net Operating Income / Property Value


class PortfolioOverviewService(PersistenceMixin):
	"""Service for real estate portfolio analysis."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._properties: dict[str, RealEstateProperty] = {}

	def add_property(self, property: RealEstateProperty) -> RealEstateProperty:
		"""Add a property to the portfolio."""
		self._properties[property.property_id] = property
		return property

	def calculate_portfolio_metrics(self) -> PortfolioMetrics:
		"""Calculate portfolio-level performance metrics."""
		if not self._properties:
			return PortfolioMetrics(
				total_properties=0,
				total_value=0.0,
				total_equity=0.0,
				total_debt=0.0,
				monthly_cash_flow=0.0,
				occupancy_rate=0.0,
				expense_ratio=0.0,
				cap_rate=0.0,
			)

		total_value = sum(p.current_value for p in self._properties.values())
		total_debt = sum(p.mortgage_balance for p in self._properties.values())
		total_equity = total_value - total_debt
		total_revenue = sum(p.monthly_revenue for p in self._properties.values())
		total_expenses = sum(p.monthly_expenses for p in self._properties.values())
		monthly_cash_flow = total_revenue - total_expenses

		# Calculate weighted occupancy
		total_units = sum(p.units for p in self._properties.values())
		occupancy_rate = (
			sum(p.units * p.occupancy_rate for p in self._properties.values()) / total_units if total_units > 0 else 0
		)

		# Cap rate (simplified: NOI/Total Value)
		noi = total_revenue - total_expenses  # Net Operating Income
		cap_rate = (noi / total_value * 100) if total_value > 0 else 0

		expense_ratio = (total_expenses / total_revenue) if total_revenue > 0 else 0

		return PortfolioMetrics(
			total_properties=len(self._properties),
			total_value=total_value,
			total_equity=total_equity,
			total_debt=total_debt,
			monthly_cash_flow=monthly_cash_flow,
			occupancy_rate=occupancy_rate * 100,
			expense_ratio=expense_ratio * 100,
			cap_rate=cap_rate,
		)

	def get_properties_by_status(self, status: PropertyStatus) -> list[RealEstateProperty]:
		"""Filter properties by status."""
		return [p for p in self._properties.values() if p.status == status]

	def get_underperforming_properties(self, min_cap_rate: float = 4.0) -> list[RealEstateProperty]:
		"""Identify properties with low cap rates."""
		underperformers = []
		for prop in self._properties.values():
			noi = prop.monthly_revenue * 12 - prop.monthly_expenses * 12
			prop_cap_rate = (noi / prop.current_value * 100) if prop.current_value > 0 else 0
			if prop_cap_rate < min_cap_rate:
				underperformers.append(prop)
		return underperformers


class PortfolioOverviewAgent(BaseWorkflow):
	"""Workflow for real estate portfolio summary and analysis."""

	workflow_id = "portfolio_overview"
	name = "Portfolio Overview"
	category = "property"
	trust_level = TrustLevel.DRAFT

	def __init__(self, service: PortfolioOverviewService | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = service or PortfolioOverviewService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle portfolio events."""
		self.state_machine.transition("planning", {"event_type": event.event_type})

		if event.event_type == "property_added":
			payload = event.payload
			self.service.add_property(
				RealEstateProperty(
					property_id=str(payload.get("property_id", "")),
					address=str(payload.get("address", "")),
					property_type=PropertyType(str(payload.get("property_type", "single_family"))),
					acquisition_date=date.fromisoformat(str(payload.get("acquisition_date", date.today().isoformat()))),
					purchase_price=float(payload.get("purchase_price", 0)),
					current_value=float(payload.get("current_value", 0)),
					occupancy_rate=float(payload.get("occupancy_rate", 1.0)),
					monthly_revenue=float(payload.get("monthly_revenue", 0)),
					monthly_expenses=float(payload.get("monthly_expenses", 0)),
					mortgage_balance=float(payload.get("mortgage_balance", 0)),
				)
			)

		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Generate portfolio overview."""
		metrics = self.service.calculate_portfolio_metrics()
		underperformers = self.service.get_underperforming_properties()

		return ActionPlan(
			action_type="overview_portfolio",
			confidence=0.85,
			context={
				"total_properties": metrics.total_properties,
				"total_value": metrics.total_value,
				"total_equity": metrics.total_equity,
				"total_debt": metrics.total_debt,
				"monthly_cash_flow": metrics.monthly_cash_flow,
				"occupancy_rate": metrics.occupancy_rate,
				"expense_ratio": metrics.expense_ratio,
				"cap_rate": metrics.cap_rate,
				"underperforming_count": len(underperformers),
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute portfolio overview."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})

		value = plan.context.get("total_value", 0)
		cash_flow = plan.context.get("monthly_cash_flow", 0)
		underperf = plan.context.get("underperforming_count", 0)
		summary = f"Portfolio: {value:,.0f} value, ${cash_flow:,.0f}/month cash flow"
		if underperf > 0:
			summary += f"; {underperf} underperforming properties"
		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
