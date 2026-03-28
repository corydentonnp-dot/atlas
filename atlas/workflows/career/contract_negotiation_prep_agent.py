"""Workflow #71: Contract Negotiation Prep Agent — Phase 3 Priority.
Prepares research, comparables, and talking points for employment contract negotiations.
Recommended phase: 3 (quick_win_score: 8) | Trust level: approve | Category: career
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class NegotiationStatus(str, Enum):
	PREP = "prep"
	IN_PROGRESS = "in_progress"
	COMPLETED = "completed"


@dataclass(slots=True)
class ContractNegotiationCase:
	case_id: str
	role_title: str
	organization: str
	base_offer: float
	target_offer: float
	status: NegotiationStatus = NegotiationStatus.PREP
	comparables: list[float] = field(default_factory=list)
	talking_points: list[str] = field(default_factory=list)
	created_on: date = field(default_factory=date.today)


@dataclass(frozen=True, slots=True)
class ContractNegotiationSummary:
	total_cases: int
	prep_cases: int
	avg_offer_gap: float


class ContractNegotiationPrepService(PersistenceMixin):
	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._cases: dict[str, ContractNegotiationCase] = {}

	def add_case(
		self,
		case_id: str,
		role_title: str,
		organization: str,
		base_offer: float,
		target_offer: float,
	) -> ContractNegotiationCase:
		case = ContractNegotiationCase(
			case_id=case_id,
			role_title=role_title,
			organization=organization,
			base_offer=base_offer,
			target_offer=target_offer,
		)
		self._cases[case_id] = case
		return case

	def add_comparable(self, case_id: str, salary: float) -> bool:
		if case_id not in self._cases:
			return False
		self._cases[case_id].comparables.append(salary)
		return True

	def add_talking_point(self, case_id: str, point: str) -> bool:
		if case_id not in self._cases:
			return False
		self._cases[case_id].talking_points.append(point)
		return True

	def start_negotiation(self, case_id: str) -> bool:
		if case_id not in self._cases:
			return False
		self._cases[case_id].status = NegotiationStatus.IN_PROGRESS
		return True

	def get_summary(self) -> ContractNegotiationSummary:
		vals = list(self._cases.values())
		gaps = [max(c.target_offer - c.base_offer, 0.0) for c in vals]
		return ContractNegotiationSummary(
			total_cases=len(vals),
			prep_cases=len([c for c in vals if c.status == NegotiationStatus.PREP]),
			avg_offer_gap=(sum(gaps) / len(gaps)) if gaps else 0.0,
		)


class ContractNegotiationPrepAgent(BaseWorkflow):
	workflow_id = "contract_negotiation_prep"
	name = "Contract Negotiation Prep Agent"
	category = "career"
	trust_level = TrustLevel.APPROVAL

	def __init__(
		self,
		service: ContractNegotiationPrepService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or ContractNegotiationPrepService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		summary = self.service.get_summary()
		return ActionPlan(
			action_type="prepare_negotiation_package",
			confidence=0.84,
			context={
				"prep_cases": summary.prep_cases,
				"avg_offer_gap": summary.avg_offer_gap,
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
			f"contract negotiation prep: {plan.context.get('prep_cases', 0)} case(s) ready",
			{**plan.context, "policy": decision.reason},
		)
