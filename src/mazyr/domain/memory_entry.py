from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class MemoryType(str, Enum):
    """Types of memory entries."""

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


@dataclass
class MemoryEntry:
    """A single memory entry."""

    id: str
    type: MemoryType
    content: str
    category: str
    source: str
    timestamp: str
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)

    def to_embedding_text(self) -> str:
        return f"[{self.category}] {self.content}"


@dataclass
class MemoryQuery:
    """Query for retrieving memories."""

    query: str
    types: list[MemoryType] = field(default_factory=lambda: list(MemoryType))
    categories: Optional[list[str]] = None
    limit: int = 5
    min_confidence: float = 0.5
