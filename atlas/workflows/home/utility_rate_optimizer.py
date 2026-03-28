"""Workflow #85: Utility Rate Optimizer — Phase 3 Priority.
Monitors utility rates and suggests plan changes or usage optimizations.
Recommended phase: 3 (quick_win_score: 8) | Trust level: suggest | Category: home
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class UtilityType(str, Enum):
	ELECTRIC = "electric"
	GAS = "gas"
	WATER = "water"
	INTERNET = "internet"


@dataclass(slots=True)
class UtilityPlan:
	plan_id: str
	provider: str
	utility_type: UtilityType
	rate_per_unit: float
	avg_units_per_month: float
	alternative_best_rate: float

	def estimated_monthly_cost(self) -> float:
		return self.rate_per_unit * self.avg_units_per_month

	def estimated_monthly_savings(self) -> float:
		return max((self.rate_per_unit - self.alternative_best_rate) * self.avg_units_per_month, 0.0)


@dataclass(frozen=True, slots=True)
class UtilityOptimizationSummary:
	total_plans: int
	optimizable: int
	estimated_monthly_savings: float


class UtilityRateOptimizerService(PersistenceMixin):
	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._plans: dict[str, UtilityPlan] = {}

	def add_plan(
		self,
		plan_id: str,
		provider: str,
		utility_type: UtilityType,
		rate_per_unit: float,
		avg_units_per_month: float,
		alternative_best_rate: float,
	) -> UtilityPlan:
		plan = UtilityPlan(
			plan_id=plan_id,
			provider=provider,
			utility_type=utility_type,
			rate_per_unit=rate_per_unit,
			avg_units_per_month=avg_units_per_month,
			alternative_best_rate=alternative_best_rate,
		)
		self._plans[plan_id] = plan
		return plan

	def get_optimizable(self) -> list[UtilityPlan]:
		return [p for p in self._plans.values() if p.estimated_monthly_savings() > 0.0]

	def get_summary(self) -> UtilityOptimizationSummary:
		optimizable = self.get_optimizable()
		return UtilityOptimizationSummary(
			total_plans=len(self._plans),
			optimizable=len(optimizable),
			estimated_monthly_savings=sum(p.estimated_monthly_savings() for p in optimizable),
		)


class UtilityRateOptimizerWorkflow(BaseWorkflow):
	workflow_id = "utility_rate_optimizer"
	name = "Utility Rate Optimizer"
	category = "home"
	trust_level = TrustLevel.DRAFT

	def __init__(
		self,
		service: UtilityRateOptimizerService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or UtilityRateOptimizerService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		summary = self.service.get_summary()
		return ActionPlan(
			action_type="recommend_utility_plan_changes",
			confidence=0.78,
			context={
				"optimizable": summary.optimizable,
				"estimated_monthly_savings": summary.estimated_monthly_savings,
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
			f"utility optimizer: {plan.context.get('optimizable', 0)} plan(s) can be improved",
			{**plan.context, "policy": decision.reason},
		)
