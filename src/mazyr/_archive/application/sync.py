class SyncUseCase:
    """Sync memory snapshot to GitHub and cloud relay."""

    def __init__(self, memory, github_adapter, relay_client):
        self.memory = memory
        self.github = github_adapter
        self.relay = relay_client

    def snapshot_to_github(self, instance_name: str) -> dict:
        """Create immutable snapshot of memory and push to GitHub."""
        snapshot = {
            "instance": instance_name,
            "timestamp": "...",
            "memory_summary": self.memory.summary() if hasattr(self.memory, "summary") else {},
            "skills_summary": (
                self.memory.skills_summary() if hasattr(self.memory, "skills_summary") else {}
            ),
        }
        if self.github:
            return self.github.push_snapshot(snapshot)
        return {"status": "no_github_adapter"}

    def sync_to_relay(self) -> bool:
        """Sync current state to cloud relay."""
        state = {
            "status": "active",
            "last_sync": "...",
            "memory_count": self.memory.count() if hasattr(self.memory, "count") else 0,
        }
        if self.relay:
            return self.relay.update_state(state)
        return False
