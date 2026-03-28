"""Workflow #13: Furnished Finder Lead Responder — Phase 1 Priority.

Auto-responds to Furnished Finder inquiries with a templated response,
screens the lead, and queues for user review.

Recommended phase: 1 (quick_win_score: 10)
Trust level: draft
Required credentials: Gmail (FF notifications arrive via email)
Category: property

TODO: Implement after scaffolding is approved.

Workflow states:
- idle -> lead_received -> screened -> draft_reply_prepared -> sent | rejected

Service interface:
- parse_lead(email) -> FurnishedFinderLead
- screen_lead(lead) -> ScreeningResult
- draft_response(lead, screening) -> DraftResponse
- send_response(draft, approval) -> None

Schemas needed:
- FurnishedFinderLead(name, dates, guests, budget, message, source_email)
- ScreeningResult(score, flags, recommendation)
- DraftResponse(to, subject, body, is_auto_approved)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class LeadRecommendation(str, Enum):
	AUTO_APPROVE = "auto_approve"
	REVIEW = "review"
	REJECT = "reject"


class LeadStatus(str, Enum):
	RECEIVED = "received"
	SCREENED = "screened"
	DRAFTED = "drafted"
	SENT = "sent"
	REJECTED = "rejected"


@dataclass(slots=True)
class FurnishedFinderLead:
	lead_id: str
	name: str
	check_in: date
	check_out: date
	guests: int
	budget: float
	message: str
	source_email: str
	status: LeadStatus = LeadStatus.RECEIVED

	def length_of_stay(self) -> int:
		return max((self.check_out - self.check_in).days, 0)


@dataclass(frozen=True, slots=True)
class ScreeningResult:
	score: float
	flags: list[str]
	recommendation: LeadRecommendation


@dataclass(frozen=True, slots=True)
class DraftResponse:
	to: str
	subject: str
	body: str
	is_auto_approved: bool


@dataclass(frozen=True, slots=True)
class LeadSummary:
	total_leads: int
	pending_review: int
	auto_approved: int
	rejected: int


class FurnishedFinderLeadResponderService(PersistenceMixin):
	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._leads: dict[str, FurnishedFinderLead] = {}

	def add_lead(self, lead: FurnishedFinderLead) -> FurnishedFinderLead:
		self._leads[lead.lead_id] = lead
		return lead

	def parse_lead(self, email_payload: dict[str, str]) -> FurnishedFinderLead:
		return FurnishedFinderLead(
			lead_id=email_payload.get("lead_id", "unknown_lead"),
			name=email_payload.get("name", "Unknown"),
			check_in=date.fromisoformat(email_payload.get("check_in", date.today().isoformat())),
			check_out=date.fromisoformat(email_payload.get("check_out", date.today().isoformat())),
			guests=int(email_payload.get("guests", "1")),
			budget=float(email_payload.get("budget", "0")),
			message=email_payload.get("message", ""),
			source_email=email_payload.get("source_email", ""),
		)

	def screen_lead(self, lead: FurnishedFinderLead) -> ScreeningResult:
		flags: list[str] = []
		score = 0.5
		if lead.budget >= 2500:
			score += 0.25
		else:
			flags.append("low_budget")
		if 1 <= lead.guests <= 2:
			score += 0.15
		else:
			flags.append("guest_count_review")
		if lead.length_of_stay() >= 30:
			score += 0.1
		if "party" in lead.message.lower():
			score -= 0.35
			flags.append("party_risk")

		if score >= 0.8:
			rec = LeadRecommendation.AUTO_APPROVE
		elif score >= 0.55:
			rec = LeadRecommendation.REVIEW
		else:
			rec = LeadRecommendation.REJECT

		return ScreeningResult(score=max(score, 0.0), flags=flags, recommendation=rec)

	def draft_response(self, lead: FurnishedFinderLead, screening: ScreeningResult) -> DraftResponse:
		subject = f"Re: Furnished Finder Inquiry from {lead.name}"
		body = (
			f"Hi {lead.name},\n\n"
			"Thanks for your interest in our furnished rental. "
			"We reviewed your dates and will follow up with next steps shortly.\n\n"
			"Best,\nAtlas"
		)
		return DraftResponse(
			to=lead.source_email,
			subject=subject,
			body=body,
			is_auto_approved=screening.recommendation == LeadRecommendation.AUTO_APPROVE,
		)

	def mark_sent(self, lead_id: str) -> bool:
		if lead_id not in self._leads:
			return False
		self._leads[lead_id].status = LeadStatus.SENT
		return True

	def mark_rejected(self, lead_id: str) -> bool:
		if lead_id not in self._leads:
			return False
		self._leads[lead_id].status = LeadStatus.REJECTED
		return True

	def get_pending_review(self) -> list[FurnishedFinderLead]:
		return [l for l in self._leads.values() if l.status in (LeadStatus.RECEIVED, LeadStatus.SCREENED, LeadStatus.DRAFTED)]

	def get_summary(self) -> LeadSummary:
		vals = list(self._leads.values())
		return LeadSummary(
			total_leads=len(vals),
			pending_review=len([l for l in vals if l.status in (LeadStatus.RECEIVED, LeadStatus.SCREENED, LeadStatus.DRAFTED)]),
			auto_approved=len([l for l in vals if l.status == LeadStatus.SENT]),
			rejected=len([l for l in vals if l.status == LeadStatus.REJECTED]),
		)


class FurnishedFinderLeadResponderWorkflow(BaseWorkflow):
	workflow_id = "furnished_finder_lead_responder"
	name = "Furnished Finder Lead Responder"
	category = "property"
	trust_level = TrustLevel.DRAFT

	def __init__(
		self,
		service: FurnishedFinderLeadResponderService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or FurnishedFinderLeadResponderService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		summary = self.service.get_summary()
		return ActionPlan(
			action_type="screen_and_prepare_lead_response",
			confidence=0.86,
			context={
				"total_leads": summary.total_leads,
				"pending_review": summary.pending_review,
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
			f"furnished finder responder: {plan.context.get('pending_review', 0)} lead(s) pending review",
			{**plan.context, "policy": decision.reason},
		)
