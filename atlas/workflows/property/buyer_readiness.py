"""Workflow #49: Buyer Readiness — scores home purchase qualification readiness.

Evaluates financial preparedness for home purchase across credit, savings, debt,
employment stability, and provides actionable recommendations for improvement.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class ReadinessCategory(str, Enum):
	"""Buyer readiness assessment area."""

	CREDIT = "credit"
	SAVINGS = "savings"
	DEBT_RATIO = "debt_ratio"
	EMPLOYMENT = "employment"
	DOWN_PAYMENT = "down_payment"
	RESERVE_FUNDS = "reserve_funds"


class ReadinessStatus(str, Enum):
	"""Overall readiness level."""

	NOT_READY = "not_ready"  # <60%
	DEVELOPING = "developing"  # 60-75%
	READY = "ready"  # 75-90%
	EXCELLENT = "excellent"  # 90%+


@dataclass(slots=True)
class BuyerProfile:
	"""Home buyer financial profile."""

	profile_id: str
	credit_score: int
	liquid_savings: float
	retirement_savings: float
	total_debt: float
	annual_income: float
	years_at_employer: int
	employment_stable: bool = True
	notes: str = ""


@dataclass(frozen=True, slots=True)
class ReadinessScore:
	"""Buyer readiness assessment."""

	profile_id: str
	credit_score_assessment: int  # 0-20
	savings_assessment: int  # 0-20
	debt_ratio_assessment: int  # 0-20
	employment_assessment: int  # 0-20
	down_payment_assessment: int  # 0-20
	total_score: int  # 0-100
	readiness_status: ReadinessStatus
	recommended_actions: list[str]


class BuyerReadinessService(PersistenceMixin):
	"""Service for buyer readiness scoring."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._profiles: dict[str, BuyerProfile] = {}

	def add_profile(self, profile: BuyerProfile) -> BuyerProfile:
		"""Add a buyer profile for assessment."""
		self._profiles[profile.profile_id] = profile
		return profile

	def assess_readiness(self, profile_id: str) -> ReadinessScore | None:
		"""Score buyer readiness for home purchase."""
		profile = self._profiles.get(profile_id)
		if not profile:
			return None

		# Credit score (0-20)
		if profile.credit_score >= 750:
			credit_score = 20
		elif profile.credit_score >= 700:
			credit_score = 18
		elif profile.credit_score >= 650:
			credit_score = 15
		elif profile.credit_score >= 600:
			credit_score = 10
		else:
			credit_score = 5

		# Savings assessment (0-20)
		savings_pct = profile.liquid_savings / (profile.annual_income) if profile.annual_income > 0 else 0
		if savings_pct >= 0.5:
			savings_score = 20
		elif savings_pct >= 0.3:
			savings_score = 18
		elif savings_pct >= 0.1:
			savings_score = 15
		elif savings_pct >= 0.05:
			savings_score = 10
		else:
			savings_score = 5

		# Debt-to-income ratio (0-20)
		monthly_income = profile.annual_income / 12
		dti = (profile.total_debt / monthly_income / 12) if monthly_income > 0 else 1.0
		if dti <= 0.3:
			debt_score = 20
		elif dti <= 0.43:
			debt_score = 18
		elif dti <= 0.5:
			debt_score = 15
		elif dti <= 0.6:
			debt_score = 10
		else:
			debt_score = 5

		# Employment stability (0-20)
		if profile.employment_stable and profile.years_at_employer >= 2:
			employment_score = 20
		elif profile.employment_stable and profile.years_at_employer >= 1:
			employment_score = 15
		elif profile.employment_stable:
			employment_score = 12
		else:
			employment_score = 5

		# Down payment readiness (0-20)
		down_payment_percent = (profile.liquid_savings / 300000) * 100 if profile.liquid_savings > 0 else 0  # Assume 300k home
		if down_payment_percent >= 20:
			dp_score = 20
		elif down_payment_percent >= 10:
			dp_score = 18
		elif down_payment_percent >= 5:
			dp_score = 15
		elif down_payment_percent > 0:
			dp_score = 10
		else:
			dp_score = 0

		total_score = credit_score + savings_score + debt_score + employment_score + dp_score

		# Recommendations
		recommendations = []
		if credit_score < 18:
			recommendations.append("Increase credit score above 750")
		if savings_score < 18:
			recommendations.append("Build liquid savings to 6+ months of expenses")
		if debt_score < 18:
			recommendations.append("Lower debt-to-income ratio below 0.43")
		if employment_score < 18:
			recommendations.append("Maintain stable employment for 2+ years")
		if dp_score < 20:
			recommendations.append("Save for 15-20% down payment")

		# Determine status
		if total_score >= 90:
			status = ReadinessStatus.EXCELLENT
		elif total_score >= 75:
			status = ReadinessStatus.READY
		elif total_score >= 60:
			status = ReadinessStatus.DEVELOPING
		else:
			status = ReadinessStatus.NOT_READY

		return ReadinessScore(
			profile_id=profile_id,
			credit_score_assessment=credit_score,
			savings_assessment=savings_score,
			debt_ratio_assessment=debt_score,
			employment_assessment=employment_score,
			down_payment_assessment=dp_score,
			total_score=total_score,
			readiness_status=status,
			recommended_actions=recommendations,
		)


class BuyerReadinessAgent(BaseWorkflow):
	"""Workflow for home buyer readiness assessment."""

	workflow_id = "buyer_readiness"
	name = "Buyer Readiness"
	category = "property"
	trust_level = TrustLevel.DRAFT

	def __init__(self, service: BuyerReadinessService | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = service or BuyerReadinessService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle buyer profile events."""
		self.state_machine.transition("planning", {"event_type": event.event_type})

		if event.event_type == "profile_created":
			payload = event.payload
			self.service.add_profile(
				BuyerProfile(
					profile_id=str(payload.get("profile_id", "")),
					credit_score=int(payload.get("credit_score", 650)),
					liquid_savings=float(payload.get("liquid_savings", 0)),
					retirement_savings=float(payload.get("retirement_savings", 0)),
					total_debt=float(payload.get("total_debt", 0)),
					annual_income=float(payload.get("annual_income", 0)),
					years_at_employer=int(payload.get("years_at_employer", 0)),
					employment_stable=bool(payload.get("employment_stable", True)),
				)
			)

		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Assess buyer readiness."""
		profile_id = str(run.event.payload.get("profile_id", ""))
		readiness = self.service.assess_readiness(profile_id)

		if not readiness:
			return ActionPlan(
				action_type="assess_buyer_readiness",
				confidence=0.0,
				context={"error": "Profile not found"},
			)

		return ActionPlan(
			action_type="assess_buyer_readiness",
			confidence=0.85,
			context={
				"readiness_score": readiness.total_score,
				"status": readiness.readiness_status.value,
				"credit_score": readiness.credit_score_assessment,
				"savings_score": readiness.savings_assessment,
				"debt_ratio_score": readiness.debt_ratio_assessment,
				"employment_score": readiness.employment_assessment,
				"down_payment_score": readiness.down_payment_assessment,
				"recommendations": readiness.recommended_actions,
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute readiness assessment."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})

		score = plan.context.get("readiness_score", 0)
		status = plan.context.get("status", "not_ready")
		summary = f"Buyer readiness score: {score}/100 ({status})"
		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
