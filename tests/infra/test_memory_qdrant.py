from qdrant_client import QdrantClient

from mazyr.domain.memory_entry import MemoryQuery
from mazyr.domain.memory_semantic import MemoryCategory, SemanticEntry
from mazyr.infrastructure.memory_qdrant import QdrantMemoryAdapter


class FakeEmbedder:
    def embed(self, text: str) -> list[float]:
        if "nuxt" in text.lower():
            return [1.0, 0.0, 0.0]
        return [0.0, 1.0, 0.0]


def test_semantic_save_and_retrieve():
    adapter = QdrantMemoryAdapter(
        vector_size=3,
        embedder=FakeEmbedder(),
        client=QdrantClient(":memory:"),
        collection_name="test_semantic",
    )
    adapter.connect()

    adapter.add(
        SemanticEntry(
            id="1",
            content="Khayren pake Nuxt 4",
            category=MemoryCategory.FACT,
        )
    )
    adapter.add(
        SemanticEntry(
            id="2",
            content="A separate unrelated note",
            category=MemoryCategory.FACT,
        )
    )

    results = adapter.search(MemoryQuery(query="nuxt", limit=1))

    assert len(results) == 1
    assert results[0].id == "1"
    assert results[0].content == "Khayren pake Nuxt 4"


def test_semantic_search_with_category_filter():
    adapter = QdrantMemoryAdapter(
        vector_size=3,
        embedder=FakeEmbedder(),
        client=QdrantClient(":memory:"),
        collection_name="test_semantic_filter",
    )
    adapter.connect()

    adapter.add(
        SemanticEntry(
            id="1",
            content="Khayren suka kopi",
            category=MemoryCategory.PREFERENCE,
        )
    )

    results = adapter.search(MemoryQuery(query="kopi", limit=5, categories=["preference"]))
    assert len(results) == 1

    results = adapter.search(MemoryQuery(query="kopi", limit=5, categories=["fact"]))
    assert len(results) == 0
