"""Workflow #101: Daily Briefing Agent.

Compiles a morning briefing with calendar events, tasks, deadlines, and alerts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class TaskPriority(str, Enum):
	"""Priority for briefing tasks."""

	LOW = "low"
	MEDIUM = "medium"
	HIGH = "high"
	CRITICAL = "critical"


@dataclass(slots=True)
class CalendarEvent:
	"""Calendar event included in a briefing."""

	event_id: str
	title: str
	start_at: datetime
	location: str = ""
	notes: str = ""


@dataclass(slots=True)
class TaskItem:
	"""Task included in a briefing."""

	task_id: str
	title: str
	due_date: date
	priority: TaskPriority = TaskPriority.MEDIUM
	completed: bool = False


@dataclass(slots=True)
class DeadlineItem:
	"""Deadline item included in a briefing."""

	item_id: str
	label: str
	due_date: date
	category: str


@dataclass(slots=True)
class DailyBriefing:
	"""Compiled daily briefing output."""

	briefing_id: str
	briefing_date: date
	user_id: str
	top_tasks: list[TaskItem] = field(default_factory=list)
	todays_events: list[CalendarEvent] = field(default_factory=list)
	upcoming_deadlines: list[DeadlineItem] = field(default_factory=list)
	alerts: list[str] = field(default_factory=list)
	weather_summary: str = ""
	generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class DailyBriefingService(PersistenceMixin):
	"""Service for assembling daily briefings."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._tasks: dict[str, TaskItem] = {}
		self._events: dict[str, CalendarEvent] = {}
		self._deadlines: dict[str, DeadlineItem] = {}
		self._alerts: list[str] = []
		self._weather_by_date: dict[date, str] = {}

	def add_task(self, task: TaskItem) -> TaskItem:
		"""Add or replace a task item."""
		self._tasks[task.task_id] = task
		return task

	def add_event(self, event: CalendarEvent) -> CalendarEvent:
		"""Add or replace a calendar event."""
		self._events[event.event_id] = event
		return event

	def add_deadline(self, deadline: DeadlineItem) -> DeadlineItem:
		"""Add or replace a deadline item."""
		self._deadlines[deadline.item_id] = deadline
		return deadline

	def add_alert(self, alert: str) -> None:
		"""Append a briefing alert message."""
		if alert.strip():
			self._alerts.append(alert.strip())

	def set_weather(self, on_date: date, summary: str) -> None:
		"""Set weather summary for a date."""
		self._weather_by_date[on_date] = summary.strip()

	def _priority_rank(self, priority: TaskPriority) -> int:
		rank = {
			TaskPriority.CRITICAL: 3,
			TaskPriority.HIGH: 2,
			TaskPriority.MEDIUM: 1,
			TaskPriority.LOW: 0,
		}
		return rank.get(priority, 0)

	def get_top_tasks(self, today: date, limit: int = 5) -> list[TaskItem]:
		"""Get top uncompleted tasks by urgency and priority."""
		candidates = [task for task in self._tasks.values() if not task.completed]
		candidates.sort(
			key=lambda task: (
				(task.due_date - today).days,
				-self._priority_rank(task.priority),
				task.title.lower(),
			)
		)
		return candidates[:limit]

	def get_todays_events(self, today: date) -> list[CalendarEvent]:
		"""Return events scheduled for the specified date."""
		events = [event for event in self._events.values() if event.start_at.date() == today]
		events.sort(key=lambda event: event.start_at)
		return events

	def get_upcoming_deadlines(self, today: date, days_ahead: int = 14) -> list[DeadlineItem]:
		"""Return deadlines due within the specified range."""
		items: list[DeadlineItem] = []
		for item in self._deadlines.values():
			days_remaining = (item.due_date - today).days
			if 0 <= days_remaining <= days_ahead:
				items.append(item)
		items.sort(key=lambda item: item.due_date)
		return items

	def generate_briefing(self, briefing_date: date, user_id: str) -> DailyBriefing:
		"""Compile a daily briefing snapshot."""
		return DailyBriefing(
			briefing_id=f"briefing_{user_id}_{briefing_date.isoformat()}",
			briefing_date=briefing_date,
			user_id=user_id,
			top_tasks=self.get_top_tasks(briefing_date),
			todays_events=self.get_todays_events(briefing_date),
			upcoming_deadlines=self.get_upcoming_deadlines(briefing_date),
			alerts=list(self._alerts),
			weather_summary=self._weather_by_date.get(briefing_date, "No weather summary available."),
		)


class DailyBriefingAgent(BaseWorkflow):
	"""Workflow for compiling and delivering daily briefings."""

	workflow_id = "daily_briefing"
	name = "Daily Briefing Agent"
	category = "additional"
	trust_level = TrustLevel.AUTO

	def __init__(
		self,
		service: DailyBriefingService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or DailyBriefingService(session=session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Initialize a briefing run."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Compile briefing context for action execution."""
		payload = run.event.payload
		today = date.fromisoformat(cast(str, payload.get("today", date.today().isoformat())))
		user_id = cast(str, payload.get("user_id", "default_user"))
		include_weather = cast(bool, payload.get("include_weather", True))

		briefing = self.service.generate_briefing(briefing_date=today, user_id=user_id)
		if not include_weather:
			briefing.weather_summary = ""

		return ActionPlan(
			action_type="publish_daily_briefing",
			confidence=0.92,
			context={
				"briefing_id": briefing.briefing_id,
				"user_id": briefing.user_id,
				"date": briefing.briefing_date.isoformat(),
				"task_count": len(briefing.top_tasks),
				"event_count": len(briefing.todays_events),
				"deadline_count": len(briefing.upcoming_deadlines),
				"alerts_count": len(briefing.alerts),
				"weather": briefing.weather_summary,
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Evaluate policy and produce final briefing summary."""
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
			f"Daily briefing ready for {plan.context.get('user_id')} "
			f"with {plan.context.get('task_count', 0)} tasks, "
			f"{plan.context.get('event_count', 0)} events, and "
			f"{plan.context.get('deadline_count', 0)} deadlines."
		)
		return ActionResult(
			success=True,
			summary=summary,
			metadata={**plan.context, "policy": decision.reason},
		)
