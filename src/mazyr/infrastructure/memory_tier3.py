from typing import Optional

from mazyr.domain.memory_entry import MemoryQuery
from mazyr.domain.memory_semantic import SemanticEntry
from mazyr.infrastructure.memory_qdrant import QdrantMemoryAdapter
from mazyr.infrastructure.memory_sqlite import SQLiteMemoryAdapter


class SemanticStore:
    def __init__(
        self,
        sqlite: SQLiteMemoryAdapter,
        qdrant: Optional[QdrantMemoryAdapter] = None,
        embedder=None,
    ):
        self._sqlite = sqlite
        self._qdrant = qdrant
        self._embedder = embedder

    def add(self, entry: SemanticEntry):
        self.add_batch([entry])

    def add_batch(self, entries: list[SemanticEntry]):
        if not entries:
            return

        if self._embedder:
            contents = [e.content for e in entries]
            vectors = self._embedder.embed_batch(contents)
            for entry, vector in zip(entries, vectors):
                if vector:
                    entry.embedding = vector

        self._sqlite.add_semantic_batch(entries)
        if self._qdrant:
            self._qdrant.add_batch(entries, embeddings=[e.embedding for e in entries])

    def search(self, query: MemoryQuery) -> list[SemanticEntry]:
        if self._qdrant:
            return self._qdrant.search(query)
        return []

    def count(self) -> int:
        return self._sqlite.count_semantic()

    def get_stale(self, threshold_days: int = 7) -> list[SemanticEntry]:
        return self._sqlite.get_stale_semantic(threshold_days)

    def search_by_vector(
        self,
        vector: list[float],
        filter: Optional[dict] = None,
        limit: int = 5,
        score_threshold: float = 0.95,
    ) -> list[SemanticEntry]:
        if self._qdrant:
            return self._qdrant.search_similar(
                vector=vector,
                filter=filter,
                limit=limit,
                score_threshold=score_threshold,
            )
        return []

    def update_importance(self, entry_id: str, new_score: float):
        if self._qdrant:
            self._qdrant.update_payload(entry_id, {"importance_score": new_score})
