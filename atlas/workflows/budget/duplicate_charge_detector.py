"""Workflow #40: Duplicate Charge Detector — identifies potentially duplicate transactions.

Analyzes transaction history to find duplicate or near-duplicate charges that may
indicate billing errors or fraudulent activity.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class DuplicateConfidence(str, Enum):
	"""Confidence level for duplicate detection."""

	HIGH = "high"  # Exact match or >95% similar
	MEDIUM = "medium"  # >85% similar
	LOW = "low"  # >70% similar


@dataclass(slots=True)
class Transaction:
	"""Transaction record."""

	transaction_id: str
	date: date
	amount: float
	merchant: str
	category: str
	description: str = ""


@dataclass(frozen=True, slots=True)
class DuplicateMatch:
	"""Identified duplicate or near-duplicate."""

	transaction_id_1: str
	transaction_id_2: str
	merchant: str
	amount: float
	date_diff_days: int
	confidence: DuplicateConfidence
	similarity_score: float
	recommendation: str


class DuplicateChargeService(PersistenceMixin):
	"""Service for detecting duplicate charges."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._transactions: dict[str, Transaction] = {}

	def add_transaction(self, txn: Transaction) -> Transaction:
		"""Register a transaction."""
		self._transactions[txn.transaction_id] = txn
		return txn

	def find_duplicates(self, time_window_days: int = 7) -> list[DuplicateMatch]:
		"""Find potential duplicate charges."""
		duplicates: list[DuplicateMatch] = []
		txn_list = sorted(self._transactions.values(), key=lambda t: t.date)

		for i, txn1 in enumerate(txn_list):
			for txn2 in txn_list[i + 1 :]:
				date_diff = (txn2.date - txn1.date).days

				if date_diff > time_window_days:
					break

				# Check for exact or near-match
				if abs(txn1.amount - txn2.amount) < 0.01 and txn1.merchant == txn2.merchant:
					# Exact match on amount and merchant
					similarity = 1.0
					confidence = DuplicateConfidence.HIGH
					recommendation = "Likely duplicate. Contact merchant to verify."
				elif (
					abs(txn1.amount - txn2.amount) / max(txn1.amount, txn2.amount) < 0.05
					and txn1.merchant == txn2.merchant
				):
					# Close match on amount and exact merchant match
					similarity = 0.95
					confidence = DuplicateConfidence.HIGH
					recommendation = "Probable duplicate. Review with merchant."
				elif (
					abs(txn1.amount - txn2.amount) / max(txn1.amount, txn2.amount) < 0.15
					and txn1.category == txn2.category
				):
					# Similar category and amount, but different merchant
					similarity = 0.80
					confidence = DuplicateConfidence.MEDIUM
					recommendation = "Possible duplicate or subscription. Verify."
				else:
					continue

				duplicates.append(
					DuplicateMatch(
						transaction_id_1=txn1.transaction_id,
						transaction_id_2=txn2.transaction_id,
						merchant=txn1.merchant,
						amount=txn1.amount,
						date_diff_days=date_diff,
						confidence=confidence,
						similarity_score=similarity,
						recommendation=recommendation,
					)
				)

		return duplicates

	def get_duplicate_summary(self) -> dict:
		"""Get summary of duplicates found."""
		duplicates = self.find_duplicates()
		high_conf = [d for d in duplicates if d.confidence == DuplicateConfidence.HIGH]
		return {
			"total_duplicates": len(duplicates),
			"high_confidence": len(high_conf),
			"total_transactions": len(self._transactions),
		}


class DuplicateChargeWorkflow(BaseWorkflow):
	"""Workflow for duplicate charge detection."""

	workflow_id = "duplicate_charge"
	name = "Duplicate Charge Detector"
	category = "budget"
	trust_level = TrustLevel.AUTO

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = DuplicateChargeService(session)

	def describe(self) -> str:
		return "Detect potential duplicate charges and billing errors."

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle transaction events."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Plan duplicate detection."""
		duplicates = self.service.find_duplicates()

		return ActionPlan(
			action_type="find_duplicates",
			confidence=0.85,
			context={
				"duplicates_found": len(duplicates),
				"transactions_analyzed": len(self.service._transactions),
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute duplicate detection."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		self.state_machine.transition("completed", {"reason": "detection_complete"})

		return ActionResult(
			success=True,
			summary=f"Found {plan.context.get('duplicates_found', 0)} potential duplicates",
			metadata=plan.context,
		)
