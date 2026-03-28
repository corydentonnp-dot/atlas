"""Tests for Phase 3B workflow implementations."""

from datetime import date, timedelta

from atlas.workflows.budget.shared_household_spend_summary_agent import (
	HouseholdSpendEntry,
	SharedHouseholdSpendSummaryAgent,
	SharedHouseholdSpendSummaryService,
	SpendCategory,
)
from atlas.workflows.budget.subscription_tracker import (
	BillingCycle,
	Subscription,
	SubscriptionTrackerService,
	SubscriptionTrackerWorkflow,
	SubscriptionStatus,
)
from atlas.workflows.property.insurance_proof_tracker import (
	InsuranceProof,
	InsuranceProofService,
	InsuranceProofTrackerWorkflow,
	InsuranceStatus,
)
from atlas.workflows.property.renewal_prompt_agent import LeaseRenewal, RenewalPromptAgent, RenewalPromptService, RenewalStatus
from atlas.workflows.property.utility_setup_reminder_agent import (
	MoveInUtilityPlan,
	UtilitySetupReminderAgent,
	UtilitySetupService,
	UtilityStatus,
)
from atlas.workflows.additional.private_intent_capture_router import (
	PrivateIntentCaptureRouterWorkflow,
	PrivateIntentCaptureService,
	IntentStatus,
)


class TestInsuranceProofService:
	def test_check_expiring_returns_alert(self) -> None:
		service = InsuranceProofService()
		today = date.today()
		service.add_proof(
			InsuranceProof(
				proof_id="proof-1",
				tenant_id="tenant-1",
				tenant_name="Taylor",
				property_name="Oak House",
				unit="2A",
				provider="Lemonade",
				policy_number="POL123",
				coverage_amount=100000.0,
				expiry_date=today + timedelta(days=10),
			)
		)
		alerts = service.check_expiring(days_ahead=30, today=today)
		assert len(alerts) == 1
		assert alerts[0].status == InsuranceStatus.EXPIRING

	def test_missing_for_tenants_builds_placeholder(self) -> None:
		service = InsuranceProofService()
		missing = service.missing_for_tenants([
			{"tenant_id": "tenant-2", "tenant_name": "Jordan", "property_name": "Maple", "unit": "5B"}
		])
		assert len(missing) == 1
		assert missing[0].status == InsuranceStatus.MISSING


class TestUtilitySetupService:
	def test_create_plan_builds_default_tasks(self) -> None:
		service = UtilitySetupService()
		plan = service.create_plan(
			MoveInUtilityPlan(
				plan_id="move-1",
				tenant_id="tenant-1",
				tenant_name="Taylor",
				property_name="Oak House",
				unit="2A",
				move_in_date=date.today() + timedelta(days=7),
			)
		)
		assert len(plan.tasks) == 5

	def test_mark_connected_updates_completion_rate(self) -> None:
		service = UtilitySetupService()
		plan = service.create_plan(
			MoveInUtilityPlan(
				plan_id="move-2",
				tenant_id="tenant-2",
				tenant_name="Jordan",
				property_name="Maple",
				unit="5B",
				move_in_date=date.today() + timedelta(days=3),
			)
		)
		assert service.mark_connected(plan.tasks[0].task_id, "CONF-1")
		assert service.completion_rate() == 0.2


class TestRenewalPromptService:
	def test_upcoming_prompts_marks_prompt_due(self) -> None:
		service = RenewalPromptService()
		lease = service.add_lease(
			LeaseRenewal(
				renewal_id="lease-1",
				tenant_id="tenant-1",
				tenant_name="Taylor",
				property_name="Oak House",
				unit="2A",
				lease_end_date=date.today() + timedelta(days=45),
				current_rent=1800.0,
			)
		)
		prompts = service.upcoming_prompts(today=date.today())
		assert len(prompts) == 1
		assert lease.status == RenewalStatus.PROMPT_DUE

	def test_record_response_marks_renewed(self) -> None:
		service = RenewalPromptService()
		service.add_lease(
			LeaseRenewal(
				renewal_id="lease-2",
				tenant_id="tenant-2",
				tenant_name="Jordan",
				property_name="Maple",
				unit="5B",
				lease_end_date=date.today() + timedelta(days=30),
				current_rent=2100.0,
			)
		)
		assert service.record_response("lease-2", "Tenant accepted 12 months", accepted=True)


class TestSubscriptionTrackerService:
	def test_upcoming_renewals_filters_by_window(self) -> None:
		service = SubscriptionTrackerService()
		today = date.today()
		service.add_subscription(
			Subscription(
				subscription_id="sub-1",
				vendor="Netflix",
				service_name="Streaming",
				amount=19.99,
				billing_cycle=BillingCycle.MONTHLY,
				renewal_date=today + timedelta(days=5),
			)
		)
		service.add_subscription(
			Subscription(
				subscription_id="sub-2",
				vendor="Costco",
				service_name="Membership",
				amount=120.0,
				billing_cycle=BillingCycle.ANNUAL,
				renewal_date=today + timedelta(days=60),
			)
		)
		alerts = service.upcoming_renewals(today=today, days_ahead=30)
		assert len(alerts) == 1
		assert alerts[0].vendor == "Netflix"

	def test_estimate_monthly_spend_normalizes_cycles(self) -> None:
		service = SubscriptionTrackerService()
		service.add_subscription(
			Subscription(
				subscription_id="sub-1",
				vendor="Netflix",
				service_name="Streaming",
				amount=20.0,
				billing_cycle=BillingCycle.MONTHLY,
				renewal_date=date.today() + timedelta(days=5),
			)
		)
		service.add_subscription(
			Subscription(
				subscription_id="sub-2",
				vendor="Warehouse Club",
				service_name="Membership",
				amount=120.0,
				billing_cycle=BillingCycle.ANNUAL,
				renewal_date=date.today() + timedelta(days=90),
			)
		)
		assert service.estimate_monthly_spend() == 30.0

	def test_mark_cancel_scheduled(self) -> None:
		service = SubscriptionTrackerService()
		service.add_subscription(
			Subscription(
				subscription_id="sub-3",
				vendor="Spotify",
				service_name="Music",
				amount=11.99,
				billing_cycle=BillingCycle.MONTHLY,
				renewal_date=date.today() + timedelta(days=9),
			)
		)
		assert service.mark_cancel_scheduled("sub-3")
		assert service._subscriptions["sub-3"].status == SubscriptionStatus.CANCEL_SCHEDULED


class TestSharedHouseholdSpendSummaryService:
	def test_summarize_builds_totals_and_settlements(self) -> None:
		service = SharedHouseholdSpendSummaryService()
		today = date.today()
		service.add_entry(
			HouseholdSpendEntry(
				entry_id="e1",
				entry_date=today,
				merchant="Trader Joe's",
				amount=90.0,
				paid_by="Alex",
				shared_with=("Alex", "Casey", "Jordan"),
				category=SpendCategory.GROCERIES,
			)
		)
		service.add_entry(
			HouseholdSpendEntry(
				entry_id="e2",
				entry_date=today,
				merchant="Water Utility",
				amount=60.0,
				paid_by="Casey",
				shared_with=("Alex", "Casey", "Jordan"),
				category=SpendCategory.UTILITIES,
			)
		)
		summary = service.summarize(period_start=today - timedelta(days=1), period_end=today + timedelta(days=1))
		assert summary.total_spend == 150.0
		assert summary.by_category["groceries"] == 90.0
		assert len(summary.settlements) >= 1


class TestPrivateIntentCaptureService:
	def test_capture_intent_routes_subscription_request(self) -> None:
		service = PrivateIntentCaptureService()
		intent = service.capture_intent("intent-1", "Please cancel this subscription before it auto-renews next month")
		assert intent.route_workflow_id == "subscription_tracker"
		assert intent.status == IntentStatus.ROUTED

	def test_capture_intent_marks_low_confidence_for_review(self) -> None:
		service = PrivateIntentCaptureService()
		intent = service.capture_intent("intent-2", "Need to think about something soon")
		assert intent.status == IntentStatus.NEEDS_REVIEW
		assert intent.privacy_scope == "local_only"


class TestPhase3BWorkflowImports:
	def test_insurance_workflow_instantiates(self) -> None:
		workflow = InsuranceProofTrackerWorkflow()
		assert workflow.name == "insurance_proof_tracker"

	def test_utility_workflow_instantiates(self) -> None:
		workflow = UtilitySetupReminderAgent()
		assert workflow.name == "utility_setup_reminder_agent"
		assert workflow.category == "property"

	def test_renewal_workflow_instantiates(self) -> None:
		workflow = RenewalPromptAgent()
		assert workflow.name == "renewal_prompt_agent"

	def test_subscription_workflow_instantiates(self) -> None:
		workflow = SubscriptionTrackerWorkflow()
		assert workflow.name == "subscription_tracker"

	def test_spend_summary_workflow_instantiates(self) -> None:
		workflow = SharedHouseholdSpendSummaryAgent()
		assert workflow.name == "shared_household_spend_summary_agent"

	def test_private_intent_workflow_instantiates(self) -> None:
		workflow = PrivateIntentCaptureRouterWorkflow()
		assert workflow.name == "private_intent_capture_router"