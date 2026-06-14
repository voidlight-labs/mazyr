from mazyr.domain.memory_semantic import SemanticEntry
from mazyr.infrastructure.logger import get_logger
from mazyr.infrastructure.memory_tier3 import SemanticStore

log = get_logger("memory.dedup")


class DeduplicationResult:
    def __init__(self, action: str, canonical_id: str):
        self.action = action
        self.canonical_id = canonical_id


class MemoryDeduplicator:
    def __init__(self, semantic_store: SemanticStore, embedder, threshold: float = 0.95):
        self._store = semantic_store
        self._embedder = embedder
        self.threshold = threshold

    def deduplicate(self, new_entry: SemanticEntry) -> DeduplicationResult:
        if not new_entry.content.strip():
            return DeduplicationResult(action="skip", canonical_id=new_entry.id)

        try:
            embedding = self._embedder.embed(new_entry.content)
        except Exception as e:
            log.warning("Dedup embed failed: %s", e)
            return DeduplicationResult(action="insert", canonical_id=new_entry.id)

        similar = self._store.search_by_vector(
            vector=embedding,
            filter={"category": new_entry.category.value},
            limit=5,
            score_threshold=self.threshold,
        )

        if similar:
            existing = similar[0]
            log.info(
                "Dedup merged '%s' -> '%s' (score=%.3f)",
                new_entry.content[:50],
                existing.content[:50],
                similar[0].confidence,
            )
            existing.touch()
            existing.confidence = max(existing.confidence, new_entry.confidence)
            try:
                self._store.update_importance(existing.id, existing.importance_score)
            except Exception:
                pass
            return DeduplicationResult(action="merged", canonical_id=existing.id)

        return DeduplicationResult(action="insert", canonical_id=new_entry.id)
