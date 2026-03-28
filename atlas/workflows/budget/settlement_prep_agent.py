"""Workflow #34: Settlement Prep Agent — prepares expense settlement summaries.

Aggregates shared expenses over a period and generates settlement reports
showing amounts owed between parties for periodic balancing.
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


class ExpenseType(str, Enum):
	"""Type of shared expense."""

	RENT = "rent"
	UTILITIES = "utilities"
	GROCERIES = "groceries"
	HOUSEHOLD = "household"
	DINING = "dining"
	ENTERTAINMENT = "entertainment"
	OTHER = "other"


class SettlementPeriod(str, Enum):
	"""Settlement frequency."""

	WEEKLY = "weekly"
	MONTHLY = "monthly"
	QUARTERLY = "quarterly"


@dataclass(slots=True)
class SharedExpense:
	"""Expense shared between parties."""

	expense_id: str
	date: date
	amount: float
	expense_type: ExpenseType
	description: str
	paid_by: str  # "self" or "other"
	split_ratio: float  # decimal 0.0-1.0 for self's share


@dataclass(slots=True)
class Settlement:
	"""Calculated settlement between parties."""

	settlement_id: str
	period_start: date
	period_end: date
	total_shared: float
	your_expenses: float
	their_expenses: float
	your_share: float
	their_share: float
	balance_owed: float  # positive = you owe them, negative = they owe you
	settlement_period: SettlementPeriod


class SettlementPrepService(PersistenceMixin):
	"""Service for settlement preparation."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._expenses: list[SharedExpense] = []
		self._settlements: dict[str, Settlement] = {}

	def add_expense(self, expense: SharedExpense) -> SharedExpense:
		"""Record a shared expense."""
		self._expenses.append(expense)
		return expense

	def calculate_settlement(
		self, period_start: date, period_end: date, period: SettlementPeriod = SettlementPeriod.MONTHLY
	) -> Settlement:
		"""Calculate settlement for a period."""
		period_expenses = [e for e in self._expenses if period_start <= e.date <= period_end]

		your_paid = sum(e.amount for e in period_expenses if e.paid_by == "self")
		their_paid = sum(e.amount for e in period_expenses if e.paid_by == "other")

		your_share = sum(e.amount * e.split_ratio for e in period_expenses)
		their_share = sum(e.amount * (1 - e.split_ratio) for e in period_expenses)

		total_shared = your_share + their_share

		# Calculate who owes whom
		# If you paid more than your share, they owe you
		balance_owed = your_paid - your_share

		settlement = Settlement(
			settlement_id=str(uuid4()),
			period_start=period_start,
			period_end=period_end,
			total_shared=total_shared,
			your_expenses=your_paid,
			their_expenses=their_paid,
			your_share=your_share,
			their_share=their_share,
			balance_owed=balance_owed,
			settlement_period=period,
		)

		self._settlements[settlement.settlement_id] = settlement
		return settlement

	def get_settlement_summary(self) -> dict:
		"""Get summary of all settlements."""
		return {
			"total_expenses": len(self._expenses),
			"total_settled": sum(s.total_shared for s in self._settlements.values()),
			"pending_settlements": len(self._settlements),
		}


class SettlementPrepWorkflow(BaseWorkflow):
	"""Workflow for settlement preparation."""

	workflow_id = "settlement_prep"
	name = "Settlement Prep Agent"
	category = "budget"
	trust_level = TrustLevel.DRAFT

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = SettlementPrepService(session)

	def describe(self) -> str:
		return "Prepare periodic expense settlement summaries."

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle settlement events."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Plan settlement prep."""
		settlements = len(self.service._settlements)

		return ActionPlan(
			action_type="prepare_settlement",
			confidence=0.9,
			context={
				"settlements_prepared": settlements,
				"total_expenses": len(self.service._expenses),
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute settlement prep."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		self.state_machine.transition("completed", {"reason": "prep_complete"})

		return ActionResult(
			success=True,
			summary=f"Settlement prepared for {plan.context.get('settlements_prepared', 0)} periods",
			metadata=plan.context,
		)
