"""Tests for the event bus."""

from atlas.core.events.bus import Event, EventBus


async def test_event_bus_publish_and_subscribe():
	bus = EventBus()
	received: list[str] = []

	def handler(event: Event) -> None:
		received.append(event.type)

	bus.subscribe("manual_trigger", handler)
	await bus.publish(Event(type="manual_trigger", payload={"x": 1}))

	assert received == ["manual_trigger"]


async def test_event_bus_unsubscribe():
	bus = EventBus()
	received: list[str] = []

	def handler(event: Event) -> None:
		received.append(event.type)

	bus.subscribe("test", handler)
	bus.unsubscribe("test", handler)
	await bus.publish(Event(type="test"))

	assert received == []
