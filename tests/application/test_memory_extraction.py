from unittest.mock import Mock

from mazyr.application.memory_extraction import (
    BatchedExtraction,
    MemoryExtractionEngine,
)
from mazyr.domain.memory_episodic import EpisodicEntry, MessageRole


class TestMemoryExtractionEngine:
    def test_successful_extraction(self):
        mock_llm = Mock()
        mock_llm.generate.return_value = (
            '{"facts": [{"content": "sky is blue", "category": "fact", "confidence": 0.9}], '
            '"entities": [], "relations": []}'
        )
        engine = MemoryExtractionEngine(mock_llm)
        entry = EpisodicEntry(
            id="e1", session_id="s1", role=MessageRole.USER, content="What color is the sky?"
        )
        result = engine.extract_from_entry(entry)
        assert len(result.facts) == 1
        assert result.facts[0].content == "sky is blue"
        assert result.facts[0].category.value == "fact"

    def test_llm_failure_returns_empty(self):
        mock_llm = Mock()
        mock_llm.generate.side_effect = RuntimeError("API down")
        engine = MemoryExtractionEngine(mock_llm)
        entry = EpisodicEntry(id="e1", session_id="s1", role=MessageRole.USER, content="Hi")
        result = engine.extract_from_entry(entry)
        assert result.facts == []

    def test_invalid_json_returns_empty(self):
        mock_llm = Mock()
        mock_llm.generate.return_value = "not json"
        engine = MemoryExtractionEngine(mock_llm)
        entry = EpisodicEntry(id="e1", session_id="s1", role=MessageRole.USER, content="Hi")
        result = engine.extract_from_entry(entry)
        assert result.facts == []

    def test_parse_markdown_code_block(self):
        mock_llm = Mock()
        mock_llm.generate.return_value = (
            '```json\n{"facts": [{"content": "water is wet", "category": "fact"}], '
            '"entities": [], "relations": []}\n```'
        )
        engine = MemoryExtractionEngine(mock_llm)
        entry = EpisodicEntry(id="e1", session_id="s1", role=MessageRole.USER, content="Water?")
        result = engine.extract_from_entry(entry)
        assert len(result.facts) == 1
        assert result.facts[0].content == "water is wet"

    def test_batch_extraction(self):
        mock_llm = Mock()
        mock_llm.generate.return_value = (
            '{"facts": [{"content": "batched fact", "category": "skill"}], '
            '"entities": [], "relations": []}'
        )
        engine = MemoryExtractionEngine(mock_llm)
        entries = [
            EpisodicEntry(id="e1", session_id="s1", role=MessageRole.USER, content="First"),
            EpisodicEntry(id="e2", session_id="s1", role=MessageRole.ASSISTANT, content="Second"),
        ]
        result = engine.extract_from_batch(entries)
        assert len(result.facts) == 1
        assert result.facts[0].category.value == "skill"

    def test_invalid_category_falls_back_to_fact(self):
        mock_llm = Mock()
        mock_llm.generate.return_value = (
            '{"facts": [{"content": "something", "category": "invalid_cat"}], '
            '"entities": [], "relations": []}'
        )
        engine = MemoryExtractionEngine(mock_llm)
        entry = EpisodicEntry(id="e1", session_id="s1", role=MessageRole.USER, content="Test")
        result = engine.extract_from_entry(entry)
        assert result.facts[0].category.value == "fact"


class TestBatchedExtraction:
    def test_flush_at_batch_size(self):
        mock_engine = Mock()
        mock_engine.extract_from_batch.return_value = Mock(facts=[], entities=[], relations=[])
        mock_memory = Mock()
        batch = BatchedExtraction(Mock(), mock_memory, Mock(), batch_size=2)
        batch.engine = mock_engine

        batch.submit(EpisodicEntry(id="e1", session_id="s1", role=MessageRole.USER, content="A"))
        assert len(batch._batch) == 1
        mock_engine.extract_from_batch.assert_not_called()

        batch.submit(EpisodicEntry(id="e2", session_id="s1", role=MessageRole.USER, content="B"))
        assert len(batch._batch) == 0
        assert mock_engine.extract_from_batch.called

    def test_flush_all(self):
        from mazyr.domain.memory_episodic import EpisodicEntry, MessageRole

        batch = BatchedExtraction(Mock(), Mock(), Mock(), batch_size=5)
        batch.engine = Mock()
        batch.engine.extract_from_batch.return_value = Mock(facts=[], entities=[], relations=[])
        batch._batch = [EpisodicEntry(id="e1", session_id="s1", role=MessageRole.USER, content="x")]

        batch.flush_all()
        assert len(batch._batch) == 0

    def test_flush_empty_does_nothing(self):
        batch = BatchedExtraction(Mock(), Mock(), Mock(), batch_size=5)
        batch.flush()
        assert len(batch._batch) == 0

    def test_store_result_stores_facts(self):
        fact = Mock()
        fact.id = "f1"
        result = Mock(facts=[fact], entities=[], relations=[])
        mock_memory = Mock()
        batch = BatchedExtraction(Mock(), mock_memory, Mock())
        batch._store_result(result)
        mock_memory.semantic.add_batch.assert_called_once_with([fact])

    def test_store_result_stores_graph(self):
        entity = Mock()
        entity.id = "n1"
        relation = Mock()
        relation.id = "e1"
        result = Mock(facts=[], entities=[entity], relations=[relation])
        mock_memory = Mock()
        batch = BatchedExtraction(Mock(), mock_memory, Mock())
        batch._store_result(result)
        mock_memory.graph.add_batch.assert_called_once_with([entity], [relation])
