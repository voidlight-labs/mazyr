from unittest.mock import Mock

import pytest

from mazyr.application.chat import ChatUseCase
from mazyr.application.event_bus import EventBus
from mazyr.domain.events import FilterTriggered, MessageReceived
from mazyr.domain.message import Message


class TestChatUseCaseEvents:
    def test_receive_publishes_message_received(self):
        bus = EventBus()
        handler = Mock()
        bus.subscribe("message.received", handler)

        mock_filter = Mock()
        mock_filter.process.return_value = Mock(action=Mock(value="ALLOW"), modified_message=None)
        mock_llm = Mock()
        mock_llm.generate.return_value = "Hello!"

        chat = ChatUseCase(
            Mock(instance_name="Aria"),
            Mock(primary="Learn"),
            mock_filter,
            Mock(),
            mock_llm,
            event_bus=bus,
        )
        msg = Message(id="1", content="Hi", sender="creator", platform="cli", timestamp="")
        chat.receive(msg)

        handler.assert_called_once()
        event = handler.call_args[0][0]
        assert isinstance(event, MessageReceived)

    def test_receive_publishes_filter_triggered_when_blocked(self):
        bus = EventBus()
        handler = Mock()
        bus.subscribe("filter.triggered", handler)

        mock_filter = Mock()
        mock_filter.process.return_value = Mock(
            action=Mock(value="DROP"), reason="performative", matched_rule="performative"
        )

        chat = ChatUseCase(
            Mock(instance_name="Aria"),
            Mock(primary="Learn"),
            mock_filter,
            Mock(),
            Mock(),
            event_bus=bus,
        )
        msg = Message(id="1", content="Follow me!", sender="creator", platform="cli", timestamp="")
        chat.receive(msg)

        handler.assert_called_once()
        event = handler.call_args[0][0]
        assert isinstance(event, FilterTriggered)
        assert event.original_message == "Follow me!"

    def test_receive_triggers_learning_when_configured(self):
        learn = Mock()
        learn.extract_pattern.return_value = {"type": "recurring_topic", "keywords": ["python"]}

        mock_filter = Mock()
        mock_filter.process.return_value = Mock(action=Mock(value="ALLOW"), modified_message=None)
        mock_llm = Mock()
        mock_llm.generate.return_value = "Hello!"

        chat = ChatUseCase(
            Mock(instance_name="Aria"),
            Mock(primary="Learn"),
            mock_filter,
            Mock(),
            mock_llm,
            learn_use_case=learn,
        )
        msg = Message(id="1", content="Hi", sender="creator", platform="cli", timestamp="")
        chat.receive(msg)

        learn.extract_pattern.assert_called_once_with(chat.conversation)

    def test_learn_failure_is_swallowed(self):
        learn = Mock()
        learn.extract_pattern.side_effect = RuntimeError("learning failed")

        mock_filter = Mock()
        mock_filter.process.return_value = Mock(action=Mock(value="ALLOW"), modified_message=None)
        mock_llm = Mock()
        mock_llm.generate.return_value = "Hello!"

        chat = ChatUseCase(
            Mock(instance_name="Aria"),
            Mock(primary="Learn"),
            mock_filter,
            Mock(),
            mock_llm,
            learn_use_case=learn,
        )
        msg = Message(id="1", content="Hi", sender="creator", platform="cli", timestamp="")
        result = chat.receive(msg)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_areceive_publishes_message_received(self):
        bus = EventBus()
        handler = Mock()
        bus.subscribe("message.received", handler)

        mock_filter = Mock()
        mock_filter.process.return_value = Mock(action=Mock(value="ALLOW"), modified_message=None)
        mock_llm = Mock()
        mock_llm.generate.return_value = "Hello async!"

        chat = ChatUseCase(
            Mock(instance_name="Aria"),
            Mock(primary="Learn"),
            mock_filter,
            Mock(),
            mock_llm,
            event_bus=bus,
        )
        msg = Message(id="1", content="Hi", sender="creator", platform="cli", timestamp="")
        await chat.areceive(msg)

        handler.assert_called_once()
        event = handler.call_args[0][0]
        assert isinstance(event, MessageReceived)
