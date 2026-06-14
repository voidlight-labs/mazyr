from mazyr.domain.memory_extraction import ExtractionResult
from mazyr.domain.memory_semantic import SemanticEntry, MemoryCategory
from mazyr.domain.memory_graph import GraphNode, GraphEdge


class TestExtractionResult:
    def test_default_empty(self):
        result = ExtractionResult()
        assert result.facts == []
        assert result.entities == []
        assert result.relations == []

    def test_with_items(self):
        fact = SemanticEntry(id="f1", content="test", category=MemoryCategory.FACT)
        entity = GraphNode(id="n1", label="Test", node_type="concept")
        relation = GraphEdge(id="e1", source_id="n1", target_id="n2", relation="relates_to")
        result = ExtractionResult(facts=[fact], entities=[entity], relations=[relation])
        assert len(result.facts) == 1
        assert len(result.entities) == 1
        assert len(result.relations) == 1
        assert result.facts[0].content == "test"
