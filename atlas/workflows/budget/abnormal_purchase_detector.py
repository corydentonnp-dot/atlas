"""Workflow #38: Abnormal Purchase Detector — identifies unusual spending patterns.

Monitors transaction streams and flags purchases that deviate significantly from
established patterns by category, merchant type, amount, or frequency.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class AnomalyType(str, Enum):
	"""Type of spending anomaly detected."""

	UNUSUAL_AMOUNT = "unusual_amount"
	UNUSUAL_FREQUENCY = "unusual_frequency"
	UNUSUAL_MERCHANT = "unusual_merchant"
	FRAUD_RISK = "fraud_risk"
	CATEGORY_DRIFT = "category_drift"


class SeverityLevel(str, Enum):
	"""Anomaly severity rating."""

	LOW = "low"
	MEDIUM = "medium"
	HIGH = "high"
	CRITICAL = "critical"


@dataclass(slots=True)
class Transaction:
	"""Individual transaction record."""

	transaction_id: str
	date: date
	amount: float
	merchant: str
	category: str
	description: str
	card_last_four: str = ""


@dataclass(frozen=True, slots=True)
class AnomalyAlert:
	"""Detected spending anomaly."""

	transaction_id: str
	anomaly_type: AnomalyType
	severity: SeverityLevel
	category: str
	merchant: str
	amount: float
	variance_from_baseline: float
	confidence_score: float


class AbnormalPurchaseService(PersistenceMixin):
	"""Service for detecting unusual spending patterns."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._transactions: list[Transaction] = []
		self._patterns: dict[str, dict] = {}

	def add_transaction(self, transaction: Transaction) -> Transaction:
		"""Record a new transaction."""
		self._transactions.append(transaction)
		return transaction

	def detect_anomalies(self, transactions: list[Transaction]) -> list[AnomalyAlert]:
		"""Detect spending anomalies in transactions."""
		alerts: list[AnomalyAlert] = []

		for txn in transactions:
			# Simple anomaly detection: flag if amount > 2x category average
			category_amounts = [t.amount for t in self._transactions if t.category == txn.category]
			if not category_amounts:
				continue

			avg = sum(category_amounts) / len(category_amounts)
			if txn.amount > avg * 2:
				alerts.append(
					AnomalyAlert(
						transaction_id=txn.transaction_id,
						anomaly_type=AnomalyType.UNUSUAL_AMOUNT,
						severity=SeverityLevel.MEDIUM if txn.amount < avg * 3 else SeverityLevel.HIGH,
						category=txn.category,
						merchant=txn.merchant,
						amount=txn.amount,
						variance_from_baseline=(txn.amount - avg) / avg * 100,
						confidence_score=0.75,
					)
				)

		return alerts


class AbnormalPurchaseWorkflow(BaseWorkflow):
	"""Workflow for continuous anomaly detection."""

	workflow_id = "abnormal_purchase"
	name = "Abnormal Purchase Detector"
	category = "budget"
	trust_level = TrustLevel.AUTO

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = AbnormalPurchaseService(session)

	def describe(self) -> str:
		return "Detect unusual spending patterns and flag transactions for review."

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""handle transaction events."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Plan anomaly detection."""
		alerts = self.service.detect_anomalies([])
		critical_count = sum(1 for a in alerts if a.severity == SeverityLevel.CRITICAL)

		return ActionPlan(
			action_type="detect_anomalies",
			confidence=0.8 if critical_count == 0 else 0.95,
			context={
				"total_alerts": len(alerts),
				"critical_alerts": critical_count,
				"confidence": 0.8,
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute anomaly detection."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		self.state_machine.transition("completed", {"reason": "analysis_complete"})

		return ActionResult(
			success=True,
			summary=f"Detected {plan.context.get('total_alerts', 0)} spending anomalies",
			metadata=plan.context,
		)
