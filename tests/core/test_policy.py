"""Tests for the policy engine."""

from atlas.core.policy.engine import PolicyEngine, TrustLevel


def test_policy_engine_approval_requirement():
	engine = PolicyEngine()
	engine.set_workflow_policy("workflow_a", TrustLevel.APPROVAL)
	decision = engine.evaluate_action("workflow_a", "send", {}, confidence=0.9)

	assert decision.allowed is True
	assert decision.requires_approval is True


def test_policy_engine_manual_only_blocks_action():
	engine = PolicyEngine()
	engine.set_workflow_policy("workflow_a", TrustLevel.MANUAL_ONLY)
	decision = engine.evaluate_action("workflow_a", "send", {}, confidence=0.9)

	assert decision.allowed is False


def test_policy_engine_low_confidence_promotes_auto_to_approval():
	engine = PolicyEngine()
	engine.set_workflow_policy("workflow_a", TrustLevel.AUTO)
	decision = engine.evaluate_action("workflow_a", "send", {}, confidence=0.3)

	assert decision.allowed is True
	assert decision.requires_approval is True
