"""Workflow: Appliance & Fixture Manual Librarian.

Maintains a searchable library of appliance and fixture manuals for home management.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class ApplianceType(str, Enum):
	"""Type of appliance or fixture."""

	HVAC = "hvac"
	WATER_HEATER = "water_heater"
	REFRIGERATOR = "refrigerator"
	STOVE = "stove"
	DISHWASHER = "dishwasher"
	WASHING_MACHINE = "washing_machine"
	DRYER = "dryer"
	PLUMBING = "plumbing"
	ELECTRICAL = "electrical"
	ROOFING = "roofing"
	OTHER = "other"


@dataclass(frozen=True, slots=True)
class ApplianceManual:
	"""Reference for an appliance or fixture manual."""

	manual_id: str
	appliance_type: ApplianceType
	brand: str
	model: str
	install_date: str = ""
	manual_location: str = ""
	pdf_link: str = ""
	warranty_expires: str = ""
	replacement_cost_estimate: float = 0.0


class ApplianceManualLibraryService(PersistenceMixin):
	"""Service for managing appliance/fixture manual references."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._library: dict[str, ApplianceManual] = {}

	def add_manual(self, manual: ApplianceManual) -> ApplianceManual:
		"""Add a manual to the library."""
		self._library[manual.manual_id] = manual
		return manual

	def search_by_type(self, appliance_type: ApplianceType) -> list[ApplianceManual]:
		"""Find all manuals for an appliance type."""
		return [m for m in self._library.values() if m.appliance_type == appliance_type]

	def search_by_brand_model(self, brand: str, model: str) -> list[ApplianceManual]:
		"""Find manuals matching brand and model."""
		brand_lower = brand.lower()
		model_lower = model.lower()
		return [
			m for m in self._library.values()
			if brand_lower in m.brand.lower() and model_lower in m.model.lower()
		]

	def library_summary(self) -> dict[str, object]:
		"""Get summary of library contents."""
		by_type: dict[ApplianceType, int] = {}
		for manual in self._library.values():
			by_type[manual.appliance_type] = by_type.get(manual.appliance_type, 0) + 1
		return {
			"total_manuals": len(self._library),
			"by_type": {atype.value: count for atype, count in by_type.items()},
		}


class ApplianceFixtureManualLibrarian(BaseWorkflow):
	"""Workflow for managing appliance and fixture manual library."""

	workflow_id = "appliance_fixture_manual_librarian"
	name = "appliance_fixture_manual_librarian"
	category = "home"
	trust_level = TrustLevel.AUTO

	def __init__(self, service: ApplianceManualLibraryService | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = service or ApplianceManualLibraryService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		if event.event_type == "manual_stored":
			payload = event.payload
			manual = ApplianceManual(
				manual_id=str(payload.get("manual_id", "")),
				appliance_type=ApplianceType(str(payload.get("appliance_type", "other"))),
				brand=str(payload.get("brand", "")),
				model=str(payload.get("model", "")),
				install_date=str(payload.get("install_date", "")),
				manual_location=str(payload.get("manual_location", "")),
				pdf_link=str(payload.get("pdf_link", "")),
				warranty_expires=str(payload.get("warranty_expires", "")),
				replacement_cost_estimate=float(payload.get("replacement_cost_estimate", 0.0)),
			)
			self.service.add_manual(manual)
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		summary = self.service.library_summary()
		return ActionPlan(
			action_type="manage_manual_library",
			confidence=0.90,
			context={
				"library_summary": summary,
				"total_appliances": summary.get("total_manuals", 0),
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})
		total = int(plan.context.get("total_appliances", 0))
		summary = f"Managing manual library for {total} appliance(s)/fixture(s)"
		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
