"""Workflow #67: Malpractice Coverage Review Agent — Phase 3 Priority.
Reviews malpractice insurance coverage terms, renewal dates, and premium changes.
Recommended phase: 3 (quick_win_score: 8) | Trust level: approve | Category: licensure
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class MalpracticeStatus(str, Enum):
	ACTIVE = "active"
	REVIEW_DUE = "review_due"
	EXPIRED = "expired"


@dataclass(slots=True)
class MalpracticePolicy:
	policy_id: str
	carrier: str
	renewal_date: date
	annual_premium: float
	previous_premium: float
	coverage_amount: float
	status: MalpracticeStatus = MalpracticeStatus.ACTIVE

	def days_until_renewal(self) -> int:
		return (self.renewal_date - date.today()).days

	def premium_change_pct(self) -> float:
		if self.previous_premium <= 0:
			return 0.0
		return ((self.annual_premium - self.previous_premium) / self.previous_premium) * 100


@dataclass(frozen=True, slots=True)
class MalpracticeSummary:
	total_policies: int
	review_due: int
	expired: int
	avg_premium_change_pct: float


class MalpracticeCoverageReviewService(PersistenceMixin):
	REVIEW_DUE_DAYS = 45

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._policies: dict[str, MalpracticePolicy] = {}

	def add_policy(
		self,
		policy_id: str,
		carrier: str,
		renewal_date: date,
		annual_premium: float,
		previous_premium: float,
		coverage_amount: float,
	) -> MalpracticePolicy:
		policy = MalpracticePolicy(
			policy_id=policy_id,
			carrier=carrier,
			renewal_date=renewal_date,
			annual_premium=annual_premium,
			previous_premium=previous_premium,
			coverage_amount=coverage_amount,
		)
		self._policies[policy_id] = policy
		self._refresh_status(policy)
		return policy

	def get_review_due(self) -> list[MalpracticePolicy]:
		self._refresh_all()
		return [p for p in self._policies.values() if p.status == MalpracticeStatus.REVIEW_DUE]

	def get_summary(self) -> MalpracticeSummary:
		self._refresh_all()
		vals = list(self._policies.values())
		changes = [p.premium_change_pct() for p in vals]
		return MalpracticeSummary(
			total_policies=len(vals),
			review_due=len([p for p in vals if p.status == MalpracticeStatus.REVIEW_DUE]),
			expired=len([p for p in vals if p.status == MalpracticeStatus.EXPIRED]),
			avg_premium_change_pct=(sum(changes) / len(changes)) if changes else 0.0,
		)

	def _refresh_status(self, policy: MalpracticePolicy) -> None:
		days = policy.days_until_renewal()
		if days < 0:
			policy.status = MalpracticeStatus.EXPIRED
		elif days <= self.REVIEW_DUE_DAYS:
			policy.status = MalpracticeStatus.REVIEW_DUE
		else:
			policy.status = MalpracticeStatus.ACTIVE

	def _refresh_all(self) -> None:
		for policy in self._policies.values():
			self._refresh_status(policy)


class MalpracticeCoverageReviewAgent(BaseWorkflow):
	workflow_id = "malpractice_coverage_review"
	name = "Malpractice Coverage Review Agent"
	category = "licensure"
	trust_level = TrustLevel.APPROVAL

	def __init__(
		self,
		service: MalpracticeCoverageReviewService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or MalpracticeCoverageReviewService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		summary = self.service.get_summary()
		return ActionPlan(
			action_type="review_malpractice_policy",
			confidence=0.83,
			context={
				"review_due": summary.review_due,
				"expired": summary.expired,
				"avg_premium_change_pct": summary.avg_premium_change_pct,
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
			f"malpractice review: {plan.context.get('review_due', 0)} policy(s) due",
			{**plan.context, "policy": decision.reason},
		)
