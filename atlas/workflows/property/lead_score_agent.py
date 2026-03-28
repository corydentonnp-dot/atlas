"""Workflow #15: Lead Score Agent.

Scores and ranks rental leads by budget fit, timeline, credit profile, and reliability signals.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class LeadQualification(str, Enum):
	"""Lead qualification tier."""

	STRONG = "strong"
	QUALIFIED = "qualified"
	MARGINAL = "marginal"
	WEAK = "weak"
	UNQUALIFIED = "unqualified"


@dataclass(frozen=True, slots=True)
class RentalLead:
	"""Prospective tenant lead."""

	lead_id: str
	applicant_name: str
	monthly_income: float
	annual_income: float
	requested_rent: float
	credit_score: int | None = None
	employment_stable: bool = True
	references_available: bool = False
	move_in_timeline_days: int = 30


@dataclass(frozen=True, slots=True)
class LeadScore:
	"""Scoring result for a lead."""

	lead_id: str
	qualification: LeadQualification
	total_score: float
	budget_fit_score: float
	stability_score: float
	timeline_score: float


class LeadScoringService(PersistenceMixin):
	"""Service for lead qualification and scoring."""

	# Rent-to-income ratio for qualification
	MIN_INCOME_RATIO = 0.3  # Income should be at least 3x rent
	STRONG_INCOME_RATIO = 0.2  # Income 5x rent is strong

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._leads: dict[str, RentalLead] = {}
		self._scores: dict[str, LeadScore] = {}

	def add_lead(self, lead: RentalLead) -> RentalLead:
		"""Register a lead."""
		self._leads[lead.lead_id] = lead
		return lead

	def score_lead(self, lead: RentalLead) -> LeadScore:
		"""Score a lead."""
		budget_fit = self._score_budget_fit(lead)
		stability = self._score_stability(lead)
		timeline = self._score_timeline(lead)
		total = (budget_fit + stability + timeline) / 3.0

		if total >= 8.5:
			qualification = LeadQualification.STRONG
		elif total >= 7.0:
			qualification = LeadQualification.QUALIFIED
		elif total >= 5.0:
			qualification = LeadQualification.MARGINAL
		elif total >= 3.0:
			qualification = LeadQualification.WEAK
		else:
			qualification = LeadQualification.UNQUALIFIED

		score = LeadScore(
			lead_id=lead.lead_id,
			qualification=qualification,
			total_score=total,
			budget_fit_score=budget_fit,
			stability_score=stability,
			timeline_score=timeline,
		)
		self._scores[lead.lead_id] = score
		return score

	def _score_budget_fit(self, lead: RentalLead) -> float:
		"""Score rent-to-income ratio (0-10)."""
		ratio = lead.requested_rent / max(lead.monthly_income, 1.0)
		if ratio <= self.STRONG_INCOME_RATIO:
			return 10.0
		elif ratio <= self.MIN_INCOME_RATIO:
			return 7.0
		elif ratio <= 0.4:
			return 4.0
		return 1.0

	def _score_stability(self, lead: RentalLead) -> float:
		"""Score employment/financial stability (0-10)."""
		score = 5.0
		if lead.employment_stable:
			score += 3.0
		if lead.credit_score is not None and lead.credit_score >= 700:
			score += 2.0
		if lead.references_available:
			score += 1.0
		return min(score, 10.0)

	def _score_timeline(self, lead: RentalLead) -> float:
		"""Score move-in timeline flexibility (0-10)."""
		if lead.move_in_timeline_days >= 30:
			return 9.0
		elif lead.move_in_timeline_days >= 14:
			return 6.0
		return 3.0

	def rank_leads(self) -> list[LeadScore]:
		"""Return all leads ranked by score."""
		return sorted(self._scores.values(), key=lambda s: s.total_score, reverse=True)


class LeadScoreAgent(BaseWorkflow):
	"""Workflow for lead qualification and ranking."""

	workflow_id = "lead_score_agent"
	name = "lead_score_agent"
	category = "property"
	trust_level = TrustLevel.DRAFT

	def __init__(self, service: LeadScoringService | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = service or LeadScoringService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		if event.event_type == "lead_received":
			payload = event.payload
			lead = RentalLead(
				lead_id=str(payload.get("lead_id", "")),
				applicant_name=str(payload.get("applicant_name", "")),
				monthly_income=float(payload.get("monthly_income", 0)),
				annual_income=float(payload.get("annual_income", 0)),
				requested_rent=float(payload.get("requested_rent", 0)),
				credit_score=int(payload.get("credit_score")) if "credit_score" in payload else None,
				employment_stable=bool(payload.get("employment_stable", True)),
				references_available=bool(payload.get("references_available", False)),
				move_in_timeline_days=int(payload.get("move_in_timeline_days", 30)),
			)
			self.service.add_lead(lead)
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		lead_id = str(run.event.payload.get("lead_id", ""))
		lead = self.service._leads.get(lead_id)
		if lead is None:
			return ActionPlan(action_type="score_lead", confidence=0.5, context={"error": "Lead not found"})
		score = self.service.score_lead(lead)
		return ActionPlan(
			action_type="score_lead",
			confidence=0.92,
			context={
				"lead_id": score.lead_id,
				"qualification": score.qualification.value,
				"total_score": score.total_score,
				"budget_fit": score.budget_fit_score,
				"stability": score.stability_score,
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
		qualification = plan.context.get("qualification", "unknown")
		total_score = float(plan.context.get("total_score", 0.0))
		summary = f"Lead scored {total_score:.1f}/10 ({qualification})"
		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
