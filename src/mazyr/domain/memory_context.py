from enum import Enum

from pydantic import BaseModel, Field


class ContextSource(str, Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    GRAPH = "graph"
    PROCEDURAL = "procedural"


class ContextQuery(BaseModel):
    query: str
    max_tokens: int = 2000
    include_working: bool = True
    include_episodic: bool = True
    include_semantic: bool = True
    include_graph: bool = True
    include_procedural: bool = True
    working_limit: int = 20
    episodic_limit: int = 10
    semantic_limit: int = 5
    graph_depth: int = 2
    graph_max_nodes: int = 30


class ContextItem(BaseModel):
    content: str
    source: ContextSource
    score: float = 0.0
    metadata: dict = Field(default_factory=dict)


class ContextResult(BaseModel):
    items: list[ContextItem] = Field(default_factory=list)
    total_tokens: int = 0
    formatted: str = ""
