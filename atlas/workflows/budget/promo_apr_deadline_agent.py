"""Workflow #36: Promo APR Deadline Agent — tracks promo APR expirations and escalates warnings.

This workflow monitors promotional APR offers and generates escalating alerts as deadlines approach.
It demonstrates sophisticated action planning with escalation tiers and detailed financial recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class EscalationLevel(str, Enum):
	"""Escalation level based on days remaining."""

	NORMAL = "normal"  # > 30 days
	ELEVATED = "elevated"  # 10-30 days
	URGENT = "urgent"  # 3-10 days
	CRITICAL = "critical"  # < 3 days


@dataclass(slots=True)
class PromoAPR:
	"""Promotional APR offer tracking."""

	promo_id: str
	card_name: str
	promo_rate: float
	regular_rate: float
	balance: float
	end_date: date
	status: str = "tracking"


@dataclass(frozen=True, slots=True)
class BalanceTransferOption:
	"""Optional balance transfer recommendation."""

	target_card: str
	target_apr: float
	transfer_fee_percent: float  # Typically 1-3%
	net_savings_annual: float


@dataclass(frozen=True, slots=True)
class PayoffPlan:
	"""Financial payoff plan recommendation."""

	monthly_payment: float
	months_remaining: int
	total_interest_saved: float
	interest_if_missed: float
	escalation_level: EscalationLevel
	balance_transfer_option: BalanceTransferOption | None = None


@dataclass(frozen=True, slots=True)
class PromoAlert:
	"""Alert for approaching promo deadline."""

	promo_id: str
	card_name: str
	days_remaining: int
	escalation: EscalationLevel
	payoff_plan: PayoffPlan
	message: str


class PromoAprService(PersistenceMixin):
	"""Service for managing promotional APR offers."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._promos: dict[str, PromoAPR] = {}
		self._escalation_history: dict[str, set[EscalationLevel]] = {}
		self._transfer_targets: dict[str, list[BalanceTransferOption]] = {}

	def add_promo(self, promo: PromoAPR) -> PromoAPR:
		"""Track a new promotional APR offer."""
		self._promos[promo.promo_id] = promo
		self._escalation_history[promo.promo_id] = set()
		return promo

	def check_approaching(self, days_ahead: int, today: date) -> list[PromoAPR]:
		"""Find promos expiring within specified days."""
		results: list[PromoAPR] = []
		for promo in self._promos.values():
			days_remaining = (promo.end_date - today).days
			if 0 <= days_remaining <= days_ahead and promo.status == "tracking":
				results.append(promo)
		return results

	def get_escalation_level(self, days_remaining: int) -> EscalationLevel:
		"""Determine escalation level based on days remaining."""
		if days_remaining < 3:
			return EscalationLevel.CRITICAL
		elif days_remaining < 10:
			return EscalationLevel.URGENT
		elif days_remaining <= 30:
			return EscalationLevel.ELEVATED
		return EscalationLevel.NORMAL

	def set_balance_transfer_targets(self, card_id: str, options: list[BalanceTransferOption]) -> None:
		"""Register available balance transfer targets for a card."""
		self._transfer_targets[card_id] = options

	def get_best_balance_transfer(self, card_id: str, balance: float) -> BalanceTransferOption | None:
		"""Find the best balance transfer option if available."""
		options = self._transfer_targets.get(card_id, [])
		if not options:
			return None

		# Filter to options with positive net savings
		viable = [opt for opt in options if opt.net_savings_annual > (balance * opt.transfer_fee_percent / 100)]

		if not viable:
			return None

		# Return option with highest net savings
		return max(viable, key=lambda o: o.net_savings_annual)

	def calculate_payoff_plan(self, promo: PromoAPR, today: date) -> PayoffPlan:
		"""Calculate detailed payoff plan with escalation level and balance transfer options."""
		days_remaining = (promo.end_date - today).days
		months_remaining = max(1, (promo.end_date.year - today.year) * 12 + promo.end_date.month - today.month)

		monthly_payment = round(promo.balance / months_remaining, 2)
		interest_delta = max(0.0, promo.regular_rate - promo.promo_rate)
		total_interest_saved = round(promo.balance * (interest_delta / 100.0 * (months_remaining / 12.0)), 2)

		# If deadline is missed, calculate monthly interest cost
		interest_if_missed = round(promo.balance * (promo.regular_rate / 100.0), 2)

		escalation = self.get_escalation_level(days_remaining)

		# Check for viable balance transfer options
		transfer_option = self.get_best_balance_transfer(promo.promo_id, promo.balance)

		return PayoffPlan(
			monthly_payment=monthly_payment,
			months_remaining=months_remaining,
			total_interest_saved=total_interest_saved,
			interest_if_missed=interest_if_missed,
			escalation_level=escalation,
			balance_transfer_option=transfer_option,
		)

	def generate_alert(self, promo: PromoAPR, today: date) -> PromoAlert | None:
		"""Generate an alert for an approaching promo."""
		days_remaining = (promo.end_date - today).days

		if days_remaining < 0 or promo.status != "tracking":
			return None

		payoff_plan = self.calculate_payoff_plan(promo, today)
		escalation = payoff_plan.escalation_level

		# Check if we should alert at this escalation level (allow only new escalations)
		if escalation in self._escalation_history.get(promo.promo_id, set()):
			return None

		self._escalation_history[promo.promo_id].add(escalation)

		message = self._build_alert_message(promo, days_remaining, payoff_plan, escalation)

		return PromoAlert(
			promo_id=promo.promo_id,
			card_name=promo.card_name,
			days_remaining=days_remaining,
			escalation=escalation,
			payoff_plan=payoff_plan,
			message=message,
		)

	def _build_alert_message(
		self,
		promo: PromoAPR,
		days_remaining: int,
		plan: PayoffPlan,
		escalation: EscalationLevel,
	) -> str:
		"""Build a human-readable alert message."""
		emoji_map = {
			EscalationLevel.ELEVATED: "⚠️",
			EscalationLevel.URGENT: "🔴",
			EscalationLevel.CRITICAL: "🚨",
			EscalationLevel.NORMAL: "ℹ️",
		}
		emoji = emoji_map.get(escalation, "")

		base = f"{emoji} {promo.card_name} promo APR expires in {days_remaining} days"

		transfer_note = ""
		if plan.balance_transfer_option:
			transfer_note = f" [OR transfer to {plan.balance_transfer_option.target_card} @ {plan.balance_transfer_option.target_apr}% = ${plan.balance_transfer_option.net_savings_annual:.0f} saved annually]"

		if escalation == EscalationLevel.CRITICAL:
			return f"{base} [CRITICAL]. Payoff plan: ${plan.monthly_payment}/month × {plan.months_remaining} months = ${plan.total_interest_saved} saved. Penalty if missed: ${plan.interest_if_missed}/month at {promo.regular_rate}%.{transfer_note}"

		elif escalation == EscalationLevel.URGENT:
			return f"{base}. To keep rate, pay ${plan.monthly_payment}/month (saves ${plan.total_interest_saved} total).{transfer_note}"

		elif escalation == EscalationLevel.ELEVATED:
			return f"{base}. Plan now: ${plan.monthly_payment}/month helps save ${plan.total_interest_saved}.{transfer_note}"

		return f"{base}. Promo rate: {promo.promo_rate}% → Regular: {promo.regular_rate}%.{transfer_note}"


class PromoAprDeadlineWorkflow(BaseWorkflow):
	"""Workflow for monitoring and alerting on promo APR deadlines."""

	workflow_id = "promo_apr_deadline"
	name = "Promo APR Deadline Agent"
	category = "budget"
	trust_level = TrustLevel.AUTO

	def __init__(self, service: PromoAprService | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = service or PromoAprService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Initialize workflow run from promo event."""
		self.state_machine.transition("planning", {"event_type": event.event_type})

		if event.event_type == "promo_added":
			payload = event.payload
			self.service.add_promo(
				PromoAPR(
					promo_id=str(payload["promo_id"]),
					card_name=str(payload["card_name"]),
					promo_rate=float(payload.get("promo_rate", 0.0)),
					regular_rate=float(payload.get("regular_rate", 21.0)),
					balance=float(payload.get("balance", 0.0)),
					end_date=date.fromisoformat(str(payload["end_date"])),
				)
			)

		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Generate action plan by checking for approaching deadlines."""
		today = date.fromisoformat(str(run.event.payload.get("today", date.today().isoformat())))
		days_ahead = int(run.event.payload.get("days_ahead", 90))

		approaching = self.service.check_approaching(days_ahead, today)
		alerts = []

		for promo in approaching:
			alert = self.service.generate_alert(promo, today)
			if alert:
				alerts.append(alert)

		# Confidence increases with number of alerts to address
		confidence = min(0.95, 0.7 + (0.05 * len(alerts)))

		return ActionPlan(
			action_type="escalate_promo_deadlines",
			confidence=confidence,
			context={
				"today": today.isoformat(),
				"alerts_count": len(alerts),
				"alert_details": [
					{
						"card": a.card_name,
						"days_remaining": a.days_remaining,
						"escalation": a.escalation.value,
						"monthly_payment": a.payoff_plan.monthly_payment,
						"message": a.message,
					}
					for a in alerts
				],
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute action plan via policy engine."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})

		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)

		if not decision.allowed:
			self.state_machine.transition("failed", {"reason": decision.reason})
			return ActionResult(False, decision.reason, plan.context)

		self.state_machine.transition("completed", {"reason": decision.reason})
		return ActionResult(
			True,
			f"Escalated {plan.context['alerts_count']} promo deadline alerts.",
			{**plan.context, "policy_decision": decision.reason},
		)
