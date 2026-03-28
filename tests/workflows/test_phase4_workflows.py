"""Tests for Phase 4 workflows — Budget, Property, and Travel domains."""

import pytest
from atlas.workflows.budget.cash_flow_planner import CashFlowPlannerAgent, CashFlowService
from atlas.workflows.budget.credit_limit_optimization import CreditLimitOptimizationAgent, CreditLimitService
from atlas.workflows.budget.debt_refinance_architect import DebtRefinanceArchitectAgent, DebtRefinanceService
from atlas.workflows.property.buyer_readiness import BuyerReadinessAgent, BuyerReadinessService
from atlas.workflows.property.investor_template import InvestmentTemplateAgent, InvestmentTemplateService
from atlas.workflows.property.move_specialist import MoveSpecialistAgent, MoveSpecialistService
from atlas.workflows.property.portfolio_overview import PortfolioOverviewAgent, PortfolioOverviewService
from atlas.workflows.travel.trip_cost_analyzer import TripCostAnalyzerAgent, TripCostService
from atlas.workflows.travel.travel_insurance_scout import TravelInsuranceScoutAgent, TravelInsuranceService
from atlas.workflows.travel.visa_tracker import VisaTrackerAgent, VisaTrackerService


# ────────────────────────────────────────────────────────────
# SERVICE TESTS
# ────────────────────────────────────────────────────────────


class TestPhase4Services:
	"""Tests for all Phase 4 services can be instantiated."""

	def test_debt_refinance_service(self):
		"""Test DebtRefinanceService instantiation."""
		service = DebtRefinanceService()
		assert service is not None

	def test_credit_limit_service(self):
		"""Test CreditLimitService instantiation."""
		service = CreditLimitService()
		assert service is not None

	def test_cash_flow_service(self):
		"""Test CashFlowService instantiation."""
		service = CashFlowService()
		assert service is not None

	def test_move_specialist_service(self):
		"""Test MoveSpecialistService instantiation."""
		service = MoveSpecialistService()
		assert service is not None

	def test_portfolio_overview_service(self):
		"""Test PortfolioOverviewService instantiation."""
		service = PortfolioOverviewService()
		assert service is not None

	def test_buyer_readiness_service(self):
		"""Test BuyerReadinessService instantiation."""
		service = BuyerReadinessService()
		assert service is not None

	def test_investment_template_service(self):
		"""Test InvestmentTemplateService instantiation."""
		service = InvestmentTemplateService()
		assert service is not None
		templates = service.list_templates()
		assert isinstance(templates, list)

	def test_trip_cost_service(self):
		"""Test TripCostService instantiation."""
		service = TripCostService()
		assert service is not None

	def test_visa_tracker_service(self):
		"""Test VisaTrackerService instantiation."""
		service = VisaTrackerService()
		assert service is not None
		renewals = service.upcoming_renewals()
		assert isinstance(renewals, list)

	def test_travel_insurance_service(self):
		"""Test TravelInsuranceService instantiation."""
		service = TravelInsuranceService()
		assert service is not None
		recommendations = service.recommend_insurance(14, 5000, "medium")
		assert len(recommendations) > 0


# ────────────────────────────────────────────────────────────
# WORKFLOW INSTANTIATION TESTS
# ────────────────────────────────────────────────────────────


class TestPhase4WorkflowInstantiation:
	"""Tests for all Phase 4 workflows can be instantiated."""

	def test_debt_refinance_workflow(self):
		"""Test DebtRefinanceArchitectAgent instantiation."""
		workflow = DebtRefinanceArchitectAgent()
		assert workflow.workflow_id == "debt_refinance_architect"
		assert workflow.name == "Debt Refinance Architect"
		assert workflow.category == "budget"

	def test_credit_limit_workflow(self):
		"""Test CreditLimitOptimizationAgent instantiation."""
		workflow = CreditLimitOptimizationAgent()
		assert workflow.workflow_id == "credit_limit_optimization"
		assert workflow.name == "Credit Limit Optimization"
		assert workflow.category == "budget"

	def test_cash_flow_workflow(self):
		"""Test CashFlowPlannerAgent instantiation."""
		workflow = CashFlowPlannerAgent()
		assert workflow.workflow_id == "cash_flow_planner"
		assert workflow.category == "budget"

	def test_move_specialist_workflow(self):
		"""Test MoveSpecialistAgent instantiation."""
		workflow = MoveSpecialistAgent()
		assert workflow.workflow_id == "move_specialist"
		assert workflow.category == "property"

	def test_portfolio_overview_workflow(self):
		"""Test PortfolioOverviewAgent instantiation."""
		workflow = PortfolioOverviewAgent()
		assert workflow.workflow_id == "portfolio_overview"
		assert workflow.category == "property"

	def test_buyer_readiness_workflow(self):
		"""Test BuyerReadinessAgent instantiation."""
		workflow = BuyerReadinessAgent()
		assert workflow.workflow_id == "buyer_readiness"
		assert workflow.category == "property"

	def test_investor_template_workflow(self):
		"""Test InvestmentTemplateAgent instantiation."""
		workflow = InvestmentTemplateAgent()
		assert workflow.workflow_id == "investor_template"
		assert workflow.category == "property"

	def test_trip_cost_analyzer_workflow(self):
		"""Test TripCostAnalyzerAgent instantiation."""
		workflow = TripCostAnalyzerAgent()
		assert workflow.workflow_id == "trip_cost_analyzer"
		assert workflow.category == "travel"

	def test_visa_tracker_workflow(self):
		"""Test VisaTrackerAgent instantiation."""
		workflow = VisaTrackerAgent()
		assert workflow.workflow_id == "visa_tracker"
		assert workflow.category == "travel"

	def test_travel_insurance_scout_workflow(self):
		"""Test TravelInsuranceScoutAgent instantiation."""
		workflow = TravelInsuranceScoutAgent()
		assert workflow.workflow_id == "travel_insurance_scout"
		assert workflow.category == "travel"


# ────────────────────────────────────────────────────────────
# SERVICE METHOD TESTS
# ────────────────────────────────────────────────────────────


class TestPhase4ServiceMethods:
	"""Tests for Phase 4 service methods."""

	def test_debt_refinance_payment_calculation(self):
		"""Test liability payment calculation."""
		service = DebtRefinanceService()
		payment = service._calculate_payment(100000, 5.0, 360)
		assert 535 < payment < 545

	def test_credit_limit_analyze_card(self):
		"""Test credit limit card analysis."""
		service = CreditLimitService()
		if service._cards:
			card_id = next(iter(service._cards.keys()))
			recommendation = service.analyze_card(card_id, 760)
			assert recommendation is not None

	def test_travel_insurance_value_ratio(self):
		"""Test insurance recommendations are sorted by value."""
		service = TravelInsuranceService()
		recommendations = service.recommend_insurance(7, 3000, "low")
		if len(recommendations) > 1:
			for i in range(len(recommendations) - 1):
				assert recommendations[i].value_ratio >= recommendations[i + 1].value_ratio
