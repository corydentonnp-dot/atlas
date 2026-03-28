"""Workflow #74: Conference/Abstract Deadline Agent — Phase 2 Priority.
Tracks calls for abstracts, conference registration deadlines, and submission windows.
Recommended phase: 2 (quick_win_score: 12) | Trust level: auto | Category: career
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class SubmissionType(str, Enum):
	"""Type of conference submission."""

	ABSTRACT = "abstract"
	FULL_PAPER = "full_paper"
	POSTER = "poster"
	REGISTRATION = "registration"
	EARLY_BIRD = "early_bird"


class DeadlineStatus(str, Enum):
	"""Status of a conference deadline."""

	UPCOMING = "upcoming"
	DUE_SOON = "due_soon"
	SUBMITTED = "submitted"
	PASSED = "passed"
	EXTENDED = "extended"


@dataclass(slots=True)
class ConferenceDeadline:
	"""A conference or abstract submission deadline."""

	deadline_id: str
	conference_name: str
	submission_type: SubmissionType
	due_date: date
	status: DeadlineStatus
	website_url: str = ""
	notes: str = ""
	days_until_due: int = 0


@dataclass(frozen=True, slots=True)
class DeadlineSummary:
	"""Summary of tracked conference deadlines."""

	total_tracked: int
	due_within_7_days: int
	due_within_30_days: int
	submitted: int
	passed: int
	urgent_deadlines: list[str]


class ConferenceAbstractDeadlineService(PersistenceMixin):
	"""Service for tracking conference and abstract submission deadlines."""

	DUE_SOON_DAYS = 14

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._deadlines: dict[str, ConferenceDeadline] = {}

	def add_deadline(
		self,
		deadline_id: str,
		conference_name: str,
		submission_type: SubmissionType,
		due_date: date,
		website_url: str = "",
		notes: str = "",
	) -> ConferenceDeadline:
		"""Add a conference deadline to track."""
		days_until = (due_date - date.today()).days
		if days_until < 0:
			status = DeadlineStatus.PASSED
		elif days_until <= self.DUE_SOON_DAYS:
			status = DeadlineStatus.DUE_SOON
		else:
			status = DeadlineStatus.UPCOMING

		deadline = ConferenceDeadline(
			deadline_id=deadline_id,
			conference_name=conference_name,
			submission_type=submission_type,
			due_date=due_date,
			status=status,
			website_url=website_url,
			notes=notes,
			days_until_due=days_until,
		)
		self._deadlines[deadline_id] = deadline
		return deadline

	def mark_submitted(self, deadline_id: str) -> bool:
		"""Mark a deadline as submitted."""
		if deadline_id not in self._deadlines:
			return False
		self._deadlines[deadline_id].status = DeadlineStatus.SUBMITTED
		return True

	def extend_deadline(self, deadline_id: str, new_date: date) -> bool:
		"""Update deadline to an extended date."""
		if deadline_id not in self._deadlines:
			return False
		dl = self._deadlines[deadline_id]
		dl.due_date = new_date
		dl.status = DeadlineStatus.EXTENDED
		dl.days_until_due = (new_date - date.today()).days
		return True

	def get_upcoming(self, within_days: int = 30) -> list[ConferenceDeadline]:
		"""Get all upcoming deadlines within the specified window."""
		return [
			d for d in self._deadlines.values()
			if d.status in (DeadlineStatus.UPCOMING, DeadlineStatus.DUE_SOON, DeadlineStatus.EXTENDED)
			and 0 <= d.days_until_due <= within_days
		]

	def get_summary(self) -> DeadlineSummary:
		"""Return summary of all tracked deadlines."""
		all_dl = list(self._deadlines.values())
		due7 = [d for d in all_dl if d.days_until_due <= 7 and d.days_until_due >= 0 and d.status != DeadlineStatus.SUBMITTED]
		due30 = [d for d in all_dl if d.days_until_due <= 30 and d.days_until_due >= 0 and d.status != DeadlineStatus.SUBMITTED]
		submitted = [d for d in all_dl if d.status == DeadlineStatus.SUBMITTED]
		passed = [d for d in all_dl if d.status == DeadlineStatus.PASSED]
		return DeadlineSummary(
			total_tracked=len(all_dl),
			due_within_7_days=len(due7),
			due_within_30_days=len(due30),
			submitted=len(submitted),
			passed=len(passed),
			urgent_deadlines=[f"{d.conference_name} ({d.submission_type.value}) in {d.days_until_due}d" for d in due7],
		)


class ConferenceAbstractDeadlineAgent(BaseWorkflow):
	"""Workflow for tracking conference and abstract submission deadlines."""

	workflow_id = "conference_abstract_deadline"
	name = "Conference Abstract Deadline"
	category = "career"
	trust_level = TrustLevel.AUTO

	def __init__(
		self,
		service: ConferenceAbstractDeadlineService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or ConferenceAbstractDeadlineService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Handle conference deadline events."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Build deadline summary and identify urgent items."""
		summary = self.service.get_summary()
		upcoming = self.service.get_upcoming(within_days=30)
		return ActionPlan(
			action_type="review_conference_deadlines",
			confidence=0.85,
			context={
				"total_tracked": summary.total_tracked,
				"due_within_7_days": summary.due_within_7_days,
				"due_within_30_days": summary.due_within_30_days,
				"submitted_count": summary.submitted,
				"urgent_deadlines": summary.urgent_deadlines,
				"upcoming_count": len(upcoming),
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Emit conference deadline review."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})
		urgent = plan.context.get("due_within_7_days", 0)
		total = plan.context.get("total_tracked", 0)
		if urgent:
			summary_text = f"{urgent} conference deadline(s) due within 7 days ({total} total tracked)"
		else:
			summary_text = f"No urgent conference deadlines; {total} tracked"
		return ActionResult(True, summary_text, {**plan.context, "policy": decision.reason})
