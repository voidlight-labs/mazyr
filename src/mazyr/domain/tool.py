from datetime import datetime, timedelta
from enum import IntEnum
from typing import Any, Literal, Optional, Type
from uuid import uuid4

from pydantic import BaseModel, Field


class ToolTier(IntEnum):
    BLACKLIST = 0
    SAFE = 1
    SEMI_SAFE = 2
    DANGEROUS = 3


class ToolDefinition(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z_][a-z0-9_]*$")
    description: str = Field(..., max_length=512)
    tier: ToolTier
    param_schema: dict[str, Any] = Field(default_factory=dict)
    param_model: Optional[Type[BaseModel]] = Field(default=None, exclude=True)
    parallel_safe: bool = False
    handler: str = Field(..., max_length=128)


class ToolCall(BaseModel):
    name: str
    params: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    success: bool
    data: Optional[str] = None
    error: Optional[str] = None
    duration_ms: int = 0
    status: str = "EXECUTED"


class ToolAuditEntry(BaseModel):
    session_id: str
    tool_name: str
    tier: int
    params: dict[str, Any] = Field(default_factory=dict)
    result: Optional[str] = None
    status: str = "ALLOWED"
    approved_by: Optional[str] = None
    duration_ms: int = 0


class ApprovalRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    session_id: str
    tool_call: ToolCall
    reason: str = ""
    status: Literal["pending", "approved", "denied", "timeout", "modified"] = "pending"
    proposed_params: dict[str, Any] = Field(default_factory=dict)
    approved_by: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    expires_at: str = Field(
        default_factory=lambda: (datetime.now() + timedelta(minutes=10)).isoformat()
    )

    def with_decision(
        self,
        decision: Literal["approved", "denied", "timeout", "modified"],
        approved_by: Optional[str] = None,
    ) -> "ApprovalRequest":
        return self.model_copy(update={"status": decision, "approved_by": approved_by})


class ApprovalResponse(BaseModel):
    decision: Literal["approve", "deny", "modify"]
    modified_params: Optional[dict[str, Any]] = None
    approved_by: Optional[str] = None
