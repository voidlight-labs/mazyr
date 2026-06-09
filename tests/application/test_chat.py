import pytest
from unittest.mock import Mock

from mazyr.application.chat import ChatUseCase
from mazyr.domain.message import Message


class TestChatUseCase:
    def test_successful_chat(self):
        mock_identity = Mock(instance_name="Aria")
        mock_mission = Mock(primary="Learn")
        mock_filter = Mock()
        mock_filter.process.return_value = Mock(action=Mock(value="ALLOW"), modified_message=None)
        mock_memory = Mock()
        mock_memory.search.return_value = []
        mock_llm = Mock()
        mock_llm.generate.return_value = "Hello!"

        chat = ChatUseCase(mock_identity, mock_mission, mock_filter, mock_memory, mock_llm)
        msg = Message(id="1", content="Hi", sender="creator", platform="cli", timestamp="")
        result = chat.receive(msg)

        assert result.success is True
        assert result.reply == "Hello!"

    def test_inbound_filter_blocks(self):
        mock_filter = Mock()
        mock_filter.process.return_value = Mock(
            action=Mock(value="DROP"), reason="performative", matched_rule="performative"
        )

        chat = ChatUseCase(Mock(), Mock(), mock_filter, Mock(), Mock())
        msg = Message(id="1", content="Follow me!", sender="creator", platform="cli", timestamp="")
        result = chat.receive(msg)

        assert result.success is False
        assert "blocked" in result.error

    def test_outbound_filter_blocks(self):
        mock_filter = Mock()
        mock_filter.process.side_effect = [
            Mock(action=Mock(value="ALLOW")),
            Mock(action=Mock(value="DROP"), reason="superiority"),
        ]
        mock_llm = Mock()
        mock_llm.generate.return_value = "I own this"

        chat = ChatUseCase(Mock(), Mock(), mock_filter, Mock(), mock_llm)
        msg = Message(id="1", content="Hi", sender="creator", platform="cli", timestamp="")
        result = chat.receive(msg)

        assert result.success is False
