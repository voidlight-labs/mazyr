"""Memory snapshot sync use case."""

from datetime import datetime
from typing import Any

from mazyr.domain.ports import MemorySystemPort


class SyncUseCase:
    """Sync memory snapshots to GitHub and optional cloud relay."""

    def __init__(
        self,
        memory: MemorySystemPort,
        github_adapter: Any | None = None,
        relay_client: Any | None = None,
    ):
        self.memory = memory
        self.github = github_adapter
        self.relay = relay_client

    def snapshot_to_github(self, instance_name: str) -> dict:
        """Create an immutable snapshot of memory and push to GitHub."""
        snapshot = {
            "instance": instance_name,
            "timestamp": datetime.now().isoformat(),
            "memory_summary": self.memory.summary() if hasattr(self.memory, "summary") else {},
        }
        if self.github:
            return self.github.push_snapshot(snapshot)
        return {**snapshot, "status": "no_github_adapter"}

    async def sync_to_relay(self) -> bool:
        """Sync current state to cloud relay."""
        state = {
            "status": "active",
            "last_sync": datetime.now().isoformat(),
            "memory_count": self.memory.count() if hasattr(self.memory, "count") else 0,
        }
        if self.relay and hasattr(self.relay, "send"):
            await self.relay.send(state)
            return True
        return False
