"""Workflow #31: Shared Expense Classifier — Phase 1 Priority.

Classifies transactions as shared (split with fiancée) or personal,
learns merchant patterns over time.

Recommended phase: 1 (quick_win_score: 11)
Trust level: draft
Category: budget

TODO: Implement after scaffolding is approved.

Workflow states:
- idle -> transaction_received -> classified -> confirmed | reclassified

Service interface:
- classify_transaction(transaction) -> Classification
- learn_merchant(merchant, classification) -> None
- get_unclassified() -> list[Transaction]
- get_settlement_summary(period) -> SettlementSummary

Schemas needed:
- Classification(shared/personal/unknown, confidence, category)
- SettlementSummary(period, shared_total, each_owes, transactions)
"""

# TODO: Implement BaseWorkflow subclass
# TODO: Implement merchant memory for auto-classification
# TODO: Add schemas and tests
