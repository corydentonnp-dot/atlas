"""Workflow #54: Event Coordination — organizes multi-party event logistics.

Manages coordination of events with multiple stakeholders, handles scheduling,
venue coordination, and attendance tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import Enum
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class EventStatus(str, Enum):
	"""Event status."""

	PLANNING = "planning"
	CONFIRMED = "confirmed"
	CANCELLED = "cancelled"
	COMPLETED = "completed"


class AttendeeStatus(str, Enum):
	"""Attendee response status."""

	INVITED = "invited"
	ACCEPTED = "accepted"
	DECLINED = "declined"
	MAYBE = "maybe"


@dataclass(slots=True)
class Attendee:
	"""Event attendee."""

	attendee_id: str
	name: str
	email: str
	status: AttendeeStatus = AttendeeStatus.INVITED
	dietary_restrictions: str = ""
	plus_one: bool = False


@dataclass(slots=True)
class Venue:
	"""Event venue information."""

	venue_id: str
	name: str
	address: str
	capacity: int
	parking_available: bool
	accessible: bool
	booking_confirmed: bool = False
	cost: float = 0.0


@dataclass(slots=True)
class Event:
	"""Coordinated event."""

	event_id: str
	name: str
	date: date
	start_time: time
	end_time: time
	description: str
	organizer_id: str
	status: EventStatus = EventStatus.PLANNING
	venue: Venue | None = None
	attendees: list[Attendee] = field(default_factory=list)
	budget: float = 0.0
	notes: str = ""


class EventCoordinationService(PersistenceMixin):
	"""Service for event coordination."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._events: dict[str, Event] = {}
		self._venues: dict[str, Venue] = {}
		self._initialize_default_venues()

	def _initialize_default_venues(self) -> None:
		"""Initialize default venue options."""
		venues = [
			Venue(
				venue_id="ballroom-downtown",
				name="Downtown Ballroom",
				address="123 Main St, Downtown",
				capacity=200,
				parking_available=True,
				accessible=True,
				cost=500.0,
			),
			Venue(
				venue_id="garden-park",
				name="Garden Park Pavilion",
				address="456 Park Ave, Riverside",
				capacity=100,
				parking_available=True,
				accessible=False,
				cost=200.0,
			),
			Venue(
				venue_id="conference-center",
				name="Convention Center",
				address="789 Business Blvd",
				capacity=500,
				parking_available=True,
				accessible=True,
				cost=800.0,
			),
		]

		for venue in venues:
			self._venues[venue.venue_id] = venue

	def create_event(
		self,
		event_id: str,
		name: str,
		date: date,
		start_time: time,
		end_time: time,
		description: str,
		organizer_id: str,
		budget: float = 1000.0,
	) -> Event:
		"""Create a new event."""
		event = Event(
			event_id=event_id,
			name=name,
			date=date,
			start_time=start_time,
			end_time=end_time,
			description=description,
			organizer_id=organizer_id,
			budget=budget,
		)
		self._events[event_id] = event
		return event

	def add_attendee(self, event_id: str, attendee: Attendee) -> bool:
		"""Add attendee to event."""
		if event_id not in self._events:
			return False
		self._events[event_id].attendees.append(attendee)
		return True

	def update_attendee_status(self, event_id: str, attendee_id: str, status: AttendeeStatus) -> bool:
		"""Update attendee response status."""
		if event_id not in self._events:
			return False
		for attendee in self._events[event_id].attendees:
			if attendee.attendee_id == attendee_id:
				attendee.status = status
				return True
		return False

	def assign_venue(self, event_id: str, venue_id: str) -> bool:
		"""Assign venue to event."""
		if event_id not in self._events or venue_id not in self._venues:
			return False
		self._events[event_id].venue = self._venues[venue_id]
		return True

	def get_attendance_status(self, event_id: str) -> dict:
		"""Get attendance summary."""
		if event_id not in self._events:
			return {}

		event = self._events[event_id]
		accepted = sum(1 for a in event.attendees if a.status == AttendeeStatus.ACCEPTED)
		declined = sum(1 for a in event.attendees if a.status == AttendeeStatus.DECLINED)
		maybe = sum(1 for a in event.attendees if a.status == AttendeeStatus.MAYBE)
		pending = sum(1 for a in event.attendees if a.status == AttendeeStatus.INVITED)

		return {
			"event_id": event_id,
			"total_invited": len(event.attendees),
			"accepted": accepted,
			"declined": declined,
			"maybe": maybe,
			"pending_response": pending,
			"expected_attendance": accepted + int(maybe * 0.5),
		}


class EventCoordinationAgent(BaseWorkflow):
	"""Workflow for event coordination."""

	workflow_id = "event_coordination"
	name = "Event Coordination"
	category = "additional"
	trust_level = TrustLevel.DRAFT

	def __init__(self, service: EventCoordinationService | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = service or EventCoordinationService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle event coordination requests."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Process event coordination."""
		payload = run.event.payload

		event_id = cast(str, payload.get("event_id", "event_001")) if payload else "event_001"
		event_name = cast(str, payload.get("event_name", "Event")) if payload else "Event"
		attendee_count = int(cast(int, payload.get("attendee_count", 50)) or 50) if payload else 50
		venue_required = cast(bool, payload.get("venue_required", True)) if payload else True

		# Get attendance if event exists
		if event_id in self.service._events:
			attendance = self.service.get_attendance_status(event_id)
		else:
			attendance = {"total_invited": attendee_count, "expected_attendance": int(attendee_count * 0.8)}

		return ActionPlan(
			action_type="coordinate_event",
			confidence=0.80,
			context={
				"event_id": event_id,
				"event_name": event_name,
				"attendee_count": attendee_count,
				"venue_required": venue_required,
				"attendance_status": attendance,
				"available_venues": list(self.service._venues.keys()),
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute event coordination."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})

		event_name = plan.context.get("event_name", "Event")
		attendees = plan.context.get("attendee_count", 0)
		summary = f"Coordinated {event_name} with {attendees} attendees"
		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
