from typing import Optional
from uuid import NAMESPACE_URL, uuid5

from mazyr.domain.memory_entry import MemoryEntry, MemoryQuery, MemoryType
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

class QdrantMemoryAdapter:
    """Adapter for Qdrant vector database."""

    COLLECTION_NAME = "mazyr_memory"

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        vector_size: int = 1536,
        embedder=None,
        client=None,
        collection_name: str | None = None,
    ):
        self.vector_size = vector_size
        self.embedder = embedder
        self.collection_name = collection_name or self.COLLECTION_NAME
        if client is not None:
            self.client = client
        else:
            self.client = QdrantClient(host=host, port=port)

    def connect(self):
        if not self.client:
            raise RuntimeError("qdrant-client not installed")
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if not exists:
            
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
            )

    def add(self, entry: MemoryEntry, embedding: Optional[list[float]] = None):
        if not self.client:
            raise RuntimeError("qdrant-client not installed")

        if embedding is None:
            if not self.embedder:
                raise RuntimeError("No embedding adapter configured for Qdrant memory")
            embedding = self.embedder.embed(entry.to_embedding_text())

        if len(embedding) != self.vector_size:
            raise ValueError(
                f"Embedding vector size must be {self.vector_size}, got {len(embedding)}"
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=str(uuid5(NAMESPACE_URL, entry.id)),
                    vector=embedding,
                    payload={
                        "id": entry.id,
                        "type": entry.type.value,
                        "content": entry.content,
                        "category": entry.category,
                        "source": entry.source,
                        "timestamp": entry.timestamp,
                        "confidence": entry.confidence,
                        "metadata": entry.metadata,
                    },
                )
            ],
        )

    def search(self, query: MemoryQuery, query_embedding: Optional[list[float]] = None) -> list[MemoryEntry]:
        if not self.client:
            raise RuntimeError("qdrant-client not installed")

        if query_embedding is None:
            if not self.embedder:
                raise RuntimeError("No embedding adapter configured for Qdrant memory")
            query_embedding = self.embedder.embed(query.query)

        if hasattr(self.client, "query_points"):
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                limit=query.limit,
                with_payload=True,
            ).points
        else:
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=query.limit,
                with_payload=True,
            )

        entries = []
        for r in results:
            if r.score < query.min_confidence:
                continue
            payload = r.payload
            if query.types and MemoryType(payload["type"]) not in query.types:
                continue
            if query.categories and payload["category"] not in query.categories:
                continue
            entries.append(
                MemoryEntry(
                    id=payload.get("id", str(r.id)),
                    type=MemoryType(payload["type"]),
                    content=payload["content"],
                    category=payload["category"],
                    source=payload["source"],
                    timestamp=payload["timestamp"],
                    confidence=r.score,
                    metadata=payload.get("metadata", {}),
                )
            )
        return entries
