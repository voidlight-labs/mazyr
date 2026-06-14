"""Application-layer memory facade.

MemorySystem composes the concrete tier stores but lives in the application
layer, respecting Mazyr's dependency rule: domain has no infrastructure imports.
"""

from typing import Optional

from mazyr.domain.memory_entry import MemoryQuery
from mazyr.domain.memory_episodic import EpisodicEntry
from mazyr.domain.memory_semantic import SemanticEntry
from mazyr.domain.ports import (
    EpisodicMemoryPort,
    GraphMemoryPort,
    SemanticMemoryPort,
    WorkingMemoryPort,
)
from mazyr.infrastructure.memory_graph_store import GraphStore
from mazyr.infrastructure.memory_qdrant import QdrantMemoryAdapter
from mazyr.infrastructure.memory_sqlite import SQLiteMemoryAdapter
from mazyr.infrastructure.memory_tier1 import WorkingMemoryStore
from mazyr.infrastructure.memory_tier2 import EpisodicStore
from mazyr.infrastructure.memory_tier3 import SemanticStore


class MemorySystem:
    """Composes tiered memory stores and exposes them to application use cases."""

    def __init__(
        self,
        sqlite_adapter: SQLiteMemoryAdapter,
        qdrant_adapter: Optional[QdrantMemoryAdapter] = None,
        semantic_store: Optional[SemanticMemoryPort] = None,
        episodic_store: Optional[EpisodicMemoryPort] = None,
        graph_store: Optional[GraphMemoryPort] = None,
        working_store: Optional[WorkingMemoryPort] = None,
    ):
        self._sqlite = sqlite_adapter
        self._qdrant = qdrant_adapter
        self.working = working_store or WorkingMemoryStore()
        self.episodic = episodic_store or EpisodicStore(sqlite_adapter)
        self.semantic = semantic_store or SemanticStore(
            sqlite_adapter,
            qdrant_adapter,
            embedder=qdrant_adapter.embedder if qdrant_adapter else None,
        )
        self.graph = graph_store or GraphStore(sqlite_adapter)

    def connect(self):
        self._sqlite.connect()
        if self._qdrant:
            self._qdrant.connect()

    def add(self, entry: EpisodicEntry | SemanticEntry):
        if isinstance(entry, EpisodicEntry):
            self.episodic.add(entry)
        elif isinstance(entry, SemanticEntry):
            self.semantic.add(entry)

    def add_batch(self, entries: list[EpisodicEntry | SemanticEntry]):
        episodic = [e for e in entries if isinstance(e, EpisodicEntry)]
        semantic = [e for e in entries if isinstance(e, SemanticEntry)]
        if episodic:
            self.episodic.add_batch(episodic)
        if semantic:
            self.semantic.add_batch(semantic)

    def search(self, query: MemoryQuery) -> list[SemanticEntry]:
        return self.semantic.search(query)

    def count(self) -> dict:
        return self._sqlite.count_all()

    def summary(self) -> dict:
        return self.count()

    @property
    def sqlite(self) -> SQLiteMemoryAdapter:
        """Expose the underlying SQLite adapter for tool audit logging."""
        return self._sqlite

    def close(self):
        self._sqlite.close()
