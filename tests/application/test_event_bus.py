from unittest.mock import Mock

from mazyr.application.event_bus import EventBus
from mazyr.domain.events import DomainEvent, MessageReceived


class TestEventBus:
    def test_subscribe_and_publish(self):
        bus = EventBus()
        handler = Mock()
        bus.subscribe("message.received", handler)

        event = MessageReceived(payload={"text": "hello"})
        bus.publish(event)

        handler.assert_called_once_with(event)

    def test_multiple_handlers(self):
        bus = EventBus()
        h1 = Mock()
        h2 = Mock()
        bus.subscribe("message.received", h1)
        bus.subscribe("message.received", h2)

        event = MessageReceived(payload={})
        bus.publish(event)

        h1.assert_called_once_with(event)
        h2.assert_called_once_with(event)

    def test_handler_failure_is_isolated(self):
        bus = EventBus()
        bad = Mock(side_effect=RuntimeError("boom"))
        good = Mock()
        bus.subscribe("message.received", bad)
        bus.subscribe("message.received", good)

        event = MessageReceived(payload={})
        bus.publish(event)

        bad.assert_called_once()
        good.assert_called_once_with(event)

    def test_no_handlers_does_nothing(self):
        bus = EventBus()
        event = MessageReceived(payload={})
        bus.publish(event)  # should not raise

    def test_clear_removes_handlers(self):
        bus = EventBus()
        handler = Mock()
        bus.subscribe("message.received", handler)
        bus.clear()

        event = MessageReceived(payload={})
        bus.publish(event)

        handler.assert_not_called()

    def test_base_event_attributes(self):
        event = DomainEvent(event_type="custom", payload={"key": "value"})
        assert event.event_type == "custom"
        assert event.payload == {"key": "value"}
        assert event.timestamp
