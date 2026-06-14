from mazyr.domain.memory_episodic import EpisodicEntry
from mazyr.infrastructure.memory_sqlite import SQLiteMemoryAdapter


class EpisodicStore:
    def __init__(self, sqlite: SQLiteMemoryAdapter):
        self._sqlite = sqlite

    def add(self, entry: EpisodicEntry):
        self.add_batch([entry])

    def add_batch(self, entries: list[EpisodicEntry]):
        self._sqlite.add_episodic_batch(entries)

    def get_recent(self, limit: int = 100) -> list[EpisodicEntry]:
        return self._sqlite.get_recent_episodic(limit)

    def get_unconsolidated(self, since: str = "24h") -> list[EpisodicEntry]:
        return self._sqlite.get_unconsolidated_episodic(since)

    def mark_consolidated(self, ids: list[str]):
        self._sqlite.mark_consolidated(ids)

    def get_older_than(self, days: int) -> list[EpisodicEntry]:
        return self._sqlite.get_older_than(days)

    def count(self) -> int:
        return self._sqlite.count_episodic()
