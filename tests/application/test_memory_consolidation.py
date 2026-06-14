from unittest.mock import Mock

from mazyr.application.memory_consolidation import ConsolidationEngine
from mazyr.domain.memory_episodic import EpisodicEntry, MessageRole


class TestConsolidationEngine:
    def test_process_no_unconsolidated(self):
        memory = Mock()
        memory.episodic.get_unconsolidated.return_value = []
        engine = ConsolidationEngine(memory, Mock())
        result = engine.process()
        assert result == 0

    def test_process_unconsolidated_entries(self):
        memory = Mock()
        entry = EpisodicEntry(id="e1", session_id="s1", role=MessageRole.USER, content="hello")
        memory.episodic.get_unconsolidated.return_value = [entry]
        memory.episodic.mark_consolidated = Mock()

        llm = Mock()
        llm.generate.return_value = '{"facts": [], "entities": [], "relations": []}'

        engine = ConsolidationEngine(memory, llm, batch_size=10)
        result = engine.process()

        assert result == 1
        memory.episodic.mark_consolidated.assert_called_once_with(["e1"])

    def test_process_extracts_facts(self):
        memory = Mock()
        entry = EpisodicEntry(
            id="e2", session_id="s1", role=MessageRole.USER, content="sky is blue"
        )
        memory.episodic.get_unconsolidated.return_value = [entry]
        memory.episodic.mark_consolidated = Mock()

        llm = Mock()
        llm.generate.return_value = (
            '{"facts": [{"content": "sky is blue", "category": "fact"}], '
            '"entities": [], "relations": []}'
        )

        engine = ConsolidationEngine(memory, llm, batch_size=10)
        result = engine.process()
        assert result == 1
        assert memory.semantic.add_batch.called

    def test_process_llm_failure_graceful(self):
        memory = Mock()
        entry = EpisodicEntry(id="e3", session_id="s1", role=MessageRole.USER, content="test")
        memory.episodic.get_unconsolidated.return_value = [entry]
        memory.episodic.mark_consolidated = Mock()

        llm = Mock()
        llm.generate.side_effect = RuntimeError("LLM down")

        engine = ConsolidationEngine(memory, llm, batch_size=10)
        result = engine.process()
        # Entry IS marked consolidated (empty result) to prevent infinite retries
        assert result == 1
        memory.episodic.mark_consolidated.assert_called_once_with(["e3"])

    def test_batch_size(self):
        engine = ConsolidationEngine(Mock(), Mock(), batch_size=5)
        assert engine.batch_size == 5
