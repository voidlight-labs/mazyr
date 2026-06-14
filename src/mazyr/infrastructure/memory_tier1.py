from datetime import datetime
from typing import Any, Optional

from mazyr.domain.memory_working import WorkingMemoryEntry


class WorkingMemoryStore:
    def __init__(self):
        self._store: dict[str, WorkingMemoryEntry] = {}

    def get(self, key: str) -> Optional[Any]:
        self._expire()
        entry = self._store.get(key)
        if entry is None:
            return None
        entry.touch()
        return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int = 1800):
        self._store[key] = WorkingMemoryEntry(
            key=key,
            value=value,
            ttl_seconds=ttl_seconds,
        )

    def get_all(self) -> list[WorkingMemoryEntry]:
        self._expire()
        return list(self._store.values())

    def clear_expired(self):
        now = datetime.now()
        expired = [
            k
            for k, v in self._store.items()
            if (now - datetime.fromisoformat(v.created_at)).total_seconds() > v.ttl_seconds
        ]
        for k in expired:
            del self._store[k]

    def clear(self):
        self._store.clear()

    def _expire(self):
        self.clear_expired()
