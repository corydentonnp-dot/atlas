"""Tests for Phase 5 workflows (budget intelligence tier)."""

import pytest
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.workflows.budget.abnormal_purchase_detector import (
	AbnormalPurchaseService,
	AbnormalPurchaseWorkflow,
	Transaction,
)
from atlas.workflows.budget.amazon_split_agent import AmazonSplitService, AmazonSplitWorkflow
from atlas.workflows.budget.budget_drift_agent import BudgetDriftService, BudgetDriftWorkflow
from atlas.workflows.budget.duplicate_charge_detector import DuplicateChargeService, DuplicateChargeWorkflow
from atlas.workflows.budget.refund_chase_agent import RefundChaseService, RefundChaseWorkflow
from atlas.workflows.budget.settlement_prep_agent import SettlementPrepService, SettlementPrepWorkflow


class TestPhase5ServiceInstantiation:
	"""Test that Phase 5 services instantiate correctly."""

	def test_abnormal_purchase_service_init(self) -> None:
		"""Service instantiates with optional session."""
		service = AbnormalPurchaseService()
		assert service is not None
		assert service._transactions == []
		assert service._patterns == {}

	def test_amazon_split_service_init(self) -> None:
		"""Service instantiates with optional session."""
		service = AmazonSplitService()
		assert service is not None
		assert service._orders == {}
		assert service._settlements == {}

	def test_budget_drift_service_init(self) -> None:
		"""Service instantiates with optional session."""
		service = BudgetDriftService()
		assert service is not None
		assert service._categories == {}
		assert service._spending == []

	def test_duplicate_charge_service_init(self) -> None:
		"""Service instantiates with optional session."""
		service = DuplicateChargeService()
		assert service is not None
		assert service._transactions == {}

	def test_refund_chase_service_init(self) -> None:
		"""Service instantiates with optional session."""
		service = RefundChaseService()
		assert service is not None
		assert service._refunds == {}
		assert service._reminders_sent == {}

	def test_settlement_prep_service_init(self) -> None:
		"""Service instantiates with optional session."""
		service = SettlementPrepService()
		assert service is not None
		assert service._expenses == []
		assert service._settlements == {}


class TestAbnormalPurchaseServiceMethods:
	"""Test AbnormalPurchaseService methods."""

	def test_add_transaction(self) -> None:
		"""Service can add transactions."""
		from datetime import date

		service = AbnormalPurchaseService()
		txn = Transaction("txn123", date.today(), 50.0, "Starbucks", "food", "Coffee")
		result = service.add_transaction(txn)
		assert result == txn
		assert len(service._transactions) == 1

	def test_detect_anomalies_empty_list(self) -> None:
		"""Service returns empty list when no anomalies found."""
		service = AbnormalPurchaseService()
		alerts = service.detect_anomalies([])
		assert alerts == []

	def test_detect_anomalies_with_data(self) -> None:
		"""Service detects anomalies in transaction lists."""
		from datetime import date

		service = AbnormalPurchaseService()
		# Add baseline transaction
		baseline = Transaction("txn1", date.today(), 50.0, "Store A", "groceries", "Groceries")
		service.add_transaction(baseline)

		# Add anomalous transaction (2x the baseline)
		anomaly = Transaction("txn2", date.today(), 120.0, "Store A", "groceries", "Large purchase")
		alerts = service.detect_anomalies([anomaly])

		assert len(alerts) > 0
		assert alerts[0].amount == 120.0


class TestAmazonSplitServiceMethods:
	"""Test AmazonSplitService methods."""

	def test_add_order(self) -> None:
		"""Service can add Amazon orders."""
		from datetime import date

		service = AmazonSplitService()
		from atlas.workflows.budget.amazon_split_agent import AmazonOrder, AmazonItem, ItemCategory

		item = AmazonItem("item1", "SKU123", "Book", 29.99, 1, ItemCategory.PERSONAL)
		order = AmazonOrder("ORD123", date.today(), 29.99, [item])
		result = service.add_order(order)
		assert result == order
		assert len(service._orders) == 1

	def test_calculate_settlement(self) -> None:
		"""Service can calculate settlements for shared items."""
		from datetime import date

		service = AmazonSplitService()
		from atlas.workflows.budget.amazon_split_agent import AmazonOrder, AmazonItem, ItemCategory

		item = AmazonItem("item1", "SKU123", "Household Item", 100.0, 1, ItemCategory.HOUSEHOLD_SHARED)
		order = AmazonOrder("ORD123", date.today(), 100.0, [item])
		service.add_order(order)

		settlement = service.calculate_settlement("ORD123", split_percent=0.5)
		assert settlement is not None
		assert settlement.shared_amount == 100.0
		assert settlement.your_share == 50.0


class TestBudgetDriftServiceMethods:
	"""Test BudgetDriftService methods."""

	def test_add_category(self) -> None:
		"""Service can add budget categories."""
		from datetime import date

		service = BudgetDriftService()
		from atlas.workflows.budget.budget_drift_agent import BudgetCategory

		category = BudgetCategory("cat1", "Groceries", 500.0, date.today(), date.today())
		result = service.add_category(category)
		assert result == category
		assert len(service._categories) == 1

	def test_detect_drift_no_overage(self) -> None:
		"""Service respects budget limits."""
		from datetime import date

		service = BudgetDriftService()
		from atlas.workflows.budget.budget_drift_agent import BudgetCategory, SpendingRecord

		category = BudgetCategory("cat1", "Groceries", 500.0, date.today(), date.today())
		service.add_category(category)
		service.add_spending(SpendingRecord("cat1", 400.0, date.today(), "Grocery shopping"))

		alerts = service.detect_drift()
		assert len(alerts) == 0

	def test_detect_drift_with_overage(self) -> None:
		"""Service reports budget overages."""
		from datetime import date

		service = BudgetDriftService()
		from atlas.workflows.budget.budget_drift_agent import BudgetCategory, SpendingRecord

		category = BudgetCategory("cat1", "Groceries", 500.0, date.today(), date.today())
		service.add_category(category)
		service.add_spending(SpendingRecord("cat1", 600.0, date.today(), "Over-budget spending"))

		alerts = service.detect_drift()
		assert len(alerts) == 1
		assert alerts[0].percent_over > 0


class TestDuplicateChargeServiceMethods:
	"""Test DuplicateChargeService methods."""

	def test_add_transaction(self) -> None:
		"""Service can add transactions."""
		service = DuplicateChargeService()
		from atlas.workflows.budget.duplicate_charge_detector import Transaction

		txn = Transaction("txn1", date.today(), 50.0, "Store A", "Groceries")
		result = service.add_transaction(txn)
		assert result == txn
		assert len(service._transactions) == 1

	def test_find_duplicates_empty(self) -> None:
		"""Service returns empty when no duplicates."""
		service = DuplicateChargeService()
		duplicates = service.find_duplicates()
		assert duplicates == []

	def test_find_duplicates_exact_match(self) -> None:
		"""Service detects exact duplicate matches."""
		service = DuplicateChargeService()
		from atlas.workflows.budget.duplicate_charge_detector import Transaction

		txn1 = Transaction("txn1", date.today(), 50.0, "Store A", "Groceries")
		txn2 = Transaction("txn2", date.today(), 50.0, "Store A", "Groceries")
		service.add_transaction(txn1)
		service.add_transaction(txn2)

		duplicates = service.find_duplicates()
		assert len(duplicates) > 0


class TestRefundChaseServiceMethods:
	"""Test RefundChaseService methods."""

	def test_add_refund(self) -> None:
		"""Service can add refunds."""
		from datetime import date

		service = RefundChaseService()
		from atlas.workflows.budget.refund_chase_agent import Refund, RefundSource

		refund = Refund("ref1", RefundSource.PRODUCT_RETURN, 100.0, date.today(), date.today(), "Amazon")
		result = service.add_refund(refund)
		assert result == refund
		assert len(service._refunds) == 1

	def test_get_refund_summary(self) -> None:
		"""Service provides refund summary."""
		from datetime import date

		service = RefundChaseService()
		from atlas.workflows.budget.refund_chase_agent import Refund, RefundSource

		refund = Refund("ref1", RefundSource.PRODUCT_RETURN, 100.0, date.today(), date.today(), "Amazon")
		service.add_refund(refund)

		summary = service.get_refund_summary()
		assert summary["total_refunds"] == 1
		assert summary["pending_amount"] == 100.0


class TestSettlementPrepServiceMethods:
	"""Test SettlementPrepService methods."""

	def test_add_expense(self) -> None:
		"""Service can add shared expenses."""
		from datetime import date

		service = SettlementPrepService()
		from atlas.workflows.budget.settlement_prep_agent import SharedExpense, ExpenseType

		expense = SharedExpense("exp1", date.today(), 100.0, ExpenseType.RENT, "Monthly rent", "self", 0.5)
		result = service.add_expense(expense)
		assert result == expense
		assert len(service._expenses) == 1

	def test_calculate_settlement(self) -> None:
		"""Service calculates settlements."""
		from datetime import date

		service = SettlementPrepService()
		from atlas.workflows.budget.settlement_prep_agent import SharedExpense, ExpenseType, SettlementPeriod

		expense = SharedExpense("exp1", date.today(), 100.0, ExpenseType.RENT, "Monthly rent", "self", 0.5)
		service.add_expense(expense)

		settlement = service.calculate_settlement(date.today(), date.today(), SettlementPeriod.MONTHLY)
		assert settlement is not None
		assert settlement.total_shared == 100.0

	def test_get_settlement_summary(self) -> None:
		"""Service provides settlement summary."""
		from datetime import date

		service = SettlementPrepService()
		from atlas.workflows.budget.settlement_prep_agent import SharedExpense, ExpenseType, SettlementPeriod

		expense = SharedExpense("exp1", date.today(), 100.0, ExpenseType.RENT, "Monthly rent", "self", 0.5)
		service.add_expense(expense)
		settlement = service.calculate_settlement(date.today(), date.today(), SettlementPeriod.MONTHLY)

		summary = service.get_settlement_summary()
		assert summary["total_expenses"] == 1
		assert summary["pending_settlements"] == 1
