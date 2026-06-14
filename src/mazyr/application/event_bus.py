from collections import defaultdict
from typing import Callable

from mazyr.domain.events import DomainEvent
from mazyr.infrastructure.logger import get_logger

log = get_logger("event_bus")


class EventBus:
    """In-memory publish/subscribe event bus for domain events.

    The event bus decouples producers (ChatUseCase, ToolRegistry) from
    consumers (audit, sync, notifications, learning). Handlers are called
    synchronously in registration order; async handlers should be wrapped by
    the caller.
    """

    def __init__(self):
        self._handlers: dict[str, list[Callable[[DomainEvent], None]]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Callable[[DomainEvent], None]) -> None:
        """Register a handler for a given event type."""
        self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent) -> None:
        """Publish an event to all subscribed handlers."""
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                # Event bus must not break the caller if a subscriber fails.
                # Subscribers are responsible for their own error handling.
                log.warning("Event handler %s failed for %s: %s", handler, event.event_type, e)
                continue

    def clear(self) -> None:
        """Remove all handlers. Useful for testing."""
        self._handlers.clear()
