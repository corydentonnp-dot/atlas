"""Base workflow class — abstract interface for all workflows."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from atlas.core.policy.engine import TrustLevel
from atlas.core.state.machine import StateMachine, Transition


@dataclass(frozen=True, slots=True)
class WorkflowEvent:
  event_type: str
  payload: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class WorkflowRun:
  workflow_id: str
  event: WorkflowEvent
  run_id: str = field(default_factory=lambda: str(uuid4()))
  started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
  finished_at: datetime | None = None
  status: str = "started"


@dataclass(frozen=True, slots=True)
class ActionPlan:
  action_type: str
  confidence: float
  context: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ActionResult:
  success: bool
  summary: str
  metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WorkflowStatus:
  workflow_id: str
  name: str
  category: str
  trust_level: TrustLevel
  current_state: str


class BaseWorkflow(ABC):
  """Shared contract for all Atlas workflows."""

  workflow_id: str
  name: str
  category: str
  trust_level: TrustLevel = TrustLevel.DRAFT
  required_credentials: list[str] = []

  def __init__(self) -> None:
    self.state_machine = StateMachine(
      initial_state="idle",
      states=["idle", "planning", "acting", "completed", "failed"],
      transitions=[
        Transition("idle", "planning"),
        Transition("planning", "acting"),
        Transition("acting", "completed"),
        Transition("acting", "failed"),
        Transition("failed", "idle"),
        Transition("completed", "idle"),
      ],
    )

  async def run(self, event: WorkflowEvent) -> ActionResult:
    """Execute the default lifecycle for a workflow run."""
    run = await self.trigger(event)
    plan = await self.process(run)
    result = await self.act(plan)
    await self.close(run, result)
    return result

  @abstractmethod
  async def trigger(self, event: WorkflowEvent) -> WorkflowRun:
    """Initialize a workflow run from an incoming event."""

  @abstractmethod
  async def process(self, run: WorkflowRun) -> ActionPlan:
    """Produce an action plan based on run context."""

  @abstractmethod
  async def act(self, plan: ActionPlan) -> ActionResult:
    """Execute or stage the plan."""

  async def close(self, run: WorkflowRun, result: ActionResult) -> None:
    run.finished_at = datetime.now(timezone.utc)
    run.status = "completed" if result.success else "failed"

  def get_status(self) -> WorkflowStatus:
    return WorkflowStatus(
      workflow_id=self.workflow_id,
      name=self.name,
      category=self.category,
      trust_level=self.trust_level,
      current_state=self.state_machine.current_state,
    )
