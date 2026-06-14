from unittest.mock import AsyncMock, Mock

import pytest

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

        assert result.success is True
        assert "sorry" in result.reply.lower()


@pytest.mark.asyncio
class TestAsyncChatUseCase:
    async def test_areceive_success(self):
        mock_identity = Mock(instance_name="Aria")
        mock_mission = Mock(primary="Learn")
        mock_filter = Mock()
        mock_filter.process.return_value = Mock(action=Mock(value="ALLOW"), modified_message=None)
        mock_memory = Mock()
        mock_memory.search.return_value = []
        mock_llm = Mock()
        mock_llm.generate.return_value = "Hello async!"

        chat = ChatUseCase(mock_identity, mock_mission, mock_filter, mock_memory, mock_llm)
        msg = Message(id="1", content="Hi", sender="creator", platform="cli", timestamp="")
        result = await chat.areceive(msg)

        assert result.success is True
        assert result.reply == "Hello async!"

    async def test_areceive_inbound_filter_blocks(self):
        mock_filter = Mock()
        mock_filter.process.return_value = Mock(action=Mock(value="DROP"), reason="performative")

        chat = ChatUseCase(Mock(), Mock(), mock_filter, Mock(), Mock())
        msg = Message(id="1", content="Hi", sender="creator", platform="cli", timestamp="")
        result = await chat.areceive(msg)

        assert result.success is False
        assert "blocked" in result.error

    async def test_areceive_stream_success(self):
        mock_identity = Mock(instance_name="Aria")
        mock_mission = Mock(primary="Learn")
        mock_filter = Mock()
        mock_filter.process.return_value = Mock(action=Mock(value="ALLOW"), modified_message=None)
        mock_memory = Mock()
        mock_llm = Mock()
        mock_llm.generate_stream.return_value = iter(["Hel", "lo", "!"])

        chat = ChatUseCase(mock_identity, mock_mission, mock_filter, mock_memory, mock_llm)
        msg = Message(id="1", content="Hi", sender="creator", platform="cli", timestamp="")
        events = []
        async for event in chat.areceive_stream(msg):
            events.append(event)

        tokens = [e[1] for e in events if e[0] == "token"]
        assert "".join(tokens) == "Hello!"
        assert events[-1][0] == "done"

    async def test_areceive_stream_runs_tools_in_executor(self):
        mock_identity = Mock(instance_name="Aria")
        mock_mission = Mock(primary="Learn")
        mock_filter = Mock()
        mock_filter.process.return_value = Mock(action=Mock(value="ALLOW"), modified_message=None)
        mock_memory = Mock()
        mock_llm = Mock()
        mock_llm.generate_stream.side_effect = [
            iter(['<tool name="echo">{"text":"hi"}</tool>']),
            iter(["done"]),
        ]

        mock_registry = Mock()
        mock_registry.execute.return_value = Mock(success=True, data="hi")
        mock_registry.aexecute = AsyncMock(return_value=Mock(success=True, data="hi"))
        mock_registry.get_tool_definitions.return_value = []

        chat = ChatUseCase(
            mock_identity,
            mock_mission,
            mock_filter,
            mock_memory,
            mock_llm,
            tool_registry=mock_registry,
        )
        msg = Message(id="1", content="Hi", sender="creator", platform="cli", timestamp="")
        events = []
        async for event in chat.areceive_stream(msg):
            events.append(event)

        tool_calls = [e for e in events if e[0] == "tool_call"]
        assert len(tool_calls) == 1
        assert tool_calls[0][1] == "echo"
        mock_registry.aexecute.assert_called_once()
