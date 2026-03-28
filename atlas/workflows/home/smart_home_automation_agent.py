"""Workflow #89: Smart Home Automation Agent — Phase 2 Priority.
Creates and manages Home Assistant automations based on user patterns and preferences.
Recommended phase: 2 (quick_win_score: 10) | Trust level: approve | Category: home
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class TriggerType(str, Enum):
	TIME = "time"
	SUNSET = "sunset"
	PRESENCE = "presence"
	MOTION = "motion"
	TEMPERATURE = "temperature"


class AutomationStatus(str, Enum):
	ACTIVE = "active"
	PAUSED = "paused"
	ERROR = "error"
	DISABLED = "disabled"


@dataclass(slots=True)
class AutomationRule:
	rule_id: str
	name: str
	trigger_type: TriggerType
	trigger_value: str
	action: str
	enabled: bool = True
	status: AutomationStatus = AutomationStatus.ACTIVE
	run_count: int = 0
	error_count: int = 0


@dataclass(frozen=True, slots=True)
class AutomationSummary:
	total_rules: int
	active_rules: int
	paused_rules: int
	error_rules: int
	total_runs: int


class SmartHomeAutomationService(PersistenceMixin):
	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._rules: dict[str, AutomationRule] = {}

	def add_rule(
		self,
		rule_id: str,
		name: str,
		trigger_type: TriggerType,
		trigger_value: str,
		action: str,
	) -> AutomationRule:
		rule = AutomationRule(
			rule_id=rule_id,
			name=name,
			trigger_type=trigger_type,
			trigger_value=trigger_value,
			action=action,
		)
		self._rules[rule_id] = rule
		return rule

	def disable_rule(self, rule_id: str) -> bool:
		if rule_id not in self._rules:
			return False
		rule = self._rules[rule_id]
		rule.enabled = False
		rule.status = AutomationStatus.DISABLED
		return True

	def pause_rule(self, rule_id: str) -> bool:
		if rule_id not in self._rules:
			return False
		rule = self._rules[rule_id]
		rule.status = AutomationStatus.PAUSED
		return True

	def record_run(self, rule_id: str, success: bool) -> bool:
		if rule_id not in self._rules:
			return False
		rule = self._rules[rule_id]
		rule.run_count += 1
		if success:
			rule.status = AutomationStatus.ACTIVE
		else:
			rule.error_count += 1
			rule.status = AutomationStatus.ERROR
		return True

	def get_active_rules(self) -> list[AutomationRule]:
		return [r for r in self._rules.values() if r.status == AutomationStatus.ACTIVE and r.enabled]

	def get_summary(self) -> AutomationSummary:
		vals = list(self._rules.values())
		return AutomationSummary(
			total_rules=len(vals),
			active_rules=len([r for r in vals if r.status == AutomationStatus.ACTIVE and r.enabled]),
			paused_rules=len([r for r in vals if r.status == AutomationStatus.PAUSED]),
			error_rules=len([r for r in vals if r.status == AutomationStatus.ERROR]),
			total_runs=sum(r.run_count for r in vals),
		)


class SmartHomeAutomationAgent(BaseWorkflow):
	workflow_id = "smart_home_automation"
	name = "Smart Home Automation Agent"
	category = "home"
	trust_level = TrustLevel.APPROVAL

	def __init__(
		self,
		service: SmartHomeAutomationService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or SmartHomeAutomationService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		summary = self.service.get_summary()
		return ActionPlan(
			action_type="review_automation_rules",
			confidence=0.87,
			context={
				"total_rules": summary.total_rules,
				"active_rules": summary.active_rules,
				"error_rules": summary.error_rules,
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
			f"smart home automation: {plan.context.get('active_rules', 0)} active rule(s)",
			{**plan.context, "policy": decision.reason},
		)
