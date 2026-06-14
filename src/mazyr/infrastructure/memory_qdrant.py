from typing import Optional
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from mazyr.domain.memory_entry import MemoryQuery
from mazyr.domain.memory_semantic import MemoryCategory, SemanticEntry
from mazyr.infrastructure.retry import retry_qdrant

_PAYLOAD_INDEXES: list[tuple[str, PayloadSchemaType]] = [
    ("category", PayloadSchemaType.KEYWORD),
    ("importance_score", PayloadSchemaType.FLOAT),
    ("source_session_id", PayloadSchemaType.KEYWORD),
    ("created_at", PayloadSchemaType.KEYWORD),
]


class QdrantMemoryAdapter:
    COLLECTION_NAME = "mazyr_semantic_memory"

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

    @retry_qdrant
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

        for field_name, schema in _PAYLOAD_INDEXES:
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name=field_name,
                field_schema=schema,
            )

    def add(self, entry: SemanticEntry, embedding: Optional[list[float]] = None):
        self.add_batch([entry], embeddings=[embedding] if embedding else None)

    @retry_qdrant
    def add_batch(
        self,
        entries: list[SemanticEntry],
        embeddings: Optional[list[Optional[list[float]]]] = None,
    ):
        if not self.client:
            raise RuntimeError("qdrant-client not installed")
        if not entries:
            return

        if embeddings is None:
            embeddings = [None] * len(entries)

        if len(embeddings) != len(entries):
            raise ValueError("entries and embeddings must have the same length")

        points = []
        for entry, embedding in zip(entries, embeddings):
            if embedding is None:
                if not self.embedder:
                    raise RuntimeError("No embedding adapter configured for Qdrant memory")
                embedding = self.embedder.embed(entry.content)
            if len(embedding) != self.vector_size:
                raise ValueError(
                    f"Embedding vector size must be {self.vector_size}, got {len(embedding)}"
                )
            points.append(
                PointStruct(
                    id=str(uuid5(NAMESPACE_URL, entry.id)),
                    vector=embedding,
                    payload={
                        "id": entry.id,
                        "content": entry.content,
                        "category": entry.category.value,
                        "importance_score": entry.importance_score,
                        "confidence": entry.confidence,
                        "access_count": entry.access_count,
                        "source_session_id": entry.source_session_id,
                        "source_message_id": entry.source_message_id,
                        "created_at": entry.created_at,
                        "last_accessed": entry.last_accessed,
                    },
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )

    @retry_qdrant
    def search(
        self, query: MemoryQuery, query_embedding: Optional[list[float]] = None
    ) -> list[SemanticEntry]:
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
            if query.categories and payload.get("category") not in query.categories:
                continue
            entries.append(
                SemanticEntry(
                    id=payload.get("id", str(r.id)),
                    content=payload["content"],
                    category=MemoryCategory(payload["category"]),
                    confidence=r.score,
                    importance_score=payload.get("importance_score", 0.5),
                    access_count=payload.get("access_count", 0),
                    source_session_id=payload.get("source_session_id"),
                    source_message_id=payload.get("source_message_id"),
                    created_at=payload.get("created_at", ""),
                    last_accessed=payload.get("last_accessed", ""),
                )
            )
        return entries

    @retry_qdrant
    def search_similar(
        self,
        vector: list[float],
        filter: Optional[dict] = None,
        limit: int = 5,
        score_threshold: float = 0.95,
    ) -> list[SemanticEntry]:
        if not self.client:
            raise RuntimeError("qdrant-client not installed")

        qdrant_filter = None
        if filter:
            conditions = []
            for key, value in filter.items():
                if isinstance(value, list):
                    from qdrant_client.models import MatchAny

                    conditions.append(FieldCondition(key=key, match=MatchAny(any=value)))
                else:
                    conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
            qdrant_filter = Filter(must=conditions)

        if hasattr(self.client, "query_points"):
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=vector,
                query_filter=qdrant_filter,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
            ).points
        else:
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                query_filter=qdrant_filter,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
            )

        entries = []
        for r in results:
            payload = r.payload
            entries.append(
                SemanticEntry(
                    id=payload.get("id", str(r.id)),
                    content=payload["content"],
                    category=MemoryCategory(payload["category"]),
                    confidence=r.score,
                    importance_score=payload.get("importance_score", 0.5),
                    access_count=payload.get("access_count", 0),
                    source_session_id=payload.get("source_session_id"),
                    source_message_id=payload.get("source_message_id"),
                    created_at=payload.get("created_at", ""),
                    last_accessed=payload.get("last_accessed", ""),
                )
            )
        return entries

    def update_payload(self, entry_id: str, payload: dict):
        self.update_payload_batch({entry_id: payload})

    @retry_qdrant
    def update_payload_batch(self, updates: dict[str, dict]):
        if not self.client or not updates:
            return
        # Qdrant's set_payload applies the same payload to all given points.
        # For heterogeneous updates we run one call per entry.
        for entry_id, payload in updates.items():
            point_id = str(uuid5(NAMESPACE_URL, entry_id))
            self.client.set_payload(
                collection_name=self.collection_name,
                payload=payload,
                points=[point_id],
            )

    def is_available(self) -> bool:
        return bool(self.client)
