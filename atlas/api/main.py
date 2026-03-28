"""Atlas API — FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from atlas.api.routes import router
from atlas.core.logging import configure_logging, get_logger
from atlas.core.workflow.registry import default_workflow_registry
from atlas.workflows.budget.promo_apr_deadline_agent import PromoAprDeadlineWorkflow
from atlas.workflows.budget.shared_expense_classifier import SharedExpenseClassifierWorkflow
from atlas.workflows.property.maintenance_intake_agent import MaintenanceIntakeWorkflow
from atlas.workflows.property.rent_reminder_agent import RentReminderWorkflow
from atlas.workflows.tax_legal.filing_deadline_tracker import FilingDeadlineTrackerWorkflow

LOGGER = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
	configure_logging()

	for workflow in (
		PromoAprDeadlineWorkflow(),
		FilingDeadlineTrackerWorkflow(),
		MaintenanceIntakeWorkflow(),
		SharedExpenseClassifierWorkflow(),
		RentReminderWorkflow(),
	):
		try:
			default_workflow_registry.register(workflow)
		except ValueError:
			pass

	LOGGER.info("atlas.startup.complete", workflow_count=len(default_workflow_registry.list_all()))
	
	# Note: In production, ArqWorker init would happen here:
	# from arq import create_pool
	# from atlas.core.tasks import TASK_REGISTRY
	# ctx.task_pool = await create_pool(...)
	# Will integrate after Redis is available
	
	yield
	
	# Cleanup on shutdown
	LOGGER.info("atlas.shutdown", message="Application terminating")


app = FastAPI(title="Atlas", version="0.1.0", lifespan=lifespan)
app.include_router(router)
