"""Workflow #84: Warranty Tracker — Phase 2 Priority.
Tracks warranty expiration dates for appliances, electronics, and home systems.
Recommended phase: 2 (quick_win_score: 11) | Trust level: auto | Category: home
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class WarrantyCategory(str, Enum):
	"""Category of warranted item."""

	APPLIANCE = "appliance"
	ELECTRONICS = "electronics"
	HVAC = "hvac"
	ROOFING = "roofing"
	PLUMBING = "plumbing"
	FURNITURE = "furniture"
	VEHICLE = "vehicle"
	OTHER = "other"


class WarrantyStatus(str, Enum):
	"""Status of a warranty."""

	ACTIVE = "active"
	EXPIRING_SOON = "expiring_soon"  # within 90 days
	EXPIRED = "expired"
	CLAIMED = "claimed"


@dataclass(slots=True)
class WarrantyItem:
	"""A tracked item with warranty information."""

	warranty_id: str
	item_name: str
	category: WarrantyCategory
	purchase_date: date
	warranty_expiry: date
	manufacturer: str
	model_number: str
	status: WarrantyStatus
	days_remaining: int
	purchase_price: float = 0.0
	serial_number: str = ""
	support_contact: str = ""


@dataclass(frozen=True, slots=True)
class WarrantySummary:
	"""Summary of tracked warranties."""

	total_tracked: int
	active_count: int
	expiring_soon_count: int
	expired_count: int
	expiring_within_90_days: list[str]


WARRANTY_EXPIRY_ALERT_DAYS = 90


class WarrantyTrackerService(PersistenceMixin):
	"""Service for tracking appliance and electronics warranties."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._warranties: dict[str, WarrantyItem] = {}

	def add_warranty(
		self,
		warranty_id: str,
		item_name: str,
		category: WarrantyCategory,
		purchase_date: date,
		warranty_expiry: date,
		manufacturer: str = "",
		model_number: str = "",
		purchase_price: float = 0.0,
		serial_number: str = "",
		support_contact: str = "",
	) -> WarrantyItem:
		"""Add a warranty to track."""
		days_remaining = (warranty_expiry - date.today()).days
		if days_remaining < 0:
			status = WarrantyStatus.EXPIRED
		elif days_remaining <= WARRANTY_EXPIRY_ALERT_DAYS:
			status = WarrantyStatus.EXPIRING_SOON
		else:
			status = WarrantyStatus.ACTIVE

		item = WarrantyItem(
			warranty_id=warranty_id,
			item_name=item_name,
			category=category,
			purchase_date=purchase_date,
			warranty_expiry=warranty_expiry,
			manufacturer=manufacturer,
			model_number=model_number,
			status=status,
			days_remaining=days_remaining,
			purchase_price=purchase_price,
			serial_number=serial_number,
			support_contact=support_contact,
		)
		self._warranties[warranty_id] = item
		return item

	def mark_claimed(self, warranty_id: str) -> bool:
		"""Mark a warranty item as claimed."""
		if warranty_id not in self._warranties:
			return False
		self._warranties[warranty_id].status = WarrantyStatus.CLAIMED
		return True

	def get_expiring_soon(self, within_days: int = WARRANTY_EXPIRY_ALERT_DAYS) -> list[WarrantyItem]:
		"""Get warranties expiring within the specified window."""
		return [
			w for w in self._warranties.values()
			if 0 <= w.days_remaining <= within_days and w.status != WarrantyStatus.CLAIMED
		]

	def get_by_category(self, category: WarrantyCategory) -> list[WarrantyItem]:
		"""Get all warranties in a category."""
		return [w for w in self._warranties.values() if w.category == category]

	def get_summary(self) -> WarrantySummary:
		"""Get warranty summary."""
		all_w = list(self._warranties.values())
		active = [w for w in all_w if w.status == WarrantyStatus.ACTIVE]
		expiring = [w for w in all_w if w.status == WarrantyStatus.EXPIRING_SOON]
		expired = [w for w in all_w if w.status == WarrantyStatus.EXPIRED]
		return WarrantySummary(
			total_tracked=len(all_w),
			active_count=len(active),
			expiring_soon_count=len(expiring),
			expired_count=len(expired),
			expiring_within_90_days=[
				f"{w.item_name} ({w.days_remaining}d remaining)" for w in expiring
			],
		)


class WarrantyTrackerAgent(BaseWorkflow):
	"""Workflow for tracking and alerting on warranty expirations."""

	workflow_id = "warranty_tracker"
	name = "Warranty Tracker"
	category = "home"
	trust_level = TrustLevel.AUTO

	def __init__(
		self,
		service: WarrantyTrackerService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or WarrantyTrackerService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle warranty check requests."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Identify expiring warranties and build alert plan."""
		summary = self.service.get_summary()
		expiring = self.service.get_expiring_soon()
		return ActionPlan(
			action_type="check_warranties",
			confidence=0.90,
			context={
				"total_tracked": summary.total_tracked,
				"active_count": summary.active_count,
				"expiring_soon_count": summary.expiring_soon_count,
				"expired_count": summary.expired_count,
				"expiring_items": summary.expiring_within_90_days,
				"needs_attention": len(expiring) > 0,
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Emit warranty check result."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})
		expiring = plan.context.get("expiring_soon_count", 0)
		total = plan.context.get("total_tracked", 0)
		if expiring:
			summary_text = f"{expiring} warranty(ies) expiring within 90 days ({total} total tracked)"
		else:
			summary_text = f"All {total} warranties current"
		return ActionResult(True, summary_text, {**plan.context, "policy": decision.reason})
