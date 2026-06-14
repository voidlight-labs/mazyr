import tempfile
from pathlib import Path

from mazyr.domain.memory_graph import GraphEdge, GraphNode
from mazyr.infrastructure.memory_graph_store import GraphStore
from mazyr.infrastructure.memory_sqlite import SQLiteMemoryAdapter


class TestGraphStore:
    def test_search_nodes_by_label(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            adapter = SQLiteMemoryAdapter(str(db_path))
            adapter.connect()
            store = GraphStore(adapter)

            adapter.add_graph_node(GraphNode(id="n1", label="Python", node_type="language"))
            adapter.add_graph_node(GraphNode(id="n2", label="Java", node_type="language"))

            results = store.search_nodes("Python")
            assert len(results) == 1
            assert results[0].id == "n1"

    def test_get_node_by_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            adapter = SQLiteMemoryAdapter(str(db_path))
            adapter.connect()
            store = GraphStore(adapter)

            adapter.add_graph_node(GraphNode(id="n1", label="Python", node_type="language"))
            node = store.get_node("n1")
            assert node is not None
            assert node.label == "Python"

    def test_get_node_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            adapter = SQLiteMemoryAdapter(str(db_path))
            adapter.connect()
            store = GraphStore(adapter)

            node = store.get_node("nonexistent")
            assert node is None

    def test_outgoing_edges(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            adapter = SQLiteMemoryAdapter(str(db_path))
            adapter.connect()
            store = GraphStore(adapter)

            adapter.add_graph_node(GraphNode(id="n1", label="Python", node_type="language"))
            adapter.add_graph_node(GraphNode(id="n2", label="Django", node_type="framework"))
            adapter.add_graph_edge(
                GraphEdge(id="e1", source_id="n1", target_id="n2", relation="used_in")
            )

            edges = store.get_outgoing_edges("n1")
            assert len(edges) == 1
            assert edges[0].target_id == "n2"

    def test_incoming_edges(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            adapter = SQLiteMemoryAdapter(str(db_path))
            adapter.connect()
            store = GraphStore(adapter)

            adapter.add_graph_node(GraphNode(id="n1", label="Python", node_type="language"))
            adapter.add_graph_node(GraphNode(id="n2", label="Django", node_type="framework"))
            adapter.add_graph_edge(
                GraphEdge(id="e1", source_id="n2", target_id="n1", relation="depends_on")
            )

            edges = store.get_incoming_edges("n1")
            assert len(edges) == 1
            assert edges[0].source_id == "n2"

    def test_traverse_single_hop(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            adapter = SQLiteMemoryAdapter(str(db_path))
            adapter.connect()
            store = GraphStore(adapter)

            adapter.add_graph_node(GraphNode(id="n1", label="Python", node_type="language"))
            adapter.add_graph_node(GraphNode(id="n2", label="Django", node_type="framework"))
            adapter.add_graph_edge(
                GraphEdge(id="e1", source_id="n1", target_id="n2", relation="used_in")
            )

            nodes, edges = store.traverse(start_labels=["Python"], max_depth=1)
            assert len(nodes) == 2
            assert len(edges) == 1

    def test_traverse_multi_hop(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            adapter = SQLiteMemoryAdapter(str(db_path))
            adapter.connect()
            store = GraphStore(adapter)

            adapter.add_graph_node(GraphNode(id="n1", label="Python", node_type="language"))
            adapter.add_graph_node(GraphNode(id="n2", label="Django", node_type="framework"))
            adapter.add_graph_node(GraphNode(id="n3", label="Web", node_type="concept"))
            adapter.add_graph_edge(
                GraphEdge(id="e1", source_id="n1", target_id="n2", relation="used_in")
            )
            adapter.add_graph_edge(
                GraphEdge(id="e2", source_id="n2", target_id="n3", relation="builds")
            )

            nodes, edges = store.traverse(start_labels=["Python"], max_depth=2)
            assert len(nodes) == 3
            assert len(edges) == 2

    def test_traverse_no_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            adapter = SQLiteMemoryAdapter(str(db_path))
            adapter.connect()
            store = GraphStore(adapter)

            nodes, edges = store.traverse(start_labels=["Nonexistent"], max_depth=1)
            assert nodes == []
            assert edges == []
