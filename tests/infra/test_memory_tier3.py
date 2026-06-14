import tempfile
from pathlib import Path

from qdrant_client import QdrantClient

from mazyr.domain.memory_semantic import MemoryCategory, SemanticEntry
from mazyr.infrastructure.memory_qdrant import QdrantMemoryAdapter
from mazyr.infrastructure.memory_sqlite import SQLiteMemoryAdapter
from mazyr.infrastructure.memory_tier3 import SemanticStore


class FakeEmbedder:
    def __init__(self):
        self.calls = []

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return [1.0, 0.0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[1.0, 0.0] for _ in texts]


def test_semantic_store_add_batch_precomputes_embeddings():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        sqlite = SQLiteMemoryAdapter(str(db_path))
        sqlite.connect()

        qdrant = QdrantMemoryAdapter(
            vector_size=2,
            client=QdrantClient(":memory:"),
            collection_name="test_semantic_store",
        )
        qdrant.connect()

        embedder = FakeEmbedder()
        store = SemanticStore(sqlite, qdrant, embedder=embedder)

        entries = [
            SemanticEntry(id="1", content="alpha", category=MemoryCategory.FACT),
            SemanticEntry(id="2", content="beta", category=MemoryCategory.FACT),
        ]
        store.add_batch(entries)

        assert embedder.calls == [["alpha", "beta"]]
        assert entries[0].embedding == [1.0, 0.0]
        assert entries[1].embedding == [1.0, 0.0]
        assert sqlite.count_semantic() == 2

        results = qdrant.search_similar([1.0, 0.0], limit=2)
        assert len(results) == 2
