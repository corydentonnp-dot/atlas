"""Workflow #46: Cash Flow Planner — forecasts monthly cash flow and identifies gaps.

Aggregates income sources and expense categories to project cash flow, identify
deficit months, and recommend savings targets or expense reductions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class TransactionType(str, Enum):
	"""Income or expense category."""

	SALARY = "salary"
	BONUS = "bonus"
	RENTAL_INCOME = "rental_income"
	SIDE_INCOME = "side_income"
	HOUSING = "housing"
	UTILITIES = "utilities"
	GROCERIES = "groceries"
	TRANSPORTATION = "transportation"
	INSURANCE = "insurance"
	HEALTHCARE = "healthcare"
	ENTERTAINMENT = "entertainment"
	DINING = "dining"
	DEBT_PAYMENT = "debt_payment"
	SAVINGS = "savings"
	OTHER = "other"


@dataclass(slots=True)
class CashFlowItem:
	"""Monthly recurring income or expense."""

	item_id: str
	label: str
	category: TransactionType
	amount: float
	is_recurring: bool = True
	frequency: str = "monthly"  # "weekly", "monthly", "quarterly", "annual"
	notes: str = ""


@dataclass(frozen=True, slots=True)
class MonthlyForecast:
	"""Projected monthly cash flow."""

	month: date
	projected_income: float
	projected_expenses: float
	net_cash_flow: float
	surplus_deficit: str  # "surplus" or "deficit"


class CashFlowService(PersistenceMixin):
	"""Service for cash flow forecasting and analysis."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._items: dict[str, CashFlowItem] = {}

	def add_item(self, item: CashFlowItem) -> CashFlowItem:
		"""Add an income or expense item."""
		self._items[item.item_id] = item
		return item

	def forecast_months(self, start_month: date, num_months: int = 12) -> list[MonthlyForecast]:
		"""Project cash flow for specified months."""
		forecasts: list[MonthlyForecast] = []

		for i in range(num_months):
			# Simple month advancement (doesn't handle year rollover perfectly but functional)
			month = date(start_month.year, start_month.month + i, 1) if start_month.month + i <= 12 else date(start_month.year + 1, (start_month.month + i) % 12 or 12, 1)

			income = self._calculate_income(month)
			expenses = self._calculate_expenses(month)
			net_flow = income - expenses

			forecasts.append(
				MonthlyForecast(
					month=month,
					projected_income=income,
					projected_expenses=expenses,
					net_cash_flow=net_flow,
					surplus_deficit="surplus" if net_flow >= 0 else "deficit",
				)
			)

		return forecasts

	def _calculate_income(self, month: date) -> float:
		"""Calculate total projected income for a month."""
		income = 0.0
		for item in self._items.values():
			if item.category in {TransactionType.SALARY, TransactionType.BONUS, TransactionType.RENTAL_INCOME, TransactionType.SIDE_INCOME}:
				income += item.amount
		return income

	def _calculate_expenses(self, month: date) -> float:
		"""Calculate total projected expenses for a month."""
		expenses = 0.0
		for item in self._items.values():
			if item.category not in {TransactionType.SALARY, TransactionType.BONUS, TransactionType.RENTAL_INCOME, TransactionType.SIDE_INCOME}:
				expenses += item.amount
		return expenses

	def total_monthly_income(self) -> float:
		"""Get total monthly recurring income."""
		return self._calculate_income(date.today())

	def total_monthly_expenses(self) -> float:
		"""Get total monthly recurring expenses."""
		return self._calculate_expenses(date.today())

	def monthly_savings_potential(self) -> float:
		"""Identify discretionary spending reductions."""
		discretionary = sum(
			item.amount
			for item in self._items.values()
			if item.category in {TransactionType.ENTERTAINMENT, TransactionType.DINING, TransactionType.OTHER}
		)
		return discretionary * 0.3  # 30% reduction potential


class CashFlowPlannerAgent(BaseWorkflow):
	"""Workflow for cash flow forecasting and planning."""

	workflow_id = "cash_flow_planner"
	name = "Cash Flow Planner"
	category = "budget"
	trust_level = TrustLevel.DRAFT

	def __init__(self, service: CashFlowService | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = service or CashFlowService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle cash flow events."""
		self.state_machine.transition("planning", {"event_type": event.event_type})

		if event.event_type == "item_added":
			payload = event.payload
			self.service.add_item(
				CashFlowItem(
					item_id=str(payload.get("item_id", "")),
					label=str(payload.get("label", "")),
					category=TransactionType(str(payload.get("category", "other"))),
					amount=float(payload.get("amount", 0)),
					is_recurring=bool(payload.get("is_recurring", True)),
					frequency=str(payload.get("frequency", "monthly")),
				)
			)

		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Generate cash flow forecast."""
		forecasts = self.service.forecast_months(date.today(), num_months=12)
		deficit_months = [f for f in forecasts if f.surplus_deficit == "deficit"]
		avg_monthly_flow = sum(f.net_cash_flow for f in forecasts) / len(forecasts) if forecasts else 0

		return ActionPlan(
			action_type="forecast_cash_flow",
			confidence=0.8,
			context={
				"monthly_income": self.service.total_monthly_income(),
				"monthly_expenses": self.service.total_monthly_expenses(),
				"monthly_surplus": self.service.total_monthly_income() - self.service.total_monthly_expenses(),
				"deficit_months_count": len(deficit_months),
				"average_monthly_flow": avg_monthly_flow,
				"savings_potential": self.service.monthly_savings_potential(),
				"forecast_months": [
					{
						"month": f.month.isoformat(),
						"income": f.projected_income,
						"expenses": f.projected_expenses,
						"net": f.net_cash_flow,
						"status": f.surplus_deficit,
					}
					for f in forecasts[:6]
				],
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute cash flow planning."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})

		surplus = plan.context.get("monthly_surplus", 0)
		deficit_count = plan.context.get("deficit_months_count", 0)
		if deficit_count > 0:
			summary = f"Forecast shows {deficit_count} deficit months; recommend reducing spending by ${abs(surplus):.0f}/month"
		elif surplus > 0:
			summary = f"Monthly surplus of ${surplus:.0f}; recommend allocating to savings goals"
		else:
			summary = "Monthly cash flow balanced; monitor spending in discretionary categories"
		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
