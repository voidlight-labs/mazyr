from pydantic import BaseModel, Field

from mazyr.domain.memory_graph import GraphEdge, GraphNode
from mazyr.domain.memory_semantic import SemanticEntry


class ExtractionResult(BaseModel):
    facts: list[SemanticEntry] = Field(default_factory=list)
    entities: list[GraphNode] = Field(default_factory=list)
    relations: list[GraphEdge] = Field(default_factory=list)
