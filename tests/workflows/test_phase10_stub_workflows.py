"""Tests for Phase 10 score-9/8 stub-reduction workflows:
Employment Document Tracker, Gift Idea Tracker, Trip Planner Agent,
Legal Document Review Agent, and Insurance Policy Review Agent.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from atlas.core.workflow.base import WorkflowEvent

# Employment Document Tracker
from atlas.workflows.licensure.employment_document_tracker import (
	EmploymentDocumentTrackerWorkflow,
	EmploymentDocumentTrackerService,
	EmploymentDocType,
	EmploymentDocStatus,
)


def test_employment_doc_add_active():
	service = EmploymentDocumentTrackerService()
	doc = service.add_document(
		"ed001", "Hospital Contract", EmploymentDocType.CONTRACT, "St. Mary", date.today(), date.today() + timedelta(days=90)
	)
	assert doc.doc_id == "ed001"
	assert doc.status == EmploymentDocStatus.ACTIVE


def test_employment_doc_due():
	service = EmploymentDocumentTrackerService()
	service.add_document(
		"ed002", "Privileges", EmploymentDocType.PRIVILEGES, "St. Mary", date.today(), date.today() + timedelta(days=15)
	)
	due = service.get_renewal_due()
	assert len(due) == 1


def test_employment_doc_expired():
	service = EmploymentDocumentTrackerService()
	service.add_document(
		"ed003", "Compliance", EmploymentDocType.COMPLIANCE, "St. Mary", date.today() - timedelta(days=400), date.today() - timedelta(days=2)
	)
	summary = service.get_summary()
	assert summary.expired >= 1


def test_employment_doc_archive():
	service = EmploymentDocumentTrackerService()
	service.add_document(
		"ed004", "Onboarding", EmploymentDocType.ONBOARDING, "St. Mary", date.today(), date.today() + timedelta(days=45)
	)
	assert service.archive_document("ed004") is True
	assert service._docs["ed004"].status == EmploymentDocStatus.ARCHIVED


def test_employment_doc_summary():
	service = EmploymentDocumentTrackerService()
	service.add_document(
		"ed005", "Credential", EmploymentDocType.OTHER, "St. Mary", date.today(), date.today() + timedelta(days=10)
	)
	summary = service.get_summary()
	assert summary.total_docs == 1
	assert summary.renewal_due == 1


@pytest.mark.asyncio
async def test_employment_document_tracker_lifecycle():
	agent = EmploymentDocumentTrackerWorkflow()
	event = WorkflowEvent(event_type="employment_doc_review_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "employment document tracker" in result.summary.lower()


# Gift Idea Tracker
from atlas.workflows.shopping.gift_idea_tracker import (
	GiftIdeaTrackerWorkflow,
	GiftIdeaTrackerService,
	OccasionType,
	GiftIdeaStatus,
)


def test_gift_idea_add():
	service = GiftIdeaTrackerService()
	idea = service.add_idea(
		"g001", "Alex", OccasionType.BIRTHDAY, date.today() + timedelta(days=30), "Coffee grinder", 95.0
	)
	assert idea.idea_id == "g001"
	assert idea.status == GiftIdeaStatus.IDEA


def test_gift_idea_mark_purchased():
	service = GiftIdeaTrackerService()
	service.add_idea("g002", "Morgan", OccasionType.HOLIDAY, date.today() + timedelta(days=20), "Book set", 45.0)
	assert service.mark_purchased("g002") is True
	assert service._ideas["g002"].status == GiftIdeaStatus.PURCHASED


def test_gift_idea_mark_gifted():
	service = GiftIdeaTrackerService()
	service.add_idea("g003", "Casey", OccasionType.ANNIVERSARY, date.today() + timedelta(days=40), "Dinner voucher", 120.0)
	assert service.mark_gifted("g003") is True
	assert service._ideas["g003"].status == GiftIdeaStatus.GIFTED


def test_gift_idea_occasions_soon():
	service = GiftIdeaTrackerService()
	service.add_idea("g004", "Jamie", OccasionType.BIRTHDAY, date.today() + timedelta(days=7), "Plant", 30.0)
	soon = service.get_occasions_soon()
	assert len(soon) == 1


def test_gift_idea_summary():
	service = GiftIdeaTrackerService()
	service.add_idea("g005", "Taylor", OccasionType.OTHER, date.today() + timedelta(days=14), "Gift card", 25.0)
	summary = service.get_summary()
	assert summary.total_ideas == 1
	assert summary.occasions_soon == 1


@pytest.mark.asyncio
async def test_gift_idea_tracker_lifecycle():
	agent = GiftIdeaTrackerWorkflow()
	event = WorkflowEvent(event_type="gift_review_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "gift idea tracker" in result.summary.lower()


# Trip Planner Agent
from atlas.workflows.travel.trip_planner_agent import (
	TripPlannerAgent,
	TripPlannerService,
	TripStatus,
)


def test_trip_planner_add_trip():
	service = TripPlannerService()
	trip = service.add_trip("t001", "Boston", date.today() + timedelta(days=30), date.today() + timedelta(days=36), 1800.0)
	assert trip.trip_id == "t001"
	assert trip.status == TripStatus.PLANNING


def test_trip_planner_add_itinerary_item():
	service = TripPlannerService()
	service.add_trip("t002", "Austin", date.today() + timedelta(days=40), date.today() + timedelta(days=44), 1500.0)
	assert service.add_itinerary_item("t002", "Museum visit") is True
	assert "Museum visit" in service._trips["t002"].itinerary


def test_trip_planner_mark_booked():
	service = TripPlannerService()
	service.add_trip("t003", "Denver", date.today() + timedelta(days=50), date.today() + timedelta(days=55), 1700.0)
	assert service.mark_booked("t003") is True
	assert service._trips["t003"].status == TripStatus.BOOKED


def test_trip_planner_get_upcoming():
	service = TripPlannerService()
	service.add_trip("t004", "Seattle", date.today() + timedelta(days=10), date.today() + timedelta(days=14), 1300.0)
	upcoming = service.get_upcoming()
	assert len(upcoming) == 1


def test_trip_planner_summary():
	service = TripPlannerService()
	service.add_trip("t005", "Miami", date.today() + timedelta(days=60), date.today() + timedelta(days=65), 2200.0)
	summary = service.get_summary()
	assert summary.total_trips == 1
	assert summary.upcoming == 1


@pytest.mark.asyncio
async def test_trip_planner_agent_lifecycle():
	agent = TripPlannerAgent()
	event = WorkflowEvent(event_type="trip_plan_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "trip planner" in result.summary.lower()


# Legal Document Review Agent
from atlas.workflows.tax_legal.legal_document_review_agent import (
	LegalDocumentReviewAgent,
	LegalDocumentReviewService,
	LegalDocumentType,
	LegalReviewStatus,
)


def test_legal_review_add_document():
	service = LegalDocumentReviewService()
	doc = service.add_document("l001", "Lease A", LegalDocumentType.LEASE, date.today(), date.today() + timedelta(days=40))
	assert doc.doc_id == "l001"
	assert doc.status == LegalReviewStatus.PENDING


def test_legal_review_mark_flagged():
	service = LegalDocumentReviewService()
	service.add_document("l002", "Vendor Contract", LegalDocumentType.CONTRACT, date.today(), date.today() + timedelta(days=120))
	assert service.review_document("l002", flags=["auto_renewal", "termination_fee"]) is True
	assert service._docs["l002"].status == LegalReviewStatus.FLAGGED


def test_legal_review_mark_reviewed_no_flags():
	service = LegalDocumentReviewService()
	service.add_document("l003", "NDA", LegalDocumentType.NDA, date.today())
	assert service.review_document("l003") is True
	assert service._docs["l003"].status == LegalReviewStatus.REVIEWED


def test_legal_review_renewing_soon():
	service = LegalDocumentReviewService()
	service.add_document("l004", "Service Agreement", LegalDocumentType.SERVICE_AGREEMENT, date.today(), date.today() + timedelta(days=20))
	soon = service.get_renewing_soon()
	assert len(soon) == 1


def test_legal_review_summary():
	service = LegalDocumentReviewService()
	service.add_document("l005", "Contract B", LegalDocumentType.CONTRACT, date.today(), date.today() + timedelta(days=25))
	service.review_document("l005", flags=["notice_period"])
	summary = service.get_summary()
	assert summary.total_docs == 1
	assert summary.flagged == 1


@pytest.mark.asyncio
async def test_legal_document_review_agent_lifecycle():
	agent = LegalDocumentReviewAgent()
	event = WorkflowEvent(event_type="legal_doc_review_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "legal document review" in result.summary.lower()


# Insurance Policy Review Agent
from atlas.workflows.tax_legal.insurance_policy_review_agent import (
	InsurancePolicyReviewAgent,
	InsurancePolicyReviewService,
	PolicyType,
	PolicyStatus,
)


def test_insurance_review_add_policy():
	service = InsurancePolicyReviewService()
	policy = service.add_policy("p001", PolicyType.AUTO, "State Farm", date.today() + timedelta(days=90), 100000.0, 100000.0)
	assert policy.policy_id == "p001"
	assert policy.status == PolicyStatus.ACTIVE


def test_insurance_review_due():
	service = InsurancePolicyReviewService()
	service.add_policy("p002", PolicyType.HOME, "Allstate", date.today() + timedelta(days=20), 250000.0, 250000.0)
	due = service.get_review_due()
	assert len(due) == 1


def test_insurance_review_underinsured():
	service = InsurancePolicyReviewService()
	service.add_policy("p003", PolicyType.LIFE, "AIG", date.today() + timedelta(days=100), 250000.0, 500000.0)
	under = service.get_underinsured()
	assert len(under) == 1


def test_insurance_review_lapsed():
	service = InsurancePolicyReviewService()
	service.add_policy("p004", PolicyType.RENTERS, "Lemonade", date.today() - timedelta(days=1), 50000.0, 50000.0)
	summary = service.get_summary()
	assert summary.lapsed == 1


def test_insurance_review_summary():
	service = InsurancePolicyReviewService()
	service.add_policy("p005", PolicyType.UMBRELLA, "Travelers", date.today() + timedelta(days=30), 500000.0, 600000.0)
	summary = service.get_summary()
	assert summary.total_policies == 1
	assert summary.review_due == 1


@pytest.mark.asyncio
async def test_insurance_policy_review_agent_lifecycle():
	agent = InsurancePolicyReviewAgent()
	event = WorkflowEvent(event_type="policy_review_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "insurance policy review" in result.summary.lower()
