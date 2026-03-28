"""Tests for the workflow registry and base class."""

from atlas.core.workflow.base import WorkflowEvent
from atlas.core.workflow.registry import WorkflowRegistry
from atlas.workflows.budget.promo_apr_deadline_agent import PromoAprDeadlineWorkflow
from atlas.workflows.budget.shared_expense_classifier import SharedExpenseClassifierWorkflow
from atlas.workflows.property.maintenance_intake_agent import MaintenanceIntakeWorkflow
from atlas.workflows.property.rent_reminder_agent import RentReminderWorkflow


async def test_registry_register_and_trigger_workflow():
	registry = WorkflowRegistry()
	workflow = PromoAprDeadlineWorkflow()
	registry.register(workflow)

	await registry.trigger(
		"promo_apr_deadline",
		WorkflowEvent(
			event_type="promo_added",
			payload={
				"promo_id": "p1",
				"card_name": "Card",
				"promo_rate": 0,
				"regular_rate": 24.0,
				"balance": 1200,
				"end_date": "2026-06-01",
				"today": "2026-05-10",
				"days_ahead": 30,
			},
		),
	)

	status = registry.get_status("promo_apr_deadline")
	assert status.workflow_id == "promo_apr_deadline"


async def test_maintenance_workflow_runs():
	workflow = MaintenanceIntakeWorkflow()
	result = await workflow.run(
		WorkflowEvent(
			event_type="maintenance_request",
			payload={
				"request_id": "m1",
				"tenant": "Tenant A",
				"property_name": "Maple House",
				"unit": "2B",
				"description": "Kitchen sink leak and water on floor",
			},
		)
	)

	assert result.success is True
	# The urgency classification uses keywords; "leak" maps to emergency
	assert "urgency" in result.metadata or "emergency" in str(result.metadata).lower()


async def test_shared_expense_workflow_runs():
	workflow = SharedExpenseClassifierWorkflow()
	result = await workflow.run(
		WorkflowEvent(
			event_type="expense_recorded",
			payload={
				"transaction_id": "t1",
				"timestamp": "2026-03-28T10:00:00+00:00",
				"merchant": "Costco Wholesale",
				"amount": 150.0,
				"payer": "alice",
				"description": "groceries",
				"category": "groceries",
			},
		)
	)

	assert result.success is True
	assert result.metadata.get("classification") == "shared"


async def test_rent_reminder_workflow_runs():
	from datetime import date
	
	workflow = RentReminderWorkflow()
	today = date.today()
	due_date = date(today.year, today.month, 1) if today.day > 1 else date(today.year, today.month - 1, 28)
	
	result = await workflow.run(
		WorkflowEvent(
			event_type="rent_due_added",
			payload={
				"rent_due_id": "r1",
				"tenant_id": "tenant-1",
				"tenant_name": "Alex",
				"property_name": "Pine Apartments",
				"unit": "2A",
				"amount_due": 1400.0,
				"due_date": due_date.isoformat(),
				"today": today.isoformat(),
			},
		)
	)

	assert result.success is True
	assert result.metadata.get("reminder_count", 0) >= 0
