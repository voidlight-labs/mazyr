import pytest
import tempfile
from pathlib import Path

from mazyr.infrastructure.memory_sqlite import SQLiteMemoryAdapter
from mazyr.domain.memory_entry import MemoryEntry, MemoryType


class TestSQLiteMemoryAdapter:
    def test_connect_and_add(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            adapter = SQLiteMemoryAdapter(str(db_path))
            adapter.connect()

            entry = MemoryEntry(
                id="1",
                type=MemoryType.EPISODIC,
                content="Test memory",
                category="test",
                source="test",
                timestamp="2026-01-01T00:00:00",
            )
            adapter.add(entry)

            assert adapter.count() == 1
            adapter.close()

    def test_get_recent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            adapter = SQLiteMemoryAdapter(str(db_path))
            adapter.connect()

            for i in range(3):
                adapter.add(
                    MemoryEntry(
                        id=str(i),
                        type=MemoryType.EPISODIC,
                        content=f"Memory {i}",
                        category="test",
                        source="test",
                        timestamp=f"2026-01-01T00:00:0{i}",
                    )
                )

            recent = adapter.get_recent(2)
            assert len(recent) == 2
            adapter.close()
