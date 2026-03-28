"""Workflow #41: Shared Household Spend Summary Agent.

Generates periodic household spend summaries, per-person contribution totals, and settlement suggestions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class SpendCategory(str, Enum):
	"""High-level shared spend categories."""

	GROCERIES = "groceries"
	UTILITIES = "utilities"
	HOUSEHOLD = "household"
	RENT = "rent"
	OTHER = "other"


@dataclass(frozen=True, slots=True)
class HouseholdSpendEntry:
	"""Single shared spend item."""

	entry_id: str
	entry_date: date
	merchant: str
	amount: float
	paid_by: str
	shared_with: tuple[str, ...]
	category: SpendCategory = SpendCategory.OTHER


@dataclass(frozen=True, slots=True)
class SpendSummary:
	"""Summary of household spending for a period."""

	period_start: date
	period_end: date
	total_spend: float
	by_person_paid: dict[str, float]
	by_category: dict[str, float]
	settlements: list[dict[str, object]]


class SharedHouseholdSpendSummaryService:
	"""Service for summarizing shared household spend."""

	def __init__(self) -> None:
		self._entries: dict[str, HouseholdSpendEntry] = {}

	def add_entry(self, entry: HouseholdSpendEntry) -> HouseholdSpendEntry:
		"""Record a shared household spend entry."""
		self._entries[entry.entry_id] = entry
		return entry

	def summarize(self, period_start: date, period_end: date) -> SpendSummary:
		"""Build household spend summary and simple settlement suggestions."""
		entries = [
			entry for entry in self._entries.values() if period_start <= entry.entry_date <= period_end
		]
		by_person_paid: dict[str, float] = {}
		by_category: dict[str, float] = {}
		balances: dict[str, float] = {}

		for entry in entries:
			by_person_paid[entry.paid_by] = by_person_paid.get(entry.paid_by, 0.0) + entry.amount
			by_category[entry.category.value] = by_category.get(entry.category.value, 0.0) + entry.amount

			share_count = len(entry.shared_with) if entry.shared_with else 1
			share_amount = entry.amount / share_count
			balances[entry.paid_by] = balances.get(entry.paid_by, 0.0) - entry.amount
			for person in entry.shared_with:
				balances[person] = balances.get(person, 0.0) + share_amount

		debtors = sorted([(person, amount) for person, amount in balances.items() if amount > 0.01], key=lambda item: item[1], reverse=True)
		creditors = sorted([(person, abs(amount)) for person, amount in balances.items() if amount < -0.01], key=lambda item: item[1], reverse=True)
		settlements: list[dict[str, object]] = []

		while debtors and creditors:
			debtor, owed = debtors[0]
			creditor, receivable = creditors[0]
			amount = round(min(owed, receivable), 2)
			settlements.append({"from": debtor, "to": creditor, "amount": amount})
			debtors[0] = (debtor, round(owed - amount, 2))
			creditors[0] = (creditor, round(receivable - amount, 2))
			if debtors[0][1] <= 0.01:
				debtors.pop(0)
			if creditors[0][1] <= 0.01:
				creditors.pop(0)

		return SpendSummary(
			period_start=period_start,
			period_end=period_end,
			total_spend=round(sum(entry.amount for entry in entries), 2),
			by_person_paid={person: round(amount, 2) for person, amount in by_person_paid.items()},
			by_category={category: round(amount, 2) for category, amount in by_category.items()},
			settlements=settlements,
		)


class SharedHouseholdSpendSummaryAgent(BaseWorkflow):
	"""Workflow for periodic spend summary generation."""

	workflow_id = "shared_household_spend_summary_agent"
	name = "shared_household_spend_summary_agent"
	category = "budget"
	trust_level = TrustLevel.AUTO

	def __init__(self, service: SharedHouseholdSpendSummaryService | None = None, policy_engine: PolicyEngine | None = None) -> None:
		super().__init__()
		self.service = service or SharedHouseholdSpendSummaryService()
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		if event.event_type == "household_spend_recorded":
			payload = event.payload
			shared_with = payload.get("shared_with", [])
			if not isinstance(shared_with, list):
				shared_with = []
			self.service.add_entry(
				HouseholdSpendEntry(
					entry_id=str(payload.get("entry_id", "")),
					entry_date=date.fromisoformat(str(payload.get("entry_date", date.today().isoformat()))),
					merchant=str(payload.get("merchant", "")),
					amount=float(payload.get("amount", 0)),
					paid_by=str(payload.get("paid_by", "")),
					shared_with=tuple(str(person) for person in shared_with),
					category=SpendCategory(str(payload.get("category", "other"))),
				)
			)
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		payload = run.event.payload
		period_start = date.fromisoformat(str(payload.get("period_start", date.today().replace(day=1).isoformat())))
		period_end = date.fromisoformat(str(payload.get("period_end", date.today().isoformat())))
		summary = self.service.summarize(period_start=period_start, period_end=period_end)
		return ActionPlan(
			action_type="generate_spend_summary",
			confidence=0.94 if summary.total_spend else 0.72,
			context={
				"total_spend": summary.total_spend,
				"by_person_paid": summary.by_person_paid,
				"by_category": summary.by_category,
				"settlements": summary.settlements,
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
		total_spend = float(plan.context.get("total_spend", 0))
		summary = f"Generated shared household spend summary for ${total_spend:.2f}"
		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
