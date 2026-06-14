from mazyr.domain.memory_graph import GraphNode, GraphEdge


class TestGraphNode:
    def test_valid_node(self):
        node = GraphNode(id="1", label="Khayren", node_type="person")
        assert node.label == "Khayren"
        assert node.mention_count == 1

    def test_default_embedding(self):
        node = GraphNode(id="1", label="Voidlight", node_type="organization")
        assert node.embedding_id is None


class TestGraphEdge:
    def test_valid_edge(self):
        edge = GraphEdge(id="1", source_id="1", target_id="2", relation="works_at")
        assert edge.relation == "works_at"
        assert edge.confidence == 0.8

    def test_default_confidence(self):
        edge = GraphEdge(id="1", source_id="1", target_id="2", relation="knows")
        assert edge.confidence == 0.8
