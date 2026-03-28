"""Tests for workflow registration."""

from atlas.core.workflow.registry import WorkflowRegistry
from atlas.workflows.additional.daily_briefing_agent import DailyBriefingAgent
from atlas.workflows.additional.emergency_protocol_agent import EmergencyProtocolAgent
from atlas.workflows.additional.event_coordination import EventCoordinationAgent
from atlas.workflows.additional.goal_tracker_agent import GoalTrackerAgent
from atlas.workflows.additional.private_intent_capture_router import PrivateIntentCaptureRouterWorkflow
from atlas.workflows.additional.system_check import SystemCheckAgent
from atlas.workflows.additional.system_health_monitor import SystemHealthMonitorWorkflow
from atlas.workflows.additional.weekly_review_agent import WeeklyReviewAgent
from atlas.workflows.budget.abnormal_purchase_detector import AbnormalPurchaseWorkflow
from atlas.workflows.budget.amazon_split_agent import AmazonSplitWorkflow
from atlas.workflows.budget.budget_drift_agent import BudgetDriftWorkflow
from atlas.workflows.budget.cash_flow_planner import CashFlowPlannerAgent
from atlas.workflows.budget.credit_limit_optimization import CreditLimitOptimizationAgent
from atlas.workflows.budget.debt_refinance_architect import DebtRefinanceArchitectAgent
from atlas.workflows.budget.duplicate_charge_detector import DuplicateChargeWorkflow
from atlas.workflows.budget.promo_apr_deadline_agent import PromoAprDeadlineWorkflow
from atlas.workflows.budget.refund_chase_agent import RefundChaseWorkflow
from atlas.workflows.budget.settlement_prep_agent import SettlementPrepWorkflow
from atlas.workflows.budget.shared_expense_classifier import SharedExpenseClassifierWorkflow
from atlas.workflows.property.buyer_readiness import BuyerReadinessAgent
from atlas.workflows.property.investor_template import InvestmentTemplateAgent
from atlas.workflows.property.maintenance_intake_agent import MaintenanceIntakeWorkflow
from atlas.workflows.property.move_specialist import MoveSpecialistAgent
from atlas.workflows.property.portfolio_overview import PortfolioOverviewAgent
from atlas.workflows.property.rent_reminder_agent import RentReminderWorkflow
from atlas.workflows.career.conference_abstract_deadline_agent import ConferenceAbstractDeadlineAgent
from atlas.workflows.home.seasonal_prep_agent import SeasonalPrepAgent
from atlas.workflows.home.warranty_tracker import WarrantyTrackerAgent
from atlas.workflows.tax_legal.deduction_capture_agent import DeductionCaptureAgent
from atlas.workflows.tax_legal.estimated_tax_calculator import EstimatedTaxCalculatorWorkflow
from atlas.workflows.tax_legal.filing_deadline_tracker import FilingDeadlineTrackerWorkflow
from atlas.workflows.career.job_board_monitor import JobBoardMonitorWorkflow
from atlas.workflows.communication.overdue_text_resurfacer import OverdueTextResurfacerWorkflow
from atlas.workflows.communication.promise_tracker import PromiseTrackerWorkflow
from atlas.workflows.shopping.restock_reminder_agent import RestockReminderAgent
from atlas.workflows.travel.travel_deal_monitor import TravelDealMonitorWorkflow
from atlas.workflows.travel.travel_insurance_scout import TravelInsuranceScoutAgent
from atlas.workflows.travel.trip_cost_analyzer import TripCostAnalyzerAgent
from atlas.workflows.travel.visa_tracker import VisaTrackerAgent
from atlas.workflows.shopping.price_drop_agent import PriceDropAgent
from atlas.workflows.shopping.return_window_tracker import ReturnWindowTrackerAgent
from atlas.workflows.shopping.subscription_optimizer import SubscriptionOptimizerAgent
from atlas.workflows.shopping.grocery_list_builder import GroceryListBuilderAgent
from atlas.workflows.tax_legal.document_vault_organizer import DocumentVaultOrganizerWorkflow
from atlas.workflows.licensure.credentialing_packet_agent import CredentialingPacketAgent
from atlas.workflows.home.smart_home_automation_agent import SmartHomeAutomationAgent
from atlas.workflows.career.resume_cv_update_agent import ResumeCvUpdateAgent
from atlas.workflows.shopping.coupon_aggregator import CouponAggregatorWorkflow
from atlas.workflows.property.furnished_finder_lead_responder import FurnishedFinderLeadResponderWorkflow
from atlas.workflows.licensure.employment_document_tracker import EmploymentDocumentTrackerWorkflow
from atlas.workflows.shopping.gift_idea_tracker import GiftIdeaTrackerWorkflow
from atlas.workflows.travel.trip_planner_agent import TripPlannerAgent
from atlas.workflows.tax_legal.legal_document_review_agent import LegalDocumentReviewAgent
from atlas.workflows.tax_legal.insurance_policy_review_agent import InsurancePolicyReviewAgent
from atlas.workflows.licensure.malpractice_coverage_review_agent import MalpracticeCoverageReviewAgent
from atlas.workflows.career.professional_network_nurture_agent import ProfessionalNetworkNurtureAgent
from atlas.workflows.career.contract_negotiation_prep_agent import ContractNegotiationPrepAgent
from atlas.workflows.home.utility_rate_optimizer import UtilityRateOptimizerWorkflow
from atlas.workflows.shopping.product_research_agent import ProductResearchAgent


def test_selected_workflows_register():
	registry = WorkflowRegistry()
	registry.register(PromoAprDeadlineWorkflow())
	registry.register(FilingDeadlineTrackerWorkflow())
	registry.register(MaintenanceIntakeWorkflow())
	registry.register(SharedExpenseClassifierWorkflow())
	registry.register(RentReminderWorkflow())
	registry.register(EventCoordinationAgent())
	registry.register(SystemCheckAgent())
	registry.register(DailyBriefingAgent())
	registry.register(WeeklyReviewAgent())
	registry.register(SystemHealthMonitorWorkflow())
	registry.register(GoalTrackerAgent())
	registry.register(PrivateIntentCaptureRouterWorkflow())
	registry.register(EmergencyProtocolAgent())
	registry.register(TravelInsuranceScoutAgent())
	# Phase 4 workflows
	registry.register(DebtRefinanceArchitectAgent())
	registry.register(CreditLimitOptimizationAgent())
	registry.register(CashFlowPlannerAgent())
	registry.register(MoveSpecialistAgent())
	registry.register(PortfolioOverviewAgent())
	registry.register(BuyerReadinessAgent())
	registry.register(InvestmentTemplateAgent())
	registry.register(TripCostAnalyzerAgent())
	registry.register(VisaTrackerAgent())
	# Phase 6 new stubs
	registry.register(DeductionCaptureAgent())
	# Phase 7 score-11 stubs
	registry.register(TravelDealMonitorWorkflow())
	registry.register(RestockReminderAgent())
	registry.register(PromiseTrackerWorkflow())
	registry.register(OverdueTextResurfacerWorkflow())
	registry.register(JobBoardMonitorWorkflow())
	registry.register(EstimatedTaxCalculatorWorkflow())
	registry.register(ConferenceAbstractDeadlineAgent())
	registry.register(SeasonalPrepAgent())
	registry.register(WarrantyTrackerAgent())
	# Phase 5 workflows
	registry.register(AbnormalPurchaseWorkflow())
	registry.register(AmazonSplitWorkflow())
	registry.register(BudgetDriftWorkflow())
	registry.register(DuplicateChargeWorkflow())
	registry.register(RefundChaseWorkflow())
	registry.register(SettlementPrepWorkflow())
	# Phase 8 score 14/13/12/10/10 stubs
	registry.register(PriceDropAgent())
	registry.register(ReturnWindowTrackerAgent())
	registry.register(SubscriptionOptimizerAgent())
	registry.register(GroceryListBuilderAgent())
	registry.register(DocumentVaultOrganizerWorkflow())
	# Phase 9 score-10 stubs
	registry.register(CredentialingPacketAgent())
	registry.register(SmartHomeAutomationAgent())
	registry.register(ResumeCvUpdateAgent())
	registry.register(CouponAggregatorWorkflow())
	registry.register(FurnishedFinderLeadResponderWorkflow())
	# Phase 10 score-9/8 stubs
	registry.register(EmploymentDocumentTrackerWorkflow())
	registry.register(GiftIdeaTrackerWorkflow())
	registry.register(TripPlannerAgent())
	registry.register(LegalDocumentReviewAgent())
	registry.register(InsurancePolicyReviewAgent())
	# Phase 11 score-8 stubs
	registry.register(MalpracticeCoverageReviewAgent())
	registry.register(ProfessionalNetworkNurtureAgent())
	registry.register(ContractNegotiationPrepAgent())
	registry.register(UtilityRateOptimizerWorkflow())
	registry.register(ProductResearchAgent())

	all_status = registry.list_all()
	workflow_ids = {status.workflow_id for status in all_status}

	assert workflow_ids == {
		"promo_apr_deadline",
		"filing_deadline_tracker",
		"maintenance_intake",
		"shared_expense_classifier",
		"rent_reminder",
		"event_coordination",
		"system_check",
		"daily_briefing",
		"weekly_review",
		"system_health_monitor",
		"goal_tracker",
		"private_intent_capture_router",
		"emergency_protocol",
		"travel_insurance_scout",
		# Phase 4 workflows
		"debt_refinance_architect",
		"credit_limit_optimization",
		"cash_flow_planner",
		"move_specialist",
		"portfolio_overview",
		"buyer_readiness",
		"investor_template",
		"trip_cost_analyzer",
		"visa_tracker",
		# Phase 6 new stubs
		"deduction_capture",
		# Phase 7 score-11 stubs
		"travel_deal_monitor",
		"restock_reminder",
		"promise_tracker",
		"overdue_text_resurfacer",
		"job_board_monitor",
		"estimated_tax_calculator",
		"conference_abstract_deadline",
		"seasonal_prep",
		"warranty_tracker",
		# Phase 5 workflows
		"abnormal_purchase",
		"amazon_split",
		"budget_drift",
		"duplicate_charge",
		"refund_chase",
		"settlement_prep",
		# Phase 8 stubs
		"price_drop",
		"return_window_tracker",
		"subscription_optimizer",
		"grocery_list_builder",
		"document_vault_organizer",
		# Phase 9 stubs
		"credentialing_packet",
		"smart_home_automation",
		"resume_cv_update",
		"coupon_aggregator",
		"furnished_finder_lead_responder",
		# Phase 10 stubs
		"employment_document_tracker",
		"gift_idea_tracker",
		"trip_planner",
		"legal_document_review",
		"insurance_policy_review",
		# Phase 11 stubs
		"malpractice_coverage_review",
		"professional_network_nurture",
		"contract_negotiation_prep",
		"utility_rate_optimizer",
		"product_research",
	}
