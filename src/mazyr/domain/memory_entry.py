from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    """Types of memory entries."""

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class MemoryEntry(BaseModel):
    """A single memory entry. Validated using Pydantic as per MTS-05."""

    id: str = Field(..., min_length=1)
    type: MemoryType
    content: str = Field(..., min_length=1)
    category: str = Field(default="general", max_length=64)
    source: str = Field(default="system", max_length=64)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict = Field(default_factory=dict)

    def to_embedding_text(self) -> str:
        return f"[{self.category}] {self.content}"


class MemoryQuery(BaseModel):
    """Query for retrieving memories."""

    query: str
    types: list[MemoryType] = Field(default_factory=lambda: [MemoryType.EPISODIC, MemoryType.SEMANTIC, MemoryType.PROCEDURAL])
    categories: Optional[list[str]] = None
    limit: int = 5
    min_confidence: float = 0.5
