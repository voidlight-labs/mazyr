import pytest

from mazyr.domain.memory_entry import MemoryEntry, MemoryQuery, MemoryType


class TestMemoryEntry:
    def test_to_embedding_text(self):
        entry = MemoryEntry(
            id="1",
            type=MemoryType.EPISODIC,
            content="Test content",
            category="test",
            source="test",
            timestamp="2026-01-01T00:00:00",
        )
        assert entry.to_embedding_text() == "[test] Test content"

    def test_schema_defaults(self):
        entry = MemoryEntry(id="1", type=MemoryType.SEMANTIC, content="Remember this")

        assert entry.category == "general"
        assert entry.source == "system"
        assert entry.timestamp
        assert entry.confidence == 1.0

    def test_invalid_confidence(self):
        with pytest.raises(ValueError):
            MemoryEntry(id="1", type=MemoryType.SEMANTIC, content="Bad", confidence=1.1)

    def test_requires_content(self):
        with pytest.raises(ValueError):
            MemoryEntry(id="1", type=MemoryType.SEMANTIC, content="")


class TestMemoryQuery:
    def test_default_types(self):
        query = MemoryQuery(query="test")
        assert len(query.types) == 3
        assert MemoryType.EPISODIC in query.types
