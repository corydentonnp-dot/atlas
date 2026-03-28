"""Workflow #50: Investment Property Template — creates reusable property analysis templates.

Maintains library of investment property templates (e.g., "25-unit multifamily standard",
"commercial mixed-use model") for rapid property analysis and comparison.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class PropertyTemplate(str, Enum):
	"""Investment template type."""

	SINGLE_FAMILY_RENTAL = "single_family_rental"
	DUPLEX = "duplex"
	MULTIFAMILY = "multifamily"
	COMMERCIAL_MIXED = "commercial_mixed"
	VACATION_RENTAL = "vacation_rental"


@dataclass(slots=True)
class InvestmentTemplateModel:
	"""Template for property investment analysis."""

	template_id: str
	name: str
	template_type: PropertyTemplate
	target_price_range: tuple[float, float]
	typical_cap_rate: float
	debt_service_ratio: float  # Typical DSCR
	expense_ratio: float  # Typical opex as % of income
	appreciation_rate: float  # Assumed annual appreciation
	sample_tenants: int
	sample_rent_per_unit: float
	management_notes: str = ""


@dataclass(frozen=True, slots=True)
class PropertyAnalysis:
	"""Analysis result using template."""

	property_name: str
	template_used: str
	expected_cap_rate: float
	expected_cash_flow_monthly: float
	expected_appreciation_annual: float
	matches_template: bool  # Whether property fits template criteria


class InvestmentTemplateService(PersistenceMixin):
	"""Service for investment property templates."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._templates: dict[str, InvestmentTemplateModel] = {}
		self._initialize_standard_templates()

	def _initialize_standard_templates(self) -> None:
		"""Create standard investment templates."""
		templates = [
			InvestmentTemplateModel(
				template_id="sfr-basic",
				name="Single Family Rental - Basic",
				template_type=PropertyTemplate.SINGLE_FAMILY_RENTAL,
				target_price_range=(200000, 500000),
				typical_cap_rate=5.5,
				debt_service_ratio=1.25,
				expense_ratio=0.30,
				appreciation_rate=0.025,
				sample_tenants=1,
				sample_rent_per_unit=1500,
				management_notes="Primary residence conversions; positive cash flow after mortgage",
			),
			InvestmentTemplateModel(
				template_id="duplex-standard",
				name="Duplex Standard",
				template_type=PropertyTemplate.DUPLEX,
				target_price_range=(400000, 800000),
				typical_cap_rate=6.2,
				debt_service_ratio=1.35,
				expense_ratio=0.28,
				appreciation_rate=0.03,
				sample_tenants=2,
				sample_rent_per_unit=1800,
				management_notes="Live in one unit, rent other (BRRRR strategy)",
			),
			InvestmentTemplateModel(
				template_id="multifamily-25",
				name="Multifamily - 25 Units",
				template_type=PropertyTemplate.MULTIFAMILY,
				target_price_range=(3000000, 5000000),
				typical_cap_rate=7.0,
				debt_service_ratio=1.25,
				expense_ratio=0.32,
				appreciation_rate=0.035,
				sample_tenants=25,
				sample_rent_per_unit=1400,
				management_notes="Professional management required; economies of scale",
			),
		]

		for template in templates:
			self._templates[template.template_id] = template

	def add_template(self, template: InvestmentTemplateModel) -> InvestmentTemplateModel:
		"""Add custom investment template."""
		self._templates[template.template_id] = template
		return template

	def analyze_property(
		self, property_name: str, purchase_price: float, monthly_rent: float, monthly_expenses: float, template_id: str
	) -> PropertyAnalysis:
		"""Analyze property against template."""
		template = self._templates.get(template_id)
		if not template:
			return PropertyAnalysis(
				property_name=property_name,
				template_used="unknown",
				expected_cap_rate=0,
				expected_cash_flow_monthly=0,
				expected_appreciation_annual=0,
				matches_template=False,
			)

		# Calculate metrics
		annual_rent = monthly_rent * 12
		annual_expenses = monthly_expenses * 12
		noi = annual_rent - annual_expenses
		cap_rate = (noi / purchase_price * 100) if purchase_price > 0 else 0
		monthly_cash_flow = monthly_rent - monthly_expenses
		annual_appreciation = purchase_price * template.appreciation_rate

		# Check if matches template criteria
		min_price, max_price = template.target_price_range
		in_price_range = min_price <= purchase_price <= max_price
		reasonable_cap_rate = cap_rate >= (template.typical_cap_rate * 0.8)
		matches = in_price_range and reasonable_cap_rate

		return PropertyAnalysis(
			property_name=property_name,
			template_used=template.name,
			expected_cap_rate=cap_rate,
			expected_cash_flow_monthly=monthly_cash_flow,
			expected_appreciation_annual=annual_appreciation,
			matches_template=matches,
		)

	def list_templates(self) -> list[InvestmentTemplateModel]:
		"""List all available templates."""
		return list(self._templates.values())


class InvestmentTemplateAgent(BaseWorkflow):
	"""Workflow for investment property templates and analysis."""

	workflow_id = "investor_template"
	name = "Investor Template"
	category = "property"
	trust_level = TrustLevel.DRAFT

	def __init__(self, service: InvestmentTemplateService | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = service or InvestmentTemplateService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle investment events."""
		self.state_machine.transition("planning", {"event_type": event.event_type})

		if event.event_type == "analyze_property":
			payload = event.payload
			# Analysis happens in process()
			pass

		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Analyze property against templates."""
		payload = run.event.payload

		property_name = str(payload.get("property_name", "Unknown"))
		purchase_price = float(payload.get("purchase_price", 0))
		monthly_rent = float(payload.get("monthly_rent", 0))
		monthly_expenses = float(payload.get("monthly_expenses", 0))
		template_id = str(payload.get("template_id", "sfr-basic"))

		analysis = self.service.analyze_property(property_name, purchase_price, monthly_rent, monthly_expenses, template_id)

		return ActionPlan(
			action_type="analyze_investment_property",
			confidence=0.85,
			context={
				"property_name": analysis.property_name,
				"template_used": analysis.template_used,
				"cap_rate": analysis.expected_cap_rate,
				"monthly_cash_flow": analysis.expected_cash_flow_monthly,
				"annual_appreciation": analysis.expected_appreciation_annual,
				"matches_template": analysis.matches_template,
				"available_templates": len(self.service.list_templates()),
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute investment analysis."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})

		prop = plan.context.get("property_name", "")
		cap_rate = plan.context.get("cap_rate", 0)
		cash_flow = plan.context.get("monthly_cash_flow", 0)
		matches = plan.context.get("matches_template", False)

		template_note = " (matches template)" if matches else " (outside typical range)"
		summary = f"{prop}: {cap_rate:.1f}% cap rate, ${cash_flow:,.0f}/month{template_note}"
		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
