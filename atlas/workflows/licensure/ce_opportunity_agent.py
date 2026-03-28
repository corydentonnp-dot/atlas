"""Workflow #64: CE Opportunity Agent.

Finds and recommends continuing education opportunities matching license renewal requirements.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class ProviderType(str, Enum):
	"""CE provider type."""

	UNIVERSITY = "university"
	PROFESSIONAL_ORGANIZATION = "professional_organization"
	ONLINE_PLATFORM = "online_platform"
	CLINICAL_SETTING = "clinical_setting"
	CONFERENCE = "conference"


@dataclass(frozen=True, slots=True)
class CECourse:
	"""Continuing education course."""

	course_id: str
	title: str
	provider: str
	provider_type: ProviderType
	hours: int
	cost: float
	formats: list[str]
	disciplines: list[str]
	link: str = ""


@dataclass(frozen=True, slots=True)
class CEOpportunity:
	"""Recommended CE opportunity."""

	course_id: str
	title: str
	provider: str
	hours: int
	cost: float
	relevance_score: float
	match_reason: str


class CEOpportunityService(PersistenceMixin):
	"""Service for CE course discovery and matching."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._courses = self.SAMPLE_COURSES

	SAMPLE_COURSES: list[CECourse] = [
		CECourse(
			course_id="ce-1", title="Advanced Pharmacology", provider="University of Washington",
			provider_type=ProviderType.UNIVERSITY, hours=6, cost=400.0,
			formats=["in-person"], disciplines=["pharmacology"], link="https://nursing.uw.edu"
		),
		CECourse(
			course_id="ce-2", title="NP Board Review", provider="AANP",
			provider_type=ProviderType.PROFESSIONAL_ORGANIZATION, hours=8, cost=300.0,
			formats=["online"], disciplines=["general"], link="https://www.aanp.org"
		),
		CECourse(
			course_id="ce-3", title="Acute Care Fundamentals", provider="National Teacher's College",
			provider_type=ProviderType.ONLINE_PLATFORM, hours=10, cost=200.0,
			formats=["online"], disciplines=["acute_care"], link="https://ntccourse.com"
		),
		CECourse(
			course_id="ce-4", title="Emergency Medicine Update", provider="American Academy EM",
			provider_type=ProviderType.CONFERENCE, hours=16, cost=500.0,
			formats=["in-person"], disciplines=["emergency"], link="https://www.aaem.org"
		),
	]

	def find_opportunities(self, discipline: str | None = None, max_cost: float = 1000.0, format_preference: str = "any") -> list[CEOpportunity]:
		"""Find matching CE opportunities."""
		opportunities: list[CEOpportunity] = []
		for course in self._courses:
			if course.cost > max_cost:
				continue
			if format_preference != "any" and format_preference not in course.formats:
				continue
			relevance = 0.5
			reason = "General educational value"
			if discipline and discipline in course.disciplines:
				relevance = 0.95
				reason = f"Directly matches {discipline} requirement"
			elif not discipline and "general" in course.disciplines:
				relevance = 0.8
				reason = "Satisfies general CE requirement"
			opportunities.append(
				CEOpportunity(
					course_id=course.course_id,
					title=course.title,
					provider=course.provider,
					hours=course.hours,
					cost=course.cost,
					relevance_score=relevance,
					match_reason=reason,
				)
			)
		return sorted(opportunities, key=lambda o: o.relevance_score, reverse=True)


class CEOpportunityAgent(BaseWorkflow):
	"""Workflow for finding CE opportunities."""

	workflow_id = "ce_opportunity_agent"
	name = "ce_opportunity_agent"
	category = "licensure"
	trust_level = TrustLevel.DRAFT

	def __init__(self, service: CEOpportunityService | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = service or CEOpportunityService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		# No special trigger actions for now
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		payload = run.event.payload
		discipline = payload.get("discipline") if payload else None
		max_cost = float(payload.get("max_cost", 1000.0)) if payload else 1000.0
		format_pref = str(payload.get("format", "any")) if payload else "any"
		opportunities = self.service.find_opportunities(discipline, max_cost, format_pref)
		return ActionPlan(
			action_type="find_ce_opportunities",
			confidence=0.88 if opportunities else 0.6,
			context={
				"discipline": discipline,
				"opportunity_count": len(opportunities),
				"opportunities": [
					{
						"title": opp.title,
						"provider": opp.provider,
						"hours": opp.hours,
						"cost": opp.cost,
						"relevance": opp.relevance_score,
					}
					for opp in opportunities[:5]
				],
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
		count = int(plan.context.get("opportunity_count", 0))
		summary = f"Found {count} matching CE opportunity(ies)" if count else "No matching CE opportunities found"
		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
