import pytest

from mazyr.domain.memory_episodic import EpisodicEntry, MessageRole


class TestEpisodicEntry:
    def test_valid_entry(self):
        entry = EpisodicEntry(
            id="1",
            session_id="s1",
            role=MessageRole.USER,
            content="Hello",
        )
        assert entry.role == MessageRole.USER
        assert entry.importance_score == 0.5
        assert entry.consolidated is False

    def test_to_embedding_text(self):
        entry = EpisodicEntry(
            id="1",
            session_id="s1",
            role=MessageRole.ASSISTANT,
            content="Hi there",
        )
        assert entry.to_embedding_text() == "[assistant] Hi there"

    def test_default_tool_calls(self):
        entry = EpisodicEntry(
            id="1",
            session_id="s1",
            role=MessageRole.USER,
            content="test",
        )
        assert entry.tool_calls == []

    def test_requires_content(self):
        with pytest.raises(ValueError):
            EpisodicEntry(id="1", session_id="s1", role=MessageRole.USER, content="")

    def test_role_enum_values(self):
        assert MessageRole.USER.value == "user"
        assert MessageRole.ASSISTANT.value == "assistant"
        assert MessageRole.SYSTEM.value == "system"
        assert MessageRole.TOOL.value == "tool"
