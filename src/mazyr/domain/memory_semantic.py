from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MemoryCategory(str, Enum):
    PREFERENCE = "preference"
    FACT = "fact"
    SKILL = "skill"
    RELATIONSHIP = "relationship"
    GOAL = "goal"
    CONSTRAINT = "constraint"


class SemanticEntry(BaseModel):
    id: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    category: MemoryCategory
    embedding: Optional[list[float]] = None
    vector_id: Optional[str] = None
    source_session_id: Optional[str] = None
    source_message_id: Optional[str] = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    access_count: int = 0
    decay_rate: float = Field(default=0.01, ge=0.0, le=1.0)
    duplicate_of: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    last_accessed: str = Field(default_factory=lambda: datetime.now().isoformat())

    def touch(self):
        self.access_count += 1
        self.last_accessed = datetime.now().isoformat()
        self.importance_score = min(1.0, self.importance_score + 0.02)

    def apply_decay(self, days_elapsed: int) -> float:
        return max(0.1, self.importance_score * (1 - self.decay_rate) ** days_elapsed)
