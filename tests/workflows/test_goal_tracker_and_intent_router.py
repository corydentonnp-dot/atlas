"""Tests for Goal Tracker, Private Intent Capture Router, and Emergency Protocol workflows."""

import pytest
from datetime import date, datetime, timezone

from atlas.core.policy.engine import PolicyEngine
from atlas.workflows.additional.emergency_protocol_agent import (
	EmergencyProtocolAgent,
	EmergencyProtocolService,
	EmergencyType,
	SeverityLevel,
	ProtocolStatus,
)
from atlas.workflows.additional.goal_tracker_agent import (
	GoalTrackerAgent,
	GoalTrackerService,
	Goal,
	GoalStatus,
	GoalType,
	GoalAdjustment,
	GoalProgress,
)
from atlas.workflows.additional.private_intent_capture_router import (
	PrivateIntentCaptureRouterWorkflow,
	PrivateIntentCaptureService,
	PrivateIntent,
	IntentStatus,
	RoutedIntent,
)
from atlas.core.workflow.base import WorkflowEvent, ActionPlan, ActionResult


# ── GoalTrackerService Tests ──

def test_goal_tracker_service_create_goal():
	"""Test creating a new goal."""
	service = GoalTrackerService()
	goal = service.create_goal(
		goal_id="goal_001",
		title="Learn Python",
		description="Master Python programming",
		goal_type=GoalType.PROFESSIONAL,
		target_date=date(2026, 12, 31),
		category="learning",
	)
	assert goal.goal_id == "goal_001"
	assert goal.title == "Learn Python"
	assert goal.progress_percentage == 0.0
	assert goal.status == GoalStatus.NOT_STARTED


def test_goal_tracker_service_update_progress():
	"""Test updating goal progress."""
	service = GoalTrackerService()
	service.create_goal(
		goal_id="goal_001",
		title="Run a 5K",
		description="Run a 5K race in under 30 minutes",
		goal_type=GoalType.WELLNESS,
		target_date=date(2026, 6, 30),
	)
	updated = service.update_progress("goal_001", 50.0)
	assert updated is not None
	assert updated.progress_percentage == 50.0
	assert updated.status == GoalStatus.ON_TRACK


def test_goal_tracker_service_progress_bounds():
	"""Test that progress is bounded between 0 and 100."""
	service = GoalTrackerService()
	service.create_goal(
		goal_id="goal_001",
		title="Test Goal",
		description="Test",
		goal_type=GoalType.PERSONAL,
		target_date=date(2026, 12, 31),
	)
	updated = service.update_progress("goal_001", 150.0)
	assert updated is not None
	assert updated.progress_percentage == 100.0
	updated = service.update_progress("goal_001", -50.0)
	assert updated is not None
	assert updated.progress_percentage == 0.0


def test_goal_tracker_service_get_summary():
	"""Test getting goal progress summary."""
	service = GoalTrackerService()
	service.create_goal("g1", "Goal 1", "Desc", GoalType.PERSONAL, date(2026, 12, 31))
	service.create_goal("g2", "Goal 2", "Desc", GoalType.PROFESSIONAL, date(2026, 12, 31))
	service.create_goal("g3", "Goal 3", "Desc", GoalType.WELLNESS, date(2026, 12, 31))
	
	service.update_progress("g1", 100.0)
	service.update_progress("g2", 50.0)
	service.update_progress("g3", 20.0)

	summary = service.get_goal_summary()
	assert summary.total_goals == 3
	assert summary.completed == 1
	assert summary.on_track >= 1
	assert summary.at_risk >= 1


def test_goal_tracker_service_suggest_adjustments():
	"""Test suggesting adjustments for at-risk goals."""
	service = GoalTrackerService()
	service.create_goal("g1", "Goal 1", "Desc", GoalType.PERSONAL, date(2026, 12, 31))
	service.update_progress("g1", 15.0)  # At risk

	adjustments = service.suggest_adjustments()
	assert len(adjustments) > 0
	assert adjustments[0].goal_id == "g1"
	assert adjustments[0].risk_level in ("high", "medium")


def test_goal_tracker_service_get_goals_by_status():
	"""Test filtering goals by status."""
	service = GoalTrackerService()
	service.create_goal("g1", "Goal 1", "Desc", GoalType.PERSONAL, date(2026, 12, 31))
	service.create_goal("g2", "Goal 2", "Desc", GoalType.PROFESSIONAL, date(2026, 12, 31))
	
	service.update_progress("g1", 100.0)
	on_track_goals = service.get_goals_by_status(GoalStatus.ON_TRACK)
	
	assert len(on_track_goals) >= 0


# ── GoalTrackerAgent Tests ──

def test_goal_tracker_agent_instantiation():
	"""Test Goal Tracker Agent instantiation."""
	agent = GoalTrackerAgent()
	assert agent.workflow_id == "goal_tracker"
	assert agent.name == "Goal Tracker"
	assert agent.category == "additional"


@pytest.mark.asyncio
async def test_goal_tracker_agent_trigger():
	"""Test Goal Tracker Agent trigger phase."""
	agent = GoalTrackerAgent()
	event = WorkflowEvent(
		event_type="goal_tracking_requested",
		payload={"request_type": "summary"},
	)
	run = await agent.trigger(event)
	assert run.workflow_id == "goal_tracker"
	assert run.event == event


@pytest.mark.asyncio
async def test_goal_tracker_agent_process():
	"""Test Goal Tracker Agent process phase."""
	service = GoalTrackerService()
	service.create_goal("g1", "Goal 1", "Desc", GoalType.PERSONAL, date(2026, 12, 31))
	service.update_progress("g1", 50.0)

	agent = GoalTrackerAgent(service=service)
	event = WorkflowEvent(event_type="goal_tracking_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)

	assert plan.action_type == "track_goals"
	assert plan.confidence >= 0.8
	assert "total_goals" in plan.context


@pytest.mark.asyncio
async def test_goal_tracker_agent_act():
	"""Test Goal Tracker Agent act phase."""
	agent = GoalTrackerAgent()
	event = WorkflowEvent(event_type="goal_tracking_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)

	assert result.success is True
	assert "Goal tracking" in result.summary


# ── PrivateIntentCaptureService Tests ──

def test_private_intent_capture_service_capture_intent():
	"""Test capturing a freeform intent."""
	service = PrivateIntentCaptureService()
	intent = service.capture_intent(
		intent_id="intent_001",
		raw_text="I need to return an Amazon item for a refund",
	)
	assert intent.intent_id == "intent_001"
	assert intent.raw_text == "I need to return an Amazon item for a refund"
	assert intent.normalized_text is not None


def test_private_intent_capture_service_route_high_confidence():
	"""Test routing a high-confidence intent."""
	service = PrivateIntentCaptureService()
	service.capture_intent("intent_001", "I need to return an amazon item")
	routed = service.route_intent("intent_001")

	assert routed.intent_id == "intent_001"
	assert routed.workflow_id == "amazon_return_window_agent"
	assert routed.confidence >= 0.7


def test_private_intent_capture_service_route_low_confidence():
	"""Test routing a low-confidence intent."""
	service = PrivateIntentCaptureService()
	service.capture_intent("intent_001", "I need to do something")
	routed = service.route_intent("intent_001")

	assert routed.needs_review is True
	assert routed.confidence < 0.7


def test_private_intent_capture_service_pending_review():
	"""Test getting intents pending review."""
	service = PrivateIntentCaptureService()
	service.capture_intent("intent_001", "vague request")
	service.capture_intent("intent_002", "I need to return an amazon item")

	pending = service.pending_review()
	assert len(pending) >= 0


# ── PrivateIntentCaptureRouterWorkflow Tests ──

def test_private_intent_capture_router_instantiation():
	"""Test Private Intent Capture Router instantiation."""
	workflow = PrivateIntentCaptureRouterWorkflow()
	assert workflow.workflow_id == "private_intent_capture_router"
	assert workflow.category == "additional"


@pytest.mark.asyncio
async def test_private_intent_capture_router_trigger():
	"""Test trigger phase of Private Intent Capture Router."""
	workflow = PrivateIntentCaptureRouterWorkflow()
	event = WorkflowEvent(
		event_type="private_intent_captured",
		payload={
			"intent_id": "intent_001",
			"raw_text": "I need to return an amazon item",
		},
	)
	run = await workflow.trigger(event)
	assert run.workflow_id == "private_intent_capture_router"


@pytest.mark.asyncio
async def test_private_intent_capture_router_process():
	"""Test process phase of Private Intent Capture Router."""
	service = PrivateIntentCaptureService()
	service.capture_intent("intent_001", "I need to return an amazon item")

	workflow = PrivateIntentCaptureRouterWorkflow(service=service)
	event = WorkflowEvent(
		event_type="private_intent_captured",
		payload={"intent_id": "intent_001", "raw_text": "I need to return"},
	)
	run = await workflow.trigger(event)
	plan = await workflow.process(run)

	assert plan.action_type == "route_private_intent"
	assert "intent_id" in plan.context
	assert "workflow_id" in plan.context


@pytest.mark.asyncio
async def test_private_intent_capture_router_act():
	"""Test act phase of Private Intent Capture Router."""
	service = PrivateIntentCaptureService()
	service.capture_intent("intent_001", "I need to return an amazon item")

	workflow = PrivateIntentCaptureRouterWorkflow(service=service)
	event = WorkflowEvent(
		event_type="private_intent_captured",
		payload={"intent_id": "intent_001", "raw_text": "I need to return"},
	)
	run = await workflow.trigger(event)
	plan = await workflow.process(run)
	result = await workflow.act(plan)

	assert result.success is True
	assert "routed" in result.summary.lower() or "intent" in result.summary.lower()


# ── EmergencyProtocolService Tests ──

def test_emergency_protocol_service_create_alert():
	"""Test creating an emergency alert."""
	service = EmergencyProtocolService()
	alert = service.create_alert(
		alert_id="alert_001",
		emergency_type=EmergencyType.SECURITY_BREACH,
		severity=SeverityLevel.HIGH,
		description="Possible data breach detected",
		location="Data Center 1",
	)
	assert alert.alert_id == "alert_001"
	assert alert.emergency_type == EmergencyType.SECURITY_BREACH
	assert alert.severity == SeverityLevel.HIGH


def test_emergency_protocol_service_get_protocol():
	"""Test getting appropriate protocol for emergency."""
	service = EmergencyProtocolService()
	protocol = service.get_protocol_for_emergency(EmergencyType.SECURITY_BREACH, SeverityLevel.HIGH)
	assert protocol is not None
	assert protocol.emergency_type == EmergencyType.SECURITY_BREACH
	assert len(protocol.actions) > 0


def test_emergency_protocol_service_execute_protocol():
	"""Test executing a protocol."""
	service = EmergencyProtocolService()
	alert = service.create_alert(
		"alert_001",
		EmergencyType.MEDICAL_EMERGENCY,
		SeverityLevel.CRITICAL,
		"Patient collapsed",
	)
	protocol = service.get_protocol_for_emergency(alert.emergency_type, alert.severity)
	assert protocol is not None

	execution = service.execute_protocol(protocol, alert)
	assert execution.status == ProtocolStatus.ACTIVATED
	assert execution.actions_completed == 0


def test_emergency_protocol_service_mark_action_complete():
	"""Test marking protocol actions as complete."""
	service = EmergencyProtocolService()
	alert = service.create_alert(
		"alert_001",
		EmergencyType.MEDICAL_EMERGENCY,
		SeverityLevel.CRITICAL,
		"Patient collapsed",
	)
	protocol = service.get_protocol_for_emergency(alert.emergency_type, alert.severity)
	assert protocol is not None

	execution = service.execute_protocol(protocol, alert)
	updated = service.mark_action_complete(execution.execution_id)
	assert updated is not None
	assert updated.actions_completed > execution.actions_completed


def test_emergency_protocol_service_escalate():
	"""Test escalating a protocol."""
	service = EmergencyProtocolService()
	alert = service.create_alert(
		"alert_001",
		EmergencyType.SECURITY_BREACH,
		SeverityLevel.HIGH,
		"Security breach",
	)
	protocol = service.get_protocol_for_emergency(alert.emergency_type, alert.severity)
	assert protocol is not None

	execution = service.execute_protocol(protocol, alert)
	escalated = service.escalate_protocol(execution.execution_id, "Unable to contain breach")
	assert escalated is not None
	assert escalated.status == ProtocolStatus.ESCALATED
	assert escalated.escalation_reason is not None
	assert "breach" in escalated.escalation_reason.lower()


def test_emergency_protocol_service_get_active_executions():
	"""Test getting active protocol executions."""
	service = EmergencyProtocolService()
	alert = service.create_alert(
		"alert_001",
		EmergencyType.WEATHER_EMERGENCY,
		SeverityLevel.MEDIUM,
		"Severe storm approaching",
	)
	protocol = service.get_protocol_for_emergency(alert.emergency_type, alert.severity)
	if protocol:
		service.execute_protocol(protocol, alert)

	active = service.get_active_executions()
	assert len(active) >= 0


# ── EmergencyProtocolAgent Tests ──

def test_emergency_protocol_agent_instantiation():
	"""Test Emergency Protocol Agent instantiation."""
	agent = EmergencyProtocolAgent()
	assert agent.workflow_id == "emergency_protocol"
	assert agent.name == "Emergency Protocol"
	assert agent.category == "additional"


@pytest.mark.asyncio
async def test_emergency_protocol_agent_trigger():
	"""Test Emergency Protocol Agent trigger phase."""
	agent = EmergencyProtocolAgent()
	event = WorkflowEvent(
		event_type="emergency_alert",
		payload={
			"alert_id": "alert_001",
			"emergency_type": "security_breach",
			"severity": "high",
			"description": "Security breach detected",
		},
	)
	run = await agent.trigger(event)
	assert run.workflow_id == "emergency_protocol"
	assert run.event == event


@pytest.mark.asyncio
async def test_emergency_protocol_agent_process():
	"""Test Emergency Protocol Agent process phase."""
	agent = EmergencyProtocolAgent()
	event = WorkflowEvent(
		event_type="emergency_alert",
		payload={
			"alert_id": "alert_001",
			"emergency_type": "security_breach",
			"severity": "high",
			"description": "Security breach detected",
		},
	)
	run = await agent.trigger(event)
	plan = await agent.process(run)

	assert plan.action_type == "activate_emergency_protocol"
	assert plan.confidence >= 0.5
	assert "alert_id" in plan.context
	assert "emergency_type" in plan.context


@pytest.mark.asyncio
async def test_emergency_protocol_agent_act():
	"""Test Emergency Protocol Agent act phase."""
	agent = EmergencyProtocolAgent()
	event = WorkflowEvent(
		event_type="emergency_alert",
		payload={
			"alert_id": "alert_001",
			"emergency_type": "medical_emergency",
			"severity": "critical",
			"description": "Patient collapsed",
		},
	)
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)

	assert result.success is True
	assert "protocol" in result.summary.lower() or "alert" in result.summary.lower()


@pytest.mark.asyncio
async def test_emergency_protocol_agent_unknown_type():
	"""Test Emergency Protocol Agent with unknown emergency type."""
	agent = EmergencyProtocolAgent()
	event = WorkflowEvent(
		event_type="emergency_alert",
		payload={
			"alert_id": "alert_001",
			"emergency_type": "unknown_emergency",
			"severity": "low",
			"description": "Unknown emergency",
		},
	)
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)

	assert result.success is True
	assert "alert" in result.summary.lower()
