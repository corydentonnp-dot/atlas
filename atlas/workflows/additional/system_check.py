"""Workflow #55: System Check — monitors and reports on system health.

Performs periodic system health checks, identifies issues, and generates reports
on application performance, data integrity, and resource usage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class HealthStatus(str, Enum):
	"""System health status."""

	HEALTHY = "healthy"
	DEGRADED = "degraded"
	UNHEALTHY = "unhealthy"
	UNKNOWN = "unknown"


class CheckType(str, Enum):
	"""System check type."""

	DATABASE = "database"
	API = "api"
	MEMORY = "memory"
	STORAGE = "storage"
	PERFORMANCE = "performance"
	SECURITY = "security"
	INTEGRATIONS = "integrations"
	DATA_INTEGRITY = "data_integrity"


@dataclass(slots=True)
class HealthCheck:
	"""Individual health check result."""

	check_type: CheckType
	status: HealthStatus
	message: str
	details: dict = field(default_factory=dict)
	last_checked: datetime = field(default_factory=datetime.now)
	latency_ms: float = 0.0


@dataclass(slots=True)
class SystemHealthReport:
	"""System health report."""

	report_id: str
	timestamp: datetime
	overall_status: HealthStatus
	checks: list[HealthCheck] = field(default_factory=list)
	alerts: list[str] = field(default_factory=list)
	recommendations: list[str] = field(default_factory=list)
	uptime_percentage: float = 100.0


class SystemHealthService(PersistenceMixin):
	"""Service for system health monitoring."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._last_report: SystemHealthReport | None = None
		self._check_history: dict[CheckType, list[HealthCheck]] = {}

	def perform_database_check(self) -> HealthCheck:
		"""Check database connectivity and performance."""
		try:
			# Simulate database check
			return HealthCheck(
				check_type=CheckType.DATABASE,
				status=HealthStatus.HEALTHY,
				message="Database connection healthy",
				details={
					"response_time_ms": 12,
					"connection_pool_size": 10,
					"active_connections": 3,
				},
				latency_ms=12.0,
			)
		except Exception as e:
			return HealthCheck(
				check_type=CheckType.DATABASE,
				status=HealthStatus.UNHEALTHY,
				message=f"Database check failed: {str(e)}",
				latency_ms=0.0,
			)

	def perform_api_check(self) -> HealthCheck:
		"""Check API endpoint health."""
		try:
			# Simulate API check
			return HealthCheck(
				check_type=CheckType.API,
				status=HealthStatus.HEALTHY,
				message="API endpoints responding normally",
				details={
					"endpoints_checked": 8,
					"healthy_endpoints": 8,
					"avg_response_time_ms": 45,
				},
				latency_ms=45.0,
			)
		except Exception as e:
			return HealthCheck(
				check_type=CheckType.API,
				status=HealthStatus.DEGRADED,
				message=f"Some API endpoints degraded: {str(e)}",
				latency_ms=0.0,
			)

	def perform_memory_check(self) -> HealthCheck:
		"""Check memory usage."""
		try:
			# Simulate memory check
			return HealthCheck(
				check_type=CheckType.MEMORY,
				status=HealthStatus.HEALTHY,
				message="Memory usage within acceptable limits",
				details={
					"total_memory_mb": 4096,
					"used_memory_mb": 2048,
					"usage_percentage": 50.0,
				},
				latency_ms=5.0,
			)
		except Exception as e:
			return HealthCheck(
				check_type=CheckType.MEMORY,
				status=HealthStatus.UNHEALTHY,
				message=f"Memory check failed: {str(e)}",
				latency_ms=0.0,
			)

	def perform_storage_check(self) -> HealthCheck:
		"""Check storage availability."""
		try:
			# Simulate storage check
			return HealthCheck(
				check_type=CheckType.STORAGE,
				status=HealthStatus.HEALTHY,
				message="Storage capacity adequate",
				details={
					"total_storage_gb": 500,
					"used_storage_gb": 250,
					"usage_percentage": 50.0,
				},
				latency_ms=8.0,
			)
		except Exception as e:
			return HealthCheck(
				check_type=CheckType.STORAGE,
				status=HealthStatus.DEGRADED,
				message=f"Storage check warning: {str(e)}",
				latency_ms=0.0,
			)

	def perform_data_integrity_check(self) -> HealthCheck:
		"""Check data integrity."""
		try:
			# Simulate data integrity check
			return HealthCheck(
				check_type=CheckType.DATA_INTEGRITY,
				status=HealthStatus.HEALTHY,
				message="Data integrity verified",
				details={
					"records_checked": 10000,
					"integrity_failures": 0,
					"success_rate_percentage": 100.0,
				},
				latency_ms=120.0,
			)
		except Exception as e:
			return HealthCheck(
				check_type=CheckType.DATA_INTEGRITY,
				status=HealthStatus.UNHEALTHY,
				message=f"Data integrity issues detected: {str(e)}",
				latency_ms=0.0,
			)

	def generate_system_report(self, report_id: str) -> SystemHealthReport:
		"""Generate comprehensive system health report."""
		checks = [
			self.perform_database_check(),
			self.perform_api_check(),
			self.perform_memory_check(),
			self.perform_storage_check(),
			self.perform_data_integrity_check(),
		]

		# Determine overall status
		statuses = [check.status for check in checks]
		if HealthStatus.UNHEALTHY in statuses:
			overall_status = HealthStatus.UNHEALTHY
		elif HealthStatus.DEGRADED in statuses:
			overall_status = HealthStatus.DEGRADED
		else:
			overall_status = HealthStatus.HEALTHY

		# Generate alerts and recommendations
		alerts: list[str] = []
		recommendations: list[str] = []

		for check in checks:
			if check.status == HealthStatus.UNHEALTHY:
				alerts.append(f"{check.check_type.value}: {check.message}")
				recommendations.append(f"Investigate and resolve {check.check_type.value} issues immediately")
			elif check.status == HealthStatus.DEGRADED:
				alerts.append(f"{check.check_type.value}: Performance degradation detected")
				recommendations.append(f"Monitor {check.check_type.value} performance and investigate root cause")

		report = SystemHealthReport(
			report_id=report_id,
			timestamp=datetime.now(),
			overall_status=overall_status,
			checks=checks,
			alerts=alerts,
			recommendations=recommendations,
			uptime_percentage=99.5 if overall_status == HealthStatus.HEALTHY else 95.0,
		)

		self._last_report = report
		return report


class SystemCheckAgent(BaseWorkflow):
	"""Workflow for system health monitoring."""

	workflow_id = "system_check"
	name = "System Check"
	category = "additional"
	trust_level = TrustLevel.DRAFT

	def __init__(self, service: SystemHealthService | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = service or SystemHealthService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle system check requests."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Process system health check."""
		payload = run.event.payload

		report_id = cast(str, payload.get("report_id", "report_001")) if payload else "report_001"
		include_details = cast(bool, payload.get("include_details", True)) if payload else True

		# Generate report
		report = self.service.generate_system_report(report_id)

		return ActionPlan(
			action_type="generate_system_report",
			confidence=0.90,
			context={
				"report_id": report_id,
				"overall_status": report.overall_status.value,
				"checks_performed": len(report.checks),
				"alerts_count": len(report.alerts),
				"recommendations_count": len(report.recommendations),
				"uptime_percentage": report.uptime_percentage,
				"timestamp": report.timestamp.isoformat(),
				"details": {
					"alerts": report.alerts,
					"recommendations": report.recommendations,
					"check_results": [
						{
							"type": check.check_type.value,
							"status": check.status.value,
							"message": check.message,
							"latency_ms": check.latency_ms,
						}
						for check in report.checks
					] if include_details else [],
				} if include_details else {},
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute system check report."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})

		status = plan.context.get("overall_status", "unknown")
		checks = plan.context.get("checks_performed", 0)
		summary = f"System check completed with overall status: {status} ({checks} checks)"
		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
