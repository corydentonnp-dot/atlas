"""Workflow #105: System Health Monitor.

Monitors Atlas platform health across key subsystems and produces an actionable snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class ComponentStatus(str, Enum):
	"""Status for an observed system component."""

	HEALTHY = "healthy"
	DEGRADED = "degraded"
	UNHEALTHY = "unhealthy"


@dataclass(slots=True)
class ComponentHealth:
	"""Health information for one monitored component."""

	component: str
	status: ComponentStatus
	latency_ms: float = 0.0
	error_rate: float = 0.0
	last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
	note: str = ""


@dataclass(slots=True)
class HealthIncident:
	"""Raised incident when unhealthy components are present."""

	incident_id: str
	created_at: datetime
	severity: str
	affected_components: list[str]
	description: str


@dataclass(slots=True)
class HealthSnapshot:
	"""Overall health snapshot used for notifications and audit."""

	snapshot_id: str
	timestamp: datetime
	overall_status: ComponentStatus
	components: list[ComponentHealth]
	incident: HealthIncident | None = None


class SystemHealthMonitorService(PersistenceMixin):
	"""Service for collecting component health and generating snapshots."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._components: dict[str, ComponentHealth] = {}
		self._incidents: dict[str, HealthIncident] = {}

	def register_component(self, component_health: ComponentHealth) -> ComponentHealth:
		"""Insert or update a component health record."""
		self._components[component_health.component] = component_health
		return component_health

	def evaluate_overall_status(self) -> ComponentStatus:
		"""Determine overall health from component statuses."""
		statuses = [component.status for component in self._components.values()]
		if not statuses:
			return ComponentStatus.HEALTHY
		if ComponentStatus.UNHEALTHY in statuses:
			return ComponentStatus.UNHEALTHY
		if ComponentStatus.DEGRADED in statuses:
			return ComponentStatus.DEGRADED
		return ComponentStatus.HEALTHY

	def get_unhealthy_components(self) -> list[ComponentHealth]:
		"""Return components that are degraded or unhealthy."""
		return [
			component
			for component in self._components.values()
			if component.status in {ComponentStatus.DEGRADED, ComponentStatus.UNHEALTHY}
		]

	def create_incident_if_needed(self) -> HealthIncident | None:
		"""Create an incident when at least one component is unhealthy."""
		affected = [
			component.component
			for component in self._components.values()
			if component.status == ComponentStatus.UNHEALTHY
		]
		if not affected:
			return None

		incident = HealthIncident(
			incident_id=f"incident_{datetime.now(timezone.utc).timestamp()}",
			created_at=datetime.now(timezone.utc),
			severity="critical" if len(affected) > 1 else "high",
			affected_components=affected,
			description=f"Detected unhealthy components: {', '.join(affected)}",
		)
		self._incidents[incident.incident_id] = incident
		return incident

	def generate_snapshot(self, snapshot_id: str) -> HealthSnapshot:
		"""Generate a full health snapshot and optional incident."""
		incident = self.create_incident_if_needed()
		return HealthSnapshot(
			snapshot_id=snapshot_id,
			timestamp=datetime.now(timezone.utc),
			overall_status=self.evaluate_overall_status(),
			components=list(self._components.values()),
			incident=incident,
		)


class SystemHealthMonitorWorkflow(BaseWorkflow):
	"""Workflow for system health monitoring."""

	workflow_id = "system_health_monitor"
	name = "System Health Monitor"
	category = "additional"
	trust_level = TrustLevel.AUTO

	def __init__(
		self,
		service: SystemHealthMonitorService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or SystemHealthMonitorService(session=session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Initialize a monitoring run."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Process monitoring payload and create snapshot context."""
		payload = run.event.payload
		snapshot_id = cast(str, payload.get("snapshot_id", "snapshot_001"))
		components = cast(list[dict[str, object]], payload.get("components", []))

		for component in components:
			status_value = cast(str, component.get("status", ComponentStatus.HEALTHY.value))
			status = ComponentStatus(status_value)
			self.service.register_component(
				ComponentHealth(
					component=cast(str, component.get("name", "unknown")),
					status=status,
					latency_ms=float(component.get("latency_ms", 0.0)),
					error_rate=float(component.get("error_rate", 0.0)),
					note=cast(str, component.get("note", "")),
				)
			)

		snapshot = self.service.generate_snapshot(snapshot_id=snapshot_id)
		return ActionPlan(
			action_type="publish_system_health_snapshot",
			confidence=0.94,
			context={
				"snapshot_id": snapshot.snapshot_id,
				"overall_status": snapshot.overall_status.value,
				"component_count": len(snapshot.components),
				"unhealthy_count": len(self.service.get_unhealthy_components()),
				"incident_id": snapshot.incident.incident_id if snapshot.incident else "",
				"incident_severity": snapshot.incident.severity if snapshot.incident else "",
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Evaluate policy and publish final summary."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})

		summary = (
			f"System health snapshot {plan.context.get('snapshot_id')} "
			f"status={plan.context.get('overall_status')} "
			f"components={plan.context.get('component_count')}"
		)
		return ActionResult(
			success=True,
			summary=summary,
			metadata={**plan.context, "policy": decision.reason},
		)
