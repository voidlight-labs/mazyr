"""Pydantic parameter models for tool validation.

Each model enforces the runtime contract for a tool call beyond the
stringly-typed schema used in the LLM-facing tool description.
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ReadFileParams(BaseModel):
    path: str = Field(..., min_length=1)

    @field_validator("path")
    @classmethod
    def _no_traversal(cls, v: str) -> str:
        if ".." in v or "~" in v:
            raise ValueError("path must not contain parent references or home expansion")
        return v


class ListDirectoryParams(BaseModel):
    path: str = Field(default=".", min_length=1)

    @field_validator("path")
    @classmethod
    def _no_traversal(cls, v: str) -> str:
        if ".." in v or "~" in v:
            raise ValueError("path must not contain parent references or home expansion")
        return v


class SearchMemoryParams(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(default=5, ge=1, le=100)


class AddMemoryParams(BaseModel):
    content: str = Field(..., min_length=1)
    category: str = Field(default="fact")
    source: str = Field(default="tool")
    type: str = Field(default="episodic")


class RunCodeParams(BaseModel):
    code: str = Field(..., min_length=1)
    language: str = Field(default="python")
    timeout: int = Field(default=30, ge=1, le=300)


class FileWriteParams(BaseModel):
    path: str = Field(..., min_length=1)
    content: str

    @field_validator("path")
    @classmethod
    def _no_traversal(cls, v: str) -> str:
        if ".." in v or "~" in v:
            raise ValueError("path must not contain parent references or home expansion")
        return v


class ExecuteShellParams(BaseModel):
    command: str = Field(..., min_length=1, max_length=4096)
    timeout: int = Field(default=30, ge=1, le=300)


class ApiCallExternalParams(BaseModel):
    url: str = Field(..., min_length=1)
    method: str = Field(default="GET")
    headers: dict[str, str] = Field(default_factory=dict)
    body: Any = None


class MemoryAdminParams(BaseModel):
    action: str = Field(..., min_length=1)
    limit: int = Field(default=10, ge=1, le=1000)


class SetActiveSkillParams(BaseModel):
    name: str = Field(default="", min_length=0)
