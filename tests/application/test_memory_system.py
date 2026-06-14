import tempfile
from pathlib import Path

from mazyr.application.memory_system import MemorySystem
from mazyr.domain.memory_episodic import EpisodicEntry, MessageRole
from mazyr.infrastructure.memory_sqlite import SQLiteMemoryAdapter


class TestMemorySystem:
    def test_add_episodic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            sqlite = SQLiteMemoryAdapter(str(db_path))
            ms = MemorySystem(sqlite)
            ms.connect()

            entry = EpisodicEntry(
                id="1",
                session_id="s1",
                role=MessageRole.USER,
                content="Hello",
                timestamp="2026-01-01T00:00:00",
            )
            ms.add(entry)

            counts = ms.count()
            assert counts["episodic"] == 1

    def test_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            ms = MemorySystem(SQLiteMemoryAdapter(str(db_path)))
            ms.connect()

            counts = ms.count()
            assert isinstance(counts, dict)
            assert "episodic" in counts
            assert "semantic" in counts
