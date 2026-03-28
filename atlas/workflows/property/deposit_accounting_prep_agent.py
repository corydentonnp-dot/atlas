"""Workflow #25: Deposit Accounting Prep Agent.

Prepares security deposit accounting and reconciliation after tenant move-out.
Calculates damages, deductions, and refund amounts with audit trail.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class DeductionCategory(str, Enum):
	"""Types of security deposit deductions."""

	DAMAGE = "damage"
	CLEANING = "cleaning"
	REPAIRS = "repairs"
	RENT_DEFAULT = "rent_default"
	UTILITY_ARREARS = "utility_arrears"


@dataclass(slots=True)
class DepositDeduction:
	"""Single deduction item from security deposit."""

	deduction_id: str
	category: DeductionCategory
	description: str
	amount: float
	documented: bool = False
	photo_references: list[str] = None

	def __post_init__(self) -> None:
		if self.photo_references is None:
			self.photo_references = []


@dataclass(slots=True)
class DepositAccounting:
	"""Complete security deposit accounting record."""

	accounting_id: str
	tenant_id: str
	tenant_name: str
	property_unit: str
	deposit_amount: float
	move_out_date: date
	deductions: list[DepositDeduction]
	documentation_complete: bool = False
	refund_amount: float | None = None


class DepositAccountingService(PersistenceMixin):
	"""Service for security deposit accounting and reconciliation."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._accountings: dict[str, DepositAccounting] = {}

	def create_accounting(self, accounting: DepositAccounting) -> DepositAccounting:
		"""Create a new deposit accounting record."""
		self._accountings[accounting.accounting_id] = accounting
		return accounting

	def add_deduction(self, accounting_id: str, deduction: DepositDeduction) -> bool:
		"""Add a deduction to accounting."""
		accounting = self._accountings.get(accounting_id)
		if accounting is None:
			return False
		accounting.deductions.append(deduction)
		return True

	def calculate_refund(self, accounting_id: str) -> float:
		"""Calculate refund amount (deposit - total deductions)."""
		accounting = self._accountings.get(accounting_id)
		if accounting is None:
			return 0.0
		total_deductions = sum(d.amount for d in accounting.deductions)
		refund = accounting.deposit_amount - total_deductions
		accounting.refund_amount = max(0.0, refund)
		return accounting.refund_amount

	def documentation_summary(self, accounting_id: str) -> dict[str, object]:
		"""Return summary of documentation status."""
		accounting = self._accountings.get(accounting_id)
		if accounting is None:
			return {}
		documented = sum(1 for d in accounting.deductions if d.documented)
		total = len(accounting.deductions)
		refund = self.calculate_refund(accounting_id)
		return {
			"deduction_count": total,
			"documented_count": documented,
			"documentation_complete": documented == total,
			"total_deductions": sum(d.amount for d in accounting.deductions),
			"refund_amount": refund,
		}

	def is_audit_ready(self, accounting_id: str) -> bool:
		"""Check if accounting is ready for audit/approval."""
		accounting = self._accountings.get(accounting_id)
		if accounting is None or not accounting.deductions:
			return True  # No deductions = straightforward full refund
		documented = sum(1 for d in accounting.deductions if d.documented)
		return documented == len(accounting.deductions)


class DepositAccountingPrepAgent(BaseWorkflow):
	"""Workflow for security deposit accounting preparation."""

	workflow_id = "deposit_accounting_prep_agent"
	name = "deposit_accounting_prep_agent"
	category = "property"
	trust_level = TrustLevel.APPROVAL

	def __init__(self, service: DepositAccountingService | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = service or DepositAccountingService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		if event.event_type == "deposit_accounting_started":
			payload = event.payload
			self.service.create_accounting(
				DepositAccounting(
					accounting_id=str(payload.get("accounting_id", "")),
					tenant_id=str(payload.get("tenant_id", "")),
					tenant_name=str(payload.get("tenant_name", "")),
					property_unit=str(payload.get("property_unit", "")),
					deposit_amount=float(payload.get("deposit_amount", 0)),
					move_out_date=date.fromisoformat(str(payload.get("move_out_date", date.today().isoformat()))),
					deductions=[],
				)
			)
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		accounting_id = str(run.event.payload.get("accounting_id", ""))
		summary = self.service.documentation_summary(accounting_id)
		is_ready = self.service.is_audit_ready(accounting_id)
		return ActionPlan(
			action_type="prepare_deposit_accounting",
			confidence=0.95 if is_ready else 0.65,
			context={
				"accounting_id": accounting_id,
				"summary": summary,
				"audit_ready": is_ready,
				"refund_amount": summary.get("refund_amount", 0.0),
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
		if not decision.allowed:
			self.state_machine.transition("failed", {"reason": decision.reason})
			return ActionResult(False, decision.reason, plan.context)

		self.state_machine.transition("completed", {"reason": decision.reason})
		refund = float(plan.context.get("refund_amount", 0.0))
		summary = f"Deposit accounting prepared: ${refund:.2f} refund calculated"
		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
