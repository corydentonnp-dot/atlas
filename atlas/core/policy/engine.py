"""Policy engine — evaluate actions against trust levels and rules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TrustLevel(StrEnum):
	AUTO = "auto"
	DRAFT = "draft"
	APPROVAL = "approval"
	MANUAL_ONLY = "manual_only"


@dataclass(frozen=True, slots=True)
class PolicyDecision:
	allowed: bool
	requires_approval: bool
	requires_draft: bool
	reason: str
	trust_level: TrustLevel


class PolicyEngine:
	"""In-memory per-workflow policy storage and evaluator."""

	def __init__(self) -> None:
		self._workflow_policies: dict[str, TrustLevel] = {}
		self._action_policies: dict[tuple[str, str], TrustLevel] = {}
		self._domain_defaults: dict[str, TrustLevel] = {
			"communication": TrustLevel.DRAFT,
			"property": TrustLevel.DRAFT,
			"budget": TrustLevel.APPROVAL,
			"returns": TrustLevel.DRAFT,
			"scheduling": TrustLevel.DRAFT,
			"licensure": TrustLevel.AUTO,
			"career": TrustLevel.DRAFT,
			"tax_legal": TrustLevel.DRAFT,
			"home": TrustLevel.AUTO,
			"shopping": TrustLevel.DRAFT,
			"travel": TrustLevel.DRAFT,
			"additional": TrustLevel.DRAFT,
		}

	def get_trust_level(self, workflow_id: str, action_type: str, domain: str | None = None) -> TrustLevel:
		if (workflow_id, action_type) in self._action_policies:
			return self._action_policies[(workflow_id, action_type)]
		if workflow_id in self._workflow_policies:
			return self._workflow_policies[workflow_id]
		if domain and domain in self._domain_defaults:
			return self._domain_defaults[domain]
		return TrustLevel.DRAFT

	def evaluate_action(
		self,
		workflow_id: str,
		action_type: str,
		context: dict[str, object],
		confidence: float,
		domain: str | None = None,
	) -> PolicyDecision:
		trust_level = self.get_trust_level(workflow_id, action_type, domain)
		if trust_level == TrustLevel.MANUAL_ONLY:
			return PolicyDecision(False, False, False, "Workflow is configured as manual only.", trust_level)

		if trust_level == TrustLevel.APPROVAL:
			return PolicyDecision(True, True, False, "Requires explicit user approval.", trust_level)

		if trust_level == TrustLevel.DRAFT:
			return PolicyDecision(True, False, True, "Must be reviewed as draft before action.", trust_level)

		if confidence < 0.6:
			return PolicyDecision(True, True, False, "Low confidence auto action promoted to approval.", trust_level)

		return PolicyDecision(True, False, False, "Allowed to execute automatically.", trust_level)

	def set_workflow_policy(self, workflow_id: str, trust_level: TrustLevel) -> None:
		self._workflow_policies[workflow_id] = trust_level

	def set_action_policy(self, workflow_id: str, action_type: str, trust_level: TrustLevel) -> None:
		self._action_policies[(workflow_id, action_type)] = trust_level

	def get_domain_defaults(self, domain: str) -> dict[str, TrustLevel]:
		if domain not in self._domain_defaults:
			return {}
		return {domain: self._domain_defaults[domain]}
