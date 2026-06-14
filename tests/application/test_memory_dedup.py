from unittest.mock import Mock


from mazyr.application.memory_dedup import MemoryDeduplicator
from mazyr.domain.memory_semantic import MemoryCategory, SemanticEntry


class TestMemoryDeduplicator:
    def test_whitespace_content_skips(self):
        store = Mock()
        embedder = Mock()
        dedup = MemoryDeduplicator(store, embedder)
        entry = SemanticEntry(id="e1", content="   ", category=MemoryCategory.FACT)
        result = dedup.deduplicate(entry)
        assert result.action == "skip"
        assert result.canonical_id == "e1"

    def test_embed_failure_inserts(self):
        store = Mock()
        embedder = Mock()
        embedder.embed.side_effect = RuntimeError("embed fail")
        dedup = MemoryDeduplicator(store, embedder)
        entry = SemanticEntry(id="e1", content="hello world", category=MemoryCategory.FACT)
        result = dedup.deduplicate(entry)
        assert result.action == "insert"

    def test_no_similar_inserts(self):
        store = Mock()
        store.search_by_vector.return_value = []
        embedder = Mock()
        embedder.embed.return_value = [0.1, 0.2]
        dedup = MemoryDeduplicator(store, embedder)
        entry = SemanticEntry(id="e1", content="unique fact", category=MemoryCategory.FACT)
        result = dedup.deduplicate(entry)
        assert result.action == "insert"
        assert result.canonical_id == "e1"

    def test_similar_merges(self):
        existing = SemanticEntry(
            id="existing", content="same fact", category=MemoryCategory.FACT, confidence=0.8
        )
        store = Mock()
        store.search_by_vector.return_value = [existing]
        embedder = Mock()
        embedder.embed.return_value = [0.1, 0.2]
        dedup = MemoryDeduplicator(store, embedder)
        new_entry = SemanticEntry(
            id="new", content="same fact", category=MemoryCategory.FACT, confidence=0.9
        )
        result = dedup.deduplicate(new_entry)
        assert result.action == "merged"
        assert result.canonical_id == "existing"

    def test_default_threshold(self):
        dedup = MemoryDeduplicator(Mock(), Mock())
        assert dedup.threshold == 0.95

    def test_custom_threshold(self):
        dedup = MemoryDeduplicator(Mock(), Mock(), threshold=0.8)
        assert dedup.threshold == 0.8
