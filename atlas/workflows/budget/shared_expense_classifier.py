"""Workflow #31: Shared Expense Classifier — classify transactions and calculate settlements.

This workflow manages shared expense tracking, classification, and settlement between
roommates/housemates. Features include merchant learning, recurring split rules,
settlement calculations, and reconciliation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class ExpenseClass(str, Enum):
	"""Classification of expense for settlement."""

	SHARED = "shared"  # Split between all occupants
	PERSONAL = "personal"  # Single occupant
	UNKNOWN = "unknown"  # Unclassified


class TransactionClass(str, Enum):
	"""Kind of transaction for learning."""

	GROCERIES = "groceries"
	UTILITIES = "utilities"
	RENT = "rent"
	FURNITURE = "furniture"
	HOUSEHOLD = "household"
	PERSONAL = "personal"
	OTHER = "other"


@dataclass(frozen=True, slots=True)
class Transaction:
	"""A financial transaction to classify."""

	transaction_id: str
	timestamp: datetime
	merchant: str
	amount: float
	payer: str  # Who paid
	description: str
	category: TransactionClass = TransactionClass.OTHER


@dataclass(frozen=True, slots=True)
class SharedExpense:
	"""A classified shared expense for settlement."""

	expense_id: str
	transaction_id: str
	merchant: str
	total_amount: float
	payer: str
	split_count: int
	share_per_person: float
	classification: ExpenseClass
	debtors: dict[str, float]  # person -> amount they owe
	settled: bool = False
	settled_at: datetime | None = None


@dataclass(slots=True)
class SplitRule:
	"""Rules for splitting expenses between occupants."""

	rule_id: str
	merchant_pattern: str  # Substring match
	class_hint: TransactionClass
	split_among: set[str]  # Occupants to include
	recurrence: int = 0  # 0 = one-time, 1 = weekly, 4 = monthly


@dataclass(frozen=True, slots=True)
class SettlementSummary:
	"""Summary of settlement between parties."""

	period_start: datetime
	period_end: datetime
	transactions: int
	total_shared: float  # Total amount in shared expenses
	balances: dict[str, float]  # person -> net amount owed (+ = owes, - = is owed)
	settlements: list[dict[str, object]]  # [{"from": p1, "to": p2, "amount": x}]


@dataclass(slots=True)
class ClassificationFeedback:
	"""Feedback on a classification to improve learning."""

	feedback_id: str
	expense_id: str
	original_class: ExpenseClass
	corrected_class: ExpenseClass
	merchant: str
	feedback_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
	reason: str | None = None


@dataclass(slots=True)
class SettlementRecord:
	"""Record of a completed settlement payment."""

	settlement_id: str
	from_person: str
	to_person: str
	amount: float
	timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
	confirmed: bool = False
	confirmed_at: datetime | None = None


class SharedExpenseService(PersistenceMixin):
	"""Service for classifying shared expenses and calculating settlements."""

	def __init__(self, occupants: list[str] | None = None, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self.occupants = occupants or []
		self._transactions: dict[str, Transaction] = {}
		self._expenses: dict[str, SharedExpense] = {}
		self._split_rules: dict[str, SplitRule] = {}
		self._merchant_memory: dict[str, TransactionClass] = {}
		self._feedback_history: dict[str, ClassificationFeedback] = {}
		self._settlement_records: dict[str, SettlementRecord] = {}

	def add_occupant(self, name: str) -> None:
		"""Register an occupant for splitting."""
		if name not in self.occupants:
			self.occupants.append(name)

	def add_split_rule(self, rule: SplitRule) -> None:
		"""Register a spending pattern rule."""
		self._split_rules[rule.rule_id] = rule
		if rule.merchant_pattern.lower() not in self._merchant_memory:
			self._merchant_memory[rule.merchant_pattern.lower()] = rule.class_hint

	def classify_transaction(self, transaction: Transaction) -> tuple[ExpenseClass, set[str]]:
		"""Classify a transaction and determine split."""
		merchant_lower = transaction.merchant.lower()

		# Check merchant memory first
		if merchant_lower in self._merchant_memory:
			split_among = self.occupants
			# See if there's a rule for this merchant
			for rule in self._split_rules.values():
				if rule.merchant_pattern.lower() in merchant_lower:
					split_among = list(rule.split_among)
					break

			# Shared if split across multiple, personal if single
			if len(split_among) > 1:
				return ExpenseClass.SHARED, set(split_among)
			return ExpenseClass.PERSONAL, set()

		# Heuristic classification based on keywords
		description_lower = (transaction.description + " " + transaction.merchant).lower()

		if any(k in description_lower for k in ["grocery", "food", "trader", "whole", "safeway"]):
			return ExpenseClass.SHARED, set(self.occupants)

		if any(k in description_lower for k in ["utility", "electric", "water", "internet", "gas"]):
			return ExpenseClass.SHARED, set(self.occupants)

		if any(k in description_lower for k in ["coffee", "lunch", "uber", "gas station", "parking"]):
			return ExpenseClass.PERSONAL, set()

		if any(k in description_lower for k in ["furniture", "hardware", "home depot", "target"]):
			return ExpenseClass.SHARED, set(self.occupants)

		# Default to unknown
		return ExpenseClass.UNKNOWN, set()

	def record_transaction(self, transaction: Transaction) -> SharedExpense | None:
		"""Record and classify a transaction."""
		self._transactions[transaction.transaction_id] = transaction

		classification, split_among = self.classify_transaction(transaction)

		if classification == ExpenseClass.PERSONAL:
			return None

		# For unknown, still record but don't settle automatically
		if classification == ExpenseClass.UNKNOWN:
			split_among = set()

		split_count = len(split_among) if split_among else 1
		share_per_person = transaction.amount / split_count if split_count > 0 else transaction.amount

		# Calculate debtors (everyone who should pay except the payer)
		debtors = {}
		for person in split_among:
			if person != transaction.payer:
				debtors[person] = share_per_person

		expense = SharedExpense(
			expense_id=f"exp_{transaction.transaction_id}",
			transaction_id=transaction.transaction_id,
			merchant=transaction.merchant,
			total_amount=transaction.amount,
			payer=transaction.payer,
			split_count=split_count,
			share_per_person=share_per_person,
			classification=classification,
			debtors=debtors,
		)

		self._expenses[expense.expense_id] = expense
		return expense

	def calculate_balance(self, person: str, start_date: datetime, end_date: datetime) -> float:
		"""Calculate balance for a person in a period (+ = owes, - = is owed)."""
		balance = 0.0

		for expense in self._expenses.values():
			if expense.settled:
				continue

			# Amount they paid out (they advanced)
			if expense.payer == person:
				# They should get reimbursed from debtors
				balance -= expense.total_amount
				# Except the amount others owe them
				for debtor in expense.debtors:
					balance += expense.debtors[debtor]

			# Amount they owe
			if person in expense.debtors:
				balance += expense.debtors[person]

		return balance

	def suggest_settlements(self, period_start: datetime, period_end: datetime) -> SettlementSummary:
		"""Suggest settlements for a period."""
		balances = {}

		for person in self.occupants:
			balance = self.calculate_balance(person, period_start, period_end)
			if abs(balance) > 0.01:  # Only include non-zero
				balances[person] = balance

		# Simple settlement: sort by who owes (positive), who is owed (negative)
		debtors = sorted([(p, b) for p, b in balances.items() if b > 0], key=lambda x: x[1], reverse=True)
		creditors = sorted([(p, abs(b)) for p, b in balances.items() if b < 0], key=lambda x: x[1], reverse=True)

		settlements = []
		debtors_copy = list(debtors)
		creditors_copy = list(creditors)

		while debtors_copy and creditors_copy:
			debtor, owed = debtors_copy[0]
			creditor, owed_to = creditors_copy[0]

			settle_amount = min(owed, owed_to)
			settlements.append({"from": debtor, "to": creditor, "amount": settle_amount})

			debtors_copy[0] = (debtor, owed - settle_amount)
			creditors_copy[0] = (creditor, owed_to - settle_amount)

			if debtors_copy[0][1] < 0.01:
				debtors_copy.pop(0)
			if creditors_copy[0][1] < 0.01:
				creditors_copy.pop(0)

		return SettlementSummary(
			period_start=period_start,
			period_end=period_end,
			transactions=len([t for t in self._transactions.values() if period_start <= t.timestamp <= period_end]),
			total_shared=sum(e.total_amount for e in self._expenses.values() if e.classification == ExpenseClass.SHARED),
			balances=balances,
			settlements=settlements,
		)

	def record_settlement(self, from_person: str, to_person: str, amount: float) -> SettlementRecord:
		"""Record a settlement payment between two people."""
		settlement_id = f"settlement_{from_person}_{to_person}_{datetime.now(timezone.utc).timestamp()}"
		record = SettlementRecord(
			settlement_id=settlement_id,
			from_person=from_person,
			to_person=to_person,
			amount=amount,
		)
		self._settlement_records[settlement_id] = record
		return record

	def confirm_settlement(self, settlement_id: str) -> bool:
		"""Mark a settlement as confirmed/paid."""
		if settlement_id not in self._settlement_records:
			return False
		
		record = self._settlement_records[settlement_id]
		record.confirmed = True
		record.confirmed_at = datetime.now(timezone.utc)
		return True

	def get_pending_settlements(self) -> list[SettlementRecord]:
		"""Get all unconfirmed settlements."""
		return [r for r in self._settlement_records.values() if not r.confirmed]

	def record_feedback(self, expense_id: str, original: ExpenseClass, corrected: ExpenseClass, merchant: str, reason: str | None = None) -> ClassificationFeedback:
		"""Record feedback on a classification to improve merchant memory."""
		feedback_id = f"feedback_{expense_id}_{datetime.now(timezone.utc).timestamp()}"
		feedback = ClassificationFeedback(
			feedback_id=feedback_id,
			expense_id=expense_id,
			original_class=original,
			corrected_class=corrected,
			merchant=merchant,
			reason=reason,
		)
		self._feedback_history[feedback_id] = feedback
		
		# Update merchant memory if corrected class is different from original
		if corrected.value != original.value:
			# Determine the transaction class based on corrected expense class
			if corrected == ExpenseClass.SHARED:
				# Try to infer transaction class from merchant or rule
				for rule in self._split_rules.values():
					if rule.merchant_pattern.lower() in merchant.lower():
						self._merchant_memory[merchant.lower()] = rule.class_hint
						break
				else:
					# Default to HOUSEHOLD for shared
					self._merchant_memory[merchant.lower()] = TransactionClass.HOUSEHOLD
		
		return feedback

	def get_feedback_history(self, merchant: str = "") -> list[ClassificationFeedback]:
		"""Get feedback history, optionally filtered by merchant."""
		if not merchant:
			return list(self._feedback_history.values())
		return [f for f in self._feedback_history.values() if f.merchant.lower() == merchant.lower()]

	def get_settlement_history(self, person: str = "") -> list[SettlementRecord]:
		"""Get settlement history, optionally filtered by person involved."""
		if not person:
			return list(self._settlement_records.values())
		return [s for s in self._settlement_records.values() if s.from_person == person or s.to_person == person]


class SharedExpenseClassifierWorkflow(BaseWorkflow):
	"""Workflow for classifying shared expenses and managing settlements."""

	workflow_id = "shared_expense_classifier"
	name = "Shared Expense Classifier"
	category = "budget"
	trust_level = TrustLevel.DRAFT

	def __init__(
		self,
		service: SharedExpenseService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or SharedExpenseService(session=session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Record a new transaction."""
		self.state_machine.transition("planning", {"event_type": event.event_type})

		if event.event_type == "expense_recorded":
			transaction = Transaction(
				transaction_id=str(event.payload.get("transaction_id", "")),
				timestamp=datetime.fromisoformat(str(event.payload.get("timestamp", datetime.now(timezone.utc).isoformat()))),
				merchant=str(event.payload.get("merchant", "")),
				amount=float(event.payload.get("amount", 0)),
				payer=str(event.payload.get("payer", "")),
				description=str(event.payload.get("description", "")),
				category=TransactionClass(event.payload.get("category", "other")),
			)
			self.service.record_transaction(transaction)

		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Analyze and classify the expense."""
		payload = run.event.payload
		transaction_id = str(payload.get("transaction_id", ""))

		if transaction_id not in self.service._transactions:
			return ActionPlan(
				action_type="classification_failed",
				confidence=0.0,
				context={"transaction_id": transaction_id},
			)

		transaction = self.service._transactions[transaction_id]
		classification, split_among = self.service.classify_transaction(transaction)

		if classification == ExpenseClass.UNKNOWN:
			confidence = 0.4  # Low confidence for unknown
		elif classification == ExpenseClass.PERSONAL:
			confidence = 0.95  # High confidence personal
		else:
			confidence = 0.85  # Good confidence shared

		return ActionPlan(
			action_type="classify_expense",
			confidence=confidence,
			context={
				"transaction_id": transaction_id,
				"merchant": transaction.merchant,
				"amount": transaction.amount,
				"payer": transaction.payer,
				"classification": classification.value,
				"split_among": list(split_among),
				"notes": f"Transaction classified as {classification.value}",
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Execute classification with policy gating."""
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
			f"Expense classified as {plan.context.get('classification')}",
			{**plan.context, "policy": decision.reason},
		)
