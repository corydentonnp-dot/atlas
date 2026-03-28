"""Workflow #42: Budget Drift Agent — detects spending deviations from budget targets.

Monitors spending across budget categories and alerts when actual spending
deviates significantly from planned amounts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class DriftLevel(str, Enum):
	"""Budget drift severity."""

	MINOR = "minor"  # Under 10%
	MODERATE = "moderate"  # 10-25% over
	SIGNIFICANT = "significant"  # 25-50% over
	CRITICAL = "critical"  # Over 50%


@dataclass(slots=True)
class BudgetCategory:
	"""Budget category with limits."""

	category_id: str
	name: str
	monthly_limit: float
	period_start: date
	period_end: date


@dataclass(slots=True)
class SpendingRecord:
	"""Spending in a category."""

	category_id: str
	amount: float
	date: date
	description: str


@dataclass(frozen=True, slots=True)
class DriftAlert:
	"""Budget drift alert."""

	category_id: str
	category_name: str
	budget_limit: float
	actual_spending: float
	percent_over: float
	drift_level: DriftLevel
	recommendation: str


class BudgetDriftService(PersistenceMixin):
	"""Service for budget drift monitoring."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._categories: dict[str, BudgetCategory] = {}
		self._spending: list[SpendingRecord] = []

	def add_category(self, category: BudgetCategory) -> BudgetCategory:
		"""Register a budget category."""
		self._categories[category.category_id] = category
		return category

	def add_spending(self, record: SpendingRecord) -> SpendingRecord:
		"""Record spending against a category."""
		self._spending.append(record)
		return record

	def detect_drift(self) -> list[DriftAlert]:
		"""Detect budget drift across categories."""
		alerts: list[DriftAlert] = []

		for category in self._categories.values():
			category_spending = sum(
				s.amount
				for s in self._spending
				if s.category_id == category.category_id
				and category.period_start <= s.date <= category.period_end
			)

			if category_spending <= category.monthly_limit:
				continue

			percent_over = (category_spending - category.monthly_limit) / category.monthly_limit * 100

			if percent_over > 50:
				drift_level = DriftLevel.CRITICAL
				recommendation = "Immediately review spending; consider category freeze"
			elif percent_over > 25:
				drift_level = DriftLevel.SIGNIFICANT
				recommendation = "Reduce spending in this category; review recent purchases"
			elif percent_over > 10:
				drift_level = DriftLevel.MODERATE
				recommendation = "Monitor closely; consider reducing purchases"
			else:
				drift_level = DriftLevel.MINOR
				recommendation = "Minor overage; no action needed"

			alerts.append(
				DriftAlert(
					category_id=category.category_id,
					category_name=category.name,
					budget_limit=category.monthly_limit,
					actual_spending=category_spending,
					percent_over=percent_over,
					drift_level=drift_level,
					recommendation=recommendation,
				)
			)

		return alerts

	def get_budget_status(self) -> dict[str, dict]:
		"""Get current budget status across all categories."""
		status = {}
		for category in self._categories.values():
			category_spending = sum(
				s.amount
				for s in self._spending
				if s.category_id == category.category_id
				and category.period_start <= s.date <= category.period_end
			)
			status[category.category_id] = {
				"name": category.name,
				"limit": category.monthly_limit,
				"spent": category_spending,
				"remaining": category.monthly_limit - category_spending,
				"percent_used": category_spending / category.monthly_limit * 100,
			}
		return status


class BudgetDriftWorkflow(BaseWorkflow):
	"""Workflow for budget drift monitoring and alerts."""

	workflow_id = "budget_drift"
	name = "Budget Drift Agent"
	category = "budget"
	trust_level = TrustLevel.AUTO

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = BudgetDriftService(session)

	def describe(self) -> str:
		return "Monitor budgets and alert when spending drifts from targets."

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle budget events."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Plan budget monitoring."""
		alerts = self.service.detect_drift()

		return ActionPlan(
			action_type="monitor_budget",
			confidence=0.9,
			context={
				"drifting_categories": len(alerts),
				"total_categories": len(self.service._categories),
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute budget monitoring."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		self.state_machine.transition("completed", {"reason": "monitoring_complete"})

		return ActionResult(
			success=True,
			summary=f"Budget check complete: {plan.context.get('drifting_categories', 0)} categories over budget",
			metadata=plan.context,
		)
