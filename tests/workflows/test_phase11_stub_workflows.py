"""Tests for Phase 11 score-8 stub-reduction workflows:
Malpractice Coverage Review Agent, Professional Network Nurture Agent,
Contract Negotiation Prep Agent, Utility Rate Optimizer,
and Product Research Agent.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from atlas.core.workflow.base import WorkflowEvent

# Malpractice Coverage Review Agent
from atlas.workflows.licensure.malpractice_coverage_review_agent import (
	MalpracticeCoverageReviewAgent,
	MalpracticeCoverageReviewService,
	MalpracticeStatus,
)


def test_malpractice_add_policy():
	service = MalpracticeCoverageReviewService()
	policy = service.add_policy("m001", "Carrier A", date.today() + timedelta(days=90), 12000.0, 11000.0, 1000000.0)
	assert policy.policy_id == "m001"
	assert policy.status == MalpracticeStatus.ACTIVE


def test_malpractice_review_due():
	service = MalpracticeCoverageReviewService()
	service.add_policy("m002", "Carrier B", date.today() + timedelta(days=20), 11500.0, 11000.0, 1000000.0)
	due = service.get_review_due()
	assert len(due) == 1


def test_malpractice_expired():
	service = MalpracticeCoverageReviewService()
	service.add_policy("m003", "Carrier C", date.today() - timedelta(days=1), 12000.0, 12000.0, 1000000.0)
	summary = service.get_summary()
	assert summary.expired == 1


def test_malpractice_premium_change():
	service = MalpracticeCoverageReviewService()
	policy = service.add_policy("m004", "Carrier D", date.today() + timedelta(days=180), 13000.0, 10000.0, 1000000.0)
	assert policy.premium_change_pct() == pytest.approx(30.0)


def test_malpractice_summary():
	service = MalpracticeCoverageReviewService()
	service.add_policy("m005", "Carrier E", date.today() + timedelta(days=35), 12500.0, 12000.0, 1000000.0)
	summary = service.get_summary()
	assert summary.total_policies == 1
	assert summary.review_due == 1


@pytest.mark.asyncio
async def test_malpractice_coverage_review_lifecycle():
	agent = MalpracticeCoverageReviewAgent()
	event = WorkflowEvent(event_type="malpractice_review_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "malpractice" in result.summary.lower()


# Professional Network Nurture Agent
from atlas.workflows.career.professional_network_nurture_agent import (
	ProfessionalNetworkNurtureAgent,
	ProfessionalNetworkNurtureService,
	ContactTier,
)


def test_network_add_contact():
	service = ProfessionalNetworkNurtureService()
	contact = service.add_contact("n001", "Alex", "Former manager", ContactTier.CORE, date.today() - timedelta(days=10), 30)
	assert contact.contact_id == "n001"


def test_network_due_outreach():
	service = ProfessionalNetworkNurtureService()
	service.add_contact("n002", "Morgan", "Mentor", ContactTier.IMPORTANT, date.today() - timedelta(days=40), 30)
	due = service.get_due_outreach()
	assert len(due) == 1


def test_network_log_outreach():
	service = ProfessionalNetworkNurtureService()
	service.add_contact("n003", "Jamie", "Colleague", ContactTier.EXTENDED, date.today() - timedelta(days=20), 30)
	assert service.log_outreach("n003") is True
	assert service._contacts["n003"].days_since_touchpoint() <= 1


def test_network_overdue():
	service = ProfessionalNetworkNurtureService()
	service.add_contact("n004", "Taylor", "Advisor", ContactTier.CORE, date.today() - timedelta(days=80), 30)
	summary = service.get_summary()
	assert summary.overdue_outreach == 1


def test_network_summary():
	service = ProfessionalNetworkNurtureService()
	service.add_contact("n005", "Riley", "Peer", ContactTier.IMPORTANT, date.today() - timedelta(days=35), 30)
	summary = service.get_summary()
	assert summary.total_contacts == 1
	assert summary.due_outreach == 1


@pytest.mark.asyncio
async def test_network_nurture_lifecycle():
	agent = ProfessionalNetworkNurtureAgent()
	event = WorkflowEvent(event_type="network_review_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "network nurture" in result.summary.lower()


# Contract Negotiation Prep Agent
from atlas.workflows.career.contract_negotiation_prep_agent import (
	ContractNegotiationPrepAgent,
	ContractNegotiationPrepService,
	NegotiationStatus,
)


def test_contract_negotiation_add_case():
	service = ContractNegotiationPrepService()
	case = service.add_case("c001", "NP", "Clinic A", 120000.0, 140000.0)
	assert case.case_id == "c001"
	assert case.status == NegotiationStatus.PREP


def test_contract_negotiation_add_comparable():
	service = ContractNegotiationPrepService()
	service.add_case("c002", "NP", "Clinic B", 125000.0, 145000.0)
	assert service.add_comparable("c002", 138000.0) is True
	assert service._cases["c002"].comparables == [138000.0]


def test_contract_negotiation_add_talking_point():
	service = ContractNegotiationPrepService()
	service.add_case("c003", "NP", "Clinic C", 130000.0, 150000.0)
	assert service.add_talking_point("c003", "Quality metrics exceeded target") is True
	assert len(service._cases["c003"].talking_points) == 1


def test_contract_negotiation_start():
	service = ContractNegotiationPrepService()
	service.add_case("c004", "NP", "Clinic D", 132000.0, 148000.0)
	assert service.start_negotiation("c004") is True
	assert service._cases["c004"].status == NegotiationStatus.IN_PROGRESS


def test_contract_negotiation_summary():
	service = ContractNegotiationPrepService()
	service.add_case("c005", "NP", "Clinic E", 120000.0, 150000.0)
	summary = service.get_summary()
	assert summary.total_cases == 1
	assert summary.avg_offer_gap == pytest.approx(30000.0)


@pytest.mark.asyncio
async def test_contract_negotiation_lifecycle():
	agent = ContractNegotiationPrepAgent()
	event = WorkflowEvent(event_type="contract_negotiation_prep_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "contract negotiation prep" in result.summary.lower()


# Utility Rate Optimizer
from atlas.workflows.home.utility_rate_optimizer import (
	UtilityRateOptimizerWorkflow,
	UtilityRateOptimizerService,
	UtilityType,
)


def test_utility_add_plan():
	service = UtilityRateOptimizerService()
	plan = service.add_plan("u001", "Provider A", UtilityType.ELECTRIC, 0.18, 1000.0, 0.14)
	assert plan.plan_id == "u001"


def test_utility_optimizable():
	service = UtilityRateOptimizerService()
	service.add_plan("u002", "Provider B", UtilityType.GAS, 1.50, 100.0, 1.00)
	opt = service.get_optimizable()
	assert len(opt) == 1


def test_utility_not_optimizable():
	service = UtilityRateOptimizerService()
	service.add_plan("u003", "Provider C", UtilityType.WATER, 0.02, 5000.0, 0.02)
	opt = service.get_optimizable()
	assert len(opt) == 0


def test_utility_monthly_savings_calc():
	service = UtilityRateOptimizerService()
	plan = service.add_plan("u004", "Provider D", UtilityType.INTERNET, 80.0, 1.0, 60.0)
	assert plan.estimated_monthly_savings() == pytest.approx(20.0)


def test_utility_summary():
	service = UtilityRateOptimizerService()
	service.add_plan("u005", "Provider E", UtilityType.ELECTRIC, 0.20, 900.0, 0.15)
	summary = service.get_summary()
	assert summary.total_plans == 1
	assert summary.optimizable == 1


@pytest.mark.asyncio
async def test_utility_rate_optimizer_lifecycle():
	agent = UtilityRateOptimizerWorkflow()
	event = WorkflowEvent(event_type="utility_rate_review_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "utility optimizer" in result.summary.lower()


# Product Research Agent
from atlas.workflows.shopping.product_research_agent import (
	ProductResearchAgent,
	ProductResearchService,
	ResearchStatus,
)


def test_product_research_add_candidate():
	service = ProductResearchService()
	c = service.add_candidate("p001", "Widget A", "electronics", 99.0, 4.5, 900)
	assert c.product_id == "p001"


def test_product_research_shortlist():
	service = ProductResearchService()
	c = service.add_candidate("p002", "Widget B", "electronics", 80.0, 4.8, 1000)
	assert c.status in (ResearchStatus.SHORTLISTED, ResearchStatus.RESEARCHING)


def test_product_research_mark_selected():
	service = ProductResearchService()
	service.add_candidate("p003", "Widget C", "home", 75.0, 4.2, 200)
	assert service.mark_selected("p003") is True
	assert service._candidates["p003"].status == ResearchStatus.SELECTED


def test_product_research_get_shortlist():
	service = ProductResearchService()
	service.add_candidate("p004", "Widget D", "home", 60.0, 4.9, 1200)
	short = service.get_shortlist()
	assert len(short) >= 1


def test_product_research_summary():
	service = ProductResearchService()
	service.add_candidate("p005", "Widget E", "office", 49.0, 4.6, 350)
	summary = service.get_summary()
	assert summary.total_candidates == 1
	assert summary.best_candidate != ""


@pytest.mark.asyncio
async def test_product_research_lifecycle():
	agent = ProductResearchAgent()
	event = WorkflowEvent(event_type="product_research_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "product research" in result.summary.lower()
