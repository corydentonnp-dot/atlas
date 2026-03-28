"""Workflow #104: Private Intent Capture Router.

Captures local-only user intents from freeform text and routes them to the most relevant
existing workflow using lightweight heuristics and confidence scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import re

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class IntentStatus(str, Enum):
	"""Routing state for a captured intent."""

	CAPTURED = "captured"
	ROUTED = "routed"
	NEEDS_REVIEW = "needs_review"
	ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class PrivateIntent:
	"""Local-only structured intent extracted from freeform text."""

	intent_id: str
	raw_text: str
	normalized_text: str
	route_workflow_id: str | None
	confidence: float
	status: IntentStatus
	privacy_scope: str = "local_only"
	created_at: datetime = datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class RoutedIntent:
	"""Resolved route for a private intent."""

	intent_id: str
	workflow_id: str | None
	confidence: float
	reason: str
	needs_review: bool


class PrivateIntentCaptureService(PersistenceMixin):
	"""Service for parsing local-only intents and routing them to workflows."""

	ROUTE_KEYWORDS: dict[str, tuple[str, ...]] = {
		"amazon_return_window_agent": ("return", "amazon", "refund", "send back"),
		"subscription_tracker": ("subscription", "renewal", "cancel", "auto-renew"),
		"renewal_prompt_agent": ("lease", "renew", "tenant", "term"),
		"utility_setup_reminder_agent": ("utility", "electric", "water", "internet", "move in"),
		"insurance_proof_tracker": ("insurance", "policy", "coverage", "proof"),
		"maintenance_intake": ("maintenance", "repair", "leak", "hvac"),
		"shared_household_spend_summary_agent": ("shared spend", "household spend", "roommate", "summary"),
		"shared_expense_classifier": ("split expense", "split bill", "shared expense"),
		"np_license_tracker": ("np license", "board renewal", "ce hours"),
		"dea_tracker": ("dea", "controlled substance", "registration"),
		"bls_acls_renewal_agent": ("bls", "acls", "certification"),
	}

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._intents: dict[str, PrivateIntent] = {}

	def capture_intent(self, intent_id: str, raw_text: str) -> PrivateIntent:
		"""Normalize freeform text and score the best route."""
		normalized_text = re.sub(r"\s+", " ", raw_text.strip().lower())
		workflow_id, confidence, reason = self._score_route(normalized_text)
		status = IntentStatus.ROUTED if workflow_id and confidence >= 0.7 else IntentStatus.NEEDS_REVIEW
		intent = PrivateIntent(
			intent_id=intent_id,
			raw_text=raw_text,
			normalized_text=normalized_text,
			route_workflow_id=workflow_id,
			confidence=confidence,
			status=status,
		)
		self._intents[intent_id] = intent
		return intent

	def route_intent(self, intent_id: str) -> RoutedIntent:
		"""Return routing decision for a captured intent."""
		intent = self._intents[intent_id]
		needs_review = intent.status == IntentStatus.NEEDS_REVIEW
		reason = "High-confidence keyword match" if not needs_review else "Low-confidence match requires review"
		return RoutedIntent(
			intent_id=intent.intent_id,
			workflow_id=intent.route_workflow_id,
			confidence=intent.confidence,
			reason=reason,
			needs_review=needs_review,
		)

	def pending_review(self) -> list[PrivateIntent]:
		"""Return intents that could not be routed confidently."""
		return [intent for intent in self._intents.values() if intent.status == IntentStatus.NEEDS_REVIEW]

	def _score_route(self, normalized_text: str) -> tuple[str | None, float, str]:
		best_workflow: str | None = None
		best_score = 0
		best_reason = "No keyword match"
		for workflow_id, keywords in self.ROUTE_KEYWORDS.items():
			score = sum(1 for keyword in keywords if keyword in normalized_text)
			if score > best_score:
				best_workflow = workflow_id
				best_score = score
				best_reason = f"Matched {score} routing keyword(s)"
		confidence = min(0.55 + (best_score * 0.15), 0.95) if best_workflow else 0.2
		return best_workflow, confidence, best_reason


class PrivateIntentCaptureRouterWorkflow(BaseWorkflow):
	"""Workflow for capturing local private intents and routing them safely."""

	workflow_id = "private_intent_capture_router"
	name = "private_intent_capture_router"
	category = "additional"
	trust_level = TrustLevel.AUTO

	def __init__(self, service: PrivateIntentCaptureService | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:
		super().__init__()
		self.service = service or PrivateIntentCaptureService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		self.state_machine.transition("planning", {"event_type": event.event_type})
		if event.event_type == "private_intent_captured":
			payload = event.payload
			self.service.capture_intent(
				intent_id=str(payload.get("intent_id", "")),
				raw_text=str(payload.get("raw_text", "")),
			)
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		intent_id = str(run.event.payload.get("intent_id", ""))
		routed = self.service.route_intent(intent_id)
		return ActionPlan(
			action_type="route_private_intent",
			confidence=routed.confidence,
			context={
				"intent_id": routed.intent_id,
				"workflow_id": routed.workflow_id,
				"needs_review": routed.needs_review,
				"reason": routed.reason,
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
		workflow_id = plan.context.get("workflow_id") or "unrouted"
		if plan.context.get("needs_review"):
			summary = f"Captured private intent for review; suggested route: {workflow_id}"
		else:
			summary = f"Captured and routed private intent to {workflow_id}"
		return ActionResult(True, summary, {**plan.context, "policy": decision.reason})