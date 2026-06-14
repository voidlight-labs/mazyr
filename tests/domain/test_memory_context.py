from mazyr.domain.memory_context import ContextItem, ContextQuery, ContextResult, ContextSource


class TestContextQuery:
    def test_defaults(self):
        q = ContextQuery(query="hello")
        assert q.query == "hello"
        assert q.max_tokens == 2000
        assert q.include_working is True
        assert q.include_graph is True
        assert q.graph_depth == 2
        assert q.episodic_limit == 10

    def test_custom_values(self):
        q = ContextQuery(query="test", max_tokens=500, include_working=False, episodic_limit=5)
        assert q.max_tokens == 500
        assert q.include_working is False
        assert q.episodic_limit == 5


class TestContextItem:
    def test_minimal(self):
        item = ContextItem(content="hello", source=ContextSource.SEMANTIC)
        assert item.content == "hello"
        assert item.source == ContextSource.SEMANTIC
        assert item.score == 0.0
        assert item.metadata == {}

    def test_with_all_fields(self):
        item = ContextItem(
            content="test fact",
            source=ContextSource.WORKING,
            score=0.95,
            metadata={"key": "foo"},
        )
        assert item.score == 0.95
        assert item.metadata["key"] == "foo"


class TestContextResult:
    def test_default_empty(self):
        result = ContextResult()
        assert result.items == []
        assert result.total_tokens == 0
        assert result.formatted == ""

    def test_with_items(self):
        items = [
            ContextItem(content="a", source=ContextSource.WORKING, score=1.0),
            ContextItem(content="b", source=ContextSource.SEMANTIC, score=0.5),
        ]
        result = ContextResult(items=items, total_tokens=10, formatted="test")
        assert len(result.items) == 2
        assert result.total_tokens == 10
        assert result.formatted == "test"
