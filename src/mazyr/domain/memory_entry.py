from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class MemoryQuery(BaseModel):
    query: str
    types: list[MemoryType] = Field(
        default_factory=lambda: [MemoryType.EPISODIC, MemoryType.SEMANTIC, MemoryType.PROCEDURAL]
    )
    categories: Optional[list[str]] = None
    limit: int = 5
    min_confidence: float = 0.5
