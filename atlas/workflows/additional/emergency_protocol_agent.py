"""Workflow #106: Emergency Protocol Agent — Phase 2 Priority.
Activates predefined emergency protocols (security breach, weather emergency, medical).
Recommended phase: 2 (quick_win_score: 9) | Trust level: approval | Category: additional
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class EmergencyType(str, Enum):
	"""Type of emergency."""

	SECURITY_BREACH = "security_breach"
	WEATHER_EMERGENCY = "weather_emergency"
	MEDICAL_EMERGENCY = "medical_emergency"
	DATA_LOSS = "data_loss"
	SYSTEM_FAILURE = "system_failure"
	UNKNOWN = "unknown"


class SeverityLevel(str, Enum):
	"""Severity of emergency."""

	LOW = "low"
	MEDIUM = "medium"
	HIGH = "high"
	CRITICAL = "critical"


class ProtocolStatus(str, Enum):
	"""Status of emergency protocol execution."""

	ACTIVATED = "activated"
	IN_PROGRESS = "in_progress"
	COMPLETED = "completed"
	ESCALATED = "escalated"


@dataclass(frozen=True, slots=True)
class EmergencyAlert:
	"""Emergency alert triggered."""

	alert_id: str
	emergency_type: EmergencyType
	severity: SeverityLevel
	description: str
	triggered_at: datetime = datetime.now(timezone.utc)
	location: str = ""


@dataclass(frozen=True, slots=True)
class ProtocolAction:
	"""Single action within an emergency protocol."""

	action_id: str
	action_type: str
	description: str
	required: bool
	completed: bool = False


@dataclass(frozen=True, slots=True)
class EmergencyProtocol:
	"""Predefined emergency protocol."""

	protocol_id: str
	name: str
	emergency_type: EmergencyType
	severity_threshold: SeverityLevel
	actions: list[ProtocolAction]
	description: str
	escalation_contacts: list[str]


@dataclass(frozen=True, slots=True)
class ProtocolExecution:
	"""Record of protocol execution."""

	execution_id: str
	protocol_id: str
	alert_id: str
	status: ProtocolStatus
	started_at: datetime
	actions_completed: int
	actions_total: int
	escalation_reason: str | None = None


class EmergencyProtocolService(PersistenceMixin):
	"""Service for managing emergency protocols."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._protocols: dict[str, EmergencyProtocol] = {}
		self._executions: dict[str, ProtocolExecution] = {}
		self._initialize_default_protocols()

	def _initialize_default_protocols(self) -> None:
		"""Initialize default emergency protocols."""
		protocols = [
			EmergencyProtocol(
				protocol_id="security_breach",
				name="Security Breach Response",
				emergency_type=EmergencyType.SECURITY_BREACH,
				severity_threshold=SeverityLevel.HIGH,
				actions=[
					ProtocolAction("action_1", "notify_security_team", "Alert security team immediately", True),
					ProtocolAction("action_2", "isolate_systems", "Isolate affected systems", True),
					ProtocolAction("action_3", "backup_data", "Immediate data backup", True),
					ProtocolAction("action_4", "notify_stakeholders", "Notify key stakeholders", True),
				],
				description="Response protocol for security breaches",
				escalation_contacts=["security@company.com", "ceo@company.com"],
			),
			EmergencyProtocol(
				protocol_id="weather_emergency",
				name="Weather Emergency Response",
				emergency_type=EmergencyType.WEATHER_EMERGENCY,
				severity_threshold=SeverityLevel.MEDIUM,
				actions=[
					ProtocolAction("action_1", "alert_team", "Alert field teams", True),
					ProtocolAction("action_2", "secure_equipment", "Secure outdoor equipment", True),
					ProtocolAction("action_3", "activate_contingency", "Activate contingency plans", False),
					ProtocolAction("action_4", "monitor_situation", "Continuous situation monitoring", False),
				],
				description="Response protocol for severe weather",
				escalation_contacts=["operations@company.com"],
			),
			EmergencyProtocol(
				protocol_id="medical_emergency",
				name="Medical Emergency Response",
				emergency_type=EmergencyType.MEDICAL_EMERGENCY,
				severity_threshold=SeverityLevel.CRITICAL,
				actions=[
					ProtocolAction("action_1", "call_emergency", "Call emergency services (911)", True),
					ProtocolAction("action_2", "provide_first_aid", "Provide first aid if trained", False),
					ProtocolAction("action_3", "notify_emergency_contact", "Notify emergency contact", True),
					ProtocolAction("action_4", "clear_area", "Clear area and ensure safety", True),
				],
				description="Response protocol for medical emergencies",
				escalation_contacts=["healthcare@company.com", "hr@company.com"],
			),
		]

		for protocol in protocols:
			self._protocols[protocol.protocol_id] = protocol

	def create_alert(
		self,
		alert_id: str,
		emergency_type: EmergencyType,
		severity: SeverityLevel,
		description: str,
		location: str = "",
	) -> EmergencyAlert:
		"""Create an emergency alert."""
		return EmergencyAlert(
			alert_id=alert_id,
			emergency_type=emergency_type,
			severity=severity,
			description=description,
			location=location,
		)

	def get_protocol_for_emergency(self, emergency_type: EmergencyType, severity: SeverityLevel) -> EmergencyProtocol | None:
		"""Get appropriate protocol for emergency type and severity."""
		for protocol in self._protocols.values():
			if protocol.emergency_type == emergency_type:
				if severity.value >= protocol.severity_threshold.value or severity == SeverityLevel.CRITICAL:
					return protocol
		return None

	def execute_protocol(self, protocol: EmergencyProtocol, alert: EmergencyAlert) -> ProtocolExecution:
		"""Execute an emergency protocol."""
		execution_id = f"{protocol.protocol_id}_{alert.alert_id}_{datetime.now().timestamp()}"
		execution = ProtocolExecution(
			execution_id=execution_id,
			protocol_id=protocol.protocol_id,
			alert_id=alert.alert_id,
			status=ProtocolStatus.ACTIVATED,
			started_at=datetime.now(timezone.utc),
			actions_completed=0,
			actions_total=len([a for a in protocol.actions if a.required]),
		)
		self._executions[execution_id] = execution
		return execution

	def mark_action_complete(self, execution_id: str) -> ProtocolExecution | None:
		"""Mark an action as complete in protocol execution."""
		if execution_id not in self._executions:
			return None

		execution = self._executions[execution_id]
		if execution.actions_completed < execution.actions_total:
			updated = ProtocolExecution(
				execution_id=execution.execution_id,
				protocol_id=execution.protocol_id,
				alert_id=execution.alert_id,
				status=ProtocolStatus.IN_PROGRESS if execution.actions_completed + 1 < execution.actions_total
				else ProtocolStatus.COMPLETED,
				started_at=execution.started_at,
				actions_completed=execution.actions_completed + 1,
				actions_total=execution.actions_total,
				escalation_reason=execution.escalation_reason,
			)
			self._executions[execution_id] = updated
			return updated
		return execution

	def escalate_protocol(self, execution_id: str, reason: str) -> ProtocolExecution | None:
		"""Escalate a protocol execution."""
		if execution_id not in self._executions:
			return None

		execution = self._executions[execution_id]
		updated = ProtocolExecution(
			execution_id=execution.execution_id,
			protocol_id=execution.protocol_id,
			alert_id=execution.alert_id,
			status=ProtocolStatus.ESCALATED,
			started_at=execution.started_at,
			actions_completed=execution.actions_completed,
			actions_total=execution.actions_total,
			escalation_reason=reason,
		)
		self._executions[execution_id] = updated
		return updated

	def get_active_executions(self) -> list[ProtocolExecution]:
		"""Get all active protocol executions."""
		return [e for e in self._executions.values() if e.status in (ProtocolStatus.ACTIVATED, ProtocolStatus.IN_PROGRESS)]


class EmergencyProtocolAgent(BaseWorkflow):
	"""Workflow for activating and managing emergency protocols."""

	workflow_id = "emergency_protocol"
	name = "Emergency Protocol"
	category = "additional"
	trust_level = TrustLevel.APPROVAL

	def __init__(
		self,
		service: EmergencyProtocolService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or EmergencyProtocolService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle emergency alert events."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Process emergency alert and select protocol."""
		payload = run.event.payload or {}

		alert_id = str(payload.get("alert_id", "alert_unknown"))
		emergency_type_str = str(payload.get("emergency_type", "unknown"))
		severity_str = str(payload.get("severity", "medium"))
		description = str(payload.get("description", "Unknown emergency"))

		try:
			emergency_type = EmergencyType(emergency_type_str)
		except ValueError:
			emergency_type = EmergencyType.UNKNOWN

		try:
			severity = SeverityLevel(severity_str)
		except ValueError:
			severity = SeverityLevel.MEDIUM

		alert = self.service.create_alert(alert_id, emergency_type, severity, description)
		protocol = self.service.get_protocol_for_emergency(emergency_type, severity)

		if protocol:
			execution = self.service.execute_protocol(protocol, alert)
		else:
			execution = None

		return ActionPlan(
			action_type="activate_emergency_protocol",
			confidence=0.95 if execution else 0.5,
			context={
				"alert_id": alert_id,
				"emergency_type": emergency_type.value,
				"severity": severity.value,
				"description": description,
				"protocol_found": protocol is not None,
				"protocol_id": protocol.protocol_id if protocol else "none",
				"protocol_name": protocol.name if protocol else "No matching protocol",
				"actions_required": len([a for a in protocol.actions if a.required]) if protocol else 0,
				"escalation_contacts": protocol.escalation_contacts if protocol else [],
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute emergency protocol activation."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})

		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)

		self.state_machine.transition("completed", {"reason": decision.reason})

		protocol_id = plan.context.get("protocol_id", "none")
		protocol_name = plan.context.get("protocol_name", "Unknown")
		alert_id = plan.context.get("alert_id", "unknown")

		if protocol_id != "none":
			summary = f"Emergency protocol '{protocol_name}' activated for alert {alert_id}"
		else:
			summary = f"No matching protocol found for alert {alert_id}; escalation required"

		return ActionResult(
			True,
			summary,
			{**plan.context, "policy": decision.reason},
		)
