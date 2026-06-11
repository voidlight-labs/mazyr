import sqlite3
from pathlib import Path

from mazyr.domain.memory_entry import MemoryEntry, MemoryType
from mazyr.infrastructure.paths import MAZYR_HOME


class SQLiteMemoryAdapter:
    """Adapter for SQLite database."""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = MAZYR_HOME / "memory" / "mazyr.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = None

    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS memory_entries (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT,
                source TEXT,
                timestamp TEXT,
                confidence REAL DEFAULT 1.0,
                metadata TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_entries(type);
            CREATE INDEX IF NOT EXISTS idx_memory_category ON memory_entries(category);
            CREATE INDEX IF NOT EXISTS idx_memory_timestamp ON memory_entries(timestamp);
        """
        )
        self.conn.commit()

    def add(self, entry: MemoryEntry):
        import json
        self.conn.execute(
            """INSERT OR REPLACE INTO memory_entries
               (id, type, content, category, source, timestamp, confidence, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.id,
                entry.type.value,
                entry.content,
                entry.category,
                entry.source,
                entry.timestamp,
                entry.confidence,
                json.dumps(entry.metadata),
            ),
        )
        self.conn.commit()

    def get_recent(self, limit: int = 100) -> list[MemoryEntry]:
        cursor = self.conn.execute(
            "SELECT * FROM memory_entries ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def count(self) -> int:
        cursor = self.conn.execute("SELECT COUNT(*) FROM memory_entries")
        return cursor.fetchone()[0]

    def type_distribution(self) -> dict:
        cursor = self.conn.execute(
            "SELECT type, COUNT(*) as count FROM memory_entries GROUP BY type"
        )
        return {row["type"]: row["count"] for row in cursor.fetchall()}

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        import json
        return MemoryEntry(
            id=row["id"],
            type=MemoryType(row["type"]),
            content=row["content"],
            category=row["category"],
            source=row["source"],
            timestamp=row["timestamp"],
            confidence=row["confidence"],
            metadata=json.loads(row["metadata"] or "{}"),
        )

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
