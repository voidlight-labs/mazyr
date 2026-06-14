from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class EpisodicEntry(BaseModel):
    id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    role: MessageRole
    content: str = Field(..., min_length=1)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    tool_calls: list[dict] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    extracted_facts: list[str] = Field(default_factory=list)
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    consolidated: bool = False

    def to_embedding_text(self) -> str:
        return f"[{self.role.value}] {self.content}"
