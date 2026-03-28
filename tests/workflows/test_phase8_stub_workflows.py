"""Tests for Phase 8 (score 14/13/12/10/10) stub-reduction workflows:
Price Drop Agent, Return Window Tracker, Subscription Optimizer,
Grocery List Builder, and Document Vault Organizer.
"""

from __future__ import annotations

import pytest
from datetime import date, timedelta

from atlas.core.workflow.base import WorkflowEvent

# ── Price Drop Agent ──────────────────────────────────────────────────────────
from atlas.workflows.shopping.price_drop_agent import (
	PriceDropAgent,
	PriceDropService,
	DropStatus,
)


def test_price_drop_add_product():
	service = PriceDropService()
	p = service.add_product("p001", "Laptop", "https://example.com", target_price=800.0, baseline_price=1000.0)
	assert p.product_id == "p001"
	assert p.current_price == 1000.0
	assert p.status == DropStatus.WATCHING


def test_price_drop_update_price_triggers_deal():
	service = PriceDropService()
	service.add_product("p002", "TV", "https://ex.com", target_price=400.0, baseline_price=600.0)
	updated = service.update_price("p002", 380.0)  # below target
	assert updated is not None
	assert updated.status == DropStatus.DROP_DETECTED
	assert updated.savings == pytest.approx(220.0)


def test_price_drop_no_deal_above_target():
	service = PriceDropService()
	service.add_product("p003", "Headphones", "https://ex.com", target_price=100.0, baseline_price=150.0)
	updated = service.update_price("p003", 110.0)  # still above target
	assert updated is not None
	assert updated.status == DropStatus.WATCHING


def test_price_drop_mark_purchased():
	service = PriceDropService()
	service.add_product("p004", "Chair", "https://ex.com", target_price=200.0, baseline_price=250.0)
	service.update_price("p004", 190.0)
	result = service.mark_purchased("p004")
	assert result is True
	assert service._products["p004"].status == DropStatus.PURCHASED


def test_price_drop_summary():
	service = PriceDropService()
	service.add_product("p005", "Desk", "https://ex.com", target_price=300.0, baseline_price=400.0)
	service.update_price("p005", 280.0)
	summary = service.get_summary()
	assert summary.drops_detected >= 1
	assert summary.best_deal_name == "Desk"
	assert summary.best_deal_savings == pytest.approx(120.0)


@pytest.mark.asyncio
async def test_price_drop_agent_lifecycle():
	agent = PriceDropAgent()
	assert agent.workflow_id == "price_drop"
	event = WorkflowEvent(event_type="price_check_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "price drop" in result.summary.lower()


# ── Return Window Tracker ─────────────────────────────────────────────────────
from atlas.workflows.shopping.return_window_tracker import (
	ReturnWindowTrackerAgent,
	ReturnWindowTrackerService,
	ReturnStatus,
)


def test_return_window_add_active():
	service = ReturnWindowTrackerService()
	rw = service.add_return_window("r001", "Shoes", "Amazon", date.today(), 30, price=89.99)
	assert rw.item_id == "r001"
	assert rw.status == ReturnStatus.ACTIVE
	assert rw.days_remaining >= 25


def test_return_window_due_soon():
	service = ReturnWindowTrackerService()
	# bought 26 days ago with 30-day window → 4 days left → DUE_SOON
	service.add_return_window("r002", "Jacket", "Nordstrom", date.today() - timedelta(days=26), 30, price=149.0)
	due = service.get_due_soon()
	assert any(w.item_id == "r002" for w in due)


def test_return_window_expired():
	service = ReturnWindowTrackerService()
	service.add_return_window("r003", "Pants", "Gap", date.today() - timedelta(days=35), 30, price=59.0)
	assert service._windows["r003"].status == ReturnStatus.EXPIRED


def test_return_window_mark_returned():
	service = ReturnWindowTrackerService()
	service.add_return_window("r004", "Blender", "Target", date.today(), 90, price=79.0)
	result = service.mark_returned("r004")
	assert result is True
	assert service._windows["r004"].status == ReturnStatus.RETURNED


def test_return_window_summary():
	service = ReturnWindowTrackerService()
	service.add_return_window("r005", "Watch", "Macy's", date.today(), 60, price=200.0)
	summary = service.get_summary()
	assert summary.total_tracked >= 1
	assert summary.total_value_at_risk >= 200.0


@pytest.mark.asyncio
async def test_return_window_tracker_lifecycle():
	agent = ReturnWindowTrackerAgent()
	assert agent.workflow_id == "return_window_tracker"
	event = WorkflowEvent(event_type="return_window_check", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "return window" in result.summary.lower()


# ── Subscription Optimizer ────────────────────────────────────────────────────
from atlas.workflows.shopping.subscription_optimizer import (
	SubscriptionOptimizerAgent,
	SubscriptionOptimizerService,
	BillingCycle,
	SubStatus,
)


def test_subscription_optimizer_add_active():
	service = SubscriptionOptimizerService()
	sub = service.add_subscription(
		"s001", "Netflix", 15.99, BillingCycle.MONTHLY,
		date.today() + timedelta(days=20), "streaming",
		used_in_last_30_days=True,
	)
	assert sub.sub_id == "s001"
	assert sub.status == SubStatus.ACTIVE


def test_subscription_optimizer_unused_flagged():
	service = SubscriptionOptimizerService()
	service.add_subscription(
		"s002", "Hulu", 12.99, BillingCycle.MONTHLY,
		date.today() + timedelta(days=5), "streaming",
		used_in_last_30_days=False,
	)
	candidates = service.get_cancel_candidates()
	assert any(s.sub_id == "s002" for s in candidates)


def test_subscription_optimizer_duplicate_flagged():
	service = SubscriptionOptimizerService()
	service.add_subscription(
		"s003", "ESPN+", 9.99, BillingCycle.MONTHLY,
		date.today() + timedelta(days=15), "streaming",
		have_duplicate=True,
	)
	assert service._subs["s003"].status == SubStatus.CANCEL_CANDIDATE


def test_subscription_optimizer_mark_cancelled():
	service = SubscriptionOptimizerService()
	service.add_subscription(
		"s004", "Peacock", 5.99, BillingCycle.MONTHLY,
		date.today() + timedelta(days=10), "streaming",
		used_in_last_30_days=False,
	)
	result = service.mark_cancelled("s004")
	assert result is True
	assert service._subs["s004"].status == SubStatus.CANCELLED


def test_subscription_optimizer_summary():
	service = SubscriptionOptimizerService()
	service.add_subscription(
		"s005", "Adobe CC", 54.99, BillingCycle.MONTHLY,
		date.today() + timedelta(days=12), "software",
	)
	service.add_subscription(
		"s006", "Spotify", 9.99, BillingCycle.MONTHLY,
		date.today() + timedelta(days=3), "music",
		used_in_last_30_days=False,
	)
	summary = service.get_summary()
	assert summary.total_active >= 2
	assert summary.total_monthly_spend > 0
	assert summary.cancel_candidates >= 1


@pytest.mark.asyncio
async def test_subscription_optimizer_lifecycle():
	agent = SubscriptionOptimizerAgent()
	assert agent.workflow_id == "subscription_optimizer"
	event = WorkflowEvent(event_type="subscription_audit_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "subscription" in result.summary.lower()


# ── Grocery List Builder ──────────────────────────────────────────────────────
from atlas.workflows.shopping.grocery_list_builder import (
	GroceryListBuilderAgent,
	GroceryListBuilderService,
	GrocerySection,
	ItemStatus,
)


def test_grocery_list_add_item():
	service = GroceryListBuilderService()
	item = service.add_item("g001", "Apples", GrocerySection.PRODUCE, 2.0, "lb", price_estimate=3.50)
	assert item.item_id == "g001"
	assert item.status == ItemStatus.NEEDED


def test_grocery_list_mark_in_cart():
	service = GroceryListBuilderService()
	service.add_item("g002", "Milk", GrocerySection.DAIRY, 1.0, "gallon", price_estimate=4.00)
	result = service.mark_in_cart("g002")
	assert result is True
	assert service._items["g002"].status == ItemStatus.IN_CART


def test_grocery_list_mark_purchased_updates_pantry():
	service = GroceryListBuilderService()
	service.add_item("g003", "Rice", GrocerySection.PANTRY, 5.0, "lb", price_estimate=6.00)
	service.mark_purchased("g003")
	pantry_item = service.check_pantry("Rice")
	assert pantry_item is not None
	assert pantry_item.quantity == 5.0


def test_grocery_list_compile():
	service = GroceryListBuilderService()
	service.add_item("g004", "Chicken", GrocerySection.MEAT_SEAFOOD, 2.0, "lb", price_estimate=10.00)
	service.add_item("g005", "Eggs", GrocerySection.DAIRY, 1.0, "dozen", price_estimate=4.50)
	compiled = service.compile_list("list_01")
	assert compiled.total_items == 2
	assert compiled.estimated_total == pytest.approx(14.50)
	assert len(compiled.sections) >= 1


def test_grocery_list_pantry_check():
	service = GroceryListBuilderService()
	service.update_pantry("Salt", 1.0, "box")
	item = service.check_pantry("salt")
	assert item is not None
	assert item.quantity == 1.0


@pytest.mark.asyncio
async def test_grocery_list_builder_lifecycle():
	agent = GroceryListBuilderAgent()
	assert agent.workflow_id == "grocery_list_builder"
	event = WorkflowEvent(event_type="grocery_list_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "grocery" in result.summary.lower()


# ── Document Vault Organizer ──────────────────────────────────────────────────
from atlas.workflows.tax_legal.document_vault_organizer import (
	DocumentVaultOrganizerWorkflow,
	DocumentVaultService,
	DocumentCategory,
	VaultStatus,
)


def test_vault_log_document():
	service = DocumentVaultService()
	doc = service.log_document("d001", "2023 Tax Return", DocumentCategory.TAX_RETURN, date(2024, 4, 15), "IRS")
	assert doc.doc_id == "d001"
	assert doc.status == VaultStatus.LOGGED


def test_vault_mark_uploaded():
	service = DocumentVaultService()
	service.log_document("d002", "Lease Agreement", DocumentCategory.LEASE, date(2024, 1, 1), "Landlord LLC")
	result = service.mark_uploaded("d002", drive_link="https://drive.google.com/file/123")
	assert result is True
	assert service._docs["d002"].status == VaultStatus.UPLOADED
	assert service._docs["d002"].drive_link != ""


def test_vault_mark_verified():
	service = DocumentVaultService()
	service.log_document("d003", "Will", DocumentCategory.WILL_TRUST, date(2023, 6, 1), "Attorney Office")
	service.mark_uploaded("d003")
	result = service.mark_verified("d003")
	assert result is True
	assert service._docs["d003"].status == VaultStatus.VERIFIED


def test_vault_expiring_soon():
	service = DocumentVaultService()
	expiry = date.today() + timedelta(days=30)  # within 90-day window
	service.log_document("d004", "Business License", DocumentCategory.BUSINESS_LICENSE, date(2023, 1, 1), "State", expiry_date=expiry)
	expiring = service.get_expiring_soon()
	assert any(d.doc_id == "d004" for d in expiring)


def test_vault_get_by_category():
	service = DocumentVaultService()
	service.log_document("d005", "Policy #1", DocumentCategory.INSURANCE_POLICY, date(2023, 3, 1), "Allstate")
	service.log_document("d006", "Policy #2", DocumentCategory.INSURANCE_POLICY, date(2023, 3, 1), "State Farm")
	policies = service.get_by_category(DocumentCategory.INSURANCE_POLICY)
	assert len(policies) == 2


def test_vault_summary():
	service = DocumentVaultService()
	service.log_document("d007", "Passport", DocumentCategory.IDENTIFICATION, date(2019, 5, 1), "US Gov")
	service.mark_uploaded("d007")
	summary = service.get_summary()
	assert summary.total_logged >= 1
	assert summary.uploaded >= 1


@pytest.mark.asyncio
async def test_document_vault_organizer_lifecycle():
	agent = DocumentVaultOrganizerWorkflow()
	assert agent.workflow_id == "document_vault_organizer"
	event = WorkflowEvent(event_type="vault_audit_requested", payload={})
	run = await agent.trigger(event)
	plan = await agent.process(run)
	result = await agent.act(plan)
	assert result.success is True
	assert "document vault" in result.summary.lower()
