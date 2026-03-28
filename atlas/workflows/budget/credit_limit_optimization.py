"""Workflow #45: Credit Limit Optimization — analyzes credit cards for APR/limit optimization.

Tracks credit card accounts and identifies opportunities to negotiate better rates,
request credit limit increases, or migrate balances to lower-rate cards.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class CardStatus(str, Enum):
	"""Credit card status."""

	ACTIVE = "active"
	INACTIVE = "inactive"
	CLOSED = "closed"


class OptimizationOpportunity(str, Enum):
	"""Type of credit optimization available."""

	RATE_NEGOTIATION = "rate_negotiation"  # APR reduction
	LIMIT_INCREASE = "limit_increase"  # Credit line expansion
	BALANCE_TRANSFER = "balance_transfer"  # Migrate to better rate
	REWARDS_UPGRADE = "rewards_upgrade"  # Switch to better rewards card
	PRODUCT_SWITCH = "product_switch"  # Switch card altogether


@dataclass(slots=True)
class CreditCard:
	"""Credit card account."""

	card_id: str
	issuer: str
	last_four: str
	current_apr: float
	credit_limit: float
	current_balance: float
	annual_fee: float = 0.0
	rewards_category: str = "1x"
	status: CardStatus = CardStatus.ACTIVE
	months_since_opened: int = 12


@dataclass(frozen=True, slots=True)
class OptimizationRecommendation:
	"""Recommended optimization action."""

	card_id: str
	issuer: str
	opportunity_type: OptimizationOpportunity
	current_apr: float
	target_apr: float
	estimated_annual_savings: float
	effort_level: str  # "low", "medium", "high"
	success_probability: float  # 0.0-1.0


class CreditLimitService(PersistenceMixin):
	"""Service for credit card optimization analysis."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._cards: dict[str, CreditCard] = {}
		self._market_rates: dict[str, float] = {
			"Chase": 18.5,
			"AmEx": 19.0,
			"Citi": 17.5,
			"Bank of America": 18.0,
			"Capital One": 20.0,
		}

	def add_card(self, card: CreditCard) -> CreditCard:
		"""Register a credit card for optimization."""
		self._cards[card.card_id] = card
		return card

	def analyze_optimization_opportunities(self) -> list[OptimizationRecommendation]:
		"""Find optimization opportunities across portfolio."""
		recommendations: list[OptimizationRecommendation] = []

		for card in self._cards.values():
			if card.status != CardStatus.ACTIVE:
				continue

			# Rate negotiation
			if card.current_apr > 15:
				market_rate = self._market_rates.get(card.issuer, card.current_apr - 2)
				if market_rate < card.current_apr - 1.5:  # Negotiation buffer
					savings = (card.current_apr - market_rate) * card.current_balance / 100
					recommendations.append(
						OptimizationRecommendation(
							card_id=card.card_id,
							issuer=card.issuer,
							opportunity_type=OptimizationOpportunity.RATE_NEGOTIATION,
							current_apr=card.current_apr,
							target_apr=market_rate,
							estimated_annual_savings=savings,
							effort_level="low",
							success_probability=0.65,
						)
					)

			# Limit increase (if good payment history)
			if card.current_balance / card.credit_limit > 0.3 and card.months_since_opened > 6:
				recommendations.append(
					OptimizationRecommendation(
						card_id=card.card_id,
						issuer=card.issuer,
						opportunity_type=OptimizationOpportunity.LIMIT_INCREASE,
						current_apr=card.current_apr,
						target_apr=card.current_apr,
						estimated_annual_savings=0,
						effort_level="low",
						success_probability=0.75,
					)
				)

			# Balance transfer opportunity
			if card.current_balance > 5000 and card.current_apr > 18:
				recommendations.append(
					OptimizationRecommendation(
						card_id=card.card_id,
						issuer=card.issuer,
						opportunity_type=OptimizationOpportunity.BALANCE_TRANSFER,
						current_apr=card.current_apr,
						target_apr=0.0,  # 0% intro period
						estimated_annual_savings=(card.current_apr / 100) * card.current_balance,
						effort_level="medium",
						success_probability=0.5,
					)
				)

		return sorted(recommendations, key=lambda r: r.estimated_annual_savings, reverse=True)

	def total_credit_limit(self) -> float:
		"""Total available credit across active cards."""
		return sum(c.credit_limit for c in self._cards.values() if c.status == CardStatus.ACTIVE)

	def total_balance(self) -> float:
		"""Total balance across all cards."""
		return sum(c.current_balance for c in self._cards.values())

	def utilization_ratio(self) -> float:
		"""Credit utilization percentage."""
		total_limit = self.total_credit_limit()
		if total_limit == 0:
			return 0.0
		return (self.total_balance() / total_limit) * 100


class CreditLimitOptimizationAgent(BaseWorkflow):
	"""Workflow for credit card optimization opportunities."""

	workflow_id = "credit_limit_optimization"
	name = "Credit Limit Optimization"
	category = "budget"
	trust_level = TrustLevel.DRAFT

	def __init__(self, service: CreditLimitService | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = service or CreditLimitService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle credit card events."""
		self.state_machine.transition("planning", {"event_type": event.event_type})

		if event.event_type == "card_added":
			payload = event.payload
			self.service.add_card(
				CreditCard(
					card_id=str(payload.get("card_id", "")),
					issuer=str(payload.get("issuer", "")),
					last_four=str(payload.get("last_four", "")),
					current_apr=float(payload.get("current_apr", 18.0)),
					credit_limit=float(payload.get("credit_limit", 5000)),
					current_balance=float(payload.get("current_balance", 0)),
					annual_fee=float(payload.get("annual_fee", 0)),
					months_since_opened=int(payload.get("months_since_opened", 12)),
				)
			)

		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Identify optimization opportunities."""
		opportunities = self.service.analyze_optimization_opportunities()
		high_priority = [o for o in opportunities if o.estimated_annual_savings > 200]

		return ActionPlan(
			action_type="optimize_credit_cards",
			confidence=0.85 if high_priority else 0.6,
			context={
				"total_credit_limit": self.service.total_credit_limit(),
				"total_balance": self.service.total_balance(),
				"utilization_ratio": self.service.utilization_ratio(),
				"opportunities_count": len(opportunities),
				"high_priority_count": len(high_priority),
				"potential_annual_savings": sum(o.estimated_annual_savings for o in opportunities),
				"opportunities": [
					{
						"issuer": o.issuer,
						"type": o.opportunity_type.value,
						"current_apr": o.current_apr,
						"target_apr": o.target_apr,
						"savings": o.estimated_annual_savings,
						"effort": o.effort_level,
					}
					for o in opportunities[:5]
				],
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute credit optimization analysis."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})

		savings = plan.context.get("potential_annual_savings", 0)
		count = plan.context.get("opportunities_count", 0)
		summary = f"Found {count} optimization opportunities with ${savings:.0f}/year potential savings" if count else "No immediate optimization opportunities"
		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
