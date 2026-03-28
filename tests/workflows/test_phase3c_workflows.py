"""Tests for Phase 3C workflow implementations (score 8-9 tier)."""

from datetime import date, timedelta

from atlas.workflows.budget.merchant_memory_agent import MerchantClass, MerchantMemoryService, MerchantMemoryAgent
from atlas.workflows.home.appliance_fixture_manual_librarian import (
	ApplianceFixtureManualLibrarian,
	ApplianceManual,
	ApplianceManualLibraryService,
	ApplianceType,
)
from atlas.workflows.licensure.ce_opportunity_agent import CEOpportunityAgent, CEOpportunityService
from atlas.workflows.property.deposit_accounting_prep_agent import (
	DepositAccounting,
	DepositAccountingPrepAgent,
	DepositAccountingService,
	DepositDeduction,
	DeductionCategory,
)
from atlas.workflows.property.lead_score_agent import LeadQualification, LeadScoreAgent, LeadScoringService, RentalLead
from atlas.workflows.property.move_in_sequence_agent import MoveInSequenceAgent, MoveInSequenceService
from atlas.workflows.property.move_out_sequence_agent import MoveOutSequenceAgent, MoveOutSequenceService


class TestDepositAccountingService:
	def test_calculate_refund(self) -> None:
		service = DepositAccountingService()
		accounting = service.create_accounting(
			DepositAccounting(
				accounting_id="dep-1",
				tenant_id="tenant-1",
				tenant_name="Alice",
				property_unit="2A",
				deposit_amount=1500.0,
				move_out_date=date.today(),
				deductions=[],
			)
		)
		service.add_deduction(
			"dep-1",
			DepositDeduction(
				deduction_id="ded-1",
				category=DeductionCategory.DAMAGE,
				description="Wall damage",
				amount=300.0,
				documented=True,
			),
		)
		refund = service.calculate_refund("dep-1")
		assert refund == 1200.0

	def test_documentation_summary(self) -> None:
		service = DepositAccountingService()
		accounting = service.create_accounting(
			DepositAccounting(
				accounting_id="dep-2",
				tenant_id="tenant-2",
				tenant_name="Bob",
				property_unit="3B",
				deposit_amount=2000.0,
				move_out_date=date.today(),
				deductions=[],
			)
		)
		service.add_deduction(
			"dep-2",
			DepositDeduction(
				deduction_id="ded-2",
				category=DeductionCategory.CLEANING,
				description="Professional cleaning required",
				amount=200.0,
				documented=True,
			),
		)
		summary = service.documentation_summary("dep-2")
		assert summary["documented_count"] == 1
		assert summary["documentation_complete"] is True


class TestMoveInSequenceService:
	def test_create_checklist_includes_defaults(self) -> None:
		service = MoveInSequenceService()
		checklist = service.create_checklist("tenant-1", date.today())
		assert len(checklist) > 5
		categories = {item.category for item in checklist}
		assert "keys" in categories
		assert "utilities" in categories

	def test_completion_rate(self) -> None:
		service = MoveInSequenceService()
		service.create_checklist("tenant-2", date.today())
		service.complete_item("tenant-2", "tenant-2-keys-0")
		rate = service.completion_rate("tenant-2")
		assert 0 < rate < 1.0


class TestMoveOutSequenceService:
	def test_create_sequence_builds_tasks(self) -> None:
		service = MoveOutSequenceService()
		tasks = service.create_sequence("tenant-1", date.today())
		assert len(tasks) == 8
		categories = {task.category for task in tasks}
		assert "walkthrough" in categories

	def test_completion_status(self) -> None:
		service = MoveOutSequenceService()
		service.create_sequence("tenant-2", date.today())
		service.mark_task_complete("tenant-2", "tenant-2-final_walkthrough")
		status = service.completion_status("tenant-2")
		assert status["completed_tasks"] == 1
		assert status["total_tasks"] == 8


class TestLeadScoringService:
	def test_score_strong_lead(self) -> None:
		service = LeadScoringService()
		lead = RentalLead(
			lead_id="lead-1",
			applicant_name="Carol",
			monthly_income=5000.0,
			annual_income=60000.0,
			requested_rent=1000.0,
			credit_score=750,
			employment_stable=True,
			references_available=True,
			move_in_timeline_days=30,
		)
		service.add_lead(lead)
		score = service.score_lead(lead)
		assert score.qualification == LeadQualification.STRONG
		assert score.total_score >= 8.0

	def test_score_unqualified_lead(self) -> None:
		service = LeadScoringService()
		lead = RentalLead(
			lead_id="lead-2",
			applicant_name="Dave",
			monthly_income=1000.0,
			annual_income=12000.0,
			requested_rent=2000.0,
			employment_stable=False,
			references_available=False,
			move_in_timeline_days=5,
		)
		service.add_lead(lead)
		score = service.score_lead(lead)
		assert score.qualification == LeadQualification.WEAK


class TestMerchantMemoryService:
	def test_learn_merchant(self) -> None:
		service = MerchantMemoryService()
		pattern = service.learn_merchant("Whole Foods Market", MerchantClass.GROCERIES)
		assert pattern.normalized_name == "whole foods market"
		assert pattern.classification == MerchantClass.GROCERIES

	def test_classify_by_keyword(self) -> None:
		service = MerchantMemoryService()
		result = service.classify_merchant("Trader Joe's")
		assert result is not None
		assert result.classification == MerchantClass.GROCERIES

	def test_confidence_increases_with_repetition(self) -> None:
		service = MerchantMemoryService()
		pattern1 = service.learn_merchant("Target", MerchantClass.HOUSEHOLD)
		assert pattern1.confidence == 0.7
		pattern2 = service.learn_merchant("Target", MerchantClass.HOUSEHOLD)
		assert pattern2.confidence == 0.8


class TestCEOpportunityService:
	def test_find_opportunities_returns_courses(self) -> None:
		service = CEOpportunityService()
		opportunities = service.find_opportunities()
		assert len(opportunities) >= 3

	def test_filter_by_cost(self) -> None:
		service = CEOpportunityService()
		opportunities = service.find_opportunities(max_cost=300.0)
		assert all(opp.cost <= 300.0 for opp in opportunities)


class TestApplianceManualLibraryService:
	def test_add_and_search_manual(self) -> None:
		service = ApplianceManualLibraryService()
		manual = ApplianceManual(
			manual_id="man-1",
			appliance_type=ApplianceType.HVAC,
			brand="Carrier",
			model="25HBC",
			install_date="2020-01-15",
		)
		service.add_manual(manual)
		results = service.search_by_type(ApplianceType.HVAC)
		assert len(results) == 1

	def test_library_summary(self) -> None:
		service = ApplianceManualLibraryService()
		service.add_manual(
			ApplianceManual(
				manual_id="man-2",
				appliance_type=ApplianceType.WATER_HEATER,
				brand="Rheem",
				model="G75",
			)
		)
		summary = service.library_summary()
		assert summary["total_manuals"] == 1


class TestPhase3CWorkflowImports:
	def test_deposit_accounting_workflow_instantiates(self) -> None:
		workflow = DepositAccountingPrepAgent()
		assert workflow.name == "deposit_accounting_prep_agent"

	def test_move_in_workflow_instantiates(self) -> None:
		workflow = MoveInSequenceAgent()
		assert workflow.name == "move_in_sequence_agent"

	def test_move_out_workflow_instantiates(self) -> None:
		workflow = MoveOutSequenceAgent()
		assert workflow.name == "move_out_sequence_agent"

	def test_lead_score_workflow_instantiates(self) -> None:
		workflow = LeadScoreAgent()
		assert workflow.name == "lead_score_agent"

	def test_merchant_memory_workflow_instantiates(self) -> None:
		workflow = MerchantMemoryAgent()
		assert workflow.name == "merchant_memory_agent"

	def test_ce_opportunity_workflow_instantiates(self) -> None:
		workflow = CEOpportunityAgent()
		assert workflow.name == "ce_opportunity_agent"

	def test_appliance_librarian_workflow_instantiates(self) -> None:
		workflow = ApplianceFixtureManualLibrarian()
		assert workflow.name == "appliance_fixture_manual_librarian"
