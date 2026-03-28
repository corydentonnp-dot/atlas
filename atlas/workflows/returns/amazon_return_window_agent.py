"""Workflow #43: Amazon Return Window Agent — tracks order return deadlines.

Monitors Amazon purchase return windows and sends escalating alerts as deadlines approach.
Demonstrates simple deadline tracking with multi-tier urgency levels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from uuid import uuid4

from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class ReturnStatus(str, Enum):
	"""Return window status."""

	TRACKING = "tracking"
	WINDOW_CLOSING = "window_closing"
	WINDOW_CLOSED = "window_closed"
	RETURNED = "returned"
	KEEPING = "keeping"


class ReturnUrgency(str, Enum):
	"""Return urgency level."""

	NORMAL = "normal"  # > 7 days
	WARNING = "warning"  # 3-7 days
	URGENT = "urgent"  # 1-3 days
	EXPIRED = "expired"  # < 1 day or past deadline


@dataclass(slots=True)
class AmazonOrder:
	"""Amazon order with return window tracking."""

	order_id: str
	item_name: str
	purchase_date: date
	return_deadline: date
	asin: str = ""
	amount: float = 0.0
	status: ReturnStatus = ReturnStatus.TRACKING
	notes: str = ""


@dataclass(frozen=True, slots=True)
class ReturnAlert:
	"""Alert for approaching return deadline."""

	order_id: str
	item_name: str
	days_remaining: int
	urgency: ReturnUrgency
	return_deadline: date
	action_url: str = "https://www.amazon.com/returns"


class AmazonReturnService:
	"""Service for tracking Amazon order return windows."""

	def __init__(self) -> None:
		self._orders: dict[str, AmazonOrder] = {}
		self._return_history: dict[str, set[ReturnStatus]] = {}

	def add_order(self, order: AmazonOrder) -> AmazonOrder:
		"""Track a new Amazon order with return window."""
		self._orders[order.order_id] = order
		self._return_history[order.order_id] = {order.status}
		return order

	def check_closing_soon(self, days_ahead: int, today: date) -> list[AmazonOrder]:
		"""Find orders with return windows closing within specified days."""
		results: list[AmazonOrder] = []
		for order in self._orders.values():
			days_remaining = (order.return_deadline - today).days
			if 0 <= days_remaining <= days_ahead and order.status == ReturnStatus.TRACKING:
				results.append(order)
		results.sort(key=lambda o: (o.return_deadline - today).days)
		return results

	def get_urgency(self, days_remaining: int) -> ReturnUrgency:
		"""Determine urgency level based on days remaining."""
		if days_remaining < 1:
			return ReturnUrgency.EXPIRED
		elif days_remaining <= 3:
			return ReturnUrgency.URGENT
		elif days_remaining <= 7:
			return ReturnUrgency.WARNING
		return ReturnUrgency.NORMAL

	def mark_returned(self, order_id: str) -> bool:
		"""Mark an order as returned."""
		if order_id in self._orders:
			self._orders[order_id].status = ReturnStatus.RETURNED
			self._return_history[order_id].add(ReturnStatus.RETURNED)
			return True
		return False

	def mark_keeping(self, order_id: str) -> bool:
		"""Mark an order as keeping (not returning)."""
		if order_id in self._orders:
			self._orders[order_id].status = ReturnStatus.KEEPING
			self._return_history[order_id].add(ReturnStatus.KEEPING)
			return True
		return False

	def get_return_alert(self, order: AmazonOrder, today: date) -> ReturnAlert | None:
		"""Generate alert for order if return window is open."""
		if order.status != ReturnStatus.TRACKING:
			return None
		days_remaining = (order.return_deadline - today).days
		if days_remaining < 0:
			order.status = ReturnStatus.WINDOW_CLOSED
			return None
		urgency = self.get_urgency(days_remaining)
		return ReturnAlert(
			order_id=order.order_id,
			item_name=order.item_name,
			days_remaining=days_remaining,
			urgency=urgency,
			return_deadline=order.return_deadline,
		)

	def list_all(self) -> list[AmazonOrder]:
		"""List all tracked orders."""
		return list(self._orders.values())


class AmazonReturnWindowAgent(BaseWorkflow):
	"""Workflow for tracking Amazon return windows and sending alerts."""

	name = "amazon_return_window_agent"
	description = "Track Amazon order return windows; escalate alerts as deadline approaches"
	category = "returns"
	version = "1.0.0"

	def __init__(self) -> None:
		super().__init__()
		self.service = AmazonReturnService()
		self.policy = PolicyEngine()

	def trigger(self, event: WorkflowEvent) -> bool:
		"""Triggered by daily check or manual order submission."""
		return event.event_type in {"order.added", "return.check_due"}

	def process(self, run: WorkflowRun) -> ActionPlan:
		"""Identify orders with closing return windows."""
		if not run.input_data:
			# Daily check mode
			today = date.today()
			closing_soon = self.service.check_closing_soon(days_ahead=30, today=today)
			if not closing_soon:
				return ActionPlan(
					action="wait",
					rationale="No return windows closing soon",
					next_scheduled=date.today().isoformat(),
				)
			run.add_output("orders_closing_soon", len(closing_soon))
			run.add_output("order_details", [
				{
					"order_id": o.order_id,
					"item": o.item_name,
					"deadline": o.return_deadline.isoformat(),
					"days_left": (o.return_deadline - today).days,
				}
				for o in closing_soon
			])
			return ActionPlan(
				action="notify",
				rationale=f"Found {len(closing_soon)} orders with closing return windows",
				target_audience="user",
				next_scheduled=date.today().isoformat(),
			)
		else:
			# New order added
			order_data = run.input_data
			order = AmazonOrder(
				order_id=order_data.get("order_id", str(uuid4())),
				item_name=order_data.get("item_name", "Unknown Item"),
				purchase_date=date.fromisoformat(order_data.get("purchase_date", date.today().isoformat())),
				return_deadline=date.fromisoformat(order_data.get("return_deadline")),
				asin=order_data.get("asin", ""),
				amount=float(order_data.get("amount", 0.0)),
			)
			added = self.service.add_order(order)
			run.add_output("order_id", added.order_id)
			run.add_output("return_deadline_days", (added.return_deadline - date.today()).days)
			return ActionPlan(
				action="track",
				rationale=f"Tracking return window for {added.item_name}",
				next_scheduled=date.today().isoformat(),
			)

	def act(self, plan: ActionPlan, run: WorkflowRun) -> ActionResult:
		"""Send notification or record action."""
		if plan.action == "notify":
			details = run.output_data.get("order_details", [])
			message = f"⏰ Return deadlines approaching:\n"
			for detail in details:
				message += f"- {detail['item']} ({detail['days_left']} days left)\n"
			return ActionResult(
				success=True,
				action_taken="notification_sent",
				summary=message,
				details={"order_count": len(details)},
			)
		elif plan.action == "track":
			return ActionResult(
				success=True,
				action_taken="order_tracked",
				summary=f"Tracking order {run.output_data.get('order_id')}",
			)
		else:
			return ActionResult(
				success=True,
				action_taken="wait",
				summary="No urgent return windows at this time",
			)

	def close(self, result: ActionResult, run: WorkflowRun) -> None:
		"""Log final status."""
		run.add_output("final_status", "completed")
		run.add_output("action", result.action_taken)
