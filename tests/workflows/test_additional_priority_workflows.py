"""Tests for Phase 4 additional priority workflows.

Covers Daily Briefing (#101), Weekly Review (#102), and System Health Monitor (#105).
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from atlas.core.workflow.base import WorkflowEvent
from atlas.workflows.additional.daily_briefing_agent import (
	CalendarEvent,
	DailyBriefingAgent,
	DailyBriefingService,
	DeadlineItem,
	TaskItem,
	TaskPriority,
)
from atlas.workflows.additional.system_health_monitor import (
	ComponentHealth,
	ComponentStatus,
	SystemHealthMonitorService,
	SystemHealthMonitorWorkflow,
)
from atlas.workflows.additional.weekly_review_agent import (
	ReviewPriority,
	WeeklyItem,
	WeeklyReviewAgent,
	WeeklyReviewService,
)


class TestDailyBriefingService:
	"""Tests for DailyBriefingService."""

	def test_add_task_and_get_top_tasks(self) -> None:
		service = DailyBriefingService()
		today = date.today()
		service.add_task(TaskItem("t1", "Low later", today + timedelta(days=5), TaskPriority.LOW))
		service.add_task(TaskItem("t2", "Critical today", today, TaskPriority.CRITICAL))
		service.add_task(TaskItem("t3", "High tomorrow", today + timedelta(days=1), TaskPriority.HIGH))

		top_tasks = service.get_top_tasks(today=today)
		assert len(top_tasks) == 3
		assert top_tasks[0].task_id == "t2"

	def test_get_todays_events_sorted(self) -> None:
		service = DailyBriefingService()
		today = date.today()
		service.add_event(
			CalendarEvent(
				event_id="e1",
				title="Later",
				start_at=datetime.combine(today, datetime.min.time()).replace(hour=14, tzinfo=timezone.utc),
			)
		)
		service.add_event(
			CalendarEvent(
				event_id="e2",
				title="Earlier",
				start_at=datetime.combine(today, datetime.min.time()).replace(hour=9, tzinfo=timezone.utc),
			)
		)

		events = service.get_todays_events(today=today)
		assert [event.event_id for event in events] == ["e2", "e1"]

	def test_generate_briefing_contains_sections(self) -> None:
		service = DailyBriefingService()
		today = date.today()
		service.add_task(TaskItem("t1", "Submit docs", today, TaskPriority.HIGH))
		service.add_deadline(DeadlineItem("d1", "Tax filing", today + timedelta(days=7), "tax_legal"))
		service.add_alert("Budget overage detected")
		service.set_weather(today, "Sunny, high 72F")

		briefing = service.generate_briefing(briefing_date=today, user_id="user1")
		assert briefing.user_id == "user1"
		assert len(briefing.top_tasks) == 1
		assert len(briefing.upcoming_deadlines) == 1
		assert briefing.alerts == ["Budget overage detected"]
		assert briefing.weather_summary == "Sunny, high 72F"


@pytest.mark.asyncio
class TestDailyBriefingWorkflow:
	"""Tests for DailyBriefingAgent."""

	async def test_workflow_instantiates(self) -> None:
		workflow = DailyBriefingAgent(session=None)
		assert workflow.workflow_id == "daily_briefing"
		assert workflow.service is not None

	async def test_process_and_act(self) -> None:
		workflow = DailyBriefingAgent()
		today = date.today()
		workflow.service.add_task(TaskItem("t1", "Review leases", today, TaskPriority.HIGH))

		event = WorkflowEvent(
			event_type="daily_briefing.generate",
			payload={"today": today.isoformat(), "user_id": "user42", "include_weather": False},
		)
		run = await workflow.trigger(event)
		plan = await workflow.process(run)
		result = await workflow.act(plan)

		assert plan.action_type == "publish_daily_briefing"
		assert plan.context["task_count"] == 1
		assert result.success
		assert "user42" in result.summary


class TestSystemHealthMonitorService:
	"""Tests for SystemHealthMonitorService."""

	def test_overall_status_healthy_when_empty(self) -> None:
		service = SystemHealthMonitorService()
		assert service.evaluate_overall_status() == ComponentStatus.HEALTHY

	def test_overall_status_degraded(self) -> None:
		service = SystemHealthMonitorService()
		service.register_component(ComponentHealth("api", ComponentStatus.DEGRADED, latency_ms=220.0))
		assert service.evaluate_overall_status() == ComponentStatus.DEGRADED

	def test_incident_created_for_unhealthy_component(self) -> None:
		service = SystemHealthMonitorService()
		service.register_component(ComponentHealth("database", ComponentStatus.UNHEALTHY, latency_ms=0.0))

		incident = service.create_incident_if_needed()
		assert incident is not None
		assert incident.severity == "high"
		assert "database" in incident.affected_components

	def test_generate_snapshot_includes_incident(self) -> None:
		service = SystemHealthMonitorService()
		service.register_component(ComponentHealth("queue", ComponentStatus.UNHEALTHY))
		snapshot = service.generate_snapshot("snap_1")

		assert snapshot.snapshot_id == "snap_1"
		assert snapshot.overall_status == ComponentStatus.UNHEALTHY
		assert snapshot.incident is not None


@pytest.mark.asyncio
class TestSystemHealthMonitorWorkflow:
	"""Tests for SystemHealthMonitorWorkflow."""

	async def test_workflow_instantiates(self) -> None:
		workflow = SystemHealthMonitorWorkflow(session=None)
		assert workflow.workflow_id == "system_health_monitor"
		assert workflow.service is not None

	async def test_process_and_act(self) -> None:
		workflow = SystemHealthMonitorWorkflow()
		event = WorkflowEvent(
			event_type="system_health.scan",
			payload={
				"snapshot_id": "snap_42",
				"components": [
					{"name": "api", "status": "healthy", "latency_ms": 45.0, "error_rate": 0.0},
					{"name": "database", "status": "unhealthy", "latency_ms": 0.0, "error_rate": 1.0},
				],
			},
		)
		run = await workflow.trigger(event)
		plan = await workflow.process(run)
		result = await workflow.act(plan)

		assert plan.action_type == "publish_system_health_snapshot"
		assert plan.context["overall_status"] == "unhealthy"
		unhealthy_count = plan.context.get("unhealthy_count")
		assert isinstance(unhealthy_count, int)
		assert unhealthy_count >= 1
		assert result.success
		assert "snap_42" in result.summary


class TestWeeklyReviewService:
	"""Tests for WeeklyReviewService."""

	def test_add_item_and_get_next_priorities(self) -> None:
		service = WeeklyReviewService()
		service.add_item(WeeklyItem("w1", "Refactor billing", "engineering", ReviewPriority.MEDIUM, completed=False))
		service.add_item(WeeklyItem("w2", "Fix production bug", "operations", ReviewPriority.HIGH, completed=False))
		service.add_item(WeeklyItem("w3", "Archive notes", "admin", ReviewPriority.LOW, completed=False))

		next_priorities = service.get_next_priorities()
		assert len(next_priorities) == 3
		assert next_priorities[0].item_id == "w2"

	def test_build_review_counts_and_notes(self) -> None:
		service = WeeklyReviewService()
		today = date.today()
		service.add_item(WeeklyItem("w1", "Completed thing", "ops", ReviewPriority.MEDIUM, completed=True))
		service.add_item(WeeklyItem("w2", "Pending thing", "ops", ReviewPriority.HIGH, completed=False))
		service.add_win("Closed high-priority incident")
		service.add_blocker("Waiting on external vendor")

		review = service.build_review(week_of=today)
		assert review.completed_count == 1
		assert review.pending_count == 1
		assert review.wins == ["Closed high-priority incident"]
		assert review.blockers == ["Waiting on external vendor"]
		assert len(review.next_priorities) == 1


@pytest.mark.asyncio
class TestWeeklyReviewWorkflow:
	"""Tests for WeeklyReviewAgent."""

	async def test_workflow_instantiates(self) -> None:
		workflow = WeeklyReviewAgent(session=None)
		assert workflow.workflow_id == "weekly_review"
		assert workflow.service is not None

	async def test_process_and_act(self) -> None:
		workflow = WeeklyReviewAgent()
		workflow.service.add_item(WeeklyItem("w1", "Finish migrations", "platform", ReviewPriority.HIGH, completed=False))
		event = WorkflowEvent(event_type="weekly_review.generate", payload={"week_of": date.today().isoformat()})
		run = await workflow.trigger(event)
		plan = await workflow.process(run)
		result = await workflow.act(plan)

		assert plan.action_type == "publish_weekly_review"
		assert plan.context["pending_count"] == 1
		assert result.success
		assert "completed=" in result.summary
