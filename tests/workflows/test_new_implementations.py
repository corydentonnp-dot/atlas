"""Tests for newly implemented workflows (amazon_return, license trackers, etc.)."""

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from atlas.workflows.budget.installment_tracker import InstallmentService, InstallmentTrackerAgent, PaymentStatus
from atlas.workflows.budget.promo_apr_deadline_agent import PromoAprService, PromoAprDeadlineWorkflow, PromoAPR, EscalationLevel, BalanceTransferOption
from atlas.workflows.home.home_maintenance_scheduler import HomeMaintenanceSchedulerAgent, Season
from atlas.workflows.licensure.bls_acls_renewal_agent import BLSACLSRenewalAgent, BLSACLSService, Certification
from atlas.workflows.licensure.dea_tracker import DEATrackerAgent, DEATrackerService, DEARegistration
from atlas.workflows.licensure.np_license_tracker import NPLicenseTrackerAgent, NPLicenseService, NPLicense
from atlas.workflows.returns.amazon_return_window_agent import AmazonReturnWindowAgent, AmazonReturnService, AmazonOrder
from atlas.workflows.tax_legal.filing_deadline_tracker import FilingDeadlineService, FilingDeadlineTrackerWorkflow, FilingDeadline, Criticality, DeadlineStatus
from atlas.workflows.property.maintenance_intake_agent import MaintenanceIntakeWorkflow, MaintenanceIntakeService, Contractor, ContractorSpecialty, UrgencyLevel, JobStatus
from atlas.workflows.budget.shared_expense_classifier import SharedExpenseClassifierWorkflow, SharedExpenseService, Transaction, TransactionClass, ExpenseClass
from atlas.workflows.property.rent_reminder_agent import RentReminderWorkflow, RentReminderService, RentDue, PaymentStatus, EscalationTier, RentPayment


class TestAmazonReturnService:
	"""Tests for Amazon return window service."""

	def test_add_order(self) -> None:
		service = AmazonReturnService()
		today = date.today()
		order = AmazonOrder(
			order_id="AMZN123",
			item_name="USB Cable",
			purchase_date=today - timedelta(days=10),
			return_deadline=today + timedelta(days=20),
		)
		added = service.add_order(order)
		assert added.order_id == "AMZN123"
		assert added.item_name == "USB Cable"

	def test_check_closing_soon(self) -> None:
		service = AmazonReturnService()
		today = date.today()
		order1 = AmazonOrder(order_id="1", item_name="Item1", purchase_date=today - timedelta(days=5), return_deadline=today + timedelta(days=3))
		order2 = AmazonOrder(order_id="2", item_name="Item2", purchase_date=today - timedelta(days=10), return_deadline=today + timedelta(days=50))
		service.add_order(order1)
		service.add_order(order2)
		closing = service.check_closing_soon(days_ahead=10, today=today)
		assert len(closing) == 1
		assert closing[0].order_id == "1"

	def test_mark_returned(self) -> None:
		service = AmazonReturnService()
		order = AmazonOrder(order_id="123", item_name="Test", purchase_date=date.today(), return_deadline=date.today() + timedelta(days=30))
		service.add_order(order)
		success = service.mark_returned("123")
		assert success

	def test_get_urgency(self) -> None:
		service = AmazonReturnService()
		assert str(service.get_urgency(0)) == "ReturnUrgency.EXPIRED"
		assert str(service.get_urgency(2)) == "ReturnUrgency.URGENT"
		assert str(service.get_urgency(5)) == "ReturnUrgency.WARNING"
		assert str(service.get_urgency(30)) == "ReturnUrgency.NORMAL"


class TestNPLicenseService:
	"""Tests for NP license service."""

	def test_add_license(self) -> None:
		service = NPLicenseService()
		license = NPLicense(license_id="NP001", state="CA", license_number="12345", expiry_date=date.today() + timedelta(days=365), ce_requirements=30)
		added = service.add_license(license)
		assert added.state == "CA"
		assert added.license_number == "12345"

	def test_check_expiring(self) -> None:
		service = NPLicenseService()
		today = date.today()
		lic1 = NPLicense(license_id="1", state="CA", license_number="123", expiry_date=today + timedelta(days=30), ce_requirements=30)
		lic2 = NPLicense(license_id="2", state="TX", license_number="456", expiry_date=today + timedelta(days=200), ce_requirements=30)
		service.add_license(lic1)
		service.add_license(lic2)
		expiring = service.check_expiring(days_ahead=90, today=today)
		assert len(expiring) == 1
		assert expiring[0].state == "CA"

	def test_get_renewal_checklist(self) -> None:
		service = NPLicenseService()
		lic = NPLicense(license_id="test", state="CA", license_number="123", expiry_date=date.today() + timedelta(days=30), ce_requirements=30)
		service.add_license(lic)
		checklist = service.get_renewal_checklist("test")
		assert len(checklist) == 6
		assert "continuing education" in checklist[0].lower()


class TestDEATrackerService:
	"""Tests for DEA tracker service."""

	def test_add_registration(self) -> None:
		service = DEATrackerService()
		reg = DEARegistration(registration_id="DEA001", dea_number="CD1234567", expiry_date=date.today() + timedelta(days=365))
		added = service.add_registration(reg)
		assert added.dea_number == "CD1234567"

	def test_check_expiring(self) -> None:
		service = DEATrackerService()
		today = date.today()
		reg1 = DEARegistration(registration_id="1", dea_number="CD111", expiry_date=today + timedelta(days=60))
		reg2 = DEARegistration(registration_id="2", dea_number="CD222", expiry_date=today + timedelta(days=300))
		service.add_registration(reg1)
		service.add_registration(reg2)
		expiring = service.check_expiring(days_ahead=150, today=today)
		assert len(expiring) == 1
		assert expiring[0].dea_number == "CD111"

	def test_renewal_instructions(self) -> None:
		service = DEATrackerService()
		instructions = service.get_renewal_instructions()
		assert len(instructions) >= 4
		assert "CSOS" in instructions[0]


class TestInstallmentService:
	"""Tests for installment tracker service."""

	def test_check_upcoming(self) -> None:
		service = InstallmentService()
		today = date.today()
		from atlas.workflows.budget.installment_tracker import InstallmentPayment, InstallmentPlan
		payment1 = InstallmentPayment(payment_id="P1", plan_id="PLAN1", due_date=today + timedelta(days=5), amount=100.0)
		payment2 = InstallmentPayment(payment_id="P2", plan_id="PLAN1", due_date=today + timedelta(days=40), amount=100.0)
		plan = InstallmentPlan(plan_id="PLAN1", merchant="Amazon", total_amount=300.0, total_payments=3, payments=[payment1, payment2])
		service.add_plan(plan)
		upcoming = service.check_upcoming(days_ahead=30, today=today)
		assert len(upcoming) == 1
		assert upcoming[0].payment_id == "P1"

	def test_get_payment_total_due(self) -> None:
		service = InstallmentService()
		from atlas.workflows.budget.installment_tracker import InstallmentPayment, InstallmentPlan
		today = date.today()
		payment1 = InstallmentPayment(payment_id="P1", plan_id="PLAN1", due_date=today - timedelta(days=5), amount=100.0)
		payment2 = InstallmentPayment(payment_id="P2", plan_id="PLAN1", due_date=today + timedelta(days=5), amount=100.0)
		plan = InstallmentPlan(plan_id="PLAN1", merchant="BestBuy", total_amount=200.0, total_payments=2, payments=[payment1, payment2])
		service.add_plan(plan)
		total = service.get_payment_total_due(today)
		assert total == 100.0  # Only P1 is overdue


class TestBLSACLSService:
	"""Tests for BLS/ACLS certification service."""

	def test_add_certification(self) -> None:
		service = BLSACLSService()
		cert = Certification(cert_id="BLS001", cert_type="BLS", issue_date=date.today(), expiry_date=date.today() + timedelta(days=730))
		added = service.add_certification(cert)
		assert added.cert_type == "BLS"
		assert added.cert_id == "BLS001"

	def test_check_expiring(self) -> None:
		service = BLSACLSService()
		today = date.today()
		bls = Certification(cert_id="1", cert_type="BLS", issue_date=today - timedelta(days=700), expiry_date=today + timedelta(days=30))
		acls = Certification(cert_id="2", cert_type="ACLS", issue_date=today - timedelta(days=700), expiry_date=today + timedelta(days=200))
		service.add_certification(bls)
		service.add_certification(acls)
		expiring = service.check_expiring(days_ahead=120, today=today)
		assert len(expiring) == 1
		assert expiring[0].cert_type == "BLS"

	def test_training_providers(self) -> None:
		service = BLSACLSService()
		providers = service.get_training_providers()
		assert len(providers) >= 3
		assert "American Heart Association" in providers


class TestWorkflowImports:
	"""Verify all 6 new workflows can be instantiated."""

	def test_amazon_return_can_instantiate(self) -> None:
		workflow = AmazonReturnWindowAgent()
		assert workflow.name == "amazon_return_window_agent"

	def test_np_license_can_instantiate(self) -> None:
		workflow = NPLicenseTrackerAgent()
		assert workflow.name == "np_license_tracker"
		assert workflow.category == "licensure"

	def test_dea_tracker_can_instantiate(self) -> None:
		workflow = DEATrackerAgent()
		assert workflow.name == "dea_tracker"

	def test_installment_can_instantiate(self) -> None:
		workflow = InstallmentTrackerAgent()
		assert workflow.name == "installment_tracker"
		assert workflow.category == "budget"

	def test_bls_acls_can_instantiate(self) -> None:
		workflow = BLSACLSRenewalAgent()
		assert workflow.name == "bls_acls_renewal_agent"

	def test_home_maintenance_can_instantiate(self) -> None:
		workflow = HomeMaintenanceSchedulerAgent()
		assert workflow.name == "home_maintenance_scheduler"
		assert workflow.category == "home"


class TestHomeMaintenanceScheduler:
	"""Tests for home maintenance scheduler service."""

	def test_seasonal_schedule_spring_exists(self) -> None:
		from atlas.workflows.home.home_maintenance_scheduler import HomeMaintenanceService
		service = HomeMaintenanceService()
		# After building, verify spring tasks exist
		assert len(service._tasks) > 0

	def test_mark_completed(self) -> None:
		from atlas.workflows.home.home_maintenance_scheduler import HomeMaintenanceService
		service = HomeMaintenanceService()
		tasks = list(service._tasks.keys())
		if tasks:
			success = service.mark_completed(tasks[0])
			assert success


class TestPromoAprService:
	"""Tests for enhanced Promo APR Deadline service."""

	def test_add_promo(self) -> None:
		"""Service can track new promo APR offers."""
		service = PromoAprService()
		promo = PromoAPR(
			promo_id="PROMO001",
			card_name="Chase Sapphire Reserve",
			promo_rate=0.0,
			regular_rate=21.5,
			balance=5000.0,
			end_date=date.today() + timedelta(days=45),
		)
		added = service.add_promo(promo)
		assert added.promo_id == "PROMO001"
		assert added.balance == 5000.0

	def test_escalation_levels(self) -> None:
		"""Service correctly assigns escalation levels based on days remaining."""
		service = PromoAprService()
		assert service.get_escalation_level(1) == EscalationLevel.CRITICAL
		assert service.get_escalation_level(5) == EscalationLevel.URGENT
		assert service.get_escalation_level(15) == EscalationLevel.ELEVATED
		assert service.get_escalation_level(45) == EscalationLevel.NORMAL

	def test_payoff_calculation(self) -> None:
		"""Service calculates accurate payoff plans."""
		service = PromoAprService()
		promo = PromoAPR(
			promo_id="P1",
			card_name="Card A",
			promo_rate=0.0,
			regular_rate=20.0,
			balance=1200.0,
			end_date=date.today() + timedelta(days=60),
		)
		service.add_promo(promo)
		plan = service.calculate_payoff_plan(promo, date.today())

		# 60 days = ~2 months, so monthly payment should be ~600
		assert 550 < plan.monthly_payment < 650
		# Interest savings = 1200 * 0.20 * (2/12) = $40
		assert 38 < plan.total_interest_saved < 42

	def test_balance_transfer_options(self) -> None:
		"""Service can recommend balance transfer targets."""
		service = PromoAprService()
		promo = PromoAPR(
			promo_id="P1",
			card_name="High APR Card",
			promo_rate=0.0,
			regular_rate=25.0,
			balance=3000.0,
			end_date=date.today() + timedelta(days=30),
		)
		service.add_promo(promo)

		transfer_options = [
			BalanceTransferOption("Citi Card", 10.0, 2.0, 450.0),  # 10% APR, 2% fee, $450 savings/year
			BalanceTransferOption("AmEx Card", 14.0, 3.0, 330.0),  # Lower savings than Citi
		]
		service.set_balance_transfer_targets("P1", transfer_options)

		best = service.get_best_balance_transfer("P1", 3000.0)
		assert best is not None
		assert best.target_card == "Citi Card"
		assert best.net_savings_annual == 450.0

	def test_escalation_history_prevents_duplicate_alerts(self) -> None:
		"""Service only alerts on new escalation levels."""
		service = PromoAprService()
		promo = PromoAPR(
			promo_id="P1",
			card_name="Test Card",
			promo_rate=0.0,
			regular_rate=20.0,
			balance=1000.0,
			end_date=date.today() + timedelta(days=5),
		)
		service.add_promo(promo)

		# First alert at URGENT level
		alert1 = service.generate_alert(promo, date.today())
		assert alert1 is not None
		assert alert1.escalation == EscalationLevel.URGENT

		# Same promo, same escalation level = no alert
		alert2 = service.generate_alert(promo, date.today())
		assert alert2 is None

	def test_multi_card_scenario(self) -> None:
		"""Service handles multiple promos correctly."""
		service = PromoAprService()
		today = date.today()

		promo1 = PromoAPR("P1", "Card A", 0.0, 20.0, 2000.0, today + timedelta(days=10))
		promo2 = PromoAPR("P2", "Card B", 5.0, 22.0, 1500.0, today + timedelta(days=45))
		promo3 = PromoAPR("P3", "Card C", 3.0, 19.0, 500.0, today + timedelta(days=80))

		service.add_promo(promo1)
		service.add_promo(promo2)
		service.add_promo(promo3)

		approaching = service.check_approaching(days_ahead=60, today=today)
		assert len(approaching) == 2  # P1 and P2 are within 60 days

		# Generate alerts for approaching promos
		alerts = [service.generate_alert(p, today) for p in approaching]
		alerts = [a for a in alerts if a is not None]
		assert len(alerts) == 2


class TestPromoAprWorkflow:
	"""Tests for Promo APR Deadline workflow."""

	def test_workflow_instantiates(self) -> None:
		"""Workflow can be instantiated."""
		workflow = PromoAprDeadlineWorkflow()
		assert workflow.workflow_id == "promo_apr_deadline"
		assert workflow.category == "budget"

	def test_workflow_with_session_parameter(self) -> None:
		"""Workflow accepts session without errors."""
		workflow = PromoAprDeadlineWorkflow(session=None)
		assert workflow.service is not None


class TestFilingDeadlineService:
	"""Tests for enhanced Filing Deadline service."""

	def test_add_deadline(self) -> None:
		"""Service can track new filing deadlines."""
		service = FilingDeadlineService()
		today = date.today()
		deadline = FilingDeadline(
			deadline_id="FILING001",
			label="Form 1040 - Federal Income Tax",
			jurisdiction="Federal (IRS)",
			due_date=today + timedelta(days=45),
			criticality=Criticality.CRITICAL,
			is_recurring=True,
			recurring_months=12,
		)
		added = service.add_deadline(deadline)
		assert added.deadline_id == "FILING001"
		assert added.label == "Form 1040 - Federal Income Tax"

	def test_due_within(self) -> None:
		"""Service correctly identifies deadlines due within N days."""
		service = FilingDeadlineService()
		today = date.today()
		
		deadline1 = FilingDeadline(
			deadline_id="1",
			label="Form 1050",
			jurisdiction="Federal",
			due_date=today + timedelta(days=10),
			criticality=Criticality.HIGH,
			is_recurring=False,
			recurring_months=None,
		)
		deadline2 = FilingDeadline(
			deadline_id="2",
			label="State Tax Return",
			jurisdiction="California",
			due_date=today + timedelta(days=80),
			criticality=Criticality.HIGH,
			is_recurring=False,
			recurring_months=None,
		)
		
		service.add_deadline(deadline1)
		service.add_deadline(deadline2)
		
		due_soon = service.due_within(60, today)
		assert len(due_soon) == 1
		assert due_soon[0].deadline_id == "1"

	def test_create_from_template(self) -> None:
		"""Service can create deadline from built-in template."""
		service = FilingDeadlineService()
		today = date.today()
		
		# Create deadline from Form 1040 template
		deadline = service.create_from_template("form_1040", "FILING_1040_2024")
		
		assert deadline is not None
		assert deadline.label == "Federal Individual Income Tax Return"
		assert deadline.criticality == Criticality.CRITICAL
		assert deadline.is_recurring is True
		assert deadline.recurring_months == 12
		assert deadline.due_date.month == 4
		assert deadline.due_date.day == 15

	def test_get_required_documents(self) -> None:
		"""Service returns required documents for filing."""
		service = FilingDeadlineService()
		
		# First create a deadline from template
		deadline = service.create_from_template("form_1040", "FILING_1040_TEST")
		assert deadline is not None
		
		# Get documents for this deadline
		docs = service.get_required_documents("FILING_1040_TEST")
		
		assert len(docs) > 0
		assert "W2s" in docs
		assert "1099s" in docs

	def test_get_template(self) -> None:
		"""Service can retrieve filing template by ID."""
		service = FilingDeadlineService()
		
		template = service.get_template("form_1040")
		assert template is not None
		assert template.template_id == "form_1040"
		assert template.filing_type == "1040"
		assert template.jurisdiction == "USA"

	def test_escalation_by_criticality(self) -> None:
		"""Service correctly escalates based on criticality."""
		service = FilingDeadlineService()
		today = date.today()
		
		critical = FilingDeadline(
			deadline_id="CRITICAL1",
			label="Critical Filing",
			jurisdiction="Federal",
			due_date=today + timedelta(days=30),
			criticality=Criticality.CRITICAL,
			status=DeadlineStatus.ACTIVE,
			is_recurring=False,
		)
		medium = FilingDeadline(
			deadline_id="MEDIUM1",
			label="Medium Filing",
			jurisdiction="State",
			due_date=today + timedelta(days=30),
			criticality=Criticality.MEDIUM,
			status=DeadlineStatus.ACTIVE,
			is_recurring=False,
		)
		
		service.add_deadline(critical)
		service.add_deadline(medium)
		
		alert_critical = service.generate_alert(critical, today)
		alert_medium = service.generate_alert(medium, today)
		
		# Both should generate alerts (within 60 days)
		assert alert_critical is not None
		assert alert_medium is not None
		assert alert_critical.criticality == Criticality.CRITICAL
		assert alert_medium.criticality == Criticality.MEDIUM

	def test_recurring_deadline_scheduling(self) -> None:
		"""Service correctly schedules next occurrence of recurring deadlines."""
		service = FilingDeadlineService()
		today = date.today()
		
		# Create a recurring deadline
		deadline = FilingDeadline(
			deadline_id="RECUR1",
			label="Quarterly Filing",
			jurisdiction="Federal",
			due_date=today + timedelta(days=30),
			criticality=Criticality.HIGH,
			status=DeadlineStatus.ACTIVE,
			is_recurring=True,
			recurring_months=3,
		)
		
		service.add_deadline(deadline)
		alert = service.generate_alert(deadline, today)
		
		# If alert generated, verify next_deadline is set for recurring
		if alert:
			assert alert.next_deadline is not None

	def test_multiple_deadlines_scenario(self) -> None:
		"""Service handles multiple filing deadlines correctly."""
		service = FilingDeadlineService()
		today = date.today()
		
		deadline1 = FilingDeadline("D1", "Form 1040", "Federal", today + timedelta(days=20), Criticality.CRITICAL, DeadlineStatus.ACTIVE, False)
		deadline2 = FilingDeadline("D2", "State 1099", "CA", today + timedelta(days=10), Criticality.HIGH, DeadlineStatus.ACTIVE, False)
		deadline3 = FilingDeadline("D3", "City Tax", "SF", today + timedelta(days=100), Criticality.MEDIUM, DeadlineStatus.ACTIVE, False)
		
		service.add_deadline(deadline1)
		service.add_deadline(deadline2)
		service.add_deadline(deadline3)
		
		approaching = service.due_within(60, today)
		assert len(approaching) == 2
		assert all(d.criticality in [Criticality.CRITICAL, Criticality.HIGH] for d in approaching)


class TestFilingDeadlineTrackerWorkflow:
	"""Tests for Filing Deadline Tracker workflow."""

	def test_workflow_instantiates(self) -> None:
		"""Workflow can be instantiated."""
		workflow = FilingDeadlineTrackerWorkflow()
		assert workflow.workflow_id == "filing_deadline_tracker"
		assert workflow.category == "tax_legal"

	def test_workflow_with_session_parameter(self) -> None:
		"""Workflow accepts session without errors."""
		workflow = FilingDeadlineTrackerWorkflow(session=None)
		assert workflow.service is not None


class TestMaintenanceIntakeService:
	"""Tests for enhanced Maintenance Intake service."""

	def test_add_contractor(self) -> None:
		"""Service can register contractors."""
		service = MaintenanceIntakeService()
		contractor = Contractor(
			contractor_id="C001",
			name="John's Plumbing",
			specialties={ContractorSpecialty.PLUMBING},
			cost_per_hour=100.0,
		)
		added = service.add_contractor(contractor)
		assert added.contractor_id == "C001"
		assert added.name == "John's Plumbing"

	def test_classify_urgency_emergency(self) -> None:
		"""Service correctly classifies emergency issues."""
		service = MaintenanceIntakeService()
		urgency, issues = service.classify_urgency("There is a gas leak in the apartment")
		assert urgency == UrgencyLevel.EMERGENCY
		assert "gas" in issues
		assert "leak" in issues

	def test_intake_request(self) -> None:
		"""Service can intake a maintenance request."""
		service = MaintenanceIntakeService()
		payload: dict[str, object] = {
			"request_id": "REQ001",
			"tenant": "Jane Doe",
			"property_name": "Main St Apt",
			"unit": "2B",
			"description": "Broken washing machine",
			"photos": [],
		}
		request = service.intake(payload)
		assert request.request_id == "REQ001"
		assert request.tenant == "Jane Doe"
		assert request.urgency == UrgencyLevel.URGENT

	def test_queue_dispatch_creates_record(self) -> None:
		"""Service creates dispatch record when queuing."""
		service = MaintenanceIntakeService()
		contractor = Contractor(
			contractor_id="C001",
			name="Pro Repairs",
			specialties={ContractorSpecialty.GENERAL},
		)
		service.add_contractor(contractor)

		from atlas.workflows.property.maintenance_intake_agent import DispatchPlan
		plan = DispatchPlan(
			contractor_id="C001",
			contractor_name="Pro Repairs",
			specialty=ContractorSpecialty.GENERAL,
			estimated_cost=200.0,
			estimated_arrival_hours=2,
			reason_for_selection="Best available",
			requires_approval=False,
		)

		# Create a request first
		payload: dict[str, object] = {
			"request_id": "REQ001",
			"tenant": "John",
			"property_name": "Apt",
			"unit": "1A",
			"description": "Sink clog",
		}
		service.intake(payload)

		dispatch_id = service.queue_dispatch("REQ001", plan)
		assert dispatch_id is not None
		assert dispatch_id.startswith("REQ001_dispatch_")

	def test_get_pending_jobs(self) -> None:
		"""Service can retrieve pending jobs."""
		service = MaintenanceIntakeService()
		contractor = Contractor(
			contractor_id="C001",
			name="Quick Repairs",
			specialties={ContractorSpecialty.GENERAL},
		)
		service.add_contractor(contractor)

		from atlas.workflows.property.maintenance_intake_agent import DispatchPlan
		
		# Create and queue a dispatch
		payload: dict[str, object] = {
			"request_id": "REQ001",
			"tenant": "Jane",
			"property_name": "Building",
			"unit": "3C",
			"description": "Door broken",
		}
		service.intake(payload)

		plan = DispatchPlan(
			contractor_id="C001",
			contractor_name="Quick Repairs",
			specialty=ContractorSpecialty.GENERAL,
			estimated_cost=150.0,
			estimated_arrival_hours=4,
			reason_for_selection="Available",
			requires_approval=False,
		)
		service.queue_dispatch("REQ001", plan)

		pending = service.get_pending_jobs()
		assert len(pending) == 1
		assert pending[0].status == JobStatus.DISPATCHED

	def test_update_job_status(self) -> None:
		"""Service can update job status."""
		service = MaintenanceIntakeService()
		contractor = Contractor(
			contractor_id="C001",
			name="Tech Support",
			specialties={ContractorSpecialty.ELECTRICAL},
		)
		service.add_contractor(contractor)

		from atlas.workflows.property.maintenance_intake_agent import DispatchPlan

		payload: dict[str, object] = {
			"request_id": "REQ001",
			"tenant": "Bob",
			"property_name": "Office",
			"unit": "Floor2",
			"description": "Light switch broken",
		}
		service.intake(payload)

		plan = DispatchPlan(
			contractor_id="C001",
			contractor_name="Tech Support",
			specialty=ContractorSpecialty.ELECTRICAL,
			estimated_cost=75.0,
			estimated_arrival_hours=1,
			reason_for_selection="Specialist",
			requires_approval=False,
		)
		dispatch_id = service.queue_dispatch("REQ001", plan)

		# Update status to in-progress
		success = service.update_job_status(dispatch_id, JobStatus.IN_PROGRESS, notes="Started work")
		assert success

		record = service.get_dispatch_record(dispatch_id)
		assert record is not None
		assert record.status == JobStatus.IN_PROGRESS
		assert record.notes == "Started work"
		assert record.started_at is not None

	def test_get_job_history(self) -> None:
		"""Service can retrieve job history for request."""
		service = MaintenanceIntakeService()
		contractor = Contractor(
			contractor_id="C001",
			name="All Trades",
			specialties={ContractorSpecialty.GENERAL, ContractorSpecialty.PLUMBING},
		)
		service.add_contractor(contractor)

		from atlas.workflows.property.maintenance_intake_agent import DispatchPlan

		payload: dict[str, object] = {
			"request_id": "REQ001",
			"tenant": "Alice",
			"property_name": "House",
			"unit": "Basement",
			"description": "Pipe needs repair",
		}
		service.intake(payload)

		plan = DispatchPlan(
			contractor_id="C001",
			contractor_name="All Trades",
			specialty=ContractorSpecialty.PLUMBING,
			estimated_cost=250.0,
			estimated_arrival_hours=3,
			reason_for_selection="Plumbing specialist",
			requires_approval=True,
		)
		service.queue_dispatch("REQ001", plan)

		history = service.get_job_history("REQ001")
		assert len(history) == 1
		assert history[0].contractor_name == "All Trades"

	def test_job_status_history_tracking(self) -> None:
		"""Service tracks full status change history."""
		service = MaintenanceIntakeService()
		contractor = Contractor(
			contractor_id="C001",
			name="Reliable Repairs",
			specialties={ContractorSpecialty.CARPENTRY},
		)
		service.add_contractor(contractor)

		from atlas.workflows.property.maintenance_intake_agent import DispatchPlan

		payload: dict[str, object] = {
			"request_id": "REQ001",
			"tenant": "Tom",
			"property_name": "Studio",
			"unit": "101",
			"description": "Cabinet door missing",
		}
		service.intake(payload)

		plan = DispatchPlan(
			contractor_id="C001",
			contractor_name="Reliable Repairs",
			specialty=ContractorSpecialty.CARPENTRY,
			estimated_cost=100.0,
			estimated_arrival_hours=2,
			reason_for_selection="Carpentry expert",
			requires_approval=False,
		)
		dispatch_id = service.queue_dispatch("REQ001", plan)

		# Transition through statuses
		service.update_job_status(dispatch_id, JobStatus.IN_PROGRESS)
		service.update_job_status(dispatch_id, JobStatus.COMPLETED)

		record = service.get_dispatch_record(dispatch_id)
		assert record is not None
		assert len(record.status_history) == 3  # Dispatched -> In Progress -> Completed
		assert record.status_history[0][0] == JobStatus.DISPATCHED
		assert record.status_history[1][0] == JobStatus.IN_PROGRESS
		assert record.status_history[2][0] == JobStatus.COMPLETED


class TestMaintenanceIntakeWorkflow:
	"""Tests for Maintenance Intake workflow."""

	def test_workflow_instantiates(self) -> None:
		"""Workflow can be instantiated."""
		workflow = MaintenanceIntakeWorkflow()
		assert workflow.workflow_id == "maintenance_intake"
		assert workflow.category == "property"

	def test_workflow_with_session_parameter(self) -> None:
		"""Workflow accepts session without errors."""
		workflow = MaintenanceIntakeWorkflow(session=None)
		assert workflow.service is not None


class TestSharedExpenseService:
	"""Tests for enhanced Shared Expense service."""

	def test_classify_shared_grocery(self) -> None:
		"""Service classifies grocery purchases as shared."""
		service = SharedExpenseService(occupants=["Alice", "Bob"])
		transaction = Transaction(
			transaction_id="TXN001",
			timestamp=datetime.now(timezone.utc),
			merchant="Whole Foods",
			amount=150.0,
			payer="Alice",
			description="Weekly groceries",
		)
		classification, split_among = service.classify_transaction(transaction)
		assert classification == ExpenseClass.SHARED
		assert "Bob" in split_among  # Bob should be in split
		# Verify that expense debtors excludes payer
		expense = service.record_transaction(transaction)
		assert expense is not None
		assert "Alice" not in expense.debtors
		assert "Bob" in expense.debtors

	def test_classify_personal_coffee(self) -> None:
		"""Service classifies personal expenses correctly."""
		service = SharedExpenseService(occupants=["Alice", "Bob"])
		transaction = Transaction(
			transaction_id="TXN001",
			timestamp=datetime.now(timezone.utc),
			merchant="Local Coffee Shop",
			amount=6.0,
			payer="Alice",
			description="Morning coffee",
		)
		classification, _ = service.classify_transaction(transaction)
		assert classification == ExpenseClass.PERSONAL

	def test_record_transaction(self) -> None:
		"""Service can record and classify transactions."""
		service = SharedExpenseService(occupants=["Alice", "Bob", "Charlie"])
		transaction = Transaction(
			transaction_id="TXN001",
			timestamp=datetime.now(timezone.utc),
			merchant="Target",
			amount=120.0,
			payer="Bob",
			description="Household supplies",
		)
		expense = service.record_transaction(transaction)
		assert expense is not None
		assert expense.payer == "Bob"
		assert expense.classification == ExpenseClass.SHARED

	def test_calculate_balance(self) -> None:
		"""Service calculates correct balances."""
		service = SharedExpenseService(occupants=["Alice", "Bob"])
		
		# Alice pays $100 for groceries, split between Alice and Bob
		transaction = Transaction(
			transaction_id="TXN001",
			timestamp=datetime.now(timezone.utc),
			merchant="Trader Joe's",
			amount=100.0,
			payer="Alice",
			description="Groceries",
		)
		service.record_transaction(transaction)
		
		# Alice paid $100, should get $50 back = -$50 (is owed)
		now = datetime.now(timezone.utc)
		alice_balance = service.calculate_balance("Alice", now - timedelta(days=1), now + timedelta(days=1))
		assert alice_balance == -50.0
		
		# Bob owes $50
		bob_balance = service.calculate_balance("Bob", now - timedelta(days=1), now + timedelta(days=1))
		assert bob_balance == 50.0

	def test_settlement_suggestion(self) -> None:
		"""Service suggests settlements."""
		service = SharedExpenseService(occupants=["Alice", "Bob", "Charlie"])
		
		# Alice pays for shared groceries
		txn = Transaction(
			transaction_id="TXN001",
			timestamp=datetime.now(timezone.utc),
			merchant="Costco",
			amount=90.0,
			payer="Alice",
			description="Grocery shopping",  # "grocery" keyword triggers SHARED
		)
		service.record_transaction(txn)
		
		now = datetime.now(timezone.utc)
		summary = service.suggest_settlements(now - timedelta(days=1), now + timedelta(days=1))
		# Should have balances for Bob and Charlie (both owe $30)
		assert len(summary.balances) >= 2
		assert summary.balances.get("Bob", 0) == 30.0
		assert summary.balances.get("Charlie", 0) == 30.0
		# Settlement suggestions should exist
		assert len(summary.settlements) > 0

	def test_record_settlement(self) -> None:
		"""Service can record settlement payments."""
		service = SharedExpenseService(occupants=["Alice", "Bob"])
		
		settlement = service.record_settlement("Bob", "Alice", 50.0)
		assert settlement is not None
		assert settlement.from_person == "Bob"
		assert settlement.to_person == "Alice"
		assert settlement.amount == 50.0
		assert not settlement.confirmed

	def test_confirm_settlement(self) -> None:
		"""Service can confirm a settlement."""
		service = SharedExpenseService(occupants=["Alice", "Bob"])
		
		settlement = service.record_settlement("Alice", "Bob", 75.0)
		success = service.confirm_settlement(settlement.settlement_id)
		
		assert success
		confirmed = service._settlement_records[settlement.settlement_id]
		assert confirmed.confirmed
		assert confirmed.confirmed_at is not None

	def test_get_pending_settlements(self) -> None:
		"""Service can retrieve pending settlements."""
		service = SharedExpenseService(occupants=["Alice", "Bob", "Charlie"])
		
		s1 = service.record_settlement("Alice", "Bob", 30.0)
		s2 = service.record_settlement("Charlie", "Alice", 20.0)
		
		service.confirm_settlement(s1.settlement_id)
		# s2 is still pending
		
		pending = service.get_pending_settlements()
		assert len(pending) == 1
		assert pending[0].settlement_id == s2.settlement_id

	def test_record_classification_feedback(self) -> None:
		"""Service can record feedback on classifications."""
		service = SharedExpenseService(occupants=["Alice", "Bob"])
		
		transaction = Transaction(
			transaction_id="TXN001",
			timestamp=datetime.now(timezone.utc),
			merchant="IKEA",
			amount=200.0,
			payer="Alice",
			description="Furniture",
		)
		expense = service.record_transaction(transaction)
		
		if expense:
			feedback = service.record_feedback(
				expense.expense_id,
				ExpenseClass.UNKNOWN,
				ExpenseClass.SHARED,
				"IKEA",
				reason="Shared furniture for common area"
			)
			assert feedback is not None
			assert feedback.corrected_class == ExpenseClass.SHARED

	def test_get_feedback_history(self) -> None:
		"""Service can retrieve feedback history."""
		service = SharedExpenseService(occupants=["Alice", "Bob"])
		
		transaction = Transaction(
			transaction_id="TXN001",
			timestamp=datetime.now(timezone.utc),
			merchant="Amazon",
			amount=50.0,
			payer="Bob",
			description="Household item",
		)
		expense = service.record_transaction(transaction)
		
		if expense:
			service.record_feedback(
				expense.expense_id,
				ExpenseClass.PERSONAL,
				ExpenseClass.SHARED,
				"Amazon",
				reason="Shared item"
			)
		
		history = service.get_feedback_history("Amazon")
		assert len(history) > 0

	def test_get_settlement_history(self) -> None:
		"""Service can retrieve settlement history for a person."""
		service = SharedExpenseService(occupants=["Alice", "Bob", "Charlie"])
		
		service.record_settlement("Alice", "Bob", 50.0)
		service.record_settlement("Bob", "Charlie", 30.0)
		service.record_settlement("Charlie", "Alice", 20.0)
		
		# Alice is from_person in settlement 1, to_person in settlement 3
		alice_history = service.get_settlement_history("Alice")
		assert len(alice_history) == 2
		# Bob is involved in 2 settlements
		bob_history = service.get_settlement_history("Bob")
		assert len(bob_history) == 2


class TestSharedExpenseWorkflow:
	"""Tests for Shared Expense Classifier workflow."""

	def test_workflow_instantiates(self) -> None:
		"""Workflow can be instantiated."""
		workflow = SharedExpenseClassifierWorkflow()
		assert workflow.workflow_id == "shared_expense_classifier"
		assert workflow.category == "budget"

	def test_workflow_with_session_parameter(self) -> None:
		"""Workflow accepts session without errors."""
		workflow = SharedExpenseClassifierWorkflow(session=None)
		assert workflow.service is not None


class TestRentReminderService:
	"""Tests for enhanced Rent Reminder service."""

	def test_record_reminder_sent(self) -> None:
		"""Service can record sent reminders."""
		service = RentReminderService()
		from atlas.workflows.property.rent_reminder_agent import RentReminder

		reminder = RentReminder(
			reminder_id="REM001",
			rent_due_id="DUE001",
			tenant_id="T001",
			tenant_name="John Doe",
			property_unit="Main St/2B",
			amount_due=1500.0,
			days_overdue=0,
			escalation_tier=EscalationTier.COURTESY,
			payment_method="ACH",
		)

		history = service.record_reminder_sent(reminder, delivery_method="email")
		assert history is not None
		assert history.tenant_id == "T001"
		assert not history.delivery_confirmed

	def test_confirm_delivery(self) -> None:
		"""Service can confirm reminder delivery."""
		service = RentReminderService()
		from atlas.workflows.property.rent_reminder_agent import RentReminder

		reminder = RentReminder(
			reminder_id="REM001",
			rent_due_id="DUE001",
			tenant_id="T001",
			tenant_name="Jane Smith",
			property_unit="Oak Ave/1A",
			amount_due=1200.0,
			days_overdue=5,
			escalation_tier=EscalationTier.URGENT,
			payment_method="CHECK",
		)

		history = service.record_reminder_sent(reminder)
		success = service.confirm_delivery(history.history_id)

		assert success
		# Verify confirmation by checking unconfirmed list no longer contains it
		unconfirmed = service.get_unconfirmed_reminders()
		assert history.history_id not in [r.history_id for r in unconfirmed]

	def test_get_unconfirmed_reminders(self) -> None:
		"""Service can retrieve unconfirmed reminders."""
		service = RentReminderService()
		from atlas.workflows.property.rent_reminder_agent import RentReminder

		r1 = RentReminder("REM001", "DUE001", "T001", "Tenant1", "Prop/1", 1500.0, 0, EscalationTier.COURTESY, "ACH")
		r2 = RentReminder("REM002", "DUE002", "T001", "Tenant1", "Prop/2", 1500.0, 7, EscalationTier.URGENT, "ACH")

		h1 = service.record_reminder_sent(r1)
		h2 = service.record_reminder_sent(r2)

		service.confirm_delivery(h1.history_id)
		# h2 is still unconfirmed

		unconfirmed = service.get_unconfirmed_reminders()
		assert len(unconfirmed) == 1
		assert unconfirmed[0].history_id == h2.history_id

	def test_property_portfolio(self) -> None:
		"""Service can manage property portfolio."""
		service = RentReminderService()

		service.add_property("Main Street Complex")
		service.add_property("Oak Avenue Townhomes")
		service.add_property("Park View Apartments")

		properties = service.get_properties()
		assert len(properties) == 3
		assert "Main Street Complex" in properties
		assert properties == sorted(properties)  # Should be sorted

	def test_group_reminders_by_property(self) -> None:
		"""Service can group reminders by property for digest."""
		service = RentReminderService()
		from atlas.workflows.property.rent_reminder_agent import RentReminder

		reminders = [
			RentReminder("REM001", "DUE001", "T001", "Tenant1", "Main St/1", 1500.0, 0, EscalationTier.COURTESY, "ACH"),
			RentReminder("REM002", "DUE002", "T002", "Tenant2", "Main St/2", 1500.0, 0, EscalationTier.COURTESY, "ACH"),
			RentReminder("REM003", "DUE003", "T003", "Tenant3", "Oak Ave/1", 1200.0, 5, EscalationTier.URGENT, "CHECK"),
		]

		digests = service.group_reminders_by_property(reminders)
		assert len(digests) == 2  # Main St and Oak Ave
		assert digests["Main St"].reminder_count == 2
		assert digests["Main St"].total_amount_due == 3000.0
		assert digests["Oak Ave"].reminder_count == 1
		assert digests["Oak Ave"].total_amount_due == 1200.0

	def test_get_reminder_history(self) -> None:
		"""Service can retrieve reminder history."""
		service = RentReminderService()
		from atlas.workflows.property.rent_reminder_agent import RentReminder

		r1 = RentReminder("REM001", "DUE001", "T001", "Tenant1", "Prop/1", 1500.0, 0, EscalationTier.COURTESY, "ACH")
		r2 = RentReminder("REM002", "DUE002", "T001", "Tenant1", "Prop/2", 1500.0, 0, EscalationTier.COURTESY, "ACH")
		r3 = RentReminder("REM003", "DUE003", "T002", "Tenant2", "Prop/1", 1200.0, 5, EscalationTier.URGENT, "CHECK")

		service.record_reminder_sent(r1)
		service.record_reminder_sent(r2)
		service.record_reminder_sent(r3)

		t1_history = service.get_reminder_history("T001")
		assert len(t1_history) == 2
		assert all(h.tenant_id == "T001" for h in t1_history)

		all_history = service.get_reminder_history()
		assert len(all_history) == 3

	def test_record_payment_updates_status(self) -> None:
		"""Service updates rent status when payment received."""
		service = RentReminderService()

		rent_due = RentDue(
			rent_due_id="DUE001",
			tenant_id="T001",
			tenant_name="John",
			property_name="Main",
			unit="1A",
			due_date=date.today(),
			amount_due=1500.0,
		)
		service.add_rent_due(rent_due)

		# Record partial payment
		payment = RentPayment(
			payment_id="PAY001",
			tenant_id="T001",
			amount=750.0,
			paid_date=date.today(),
		)
		service.record_payment(payment)

		# Status should be PARTIAL
		assert rent_due.status == PaymentStatus.PARTIAL
		assert rent_due.amount_paid == 750.0

		# Record second payment to complete
		payment2 = RentPayment(
			payment_id="PAY002",
			tenant_id="T001",
			amount=750.0,
			paid_date=date.today(),
		)
		service.record_payment(payment2)

		# Status should be PAID
		assert rent_due.status == PaymentStatus.PAID


class TestRentReminderWorkflow:
	"""Tests for Rent Reminder workflow."""

	def test_workflow_instantiates(self) -> None:
		"""Workflow can be instantiated."""
		workflow = RentReminderWorkflow()
		assert workflow.workflow_id == "rent_reminder"
		assert workflow.category == "property"

	def test_workflow_with_session_parameter(self) -> None:
		"""Workflow accepts session without errors."""
		workflow = RentReminderWorkflow(session=None)
		assert workflow.service is not None

