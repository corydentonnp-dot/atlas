"""Workflow #44: Debt Refinance Architect — analyzes debt portfolios for refinance optimization.

Evaluates current debt accounts (mortgages, auto loans, student loans) and recommends
refinancing opportunities based on rate improvements, term optimization, and cash flow impact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class DebtType(str, Enum):
	"""Loan type classification."""

	MORTGAGE = "mortgage"
	AUTO_LOAN = "auto_loan"
	STUDENT_LOAN = "student_loan"
	PERSONAL_LOAN = "personal_loan"
	CREDIT_CARD = "credit_card"


class RefinanceRecommendation(str, Enum):
	"""Recommendation status."""

	STRONG = "strong"  # Savings > $100/month
	MODERATE = "moderate"  # Savings $25-100/month
	WEAK = "weak"  # Savings < $25/month
	NOT_RECOMMENDED = "not_recommended"  # No savings


@dataclass(slots=True)
class DebtAccount:
	"""Existing debt account."""

	account_id: str
	debt_type: DebtType
	current_balance: float
	original_balance: float
	current_rate: float
	monthly_payment: float
	remaining_months: int
	creditor: str = ""
	notes: str = ""


@dataclass(frozen=True, slots=True)
class RefinanceOpportunity:
	"""Recommended refinance option."""

	account_id: str
	debt_type: DebtType
	creditor: str
	current_rate: float
	proposed_rate: float
	new_term_months: int
	estimated_monthly_savings: float
	estimated_total_savings: float
	refinance_cost_estimate: float
	payoff_period_months: int  # Months to recover closing costs
	recommendation: RefinanceRecommendation


class DebtRefinanceService(PersistenceMixin):
	"""Service for debt refinancing analysis."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._accounts: dict[str, DebtAccount] = {}
		self._market_rates: dict[DebtType, float] = {
			DebtType.MORTGAGE: 6.5,
			DebtType.AUTO_LOAN: 6.8,
			DebtType.STUDENT_LOAN: 5.5,
			DebtType.PERSONAL_LOAN: 8.0,
			DebtType.CREDIT_CARD: 21.0,
		}

	def add_account(self, account: DebtAccount) -> DebtAccount:
		"""Register a debt account for analysis."""
		self._accounts[account.account_id] = account
		return account

	def analyze_portfolio(self) -> list[RefinanceOpportunity]:
		"""Analyze all accounts for refinancing opportunities."""
		opportunities: list[RefinanceOpportunity] = []
		for account in self._accounts.values():
			market_rate = self._market_rates.get(account.debt_type, account.current_rate)
			if market_rate < account.current_rate:
				opportunity = self._calculate_refinance(account, market_rate)
				if opportunity.recommendation != RefinanceRecommendation.NOT_RECOMMENDED:
					opportunities.append(opportunity)
		return sorted(opportunities, key=lambda o: o.estimated_monthly_savings, reverse=True)

	def _calculate_refinance(self, account: DebtAccount, new_rate: float) -> RefinanceOpportunity:
		"""Calculate refinance metrics for an account."""
		rate_improvement = account.current_rate - new_rate
		new_monthly_payment = self._calculate_payment(account.current_balance, new_rate, account.remaining_months)
		monthly_savings = account.monthly_payment - new_monthly_payment
		total_savings = monthly_savings * account.remaining_months

		# Estimate refinance cost (0.5-2% of balance)
		refinance_cost = account.current_balance * 0.01
		net_savings = total_savings - refinance_cost
		payoff_period = int(refinance_cost / monthly_savings) if monthly_savings > 0 else 999

		# Determine recommendation
		if monthly_savings < 25:
			recommendation = RefinanceRecommendation.NOT_RECOMMENDED
		elif monthly_savings < 75:
			recommendation = RefinanceRecommendation.WEAK
		elif monthly_savings < 200:
			recommendation = RefinanceRecommendation.MODERATE
		else:
			recommendation = RefinanceRecommendation.STRONG

		return RefinanceOpportunity(
			account_id=account.account_id,
			debt_type=account.debt_type,
			creditor=account.creditor,
			current_rate=account.current_rate,
			proposed_rate=new_rate,
			new_term_months=account.remaining_months,
			estimated_monthly_savings=monthly_savings,
			estimated_total_savings=net_savings,
			refinance_cost_estimate=refinance_cost,
			payoff_period_months=payoff_period,
			recommendation=recommendation,
		)

	def _calculate_payment(self, balance: float, rate: float, months: int) -> float:
		"""Calculate monthly payment using standard amortization."""
		if rate == 0 or months == 0:
			return 0
		monthly_rate = rate / 100 / 12
		return balance * (monthly_rate * (1 + monthly_rate) ** months) / ((1 + monthly_rate) ** months - 1)

	def total_portfolio_balance(self) -> float:
		"""Get total debt outstanding."""
		return sum(acc.current_balance for acc in self._accounts.values())

	def total_monthly_debt_payment(self) -> float:
		"""Get total monthly debt payments."""
		return sum(acc.monthly_payment for acc in self._accounts.values())


class DebtRefinanceArchitectAgent(BaseWorkflow):
	"""Workflow for analyzing debt refinancing opportunities."""

	workflow_id = "debt_refinance_architect"
	name = "Debt Refinance Architect"
	category = "budget"
	trust_level = TrustLevel.DRAFT

	def __init__(self, service: DebtRefinanceService | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = service or DebtRefinanceService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle debt account events."""
		self.state_machine.transition("planning", {"event_type": event.event_type})

		if event.event_type == "account_added":
			payload = event.payload
			self.service.add_account(
				DebtAccount(
					account_id=str(payload.get("account_id", str(uuid4()))),
					debt_type=DebtType(str(payload.get("debt_type", "mortgage"))),
					current_balance=float(payload.get("current_balance", 0)),
					original_balance=float(payload.get("original_balance", 0)),
					current_rate=float(payload.get("current_rate", 0)),
					monthly_payment=float(payload.get("monthly_payment", 0)),
					remaining_months=int(payload.get("remaining_months", 360)),
					creditor=str(payload.get("creditor", "")),
				)
			)

		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Analyze portfolio and identify refinance opportunities."""
		opportunities = self.service.analyze_portfolio()
		strong_recs = [o for o in opportunities if o.recommendation == RefinanceRecommendation.STRONG]
		moderate_recs = [o for o in opportunities if o.recommendation == RefinanceRecommendation.MODERATE]

		return ActionPlan(
			action_type="analyze_refinance_opportunities",
			confidence=0.9 if strong_recs else (0.7 if moderate_recs else 0.5),
			context={
				"total_portfolio_balance": self.service.total_portfolio_balance(),
				"total_monthly_payment": self.service.total_monthly_debt_payment(),
				"strong_opportunities_count": len(strong_recs),
				"moderate_opportunities_count": len(moderate_recs),
				"potential_monthly_savings": sum(o.estimated_monthly_savings for o in opportunities),
				"opportunities": [
					{
						"creditor": o.creditor,
						"debt_type": o.debt_type.value,
						"current_rate": o.current_rate,
						"proposed_rate": o.proposed_rate,
						"monthly_savings": o.estimated_monthly_savings,
						"recommendation": o.recommendation.value,
					}
					for o in opportunities[:5]
				],
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute refinance analysis decision."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})

		savings = plan.context.get("potential_monthly_savings", 0)
		count = plan.context.get("strong_opportunities_count", 0) + plan.context.get("moderate_opportunities_count", 0)
		summary = f"Identified {count} refinancing opportunities with ${savings:.0f}/month potential savings" if count else "No refinancing opportunities found"
		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
