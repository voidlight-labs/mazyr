from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class WorkingMemoryEntry:
    key: str
    value: Any
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    ttl_seconds: int = 1800
    access_count: int = 0

    def touch(self):
        self.access_count += 1
        self.created_at = datetime.now().isoformat()
