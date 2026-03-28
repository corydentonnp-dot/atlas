"""Workflow #72: Professional Network Nurture Agent — Phase 3 Priority.
Reminds user to maintain professional contacts; suggests outreach cadence.
Recommended phase: 3 (quick_win_score: 8) | Trust level: suggest | Category: career
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class ContactTier(str, Enum):
	CORE = "core"
	IMPORTANT = "important"
	EXTENDED = "extended"


@dataclass(slots=True)
class ProfessionalContact:
	contact_id: str
	name: str
	relationship: str
	tier: ContactTier
	last_touchpoint: date
	preferred_cadence_days: int

	def days_since_touchpoint(self) -> int:
		return (date.today() - self.last_touchpoint).days


@dataclass(frozen=True, slots=True)
class NetworkNurtureSummary:
	total_contacts: int
	due_outreach: int
	overdue_outreach: int


class ProfessionalNetworkNurtureService(PersistenceMixin):
	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._contacts: dict[str, ProfessionalContact] = {}

	def add_contact(
		self,
		contact_id: str,
		name: str,
		relationship: str,
		tier: ContactTier,
		last_touchpoint: date,
		preferred_cadence_days: int,
	) -> ProfessionalContact:
		contact = ProfessionalContact(
			contact_id=contact_id,
			name=name,
			relationship=relationship,
			tier=tier,
			last_touchpoint=last_touchpoint,
			preferred_cadence_days=preferred_cadence_days,
		)
		self._contacts[contact_id] = contact
		return contact

	def log_outreach(self, contact_id: str, touchpoint_date: date | None = None) -> bool:
		if contact_id not in self._contacts:
			return False
		self._contacts[contact_id].last_touchpoint = touchpoint_date or date.today()
		return True

	def get_due_outreach(self) -> list[ProfessionalContact]:
		return [
			c for c in self._contacts.values()
			if c.days_since_touchpoint() >= c.preferred_cadence_days
		]

	def get_summary(self) -> NetworkNurtureSummary:
		vals = list(self._contacts.values())
		due = self.get_due_outreach()
		overdue = [c for c in vals if c.days_since_touchpoint() >= (c.preferred_cadence_days * 2)]
		return NetworkNurtureSummary(
			total_contacts=len(vals),
			due_outreach=len(due),
			overdue_outreach=len(overdue),
		)


class ProfessionalNetworkNurtureAgent(BaseWorkflow):
	workflow_id = "professional_network_nurture"
	name = "Professional Network Nurture Agent"
	category = "career"
	trust_level = TrustLevel.DRAFT

	def __init__(
		self,
		service: ProfessionalNetworkNurtureService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or ProfessionalNetworkNurtureService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		summary = self.service.get_summary()
		return ActionPlan(
			action_type="suggest_network_outreach",
			confidence=0.79,
			context={
				"due_outreach": summary.due_outreach,
				"overdue_outreach": summary.overdue_outreach,
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
			f"network nurture: {plan.context.get('due_outreach', 0)} contact(s) due for outreach",
			{**plan.context, "policy": decision.reason},
		)
