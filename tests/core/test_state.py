"""Tests for the state machine."""

from atlas.core.state.machine import StateMachine, Transition


def test_state_machine_transition_history():
	machine = StateMachine(
		initial_state="idle",
		states=["idle", "running", "done"],
		transitions=[Transition("idle", "running"), Transition("running", "done")],
	)

	assert machine.transition("running", {"source": "test"}) is True
	assert machine.transition("done") is True

	history = machine.get_history()
	assert len(history) == 2
	assert history[0].from_state == "idle"
	assert history[1].to_state == "done"


def test_state_machine_rejects_invalid_transition():
	machine = StateMachine(
		initial_state="idle",
		states=["idle", "running"],
		transitions=[Transition("idle", "running")],
	)

	assert machine.transition("idle") is False
	assert machine.current_state == "idle"
