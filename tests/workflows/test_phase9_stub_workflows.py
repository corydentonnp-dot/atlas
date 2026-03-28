"""Tests for Phase 9 score-10 stub-reduction workflows:
Credentialing Packet Agent, Smart Home Automation Agent,
Resume/CV Update Agent, Coupon Aggregator, and
Furnished Finder Lead Responder.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from atlas.core.workflow.base import WorkflowEvent

# Credentialing Packet Agent
from atlas.workflows.licensure.credentialing_packet_agent import (
	CredentialingPacketAgent,
	CredentialingPacketService,
	CredentialDocType,
	CredentialStatus,
)


def test_credentialing_add_requirement():
	service = CredentialingPacketService()
	req = service.add_requirement(
		"c001", "packet_a", "State License", CredentialDocType.LICENSE, date.today() + timedelta(days=20)
	)
	assert req.doc_id == "c001"
	assert req.status == CredentialStatus.MISSING


def test_credentialing_mark_submitted_and_verified():
	service = CredentialingPacketService()
	service.add_requirement("c002", "packet_a", "DEA", CredentialDocType.DEA, date.today() + timedelta(days=20))
	assert service.mark_submitted("c002") is True
	assert service._requirements["c002"].status == CredentialStatus.SUBMITTED
	assert service.mark_verified("c002") is True
	assert service._requirements["c002"].status == CredentialStatus.VERIFIED


def test_credentialing_due_soon():
	service = CredentialingPacketService()
	service.add_requirement("c003", "packet_a", "CV", CredentialDocType.CV, date.today() + timedelta(days=5))
	due_soon = service.get_due_soon()
	assert len(due_soon) == 1
	assert due_soon[0].doc_id == "c003"


def test_credentialing_expired():
	service = CredentialingPacketService()
	service.add_requirement("c004", "packet_a", "Background", CredentialDocType.BACKGROUND_CHECK, date.today() - timedelta(days=1))
	summary = service.get_summary()
	assert summary.expired >= 1


def test_credentialing_summary():
	service = CredentialingPacketService()
	service.add_requirement("c005", "packet_a", "Malpractice", CredentialDocType.MALPRACTICE, date.today() + timedelta(days=30))
	summary = service.get_summary()
	assert summary.total_requirements == 1
	assert summary.missing == 1


@pytest.mark.asyncio
async def test_credentialing_packet_agent_lifecycle():
	agent = CredentialingPacketAgent()
	event = WorkflowEvent(event_type="credentialing_review_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "credentialing packet" in result.summary.lower()


# Smart Home Automation Agent
from atlas.workflows.home.smart_home_automation_agent import (
	SmartHomeAutomationAgent,
	SmartHomeAutomationService,
	TriggerType,
	AutomationStatus,
)


def test_smart_home_add_rule():
	service = SmartHomeAutomationService()
	rule = service.add_rule("r001", "Porch Light Sunset", TriggerType.SUNSET, "sunset-15m", "turn_on_porch")
	assert rule.rule_id == "r001"
	assert rule.status == AutomationStatus.ACTIVE


def test_smart_home_pause_rule():
	service = SmartHomeAutomationService()
	service.add_rule("r002", "Night Lock", TriggerType.TIME, "22:00", "lock_doors")
	assert service.pause_rule("r002") is True
	assert service._rules["r002"].status == AutomationStatus.PAUSED


def test_smart_home_disable_rule():
	service = SmartHomeAutomationService()
	service.add_rule("r003", "Motion Hall", TriggerType.MOTION, "hall_sensor", "turn_on_hall_light")
	assert service.disable_rule("r003") is True
	assert service._rules["r003"].status == AutomationStatus.DISABLED


def test_smart_home_record_run_error():
	service = SmartHomeAutomationService()
	service.add_rule("r004", "Thermostat", TriggerType.TEMPERATURE, "<65", "set_heat_68")
	assert service.record_run("r004", success=False) is True
	assert service._rules["r004"].status == AutomationStatus.ERROR
	assert service._rules["r004"].error_count == 1


def test_smart_home_summary():
	service = SmartHomeAutomationService()
	service.add_rule("r005", "Arrive Home", TriggerType.PRESENCE, "home", "turn_on_entry_light")
	service.record_run("r005", success=True)
	summary = service.get_summary()
	assert summary.total_rules == 1
	assert summary.total_runs == 1


@pytest.mark.asyncio
async def test_smart_home_automation_lifecycle():
	agent = SmartHomeAutomationAgent()
	event = WorkflowEvent(event_type="automation_audit_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "automation" in result.summary.lower()


# Resume/CV Update Agent
from atlas.workflows.career.resume_cv_update_agent import (
	ResumeCvUpdateAgent,
	ResumeCvUpdateService,
	UpdateType,
	ResumeUpdateStatus,
)


def test_resume_cv_add_item():
	service = ResumeCvUpdateService()
	item = service.add_item("u001", "Built scheduling automation", UpdateType.PROJECT, "Saved 4h/week", date.today())
	assert item.item_id == "u001"
	assert item.status == ResumeUpdateStatus.CAPTURED


def test_resume_cv_mark_added():
	service = ResumeCvUpdateService()
	service.add_item("u002", "RN renewal", UpdateType.CERTIFICATION, "License renewed", date.today())
	assert service.mark_added("u002") is True
	assert service._items["u002"].status == ResumeUpdateStatus.ADDED_TO_RESUME


def test_resume_cv_dismiss():
	service = ResumeCvUpdateService()
	service.add_item("u003", "Minor task", UpdateType.OTHER, "low impact", date.today())
	assert service.dismiss("u003") is True
	assert service._items["u003"].status == ResumeUpdateStatus.DISMISSED


def test_resume_cv_get_pending():
	service = ResumeCvUpdateService()
	service.add_item("u004", "Poster presentation", UpdateType.PUBLICATION, "regional conference", date.today())
	pending = service.get_pending()
	assert len(pending) == 1
	assert pending[0].item_id == "u004"


def test_resume_cv_summary():
	service = ResumeCvUpdateService()
	service.add_item("u005", "New skill", UpdateType.SKILL, "Epic optimization", date.today())
	summary = service.get_summary()
	assert summary.total_items == 1
	assert summary.pending_items == 1


@pytest.mark.asyncio
async def test_resume_cv_update_agent_lifecycle():
	agent = ResumeCvUpdateAgent()
	event = WorkflowEvent(event_type="resume_refresh_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "resume" in result.summary.lower()


# Coupon Aggregator
from atlas.workflows.shopping.coupon_aggregator import (
	CouponAggregatorWorkflow,
	CouponAggregatorService,
	CouponSource,
	CouponStatus,
)


def test_coupon_add_active():
	service = CouponAggregatorService()
	coupon = service.add_coupon(
		"cp001", "Target", "SAVE10", 10.0, date.today() + timedelta(days=10), CouponSource.EMAIL
	)
	assert coupon.coupon_id == "cp001"
	assert coupon.status == CouponStatus.ACTIVE


def test_coupon_add_expired():
	service = CouponAggregatorService()
	coupon = service.add_coupon(
		"cp002", "Target", "OLD", 5.0, date.today() - timedelta(days=1), CouponSource.WEB
	)
	assert coupon.status == CouponStatus.EXPIRED


def test_coupon_mark_applied():
	service = CouponAggregatorService()
	service.add_coupon("cp003", "BestBuy", "BB15", 15.0, date.today() + timedelta(days=5), CouponSource.APP)
	assert service.mark_applied("cp003") is True
	assert service._coupons["cp003"].status == CouponStatus.APPLIED


def test_coupon_get_best_for_merchant():
	service = CouponAggregatorService()
	service.add_coupon("cp004", "Amazon", "A5", 5.0, date.today() + timedelta(days=10), CouponSource.WEB, min_spend=25.0)
	service.add_coupon("cp005", "Amazon", "A15", 15.0, date.today() + timedelta(days=10), CouponSource.WEB, min_spend=50.0)
	best = service.get_best_for_merchant("Amazon", subtotal=60.0)
	assert best is not None
	assert best.code == "A15"


def test_coupon_summary():
	service = CouponAggregatorService()
	service.add_coupon("cp006", "Ulta", "U20", 20.0, date.today() + timedelta(days=3), CouponSource.EMAIL)
	summary = service.get_summary()
	assert summary.total_tracked == 1
	assert summary.active == 1


@pytest.mark.asyncio
async def test_coupon_aggregator_workflow_lifecycle():
	agent = CouponAggregatorWorkflow()
	event = WorkflowEvent(event_type="coupon_sync_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "coupon" in result.summary.lower()


# Furnished Finder Lead Responder
from atlas.workflows.property.furnished_finder_lead_responder import (
	FurnishedFinderLeadResponderWorkflow,
	FurnishedFinderLeadResponderService,
	LeadRecommendation,
	LeadStatus,
)


def test_ff_parse_lead():
	service = FurnishedFinderLeadResponderService()
	lead = service.parse_lead(
		{
			"lead_id": "ff001",
			"name": "Pat Doe",
			"check_in": date.today().isoformat(),
			"check_out": (date.today() + timedelta(days=45)).isoformat(),
			"guests": "2",
			"budget": "3200",
			"message": "Need furnished housing for assignment",
			"source_email": "pat@example.com",
		}
	)
	assert lead.lead_id == "ff001"
	assert lead.name == "Pat Doe"


def test_ff_screen_auto_approve():
	service = FurnishedFinderLeadResponderService()
	lead = service.parse_lead(
		{
			"lead_id": "ff002",
			"name": "Sam",
			"check_in": date.today().isoformat(),
			"check_out": (date.today() + timedelta(days=60)).isoformat(),
			"guests": "1",
			"budget": "3500",
			"message": "Travel assignment",
			"source_email": "sam@example.com",
		}
	)
	screening = service.screen_lead(lead)
	assert screening.recommendation in (LeadRecommendation.AUTO_APPROVE, LeadRecommendation.REVIEW)


def test_ff_screen_reject_party_risk():
	service = FurnishedFinderLeadResponderService()
	lead = service.parse_lead(
		{
			"lead_id": "ff003",
			"name": "Chris",
			"check_in": date.today().isoformat(),
			"check_out": (date.today() + timedelta(days=5)).isoformat(),
			"guests": "6",
			"budget": "1000",
			"message": "big party weekend",
			"source_email": "chris@example.com",
		}
	)
	screening = service.screen_lead(lead)
	assert screening.recommendation == LeadRecommendation.REJECT


def test_ff_draft_response():
	service = FurnishedFinderLeadResponderService()
	lead = service.parse_lead(
		{
			"lead_id": "ff004",
			"name": "Taylor",
			"check_in": date.today().isoformat(),
			"check_out": (date.today() + timedelta(days=35)).isoformat(),
			"guests": "2",
			"budget": "3000",
			"message": "Need housing",
			"source_email": "tay@example.com",
		}
	)
	screening = service.screen_lead(lead)
	draft = service.draft_response(lead, screening)
	assert "Taylor" in draft.subject
	assert draft.to == "tay@example.com"


def test_ff_summary():
	service = FurnishedFinderLeadResponderService()
	lead = service.parse_lead(
		{
			"lead_id": "ff005",
			"name": "Jordan",
			"check_in": date.today().isoformat(),
			"check_out": (date.today() + timedelta(days=20)).isoformat(),
			"guests": "1",
			"budget": "2800",
			"message": "Travel RN",
			"source_email": "jord@example.com",
		}
	)
	service.add_lead(lead)
	service.mark_sent("ff005")
	summary = service.get_summary()
	assert summary.total_leads == 1
	assert summary.auto_approved == 1


@pytest.mark.asyncio
async def test_ff_lifecycle():
	agent = FurnishedFinderLeadResponderWorkflow()
	event = WorkflowEvent(event_type="ff_lead_received", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "furnished finder" in result.summary.lower()
