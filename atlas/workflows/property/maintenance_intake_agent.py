"""Workflow #26: Maintenance Intake Agent — intake, triage, and dispatch property maintenance requests.

This workflow manages the complete maintenance intake process from tenant request through
contractor assignment and dispatch. Features include urgency classification, contractor
matching, cost estimation, and approval-gated dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class UrgencyLevel(str, Enum):
	"""Maintenance urgency classification."""

	EMERGENCY = "emergency"  # Life/safety risk, occupant safety at risk
	URGENT = "urgent"  # Essential system failure, habitability impact
	ROUTINE = "routine"  # Normal wear and tear, non-critical
	COSMETIC = "cosmetic"  # Aesthetic only, can wait


class ContractorSpecialty(str, Enum):
	"""Contractor specializations for matching."""

	PLUMBING = "plumbing"
	ELECTRICAL = "electrical"
	HVAC = "hvac"
	GENERAL = "general"
	CARPENTRY = "carpentry"
	ROOFING = "roofing"


class JobStatus(str, Enum):
	"""Status of a dispatched maintenance job."""

	DISPATCHED = "dispatched"  # Contractor notified, awaiting confirmation
	IN_PROGRESS = "in_progress"  # Work has begun
	COMPLETED = "completed"  # Work finished
	CANCELLED = "cancelled"  # Job cancelled before completion
	NO_SHOW = "no_show"  # Contractor did not arrive


@dataclass(slots=True)
class Contractor:
	"""Active contractor for assignment."""

	contractor_id: str
	name: str
	specialties: set[ContractorSpecialty] = field(default_factory=set)
	available: bool = True
	avg_response_hours: int = 24
	cost_per_hour: float = 75.0
	rating: float = 4.5  # 1-5 stars


@dataclass(slots=True)
class MaintenanceRequest:
	"""Maintenance request with full intake details."""

	request_id: str
	tenant: str
	property_name: str
	unit: str
	description: str
	urgency: UrgencyLevel
	detected_issues: set[str] = field(default_factory=set)
	photos: list[str] = field(default_factory=list)
	created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
	estimated_hours: float = 2.0
	cost_estimate: float = 150.0


@dataclass(frozen=True, slots=True)
class DispatchPlan:
	"""Plan for dispatching a maintenance request."""

	contractor_id: str
	contractor_name: str
	specialty: ContractorSpecialty
	estimated_cost: float
	estimated_arrival_hours: int
	reason_for_selection: str
	requires_approval: bool


@dataclass(slots=True)
class DispatchRecord:
	"""Full record of a dispatched job with history."""

	dispatch_id: str
	request_id: str
	contractor_id: str
	contractor_name: str
	status: JobStatus = JobStatus.DISPATCHED
	dispatched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
	started_at: datetime | None = None
	completed_at: datetime | None = None
	actual_cost: float | None = None
	actual_hours: float | None = None
	notes: str | None = None
	status_history: list[tuple[JobStatus, datetime]] = field(default_factory=list)  # Status change log


class MaintenanceIntakeService(PersistenceMixin):
	"""Service for managing maintenance requests and contractor matching."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._requests: dict[str, MaintenanceRequest] = {}
		self._contractors: dict[str, Contractor] = {}
		self._dispatch_queue: dict[str, DispatchPlan] = {}
		self._dispatch_records: dict[str, DispatchRecord] = {}  # dispatch_id -> record
		self._request_dispatch_map: dict[str, str] = {}  # request_id -> dispatch_id
		self._issue_keywords = {
			"leak": UrgencyLevel.EMERGENCY,
			"flood": UrgencyLevel.EMERGENCY,
			"gas": UrgencyLevel.EMERGENCY,
			"fire": UrgencyLevel.EMERGENCY,
			"no heat": UrgencyLevel.EMERGENCY,
			"smoke": UrgencyLevel.EMERGENCY,
			"broken": UrgencyLevel.URGENT,
			"stopped": UrgencyLevel.URGENT,
			"clog": UrgencyLevel.URGENT,
			"not working": UrgencyLevel.URGENT,
			"no water": UrgencyLevel.URGENT,
			"paint": UrgencyLevel.COSMETIC,
			"scratch": UrgencyLevel.COSMETIC,
			"cosmetic": UrgencyLevel.COSMETIC,
			"upgrade": UrgencyLevel.COSMETIC,
		}

	def add_contractor(self, contractor: Contractor) -> Contractor:
		"""Register an available contractor."""
		self._contractors[contractor.contractor_id] = contractor
		return contractor

	def classify_urgency(self, description: str) -> tuple[UrgencyLevel, set[str]]:
		"""Classify urgency and detect specific issues."""
		text = description.lower()
		detected_issues = set()
		max_urgency = UrgencyLevel.COSMETIC
		
		# Define urgency ranking (higher number = more urgent)
		urgency_rank = {
			UrgencyLevel.COSMETIC: 0,
			UrgencyLevel.ROUTINE: 1,
			UrgencyLevel.URGENT: 2,
			UrgencyLevel.EMERGENCY: 3,
		}

		for keyword, urgency in self._issue_keywords.items():
			if keyword in text:
				detected_issues.add(keyword)
				# Update max_urgency if this keyword indicates higher urgency
				if urgency_rank.get(urgency, 0) > urgency_rank.get(max_urgency, 0):
					max_urgency = urgency

		# Default to ROUTINE if no keywords matched
		if not detected_issues:
			max_urgency = UrgencyLevel.ROUTINE

		return max_urgency, detected_issues

	def estimate_cost(self, urgency: UrgencyLevel, detected_issues: set[str]) -> tuple[float, float]:
		"""Estimate hours and cost based on urgency and issues."""
		base_hours = {
			UrgencyLevel.EMERGENCY: 3.0,
			UrgencyLevel.URGENT: 2.0,
			UrgencyLevel.ROUTINE: 1.5,
			UrgencyLevel.COSMETIC: 1.0,
		}

		base_cost = {
			UrgencyLevel.EMERGENCY: 300.0,
			UrgencyLevel.URGENT: 200.0,
			UrgencyLevel.ROUTINE: 100.0,
			UrgencyLevel.COSMETIC: 75.0,
		}

		hours = base_hours.get(urgency, 1.5)
		cost = base_cost.get(urgency, 100.0)

		# Add complexity fee for multiple issues
		if len(detected_issues) > 2:
			cost += 50.0
			hours += 0.5

		return hours, cost

	def intake(self, payload: dict[str, object]) -> MaintenanceRequest:
		"""Process a new maintenance request."""
		description = str(payload["description"])
		urgency, issues = self.classify_urgency(description)
		hours, cost = self.estimate_cost(urgency, issues)

		request = MaintenanceRequest(
			request_id=str(payload["request_id"]),
			tenant=str(payload["tenant"]),
			property_name=str(payload["property_name"]),
			unit=str(payload.get("unit", "unknown")),
			description=description,
			urgency=urgency,
			detected_issues=issues,
			photos=[str(item) for item in payload.get("photos", [])] if isinstance(payload.get("photos", []), list) else [],
			estimated_hours=hours,
			cost_estimate=cost,
		)

		self._requests[request.request_id] = request
		return request

	def find_best_contractor(self, request: MaintenanceRequest) -> Contractor | None:
		"""Find the best available contractor for this request."""
		available = [c for c in self._contractors.values() if c.available]

		if not available:
			return None

		# For emergency, prioritize whoever is available (lowest response time)
		if request.urgency == UrgencyLevel.EMERGENCY:
			return min(available, key=lambda c: c.avg_response_hours)

		# For others, prefer highest-rated
		return max(available, key=lambda c: c.rating)

	def generate_dispatch_plan(self, request: MaintenanceRequest, contractor: Contractor) -> DispatchPlan:
		"""Generate a dispatch plan for approval."""

		# Assign specialty based on issues
		specialty = ContractorSpecialty.GENERAL
		if "plumb" in request.description.lower() or "leak" in request.description.lower():
			specialty = ContractorSpecialty.PLUMBING
		elif "electric" in request.description.lower():
			specialty = ContractorSpecialty.ELECTRICAL
		elif any(k in request.description.lower() for k in ["hvac", "heat", "cool", "ac"]):
			specialty = ContractorSpecialty.HVAC

		# Determine if approval needed (emergency can dispatch immediately at draft)
		requires_approval = request.urgency not in (UrgencyLevel.EMERGENCY, UrgencyLevel.COSMETIC)

		reason = f"Emergency response needed" if request.urgency == UrgencyLevel.EMERGENCY else f"Matched {contractor.name} based on urgency {request.urgency.value}"

		return DispatchPlan(
			contractor_id=contractor.contractor_id,
			contractor_name=contractor.name,
			specialty=specialty,
			estimated_cost=request.cost_estimate,
			estimated_arrival_hours=contractor.avg_response_hours,
			reason_for_selection=reason,
			requires_approval=requires_approval,
		)

	def queue_dispatch(self, request_id: str, plan: DispatchPlan) -> str:
		"""Queue a dispatch plan for execution and return dispatch_id."""
		dispatch_id = f"{request_id}_dispatch_{datetime.now(timezone.utc).timestamp()}"
		self._dispatch_queue[request_id] = plan
		
		# Create dispatch record
		record = DispatchRecord(
			dispatch_id=dispatch_id,
			request_id=request_id,
			contractor_id=plan.contractor_id,
			contractor_name=plan.contractor_name,
		)
		record.status_history.append((record.status, record.dispatched_at))
		
		self._dispatch_records[dispatch_id] = record
		self._request_dispatch_map[request_id] = dispatch_id
		
		return dispatch_id

	def get_pending_jobs(self) -> list[DispatchRecord]:
		"""Get all pending (dispatched or in-progress) jobs."""
		pending = [
			r for r in self._dispatch_records.values() 
			if r.status in (JobStatus.DISPATCHED, JobStatus.IN_PROGRESS)
		]
		return sorted(pending, key=lambda r: r.dispatched_at)

	def get_job_history(self, request_id: str) -> list[DispatchRecord]:
		"""Get all dispatch records for a specific request."""
		dispatch_id = self._request_dispatch_map.get(request_id)
		if not dispatch_id:
			return []
		
		record = self._dispatch_records.get(dispatch_id)
		return [record] if record else []

	def update_job_status(self, dispatch_id: str, new_status: JobStatus, notes: str | None = None) -> bool:
		"""Update the status of a dispatched job."""
		if dispatch_id not in self._dispatch_records:
			return False
		
		record = self._dispatch_records[dispatch_id]
		old_status = record.status
		
		# Update status
		record.status = new_status
		now = datetime.now(timezone.utc)
		record.status_history.append((new_status, now))
		
		# Update timestamps based on new status
		if new_status == JobStatus.IN_PROGRESS and not record.started_at:
			record.started_at = now
		elif new_status == JobStatus.COMPLETED and not record.completed_at:
			record.completed_at = now
		
		# Add notes if provided
		if notes:
			record.notes = notes
		
		return True

	def get_dispatch_record(self, dispatch_id: str) -> DispatchRecord | None:
		"""Get details of a specific dispatch."""
		return self._dispatch_records.get(dispatch_id)


class MaintenanceIntakeWorkflow(BaseWorkflow):
	"""Workflow for intake, triage, and dispatch of maintenance requests."""

	workflow_id = "maintenance_intake"
	name = "Maintenance Intake Agent"
	category = "property"
	trust_level = TrustLevel.DRAFT

	def __init__(
		self,
		service: MaintenanceIntakeService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or MaintenanceIntakeService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Intake a new maintenance request."""
		self.state_machine.transition("planning", {"event_type": event.event_type})

		if event.event_type == "maintenance_request":
			self.service.intake(event.payload)

		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Analyze request and find contractor match."""
		request_id = str(run.event.payload.get("request_id", ""))
		request = self.service._requests.get(request_id)

		if not request:
			return ActionPlan(
				action_type="intake_failed",
				confidence=0.0,
				context={"request_id": request_id, "reason": "Request not found"},
			)

		contractor = self.service.find_best_contractor(request)

		if not contractor:
			return ActionPlan(
				action_type="no_contractor_available",
				confidence=0.5,
				context={
					"request_id": request_id,
					"urgency": request.urgency.value,
					"reason": "No available contractors",
				},
			)

		plan = self.service.generate_dispatch_plan(request, contractor)

		# Confidence based on urgency and availability
		confidence = {
			UrgencyLevel.EMERGENCY: 0.95,
			UrgencyLevel.URGENT: 0.85,
			UrgencyLevel.ROUTINE: 0.75,
			UrgencyLevel.COSMETIC: 0.60,
		}.get(request.urgency, 0.70)

		return ActionPlan(
			action_type="dispatch_to_contractor",
			confidence=confidence,
			context={
				"request_id": request_id,
				"contractor_id": contractor.contractor_id,
				"contractor_name": contractor.name,
				"urgency": request.urgency.value,
				"estimated_cost": request.cost_estimate,
				"estimated_hours": request.estimated_hours,
				"issues": list(request.detected_issues),
				"dispatch_plan": {
					"contractor_id": plan.contractor_id,
					"specialty": plan.specialty.value,
					"estimated_cost": plan.estimated_cost,
					"estimated_arrival_hours": plan.estimated_arrival_hours,
					"requires_approval": plan.requires_approval,
				},
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute dispatch with policy gating."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})

		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)

		if not decision.allowed:
			self.state_machine.transition("failed", {"reason": decision.reason})
			return ActionResult(False, decision.reason, plan.context)

		# Queue the dispatch
		request_id = str(plan.context.get("request_id", ""))
		dispatch_id = None
		if request_id in self.service._requests:
			# Create DispatchPlan object and queue it
			specialty_str = plan.context.get("dispatch_plan", {}).get("specialty", "general")
			try:
				specialty = ContractorSpecialty[specialty_str.upper()]
			except (KeyError, AttributeError):
				specialty = ContractorSpecialty.GENERAL
			
			dispatch_plan = DispatchPlan(
				contractor_id=plan.context.get("contractor_id", ""),
				contractor_name=plan.context.get("contractor_name", ""),
				specialty=specialty,
				estimated_cost=plan.context.get("estimated_cost", 0.0),
				estimated_arrival_hours=plan.context.get("dispatch_plan", {}).get("estimated_arrival_hours", 24),
				reason_for_selection=plan.context.get("dispatch_plan", {}).get("reason", ""),
				requires_approval=plan.context.get("dispatch_plan", {}).get("requires_approval", False),
			)
			dispatch_id = self.service.queue_dispatch(request_id, dispatch_plan)

		self.state_machine.transition("completed", {"reason": decision.reason})

		return ActionResult(
			True,
			f"Maintenance request {request_id} dispatched to {plan.context.get('contractor_name')}",
			{**plan.context, "policy_decision": decision.reason, "dispatch_id": dispatch_id},
		)
