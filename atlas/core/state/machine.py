"""State machine implementation for workflow state transitions."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class Transition:
  from_state: str
  to_state: str


@dataclass(frozen=True, slots=True)
class StateTransition:
  from_state: str
  to_state: str
  changed_at: datetime
  context: dict[str, object] = field(default_factory=dict)


StateCallback = Callable[[str, str, dict[str, object]], None]


class StateMachine:
  """Simple explicit state machine with transition guards and history."""

  def __init__(self, initial_state: str, states: list[str], transitions: list[Transition]) -> None:
    if initial_state not in states:
      raise ValueError(f"Initial state '{initial_state}' is not declared in states.")

    self._states = set(states)
    self._transition_map: dict[str, set[str]] = defaultdict(set)
    for transition in transitions:
      if transition.from_state not in self._states or transition.to_state not in self._states:
        raise ValueError("Transition includes an unknown state.")
      self._transition_map[transition.from_state].add(transition.to_state)

    self._current_state = initial_state
    self._history: list[StateTransition] = []
    self._enter_callbacks: dict[str, list[StateCallback]] = defaultdict(list)
    self._exit_callbacks: dict[str, list[StateCallback]] = defaultdict(list)

  @property
  def current_state(self) -> str:
    return self._current_state

  def can_transition(self, to_state: str) -> bool:
    return to_state in self._transition_map.get(self._current_state, set())

  def on_enter(self, state: str, callback: StateCallback) -> None:
    if state not in self._states:
      raise ValueError(f"Unknown state: {state}")
    self._enter_callbacks[state].append(callback)

  def on_exit(self, state: str, callback: StateCallback) -> None:
    if state not in self._states:
      raise ValueError(f"Unknown state: {state}")
    self._exit_callbacks[state].append(callback)

  def transition(self, to_state: str, context: dict[str, object] | None = None) -> bool:
    if not self.can_transition(to_state):
      return False

    resolved_context = context or {}
    from_state = self._current_state

    for callback in self._exit_callbacks.get(from_state, []):
      callback(from_state, to_state, resolved_context)

    self._current_state = to_state

    for callback in self._enter_callbacks.get(to_state, []):
      callback(from_state, to_state, resolved_context)

    self._history.append(
      StateTransition(
        from_state=from_state,
        to_state=to_state,
        changed_at=datetime.now(timezone.utc),
        context=resolved_context,
      )
    )
    return True

  def get_history(self) -> list[StateTransition]:
    return list(self._history)
