"""Workflow #32: Merchant Memory Agent.

Builds a persistent memory of merchant classifications for intelligent expense splitting.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class MerchantClass(str, Enum):
	"""Merchant classification for splitting logic."""

	GROCERIES = "groceries"
	UTILITIES = "utilities"
	HOUSEHOLD = "household"
	DINING = "dining"
	PERSONAL = "personal"
	SHARED = "shared"
	UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class MerchantPattern:
	"""Learned pattern for merchant classification."""

	merchant_name: str
	normalized_name: str
	classification: MerchantClass
	confidence: float
	occurrence_count: int = 1


class MerchantMemoryService(PersistenceMixin):
	"""Service for merchant learning and classification."""

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._memory: dict[str, MerchantPattern] = {}
		self._seen_count: dict[str, int] = {}

	KEYWORD_PATTERNS: dict[MerchantClass, list[str]] = {
		MerchantClass.GROCERIES: ["trader joe", "whole foods", "safeway", "kroger", "grocery"],
		MerchantClass.UTILITIES: ["electric", "water utility", "internet provider", "gas company"],
		MerchantClass.HOUSEHOLD: ["home depot", "lowe's", "ikea", "bed bath", "target"],
		MerchantClass.DINING: ["restaurant", "cafe", "pizza", "burger", "sushi"],
		MerchantClass.PERSONAL: ["gap", "target apparel", "shoes"],
	}

	def learn_merchant(self, merchant_name: str, classification: MerchantClass) -> MerchantPattern:
		"""Learn a merchant classification."""
		normalized = merchant_name.strip().lower()
		count = self._seen_count.get(normalized, 0) + 1
		self._seen_count[normalized] = count
		confidence = min(0.6 + (count * 0.1), 0.95)
		pattern = MerchantPattern(
			merchant_name=merchant_name,
			normalized_name=normalized,
			classification=classification,
			confidence=confidence,
			occurrence_count=count,
		)
		self._memory[normalized] = pattern
		return pattern

	def classify_merchant(self, merchant_name: str) -> MerchantPattern | None:
		"""Look up learned classification for a merchant."""
		normalized = merchant_name.strip().lower()
		if normalized in self._memory:
			return self._memory[normalized]
		# Try keyword matching
		for classification, keywords in self.KEYWORD_PATTERNS.items():
			for keyword in keywords:
				if keyword in normalized:
					return MerchantPattern(
						merchant_name=merchant_name,
						normalized_name=normalized,
						classification=classification,
						confidence=0.65,
					)
		return None

	def get_memory_size(self) -> int:
		"""Return number of learned merchants."""
		return len(self._memory)

	def get_confidence_report(self) -> dict[MerchantClass, float]:
		"""Return average confidence by classification."""
		by_class: dict[MerchantClass, list[float]] = {}
		for pattern in self._memory.values():
			if pattern.classification not in by_class:
				by_class[pattern.classification] = []
			by_class[pattern.classification].append(pattern.confidence)
		return {
			classification: sum(confidences) / len(confidences)
			for classification, confidences in by_class.items()
		}


class MerchantMemoryAgent(BaseWorkflow):
	"""Workflow for building merchant classification memory."""

	workflow_id = "merchant_memory_agent"
	name = "merchant_memory_agent"
	category = "budget"
	trust_level = TrustLevel.AUTO

	def __init__(self, service: MerchantMemoryService | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = service or MerchantMemoryService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		if event.event_type == "merchant_classified":
			payload = event.payload
			merchant_name = str(payload.get("merchant_name", ""))
			classification = MerchantClass(str(payload.get("classification", "unknown")))
			self.service.learn_merchant(merchant_name, classification)
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		merchant_name = str(run.event.payload.get("merchant_name", ""))
		pattern = self.service.classify_merchant(merchant_name)
		confidence = pattern.confidence if pattern else 0.0
		return ActionPlan(
			action_type="update_merchant_memory",
			confidence=confidence,
			context={
				"merchant_name": merchant_name,
				"classification": pattern.classification.value if pattern else "unknown",
				"confidence": confidence,
				"memory_size": self.service.get_memory_size(),
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})
		merchant = plan.context.get("merchant_name")
		classification = plan.context.get("classification")
		confidence = float(plan.context.get("confidence", 0.0))
		summary = f"Learned '{merchant}' as {classification} (confidence {confidence:.0%})"
		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})
