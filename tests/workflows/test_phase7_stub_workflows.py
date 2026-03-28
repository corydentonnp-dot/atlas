"""Tests for Phase 7 (score-11) stub-reduction workflows:
Travel Deal Monitor, Restock Reminder Agent, Promise Tracker,
Overdue Text Resurfacer, and Job Board Monitor.
"""

from __future__ import annotations

import pytest
from datetime import date, timedelta

from atlas.core.workflow.base import WorkflowEvent

# ── Travel Deal Monitor ───────────────────────────────────────────────────────
from atlas.workflows.travel.travel_deal_monitor import (
	TravelDealMonitorWorkflow,
	TravelDealMonitorService,
	DealType,
	AlertStatus,
)


def test_travel_deal_monitor_add_alert():
	service = TravelDealMonitorService()
	alert = service.add_alert(
		"a001", "Miami Beach", DealType.FLIGHT, "ORD",
		date(2026, 12, 20), baseline_price=450.0, drop_threshold_pct=10.0,
	)
	assert alert.alert_id == "a001"
	assert alert.status == AlertStatus.WATCHING
	assert alert.current_price == 450.0


def test_travel_deal_monitor_price_drop_triggers_deal():
	service = TravelDealMonitorService()
	service.add_alert("a002", "NYC", DealType.HOTEL, "CHI", date(2026, 11, 1), 300.0, drop_threshold_pct=15.0)
	updated = service.update_price("a002", 200.0)  # 33% drop > 15%
	assert updated is not None
	assert updated.status == AlertStatus.DROP_DETECTED
	assert updated.drop_percentage > 15.0


def test_travel_deal_monitor_no_deal_below_threshold():
	service = TravelDealMonitorService()
	service.add_alert("a003", "Denver", DealType.FLIGHT, "LAX", date(2026, 9, 1), 200.0, drop_threshold_pct=20.0)
	updated = service.update_price("a003", 195.0)  # only 2.5% drop
	assert updated is not None
	assert updated.status == AlertStatus.WATCHING


def test_travel_deal_monitor_mark_booked():
	service = TravelDealMonitorService()
	service.add_alert("a004", "Paris", DealType.PACKAGE, "JFK", date(2027, 6, 1), 1500.0)
	service.update_price("a004", 1100.0)  # big drop
	result = service.mark_booked("a004")
	assert result is True
	assert service._alerts["a004"].status == AlertStatus.BOOKED


def test_travel_deal_monitor_summary():
	service = TravelDealMonitorService()
	service.add_alert("a005", "Vegas", DealType.HOTEL, "SEA", date(2026, 7, 1), 150.0)
	service.update_price("a005", 80.0)  # large drop
	summary = service.get_summary()
	assert summary.total_watching >= 1
	assert summary.active_deals >= 1
	assert summary.best_deal_drop_pct > 0


@pytest.mark.asyncio
async def test_travel_deal_monitor_full_lifecycle():
	agent = TravelDealMonitorWorkflow()
	assert agent.workflow_id == "travel_deal_monitor"
	event = WorkflowEvent(event_type="deal_check_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "deal" in result.summary.lower()


# ── Restock Reminder Agent ────────────────────────────────────────────────────
from atlas.workflows.shopping.restock_reminder_agent import (
	RestockReminderAgent,
	RestockReminderService,
	RestockCategory,
	RestockStatus,
)


def test_restock_reminder_add_in_stock():
	service = RestockReminderService()
	item = service.add_item("i001", "AC Filter", RestockCategory.HVAC_FILTER, date.today(), 90)
	assert item.item_id == "i001"
	assert item.status == RestockStatus.IN_STOCK


def test_restock_reminder_overdue_item():
	service = RestockReminderService()
	old_date = date.today() - timedelta(days=100)
	item = service.add_item("i002", "Metformin", RestockCategory.MEDICATION, old_date, 30)
	assert item.status == RestockStatus.OVERDUE


def test_restock_reminder_due_soon():
	service = RestockReminderService()
	nearly_due = date.today() - timedelta(days=85)  # interval=90, so 5 days left
	item = service.add_item("i003", "Dog Food", RestockCategory.PET, nearly_due, 90)
	assert item.status in (RestockStatus.DUE_SOON, RestockStatus.OVERDUE)


def test_restock_reminder_record_restock():
	service = RestockReminderService()
	old_date = date.today() - timedelta(days=100)
	service.add_item("i004", "Paper Towels", RestockCategory.HOUSEHOLD, old_date, 30)
	result = service.record_restock("i004", 3)
	assert result is True
	assert service._items["i004"].status == RestockStatus.IN_STOCK


def test_restock_reminder_summary():
	service = RestockReminderService()
	service.add_item("i005", "Toothpaste", RestockCategory.PERSONAL_CARE, date.today(), 60)
	old_date = date.today() - timedelta(days=100)
	service.add_item("i006", "Vitamins", RestockCategory.MEDICATION, old_date, 30)
	summary = service.get_summary()
	assert summary.total_tracked == 2
	assert summary.overdue >= 1
	assert summary.most_urgent_item != ""


@pytest.mark.asyncio
async def test_restock_reminder_full_lifecycle():
	agent = RestockReminderAgent()
	assert agent.workflow_id == "restock_reminder"
	event = WorkflowEvent(event_type="restock_check_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "restock" in result.summary.lower()


# ── Promise Tracker ───────────────────────────────────────────────────────────
from atlas.workflows.communication.promise_tracker import (
	PromiseTrackerWorkflow,
	PromiseTrackerService,
	PromiseDirection,
	PromiseStatus,
)


def test_promise_tracker_capture_manual():
	service = PromiseTrackerService()
	promise = service.capture_promise("p001", "I'll send the report by Friday", "me", "Boss", "Email thread")
	assert promise.promise_id == "p001"
	assert promise.direction == PromiseDirection.I_PROMISED
	assert promise.status == PromiseStatus.PENDING


def test_promise_tracker_extract_from_text_i_promised():
	service = PromiseTrackerService()
	result = service.extract_from_text("p002", "I'll get that done by tomorrow.", "Alice", "Slack")
	assert result is not None
	assert result.direction == PromiseDirection.I_PROMISED


def test_promise_tracker_extract_from_text_no_match():
	service = PromiseTrackerService()
	result = service.extract_from_text("p003", "The weather is nice today.", "Bob", "SMS")
	assert result is None


def test_promise_tracker_overdue():
	service = PromiseTrackerService()
	past_date = date.today() - timedelta(days=2)
	service.capture_promise("p004", "I'll call them", "me", "Jane", "Text", due_date=past_date)
	overdue = service.get_overdue()
	assert len(overdue) == 1
	assert overdue[0].status == PromiseStatus.OVERDUE


def test_promise_tracker_mark_resolved():
	service = PromiseTrackerService()
	service.capture_promise("p005", "I'll pay the bill", "me", "Landlord", "App")
	result = service.mark_resolved("p005")
	assert result is True
	summary = service.get_summary()
	assert summary.resolved == 1


@pytest.mark.asyncio
async def test_promise_tracker_full_lifecycle():
	agent = PromiseTrackerWorkflow()
	assert agent.workflow_id == "promise_tracker"
	event = WorkflowEvent(event_type="promise_scan_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "promise" in result.summary.lower() or "pending" in result.summary.lower()


# ── Overdue Text Resurfacer ───────────────────────────────────────────────────
from atlas.workflows.communication.overdue_text_resurfacer import (
	OverdueTextResurfacerWorkflow,
	OverdueTextResurfacerService,
	ThreadUrgency,
	ThreadStatus,
)


def test_overdue_resurfacer_add_thread():
	service = OverdueTextResurfacerService()
	thread = service.add_thread(
		"t001", "Mom", "Call me when you can",
		date.today() - timedelta(days=5), waiting_on_me=True, urgency=ThreadUrgency.HIGH,
	)
	assert thread.thread_id == "t001"
	assert thread.days_overdue >= 5
	assert thread.waiting_on_me is True


def test_overdue_resurfacer_create_draft():
	service = OverdueTextResurfacerService()
	service.add_thread("t002", "Client", "Did you finish?", date.today() - timedelta(days=3), waiting_on_me=True)
	draft = service.create_draft("t002", "Sorry for the delay, I'll have it by EOD.", confidence=0.85)
	assert draft is not None
	assert draft.thread_id == "t002"
	assert service._threads["t002"].status == ThreadStatus.DRAFTED


def test_overdue_resurfacer_mark_replied():
	service = OverdueTextResurfacerService()
	service.add_thread("t003", "Joe", "Still on?", date.today() - timedelta(days=2), waiting_on_me=True)
	result = service.mark_replied("t003")
	assert result is True
	assert service._threads["t003"].status == ThreadStatus.REPLIED


def test_overdue_resurfacer_summary():
	service = OverdueTextResurfacerService()
	service.add_thread("t004", "Amy", "Need your input", date.today() - timedelta(days=4), waiting_on_me=True, urgency=ThreadUrgency.HIGH)
	service.add_thread("t005", "Bob", "Let me know", date.today() - timedelta(days=6), waiting_on_me=False, urgency=ThreadUrgency.LOW)
	summary = service.get_summary()
	assert summary.total_scanned == 2
	assert summary.waiting_on_me == 1
	assert summary.high_urgency >= 1


@pytest.mark.asyncio
async def test_overdue_resurfacer_full_lifecycle():
	agent = OverdueTextResurfacerWorkflow()
	assert agent.workflow_id == "overdue_text_resurfacer"
	event = WorkflowEvent(event_type="message_scan_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "overdue" in result.summary.lower() or "waiting" in result.summary.lower()


# ── Job Board Monitor ─────────────────────────────────────────────────────────
from atlas.workflows.career.job_board_monitor import (
	JobBoardMonitorWorkflow,
	JobBoardMonitorService,
	JobCriteria,
	JobType,
	JobStatus,
)


def test_job_board_monitor_add_posting_no_criteria():
	service = JobBoardMonitorService()
	posting = service.add_posting(
		"j001", "NP Hospitalist", "Metro Health", "Chicago IL",
		JobType.FULL_TIME, 120000.0, 160000.0, date.today(),
	)
	assert posting.job_id == "j001"
	assert posting.status == JobStatus.NEW
	assert posting.match_score == 0.5  # neutral when no criteria set


def test_job_board_monitor_scoring_with_criteria():
	service = JobBoardMonitorService()
	criteria = JobCriteria(
		titles=("NP", "Nurse Practitioner", "APRN"),
		locations=("Chicago",),
		min_salary=100000.0,
		job_types=(JobType.FULL_TIME, JobType.PER_DIEM),
		keywords=("acute care",),
	)
	service.set_criteria(criteria)
	posting = service.add_posting(
		"j002", "NP Emergency", "County Hospital", "Chicago IL",
		JobType.FULL_TIME, 130000.0, 170000.0, date.today(),
	)
	assert posting.match_score > 0.5  # should score well


def test_job_board_monitor_update_status():
	service = JobBoardMonitorService()
	service.add_posting("j003", "APRN Float", "Agency", "Remote", JobType.TRAVEL, 80.0, 95.0, date.today())
	result = service.update_status("j003", JobStatus.APPLIED)
	assert result is True
	assert service._postings["j003"].status == JobStatus.APPLIED


def test_job_board_monitor_high_match_filter():
	service = JobBoardMonitorService()
	criteria = JobCriteria(
		titles=("NP",), locations=(), min_salary=100000.0,
		job_types=(JobType.FULL_TIME,), keywords=(),
	)
	service.set_criteria(criteria)
	service.add_posting("j004", "NP Urgent Care", "US Health", "Dallas TX", JobType.FULL_TIME, 110000.0, 140000.0, date.today())
	service.add_posting("j005", "Medical Scribe", "Clinic", "Tulsa OK", JobType.PART_TIME, 30000.0, 40000.0, date.today())
	high = service.get_new_high_match()
	assert any(p.job_id == "j004" for p in high)
	assert not any(p.job_id == "j005" for p in high)


def test_job_board_monitor_summary():
	service = JobBoardMonitorService()
	service.add_posting("j006", "Staff NP", "Big Hospital", "NYC", JobType.FULL_TIME, 150000.0, 200000.0, date.today())
	service.update_status("j006", JobStatus.APPLIED)
	summary = service.get_summary()
	assert summary.total_tracked >= 1
	assert summary.applied >= 1


@pytest.mark.asyncio
async def test_job_board_monitor_full_lifecycle():
	agent = JobBoardMonitorWorkflow()
	assert agent.workflow_id == "job_board_monitor"
	event = WorkflowEvent(event_type="job_scan_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "job" in result.summary.lower() or "posting" in result.summary.lower()
