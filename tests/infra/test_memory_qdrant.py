from qdrant_client import QdrantClient

from mazyr.domain.memory_entry import MemoryEntry, MemoryQuery, MemoryType
from mazyr.infrastructure.memory_qdrant import QdrantMemoryAdapter


class FakeEmbedder:
    def embed(self, text: str) -> list[float]:
        if "qdrant" in text.lower():
            return [1.0, 0.0, 0.0]
        return [0.0, 1.0, 0.0]


def test_qdrant_save_and_retrieve_memory():
    adapter = QdrantMemoryAdapter(
        vector_size=3,
        embedder=FakeEmbedder(),
        client=QdrantClient(":memory:"),
        collection_name="test_memory",
    )
    adapter.connect()
    adapter.add(
        MemoryEntry(
            id="memory-qdrant",
            type=MemoryType.SEMANTIC,
            content="Qdrant remembers semantic facts",
            category="memory",
            source="test",
            timestamp="2026-06-10T00:00:00",
        )
    )
    adapter.add(
        MemoryEntry(
            id="memory-other",
            type=MemoryType.SEMANTIC,
            content="A separate unrelated note",
            category="memory",
            source="test",
            timestamp="2026-06-10T00:00:01",
        )
    )

    results = adapter.search(MemoryQuery(query="qdrant memory", limit=1))

    assert len(results) == 1
    assert results[0].id == "memory-qdrant"
    assert results[0].content == "Qdrant remembers semantic facts"
