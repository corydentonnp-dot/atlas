"""Event bus service — publish/subscribe for workflow triggers."""

from __future__ import annotations

import inspect
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(slots=True)
class Event:
    """A lightweight event envelope for internal bus communication."""

    type: str
    payload: dict[str, object] = field(default_factory=dict)
    workflow_id: str | None = None
    event_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


EventHandler = Callable[[Event], None | Awaitable[None]]


class EventBus:
    """Async-capable in-process publish/subscribe event bus."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Register a handler for an event type."""
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Remove a handler for an event type if present."""
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    async def publish(self, event: Event) -> None:
        """Publish an event to all registered handlers for its type."""
        for handler in list(self._subscribers.get(event.type, [])):
            result = handler(event)
            if inspect.isawaitable(result):
                await result

    def count_subscribers(self, event_type: str) -> int:
        """Return the number of subscribers registered for an event type."""
        return len(self._subscribers.get(event_type, []))


default_event_bus = EventBus()
