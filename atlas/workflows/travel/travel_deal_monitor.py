"""Workflow #99: Travel Deal Monitor — Phase 2 Priority.
Monitors flight and hotel prices for saved destinations; alerts on significant drops.
Recommended phase: 2 (quick_win_score: 11) | Trust level: auto | Category: travel
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class DealType(str, Enum):
	"""Type of travel deal."""

	FLIGHT = "flight"
	HOTEL = "hotel"
	CAR_RENTAL = "car_rental"
	PACKAGE = "package"


class AlertStatus(str, Enum):
	"""Status of a price alert."""

	WATCHING = "watching"
	DROP_DETECTED = "drop_detected"
	ALERTED = "alerted"
	BOOKED = "booked"
	EXPIRED = "expired"


@dataclass(slots=True)
class TravelAlert:
	"""A tracked travel price alert."""

	alert_id: str
	destination: str
	deal_type: DealType
	origin: str
	travel_date: date
	return_date: date | None
	baseline_price: float
	current_price: float
	drop_threshold_pct: float  # alert when price drops by this %
	status: AlertStatus
	notes: str = ""
	last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

	@property
	def drop_percentage(self) -> float:
		"""Percentage drop from baseline price."""
		if self.baseline_price <= 0:
			return 0.0
		return (self.baseline_price - self.current_price) / self.baseline_price * 100

	@property
	def is_deal(self) -> bool:
		"""Whether the current price is below the alert threshold."""
		return self.drop_percentage >= self.drop_threshold_pct


@dataclass(frozen=True, slots=True)
class TravelDealSummary:
	"""Summary of all monitored travel deals."""

	total_watching: int
	active_deals: int
	best_deal_destination: str
	best_deal_drop_pct: float


class TravelDealMonitorService(PersistenceMixin):
	"""Service for monitoring travel deals across saved destinations."""

	DEFAULT_DROP_THRESHOLD_PCT: float = 15.0  # alert on 15%+ price drop

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._alerts: dict[str, TravelAlert] = {}

	def add_alert(
		self,
		alert_id: str,
		destination: str,
		deal_type: DealType,
		origin: str,
		travel_date: date,
		baseline_price: float,
		return_date: date | None = None,
		drop_threshold_pct: float = DEFAULT_DROP_THRESHOLD_PCT,
		notes: str = "",
	) -> TravelAlert:
		"""Add a new price alert to monitor."""
		alert = TravelAlert(
			alert_id=alert_id,
			destination=destination,
			deal_type=deal_type,
			origin=origin,
			travel_date=travel_date,
			return_date=return_date,
			baseline_price=baseline_price,
			current_price=baseline_price,
			drop_threshold_pct=drop_threshold_pct,
			status=AlertStatus.WATCHING,
			notes=notes,
		)
		self._alerts[alert_id] = alert
		return alert

	def update_price(self, alert_id: str, new_price: float) -> TravelAlert | None:
		"""Update the current price and flag a deal if threshold is met."""
		if alert_id not in self._alerts:
			return None
		alert = self._alerts[alert_id]
		alert.current_price = new_price
		alert.last_checked = datetime.now(timezone.utc)
		if alert.is_deal and alert.status == AlertStatus.WATCHING:
			alert.status = AlertStatus.DROP_DETECTED
		return alert

	def mark_alerted(self, alert_id: str) -> bool:
		"""Mark a deal as having been surfaced to the user."""
		if alert_id not in self._alerts:
			return False
		self._alerts[alert_id].status = AlertStatus.ALERTED
		return True

	def mark_booked(self, alert_id: str) -> bool:
		"""Mark a deal as booked."""
		if alert_id not in self._alerts:
			return False
		self._alerts[alert_id].status = AlertStatus.BOOKED
		return True

	def get_active_deals(self) -> list[TravelAlert]:
		"""Return all alerts where a price drop has been detected."""
		return [
			a for a in self._alerts.values()
			if a.status in (AlertStatus.DROP_DETECTED, AlertStatus.ALERTED)
		]

	def get_summary(self) -> TravelDealSummary:
		"""Return a summary of deal monitoring activity."""
		watching = [a for a in self._alerts.values() if a.status != AlertStatus.EXPIRED]
		deals = self.get_active_deals()
		best = max(deals, key=lambda a: a.drop_percentage, default=None)
		return TravelDealSummary(
			total_watching=len(watching),
			active_deals=len(deals),
			best_deal_destination=best.destination if best else "",
			best_deal_drop_pct=best.drop_percentage if best else 0.0,
		)


class TravelDealMonitorWorkflow(BaseWorkflow):
	"""Workflow for monitoring flight and hotel price drops."""

	workflow_id = "travel_deal_monitor"
	name = "Travel Deal Monitor"
	category = "travel"
	trust_level = TrustLevel.AUTO

	def __init__(
		self,
		service: TravelDealMonitorService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or TravelDealMonitorService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Receive a deal-check request."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Scan saved alerts for qualifying price drops."""
		deals = self.service.get_active_deals()
		summary = self.service.get_summary()
		return ActionPlan(
			action_type="surface_travel_deals",
			confidence=0.85,
			context={
				"active_deals": len(deals),
				"best_drop_pct": summary.best_deal_drop_pct,
				"best_destination": summary.best_deal_destination,
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Surface deals that crossed the threshold."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})
		deals = plan.context.get("active_deals", 0)
		return ActionResult(
			True,
			f"travel deal monitor: {deals} active deal(s) detected",
			{**plan.context, "policy": decision.reason},
		)
