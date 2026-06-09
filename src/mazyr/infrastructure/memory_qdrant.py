from typing import Optional

from mazyr.domain.memory_entry import MemoryEntry, MemoryQuery, MemoryType


class QdrantMemoryAdapter:
    """Adapter for Qdrant vector database."""

    COLLECTION_NAME = "mazyr_memory"
    VECTOR_SIZE = 768

    def __init__(self, host: str = "localhost", port: int = 6333):
        try:
            from qdrant_client import QdrantClient
            self.client = QdrantClient(host=host, port=port)
        except ImportError:
            self.client = None

    def connect(self):
        if not self.client:
            raise RuntimeError("qdrant-client not installed")
        collections = self.client.get_collections().collections
        exists = any(c.name == self.COLLECTION_NAME for c in collections)

        if not exists:
            from qdrant_client.models import Distance, VectorParams
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(size=self.VECTOR_SIZE, distance=Distance.COSINE),
            )

    def add(self, entry: MemoryEntry, embedding: Optional[list[float]] = None):
        if not self.client:
            raise RuntimeError("qdrant-client not installed")
        from qdrant_client.models import PointStruct

        if embedding is None:
            # In a real implementation, generate embedding here
            embedding = [0.0] * self.VECTOR_SIZE

        self.client.upsert(
            collection_name=self.COLLECTION_NAME,
            points=[
                PointStruct(
                    id=entry.id,
                    vector=embedding,
                    payload={
                        "type": entry.type.value,
                        "content": entry.content,
                        "category": entry.category,
                        "source": entry.source,
                        "timestamp": entry.timestamp,
                        "confidence": entry.confidence,
                    },
                )
            ],
        )

    def search(self, query: MemoryQuery, query_embedding: Optional[list[float]] = None) -> list[MemoryEntry]:
        if not self.client:
            raise RuntimeError("qdrant-client not installed")

        if query_embedding is None:
            query_embedding = [0.0] * self.VECTOR_SIZE

        results = self.client.search(
            collection_name=self.COLLECTION_NAME,
            query_vector=query_embedding,
            limit=query.limit,
            with_payload=True,
        )

        entries = []
        for r in results:
            if r.score < query.min_confidence:
                continue
            payload = r.payload
            entries.append(
                MemoryEntry(
                    id=str(r.id),
                    type=MemoryType(payload["type"]),
                    content=payload["content"],
                    category=payload["category"],
                    source=payload["source"],
                    timestamp=payload["timestamp"],
                    confidence=r.score,
                )
            )
        return entries
