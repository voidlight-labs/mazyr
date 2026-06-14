from mazyr.domain.memory_entry import MemoryQuery, MemoryType


class TestMemoryQuery:
    def test_default_types(self):
        query = MemoryQuery(query="test")
        assert len(query.types) == 3
        assert MemoryType.EPISODIC in query.types

    def test_custom_limit(self):
        query = MemoryQuery(query="test", limit=10)
        assert query.limit == 10

    def test_min_confidence_default(self):
        query = MemoryQuery(query="test")
        assert query.min_confidence == 0.5
