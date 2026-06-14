from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    node_type: str = Field(..., min_length=1)
    embedding_id: Optional[str] = None
    first_seen: str = Field(default_factory=lambda: datetime.now().isoformat())
    last_mentioned: str = Field(default_factory=lambda: datetime.now().isoformat())
    mention_count: int = 1


class GraphEdge(BaseModel):
    id: str = Field(..., min_length=1)
    source_id: str = Field(..., min_length=1)
    target_id: str = Field(..., min_length=1)
    relation: str = Field(..., min_length=1)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    source_session_id: Optional[str] = None
    first_seen: str = Field(default_factory=lambda: datetime.now().isoformat())
