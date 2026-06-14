import tempfile
import threading
from pathlib import Path

from mazyr.domain.memory_episodic import EpisodicEntry, MessageRole
from mazyr.domain.memory_graph import GraphEdge, GraphNode
from mazyr.domain.memory_semantic import MemoryCategory, SemanticEntry
from mazyr.infrastructure.memory_sqlite import SQLiteMemoryAdapter


class TestSQLiteMemoryAdapter:
    def test_add_and_count_episodic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            adapter = SQLiteMemoryAdapter(str(db_path))
            adapter.connect()

            entry = EpisodicEntry(
                id="1",
                session_id="s1",
                role=MessageRole.USER,
                content="Test memory",
                timestamp="2026-01-01T00:00:00",
            )
            adapter.add_episodic(entry)
            assert adapter.count_episodic() == 1
            adapter.close()

    def test_get_recent_episodic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            adapter = SQLiteMemoryAdapter(str(db_path))
            adapter.connect()

            for i in range(3):
                adapter.add_episodic(
                    EpisodicEntry(
                        id=str(i),
                        session_id="s1",
                        role=MessageRole.USER,
                        content=f"Memory {i}",
                        timestamp=f"2026-01-01T00:00:0{i}",
                    )
                )

            recent = adapter.get_recent_episodic(2)
            assert len(recent) == 2
            adapter.close()

    def test_add_and_count_semantic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            adapter = SQLiteMemoryAdapter(str(db_path))
            adapter.connect()

            entry = SemanticEntry(
                id="s1",
                content="Khayren pake Nuxt 4",
                category=MemoryCategory.FACT,
            )
            adapter.add_semantic(entry)
            assert adapter.count_semantic() == 1
            adapter.close()

    def test_add_graph_node_and_edge(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            adapter = SQLiteMemoryAdapter(str(db_path))
            adapter.connect()

            node = GraphNode(id="n1", label="Khayren", node_type="person")
            adapter.add_graph_node(node)
            assert adapter.count_graph_nodes() == 1

            edge = GraphEdge(id="e1", source_id="n1", target_id="n2", relation="works_at")
            adapter.add_graph_edge(edge)
            assert adapter.count_graph_edges() == 1
            adapter.close()

    def test_get_orphan_nodes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            adapter = SQLiteMemoryAdapter(str(db_path))
            adapter.connect()

            adapter.add_graph_node(
                GraphNode(id="n1", label="Khayren", node_type="person", mention_count=1)
            )
            adapter.add_graph_node(
                GraphNode(id="n2", label="Voidlight", node_type="org", mention_count=5)
            )

            orphans = adapter.get_orphan_nodes(min_mentions=3)
            assert "n1" in orphans
            assert "n2" not in orphans
            adapter.close()

    def test_concurrent_writes_do_not_corrupt_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            adapter = SQLiteMemoryAdapter(str(db_path), max_connections=4)
            adapter.connect()

            errors = []

            def writer(start: int):
                try:
                    for i in range(start, start + 10):
                        adapter.add_episodic(
                            EpisodicEntry(
                                id=f"t{i}",
                                session_id="s1",
                                role=MessageRole.USER,
                                content=f"Memory {i}",
                                timestamp=f"2026-01-01T00:00:{i:02d}",
                            )
                        )
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=writer, args=(i * 10,)) for i in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert not errors
            assert adapter.count_episodic() == 40
            adapter.close()

    def test_close_drains_pool(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            adapter = SQLiteMemoryAdapter(str(db_path), max_connections=2)
            adapter.connect()

            adapter.add_episodic(
                EpisodicEntry(
                    id="1",
                    session_id="s1",
                    role=MessageRole.USER,
                    content="x",
                    timestamp="2026-01-01T00:00:00",
                )
            )
            adapter.close()
            assert adapter._pool.empty()
            assert adapter.conn is None
