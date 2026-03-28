"""Tests for Phase 6 stub-reduction workflows:
Deduction Capture, Conference Abstract Deadline, Estimated Tax Calculator,
Seasonal Prep, and Warranty Tracker.
"""

from __future__ import annotations

import pytest
from datetime import date

from atlas.core.workflow.base import WorkflowEvent

# ── Deduction Capture ──────────────────────────────────────────────────────────
from atlas.workflows.tax_legal.deduction_capture_agent import (
	DeductionCaptureAgent,
	DeductionCaptureService,
	DeductionCategory,
	DeductionStatus,
	SpendingItem,
)


def test_deduction_capture_service_flag_medical():
	service = DeductionCaptureService()
	item = SpendingItem("i1", "Pharmacy co-pay", 45.00, date.today(), "CVS Pharmacy")
	record = service.flag_item(item)
	assert record is not None
	assert record.deduction_category == DeductionCategory.MEDICAL
	assert record.status == DeductionStatus.FLAGGED


def test_deduction_capture_service_no_match():
	service = DeductionCaptureService()
	item = SpendingItem("i2", "Groceries", 120.00, date.today(), "Kroger")
	record = service.flag_item(item)
	assert record is None


def test_deduction_capture_service_mark_documented():
	service = DeductionCaptureService()
	item = SpendingItem("i3", "Doctor visit", 200.00, date.today(), "Methodist Hospital")
	record = service.flag_item(item)
	assert record is not None
	result = service.mark_documented(record.deduction_id)
	assert result is True
	assert service._deductions[record.deduction_id].status == DeductionStatus.DOCUMENTED


def test_deduction_capture_service_confirm_and_summary():
	service = DeductionCaptureService()
	item = SpendingItem("i4", "Donate to charity", 500.00, date.today(), "Red Cross")
	record = service.flag_item(item)
	assert record is not None
	service.confirm_deduction(record.deduction_id)

	summary = service.get_summary()
	assert summary.total_confirmed == 1
	assert summary.total_amount_confirmed == 500.00
	assert DeductionCategory.CHARITABLE.value in summary.by_category


@pytest.mark.asyncio
async def test_deduction_capture_agent_full_lifecycle():
	agent = DeductionCaptureAgent()
	assert agent.workflow_id == "deduction_capture"
	event = WorkflowEvent(event_type="deduction_scan_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "deduction" in result.summary.lower()


# ── Conference Abstract Deadline ──────────────────────────────────────────────
from atlas.workflows.career.conference_abstract_deadline_agent import (
	ConferenceAbstractDeadlineAgent,
	ConferenceAbstractDeadlineService,
	SubmissionType,
	DeadlineStatus,
)


def test_conference_deadline_service_add_upcoming():
	service = ConferenceAbstractDeadlineService()
	dl = service.add_deadline(
		"dl_001",
		"NP World 2026",
		SubmissionType.ABSTRACT,
		date(2026, 12, 1),
	)
	assert dl.deadline_id == "dl_001"
	assert dl.status in (DeadlineStatus.UPCOMING, DeadlineStatus.DUE_SOON)


def test_conference_deadline_service_add_past():
	service = ConferenceAbstractDeadlineService()
	dl = service.add_deadline(
		"dl_002",
		"Old Conference",
		SubmissionType.REGISTRATION,
		date(2025, 1, 1),
	)
	assert dl.status == DeadlineStatus.PASSED
	assert dl.days_until_due < 0


def test_conference_deadline_service_mark_submitted():
	service = ConferenceAbstractDeadlineService()
	service.add_deadline("dl_003", "AANP 2026", SubmissionType.ABSTRACT, date(2026, 9, 30))
	result = service.mark_submitted("dl_003")
	assert result is True
	assert service._deadlines["dl_003"].status == DeadlineStatus.SUBMITTED


def test_conference_deadline_service_summary():
	service = ConferenceAbstractDeadlineService()
	service.add_deadline("dl_004", "Conf A", SubmissionType.ABSTRACT, date(2026, 12, 1))
	service.add_deadline("dl_005", "Conf B", SubmissionType.POSTER, date(2025, 1, 1))
	summary = service.get_summary()
	assert summary.total_tracked == 2
	assert summary.passed >= 1


@pytest.mark.asyncio
async def test_conference_deadline_agent_full_lifecycle():
	agent = ConferenceAbstractDeadlineAgent()
	assert agent.workflow_id == "conference_abstract_deadline"
	event = WorkflowEvent(event_type="deadline_check_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "deadline" in result.summary.lower() or "conference" in result.summary.lower()


# ── Estimated Tax Calculator ──────────────────────────────────────────────────
from atlas.workflows.tax_legal.estimated_tax_calculator import (
	EstimatedTaxCalculatorWorkflow,
	EstimatedTaxService,
	IncomeEntry,
	TaxQuarter,
	FilingStatus,
)


def test_estimated_tax_service_calculate_tax():
	service = EstimatedTaxService()
	assert service.calculate_federal_tax(50000.0) > 0
	assert service.calculate_federal_tax(0.0) == 0.0


def test_estimated_tax_service_quarterly_estimate():
	service = EstimatedTaxService()
	service.add_income(IncomeEntry("inc1", "W2 Job", 30000.0, TaxQuarter.Q1, is_self_employment=False))
	estimate = service.calculate_quarterly_estimate(TaxQuarter.Q1)
	assert estimate.total_income == 30000.0
	assert estimate.federal_tax_owed >= 0
	assert estimate.total_payment_due >= 0


def test_estimated_tax_service_se_tax():
	service = EstimatedTaxService()
	service.add_income(IncomeEntry("inc2", "Consulting", 20000.0, TaxQuarter.Q1, is_self_employment=True))
	estimate = service.calculate_quarterly_estimate(TaxQuarter.Q1)
	assert estimate.self_employment_tax > 0


def test_estimated_tax_service_annual_summary():
	service = EstimatedTaxService()
	for q in TaxQuarter:
		service.add_income(IncomeEntry(f"inc_{q}", "W2", 25000.0, q))
	summary = service.get_annual_summary()
	assert summary.annual_income_estimate == 100000.0
	assert summary.total_annual_tax > 0
	assert summary.quarterly_payment > 0
	assert summary.effective_tax_rate > 0


@pytest.mark.asyncio
async def test_estimated_tax_calculator_full_lifecycle():
	agent = EstimatedTaxCalculatorWorkflow()
	assert agent.workflow_id == "estimated_tax_calculator"
	event = WorkflowEvent(event_type="tax_estimate_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "tax" in result.summary.lower()


# ── Seasonal Prep Agent ───────────────────────────────────────────────────────
from atlas.workflows.home.seasonal_prep_agent import (
	SeasonalPrepAgent,
	SeasonalPrepService,
	Season,
	ChecklistItemStatus,
)


def test_seasonal_prep_service_generate_spring():
	service = SeasonalPrepService()
	checklist = service.generate_checklist("chk_001", Season.SPRING)
	assert checklist.season == Season.SPRING
	assert checklist.total_items > 0
	assert checklist.estimated_total_hours > 0


def test_seasonal_prep_service_generate_all_seasons():
	service = SeasonalPrepService()
	for season in Season:
		checklist = service.generate_checklist(f"chk_{season.value}", season)
		assert checklist.total_items > 0


def test_seasonal_prep_service_complete_item():
	service = SeasonalPrepService()
	checklist = service.generate_checklist("chk_001", Season.FALL)
	first_item = checklist.items[0]
	result = service.complete_item("chk_001", first_item.item_id)
	assert result is True
	completed, total, pct = service.get_progress("chk_001")
	assert completed == 1
	assert pct > 0.0


def test_seasonal_prep_service_high_priority():
	service = SeasonalPrepService()
	service.generate_checklist("chk_001", Season.WINTER)
	high_priority = service.get_high_priority_items("chk_001")
	assert isinstance(high_priority, list)
	assert all(item.priority == 1 for item in high_priority)


def test_seasonal_prep_service_infer_season():
	service = SeasonalPrepService()
	season = service.infer_current_season()
	assert season in list(Season)


@pytest.mark.asyncio
async def test_seasonal_prep_agent_full_lifecycle():
	agent = SeasonalPrepAgent()
	assert agent.workflow_id == "seasonal_prep"
	event = WorkflowEvent(event_type="seasonal_prep_requested", payload={"season": "spring"})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "prep" in result.summary.lower() or "checklist" in result.summary.lower()


# ── Warranty Tracker ──────────────────────────────────────────────────────────
from atlas.workflows.home.warranty_tracker import (
	WarrantyTrackerAgent,
	WarrantyTrackerService,
	WarrantyCategory,
	WarrantyStatus,
)


def test_warranty_tracker_service_add_active():
	service = WarrantyTrackerService()
	item = service.add_warranty(
		"w001",
		"Samsung Washer",
		WarrantyCategory.APPLIANCE,
		date(2024, 1, 1),
		date(2027, 1, 1),
		manufacturer="Samsung",
		purchase_price=800.0,
	)
	assert item.warranty_id == "w001"
	assert item.status == WarrantyStatus.ACTIVE
	assert item.days_remaining > 0


def test_warranty_tracker_service_add_expired():
	service = WarrantyTrackerService()
	item = service.add_warranty(
		"w002",
		"Old TV",
		WarrantyCategory.ELECTRONICS,
		date(2020, 1, 1),
		date(2022, 1, 1),
	)
	assert item.status == WarrantyStatus.EXPIRED
	assert item.days_remaining < 0


def test_warranty_tracker_service_expiring_soon():
	service = WarrantyTrackerService()
	# Expiring in 30 days
	from datetime import timedelta
	expiry = date.today() + timedelta(days=30)
	service.add_warranty("w003", "HVAC System", WarrantyCategory.HVAC, date(2022, 1, 1), expiry)
	expiring = service.get_expiring_soon()
	assert len(expiring) == 1
	assert expiring[0].status == WarrantyStatus.EXPIRING_SOON


def test_warranty_tracker_service_mark_claimed():
	service = WarrantyTrackerService()
	service.add_warranty(
		"w004", "Refrigerator", WarrantyCategory.APPLIANCE,
		date(2024, 1, 1), date(2027, 1, 1),
	)
	result = service.mark_claimed("w004")
	assert result is True
	assert service._warranties["w004"].status == WarrantyStatus.CLAIMED


def test_warranty_tracker_service_summary():
	service = WarrantyTrackerService()
	service.add_warranty("w005", "Dishwasher", WarrantyCategory.APPLIANCE, date(2024, 1, 1), date(2027, 1, 1))
	service.add_warranty("w006", "Old Laptop", WarrantyCategory.ELECTRONICS, date(2018, 1, 1), date(2020, 1, 1))
	summary = service.get_summary()
	assert summary.total_tracked == 2
	assert summary.active_count >= 1
	assert summary.expired_count >= 1


@pytest.mark.asyncio
async def test_warranty_tracker_agent_full_lifecycle():
	agent = WarrantyTrackerAgent()
	assert agent.workflow_id == "warranty_tracker"
	event = WorkflowEvent(event_type="warranty_check_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "warrant" in result.summary.lower()
