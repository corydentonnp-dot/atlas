"""Workflow #78: Estimated Tax Calculator — Phase 2 Priority.
Calculates quarterly estimated tax payments based on income tracking and prior year data.
Recommended phase: 2 (quick_win_score: 11) | Trust level: approve | Category: tax_legal
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class TaxQuarter(str, Enum):
	"""Federal estimated tax quarter."""

	Q1 = "Q1"  # Due April 15
	Q2 = "Q2"  # Due June 15
	Q3 = "Q3"  # Due September 15
	Q4 = "Q4"  # Due January 15 next year


class FilingStatus(str, Enum):
	"""Tax filing status."""

	SINGLE = "single"
	MARRIED_JOINTLY = "married_jointly"
	MARRIED_SEPARATELY = "married_separately"
	HEAD_OF_HOUSEHOLD = "head_of_household"


@dataclass(frozen=True, slots=True)
class IncomeEntry:
	"""An income entry for tax estimation."""

	entry_id: str
	source: str
	amount: float
	quarter: TaxQuarter
	is_self_employment: bool = False


@dataclass(frozen=True, slots=True)
class QuarterlyEstimate:
	"""Calculated quarterly estimated tax payment."""

	quarter: TaxQuarter
	due_date: date
	total_income: float
	federal_tax_owed: float
	self_employment_tax: float
	total_payment_due: float
	safe_harbor_payment: float
	recommended_payment: float


@dataclass(frozen=True, slots=True)
class TaxEstimateSummary:
	"""Annual tax estimation summary."""

	annual_income_estimate: float
	annual_federal_tax: float
	annual_se_tax: float
	total_annual_tax: float
	effective_tax_rate: float
	quarterly_payment: float
	next_due_date: date | None
	next_quarter: TaxQuarter | None


QUARTER_DUE_DATES: dict[TaxQuarter, tuple[int, int]] = {
	TaxQuarter.Q1: (4, 15),
	TaxQuarter.Q2: (6, 15),
	TaxQuarter.Q3: (9, 15),
	TaxQuarter.Q4: (1, 15),
}


class EstimatedTaxService(PersistenceMixin):
	"""Service for calculating quarterly estimated tax payments."""

	# 2024 federal tax brackets (single filer, simplified)
	TAX_BRACKETS_SINGLE: list[tuple[float, float]] = [
		(11600.0, 0.10),
		(47150.0, 0.12),
		(100525.0, 0.22),
		(191950.0, 0.24),
		(243725.0, 0.32),
		(609350.0, 0.35),
		(float("inf"), 0.37),
	]
	SE_TAX_RATE = 0.153  # 15.3% self-employment tax
	SE_DEDUCTIBLE_FRACTION = 0.5  # 50% of SE tax is deductible

	def __init__(self, session: AsyncSession | None = None, filing_status: FilingStatus = FilingStatus.SINGLE) -> None:
		super().__init__(session)
		self._income_entries: list[IncomeEntry] = []
		self._filing_status = filing_status
		self._prior_year_tax: float = 0.0

	def add_income(self, entry: IncomeEntry) -> None:
		"""Record an income entry."""
		self._income_entries.append(entry)

	def set_prior_year_tax(self, amount: float) -> None:
		"""Set prior year total tax for safe harbor calculation."""
		self._prior_year_tax = amount

	def calculate_federal_tax(self, taxable_income: float) -> float:
		"""Calculate federal income tax using bracket calculation."""
		tax = 0.0
		prev_limit = 0.0
		for limit, rate in self.TAX_BRACKETS_SINGLE:
			if taxable_income <= prev_limit:
				break
			taxable_in_bracket = min(taxable_income, limit) - prev_limit
			tax += taxable_in_bracket * rate
			prev_limit = limit
		return round(tax, 2)

	def calculate_quarterly_estimate(self, quarter: TaxQuarter) -> QuarterlyEstimate:
		"""Calculate estimated tax for a specific quarter."""
		quarter_income = sum(e.amount for e in self._income_entries if e.quarter == quarter)
		se_income = sum(e.amount for e in self._income_entries if e.quarter == quarter and e.is_self_employment)

		# Self-employment tax
		se_tax = se_income * self.SE_TAX_RATE
		se_deduction = se_tax * self.SE_DEDUCTIBLE_FRACTION

		# Federal income tax
		taxable_income = quarter_income - se_deduction
		federal_tax = self.calculate_federal_tax(taxable_income)

		total_due = federal_tax + se_tax
		safe_harbor = self._prior_year_tax / 4.0
		recommended = max(total_due, safe_harbor)

		year = date.today().year
		month, day = QUARTER_DUE_DATES[quarter]
		if quarter == TaxQuarter.Q4:
			year += 1
		due_date = date(year, month, day)

		return QuarterlyEstimate(
			quarter=quarter,
			due_date=due_date,
			total_income=quarter_income,
			federal_tax_owed=federal_tax,
			self_employment_tax=se_tax,
			total_payment_due=total_due,
			safe_harbor_payment=safe_harbor,
			recommended_payment=recommended,
		)

	def get_annual_summary(self) -> TaxEstimateSummary:
		"""Get full-year tax estimation summary."""
		total_income = sum(e.amount for e in self._income_entries)
		se_income = sum(e.amount for e in self._income_entries if e.is_self_employment)
		se_tax = se_income * self.SE_TAX_RATE
		se_deduction = se_tax * self.SE_DEDUCTIBLE_FRACTION
		federal_tax = self.calculate_federal_tax(max(0.0, total_income - se_deduction))
		total_tax = federal_tax + se_tax
		effective_rate = (total_tax / total_income) if total_income > 0 else 0.0

		# Determine next due date
		today = date.today()
		next_quarter: TaxQuarter | None = None
		next_due: date | None = None
		for q, (month, day) in QUARTER_DUE_DATES.items():
			year = today.year if q != TaxQuarter.Q4 else today.year + 1
			due = date(year, month, day)
			if due >= today:
				if next_due is None or due < next_due:
					next_due = due
					next_quarter = q

		return TaxEstimateSummary(
			annual_income_estimate=total_income,
			annual_federal_tax=federal_tax,
			annual_se_tax=se_tax,
			total_annual_tax=total_tax,
			effective_tax_rate=round(effective_rate, 4),
			quarterly_payment=round(total_tax / 4, 2),
			next_due_date=next_due,
			next_quarter=next_quarter,
		)


class EstimatedTaxCalculatorWorkflow(BaseWorkflow):
	"""Workflow for calculating quarterly estimated tax payments."""

	workflow_id = "estimated_tax_calculator"
	name = "Estimated Tax Calculator"
	category = "tax_legal"
	trust_level = TrustLevel.APPROVAL

	def __init__(
		self,
		service: EstimatedTaxService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or EstimatedTaxService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle tax calculation requests."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Calculate annual summary and identify next payment."""
		summary = self.service.get_annual_summary()
		return ActionPlan(
			action_type="calculate_estimated_tax",
			confidence=0.90,
			context={
				"annual_income": summary.annual_income_estimate,
				"total_annual_tax": summary.total_annual_tax,
				"quarterly_payment": summary.quarterly_payment,
				"effective_rate": summary.effective_tax_rate,
				"next_quarter": summary.next_quarter.value if summary.next_quarter else None,
				"next_due_date": summary.next_due_date.isoformat() if summary.next_due_date else None,
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Emit estimated tax calculation result."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})
		payment = plan.context.get("quarterly_payment", 0.0)
		quarter = plan.context.get("next_quarter", "unknown")
		return ActionResult(
			True,
			f"Tax estimate complete: ${payment:.2f}/quarter due; next payment {quarter}",
			{**plan.context, "policy": decision.reason},
		)
