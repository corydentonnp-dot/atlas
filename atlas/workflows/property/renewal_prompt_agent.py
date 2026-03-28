"""Workflow #30: Renewal Prompt Agent.

Schedules lease renewal outreach windows, negotiation prep, and response tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class RenewalStatus(str, Enum):
	"""Lease renewal status."""

	TRACKING = "tracking"
	PROMPT_DUE = "prompt_due"
	NEGOTIATING = "negotiating"
	RENEWED = "renewed"
	NON_RENEWAL = "non_renewal"
	EXPIRED = "expired"


@dataclass(slots=True)
class LeaseRenewal:
	"""Lease record for renewal timing."""

	renewal_id: str
	tenant_id: str
	tenant_name: str
	property_name: str
	unit: str
	lease_end_date: date
	current_rent: float
	proposed_rent: float | None = None
	renewal_term_months: int = 12
	status: RenewalStatus = RenewalStatus.TRACKING
	notes: str = ""
	conversation_history: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RenewalPrompt:
	"""Prompt candidate for lease renewal outreach."""

	renewal_id: str
	tenant_name: str
	property_unit: str
	days_remaining: int
	status: RenewalStatus
	checklist: tuple[str, ...]


class RenewalPromptService:
	"""Service for renewal timing and lease prep."""

	def __init__(self) -> None:
		self._leases: dict[str, LeaseRenewal] = {}

	def add_lease(self, lease: LeaseRenewal) -> LeaseRenewal:
		"""Track a lease for renewal outreach."""
		self._leases[lease.renewal_id] = lease
		return lease

	def get_preparation_checklist(self, renewal_id: str) -> tuple[str, ...]:
		"""Return a standard prep checklist before outreach."""
		lease = self._leases[renewal_id]
		items = [
			"Review payment history and maintenance issues",
			"Check local rental comps",
			"Draft renewal options and term lengths",
			"Confirm notice deadlines in lease",
		]
		if lease.proposed_rent is not None and lease.proposed_rent != lease.current_rent:
			items.append("Prepare rent change explanation")
		return tuple(items)

	def upcoming_prompts(self, today: date, days_ahead: int = 75) -> list[RenewalPrompt]:
		"""Return leases that need renewal outreach soon."""
		results: list[RenewalPrompt] = []
		for lease in self._leases.values():
			days_remaining = (lease.lease_end_date - today).days
			if days_remaining < 0:
				lease.status = RenewalStatus.EXPIRED
				continue
			if days_remaining <= days_ahead and lease.status in {RenewalStatus.TRACKING, RenewalStatus.PROMPT_DUE, RenewalStatus.NEGOTIATING}:
				if lease.status == RenewalStatus.TRACKING:
					lease.status = RenewalStatus.PROMPT_DUE
				results.append(
					RenewalPrompt(
						renewal_id=lease.renewal_id,
						tenant_name=lease.tenant_name,
						property_unit=f"{lease.property_name}/{lease.unit}",
						days_remaining=days_remaining,
						status=lease.status,
						checklist=self.get_preparation_checklist(lease.renewal_id),
					)
				)
		results.sort(key=lambda prompt: prompt.days_remaining)
		return results

	def record_response(self, renewal_id: str, note: str, accepted: bool | None = None) -> bool:
		"""Record tenant response and update status."""
		lease = self._leases.get(renewal_id)
		if lease is None:
			return False
		lease.conversation_history.append(note)
		if accepted is True:
			lease.status = RenewalStatus.RENEWED
		elif accepted is False:
			lease.status = RenewalStatus.NON_RENEWAL
		else:
			lease.status = RenewalStatus.NEGOTIATING
		return True


class RenewalPromptAgent(BaseWorkflow):
	"""Workflow for lease renewal prompt timing."""

	workflow_id = "renewal_prompt_agent"
	name = "renewal_prompt_agent"
	category = "property"
	trust_level = TrustLevel.DRAFT

	def __init__(self, service: RenewalPromptService | None = None, policy_engine: PolicyEngine | None = None) -> None:
		super().__init__()
		self.service = service or RenewalPromptService()
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		if event.event_type == "lease_registered":
			payload = event.payload
			self.service.add_lease(
				LeaseRenewal(
					renewal_id=str(payload.get("renewal_id", "")),
					tenant_id=str(payload.get("tenant_id", "")),
					tenant_name=str(payload.get("tenant_name", "")),
					property_name=str(payload.get("property_name", "")),
					unit=str(payload.get("unit", "")),
					lease_end_date=date.fromisoformat(str(payload.get("lease_end_date", date.today().isoformat()))),
					current_rent=float(payload.get("current_rent", 0)),
					proposed_rent=float(payload["proposed_rent"]) if "proposed_rent" in payload else None,
					renewal_term_months=int(payload.get("renewal_term_months", 12)),
				)
			)
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		today = date.fromisoformat(str(run.event.payload.get("today", date.today().isoformat())))
		prompts = self.service.upcoming_prompts(today=today)
		return ActionPlan(
			action_type="prepare_renewal_prompts",
			confidence=0.88 if prompts else 0.7,
			context={
				"prompt_count": len(prompts),
				"prompts": [
					{
						"tenant_name": prompt.tenant_name,
						"property_unit": prompt.property_unit,
						"days_remaining": prompt.days_remaining,
						"status": prompt.status.value,
						"checklist": list(prompt.checklist),
					}
					for prompt in prompts
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
		count = int(plan.context.get("prompt_count", 0))
		summary = f"Prepared {count} renewal prompt(s)" if count else "No lease renewal prompts due"
		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
