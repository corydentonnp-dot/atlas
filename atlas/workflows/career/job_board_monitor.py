"""Workflow #70: Job Board Monitor — Phase 2 Priority.
Monitors job boards for positions matching user criteria; surfaces high-value opportunities.
Recommended phase: 2 (quick_win_score: 11) | Trust level: draft | Category: career
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.persistence.mixin import PersistenceMixin
from atlas.core.policy.engine import PolicyEngine, TrustLevel
from atlas.core.workflow.base import ActionPlan, ActionResult, BaseWorkflow, WorkflowEvent, WorkflowRun


class JobType(str, Enum):
	"""Type of employment."""

	FULL_TIME = "full_time"
	PART_TIME = "part_time"
	CONTRACT = "contract"
	PER_DIEM = "per_diem"
	TRAVEL = "travel"


class JobStatus(str, Enum):
	"""Status of a tracked job posting."""

	NEW = "new"
	REVIEWED = "reviewed"
	APPLIED = "applied"
	INTERVIEW = "interview"
	OFFER = "offer"
	DECLINED = "declined"
	EXPIRED = "expired"


@dataclass(slots=True)
class JobPosting:
	"""A tracked job opportunity."""

	job_id: str
	title: str
	employer: str
	location: str
	job_type: JobType
	salary_min: float
	salary_max: float
	posted_date: date
	source: str  # e.g. 'Indeed', 'LinkedIn', 'manual'
	status: JobStatus = JobStatus.NEW
	match_score: float = 0.0  # 0.0 - 1.0 relevance score
	notes: str = ""
	created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class JobCriteria:
	"""User-defined criteria for job matching."""

	titles: tuple[str, ...]
	locations: tuple[str, ...]  # empty = remote ok
	min_salary: float
	job_types: tuple[JobType, ...]
	keywords: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class JobBoardSummary:
	"""Summary of job board monitoring activity."""

	total_tracked: int
	new_postings: int
	applied: int
	high_match_count: int
	top_match_title: str


class JobBoardMonitorService(PersistenceMixin):
	"""Service for tracking and scoring job postings against user criteria."""

	HIGH_MATCH_THRESHOLD: float = 0.7

	def __init__(self, session: AsyncSession | None = None) -> None:
		super().__init__(session)
		self._postings: dict[str, JobPosting] = {}
		self._criteria: JobCriteria | None = None

	def set_criteria(self, criteria: JobCriteria) -> None:
		"""Set the matching criteria for job evaluation."""
		self._criteria = criteria

	def add_posting(
		self,
		job_id: str,
		title: str,
		employer: str,
		location: str,
		job_type: JobType,
		salary_min: float,
		salary_max: float,
		posted_date: date,
		source: str = "manual",
		notes: str = "",
	) -> JobPosting:
		"""Add a job posting and score it against current criteria."""
		posting = JobPosting(
			job_id=job_id,
			title=title,
			employer=employer,
			location=location,
			job_type=job_type,
			salary_min=salary_min,
			salary_max=salary_max,
			posted_date=posted_date,
			source=source,
			notes=notes,
		)
		posting.match_score = self._score_posting(posting)
		self._postings[job_id] = posting
		return posting

	def update_status(self, job_id: str, status: JobStatus) -> bool:
		"""Update the status of a tracked posting."""
		if job_id not in self._postings:
			return False
		self._postings[job_id].status = status
		return True

	def get_new_high_match(self) -> list[JobPosting]:
		"""Return new postings with a high match score."""
		return [
			p for p in self._postings.values()
			if p.status == JobStatus.NEW and p.match_score >= self.HIGH_MATCH_THRESHOLD
		]

	def get_summary(self) -> JobBoardSummary:
		"""Return a summary of job board monitoring."""
		new = [p for p in self._postings.values() if p.status == JobStatus.NEW]
		applied = [p for p in self._postings.values() if p.status == JobStatus.APPLIED]
		high_match = self.get_new_high_match()
		top = max(high_match, key=lambda p: p.match_score, default=None)
		return JobBoardSummary(
			total_tracked=len(self._postings),
			new_postings=len(new),
			applied=len(applied),
			high_match_count=len(high_match),
			top_match_title=top.title if top else "",
		)

	def _score_posting(self, posting: JobPosting) -> float:
		"""Score a posting 0-1 against stored criteria."""
		if self._criteria is None:
			return 0.5  # neutral score if no criteria set
		score = 0.0
		max_score = 3.0
		# Title match
		if any(t.lower() in posting.title.lower() for t in self._criteria.titles):
			score += 1.0
		# Job type match
		if posting.job_type in self._criteria.job_types:
			score += 1.0
		# Salary threshold
		if posting.salary_min >= self._criteria.min_salary:
			score += 1.0
		return round(min(score / max_score, 1.0), 2)


class JobBoardMonitorWorkflow(BaseWorkflow):
	"""Workflow for monitoring job boards and surfacing high-match opportunities."""

	workflow_id = "job_board_monitor"
	name = "Job Board Monitor"
	category = "career"
	trust_level = TrustLevel.DRAFT

	def __init__(
		self,
		service: JobBoardMonitorService | None = None,
		policy_engine: PolicyEngine | None = None,
		session: AsyncSession | None = None,
	) -> None:
		super().__init__()
		self.service = service or JobBoardMonitorService(session)
		self.policy_engine = policy_engine or PolicyEngine()

	async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
		"""Accept a job-board scan request."""
		self.state_machine.transition("planning", {"event_type": event.event_type})
		return WorkflowRun(workflow_id=self.workflow_id, event=event)

	async def process(self, run: WorkflowRun) -> ActionPlan:
		"""Identify new high-match postings."""
		high_match = self.service.get_new_high_match()
		summary = self.service.get_summary()
		return ActionPlan(
			action_type="surface_job_postings",
			confidence=0.80,
			context={
				"high_match": len(high_match),
				"total": summary.total_tracked,
				"new_postings": summary.new_postings,
				"top_match": summary.top_match_title,
			},
		)

	async def act(self, plan: ActionPlan) -> ActionResult:
		"""Surface high-match job postings for review."""
		self.state_machine.transition("acting", {"action_type": plan.action_type})
		decision = self.policy_engine.evaluate_action(
			workflow_id=self.workflow_id,
			action_type=plan.action_type,
			context=plan.context,
			confidence=plan.confidence,
			domain=self.category,
		)
		self.state_machine.transition("completed", {"reason": decision.reason})
		new = plan.context.get("new_postings", 0)
		high = plan.context.get("high_match", 0)
		return ActionResult(
			True,
			f"job board monitor: {new} new postings, {high} high match",
			{**plan.context, "policy": decision.reason},
		)
