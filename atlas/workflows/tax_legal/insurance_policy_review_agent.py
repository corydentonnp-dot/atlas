"""Workflow #82: Insurance Policy Review Agent — Phase 3 Priority.
Tracks insurance policy renewal dates and coverage adequacy across all policy types.
Recommended phase: 3 (quick_win_score: 8) | Trust level: suggest | Category: tax_legal
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class PolicyType(str, Enum):
	AUTO = "auto"
	HOME = "home"
	RENTERS = "renters"
	LIFE = "life"
	DISABILITY = "disability"
	UMBRELLA = "umbrella"
	MALPRACTICE = "malpractice"
	OTHER = "other"


class PolicyStatus(str, Enum):
	ACTIVE = "active"
	REVIEW_DUE = "review_due"
	LAPSED = "lapsed"
	CANCELLED = "cancelled"


@dataclass(slots=True)
class InsurancePolicy:
	policy_id: str
	policy_type: PolicyType
	carrier: str
	renewal_date: date
	coverage_amount: float
	coverage_target: float
	status: PolicyStatus = PolicyStatus.ACTIVE

	def days_until_renewal(self) -> int:
		return (self.renewal_date - date.today()).days

	def is_underinsured(self) -> bool:
		return self.coverage_amount < self.coverage_target


@dataclass(frozen=True, slots=True)
class InsuranceReviewSummary:
	total_policies: int
	review_due: int
	lapsed: int
	underinsured: int


class InsurancePolicyReviewService(PersistenceMixin):
	REVIEW_DUE_DAYS = 45

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._policies: dict[str, InsurancePolicy] = {}

	def add_policy(
		self,
		policy_id: str,
		policy_type: PolicyType,
		carrier: str,
		renewal_date: date,
		coverage_amount: float,
		coverage_target: float,
	) -> InsurancePolicy:
		policy = InsurancePolicy(
			policy_id=policy_id,
			policy_type=policy_type,
			carrier=carrier,
			renewal_date=renewal_date,
			coverage_amount=coverage_amount,
			coverage_target=coverage_target,
		)
		self._policies[policy_id] = policy
		self._refresh_status(policy)
		return policy

	def cancel_policy(self, policy_id: str) -> bool:
		if policy_id not in self._policies:
			return False
		self._policies[policy_id].status = PolicyStatus.CANCELLED
		return True

	def get_review_due(self) -> list[InsurancePolicy]:
		self._refresh_all()
		return [p for p in self._policies.values() if p.status == PolicyStatus.REVIEW_DUE]

	def get_underinsured(self) -> list[InsurancePolicy]:
		self._refresh_all()
		return [p for p in self._policies.values() if p.status in (PolicyStatus.ACTIVE, PolicyStatus.REVIEW_DUE) and p.is_underinsured()]

	def get_summary(self) -> InsuranceReviewSummary:
		self._refresh_all()
		vals = list(self._policies.values())
		return InsuranceReviewSummary(
			total_policies=len(vals),
			review_due=len([p for p in vals if p.status == PolicyStatus.REVIEW_DUE]),
			lapsed=len([p for p in vals if p.status == PolicyStatus.LAPSED]),
			underinsured=len(self.get_underinsured()),
		)

	def _refresh_status(self, policy: InsurancePolicy) -> None:
		if policy.status == PolicyStatus.CANCELLED:
			return
		days = policy.days_until_renewal()
		if days < 0:
			policy.status = PolicyStatus.LAPSED
		elif days <= self.REVIEW_DUE_DAYS:
			policy.status = PolicyStatus.REVIEW_DUE
		else:
			policy.status = PolicyStatus.ACTIVE

	def _refresh_all(self) -> None:
		for policy in self._policies.values():
			self._refresh_status(policy)


class InsurancePolicyReviewAgent(BaseWorkflow):
	workflow_id = "insurance_policy_review"
	name = "Insurance Policy Review Agent"
	category = "tax_legal"
	trust_level = TrustLevel.DRAFT

	def __init__(
		self,
		service: InsurancePolicyReviewService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or InsurancePolicyReviewService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		summary = self.service.get_summary()
		return ActionPlan(
			action_type="review_insurance_policies",
			confidence=0.81,
			context={
				"review_due": summary.review_due,
				"lapsed": summary.lapsed,
				"underinsured": summary.underinsured,
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
			f"insurance policy review: {plan.context.get('review_due', 0)} policy(s) due",
			{**plan.context, "policy": decision.reason},
		)
