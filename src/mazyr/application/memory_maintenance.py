from datetime import datetime

from mazyr.application.memory_system import MemorySystem
from mazyr.infrastructure.logger import get_logger

log = get_logger("memory.maintenance")

STALE_IMPORTANCE_THRESHOLD = 0.15
STALE_DAYS = 14


class MaintenanceEngine:
    def __init__(self, memory: MemorySystem):
        self.memory = memory

    def run_decay(self) -> int:
        """Apply decay to all semantic entries. Returns count decayed."""
        stale = self.memory.semantic.get_stale(threshold_days=1)
        count = 0
        now = datetime.now()
        for entry in stale:
            try:
                last = datetime.fromisoformat(entry.last_accessed)
                days = max(1, (now - last).days)
                new_score = entry.apply_decay(days)
                self.memory.semantic.update_importance(entry.id, new_score)
                count += 1
            except Exception as e:
                log.warning("Decay failed for %s: %s", entry.id, e)
        if count:
            log.info("Decay applied to %d entries", count)
        return count

    def run_prune(self) -> dict:
        """Remove low-importance semantic entries and orphan graph nodes. Returns counts pruned."""
        result = {"semantic": 0, "graph_nodes": 0}

        # Prune stale semantic entries below importance threshold
        stale = self.memory.semantic.get_stale(threshold_days=STALE_DAYS)
        prune_ids = [e.id for e in stale if e.importance_score < STALE_IMPORTANCE_THRESHOLD]
        result["semantic"] = len(prune_ids)

        # Prune orphan graph nodes (no edges, low mentions)
        orphan_ids = self.memory.sqlite.get_orphan_nodes(min_mentions=3)
        result["graph_nodes"] = len(orphan_ids)

        if prune_ids:
            try:
                self.memory.sqlite._prune_semantic(prune_ids)
            except Exception as e:
                log.warning("Semantic prune failed: %s", e)
                result["semantic"] = 0

        if orphan_ids:
            try:
                self.memory.sqlite.delete_nodes(orphan_ids)
            except Exception as e:
                log.warning("Graph node prune failed: %s", e)
                result["graph_nodes"] = 0

        if any(result.values()):
            log.info("Prune: %s", result)
        return result

    def run_expire(self) -> int:
        """Clear expired working memory entries. Returns count expired."""
        before = len(self.memory.working.get_all())
        self.memory.working.clear_expired()
        after = len(self.memory.working.get_all())
        count = before - after
        if count:
            log.info("Expired %d working memory entries", count)
        return count

    def run_all(self) -> dict:
        """Run all maintenance tasks. Returns summary dict."""
        return {
            "decay": self.run_decay(),
            "prune": self.run_prune(),
            "expire": self.run_expire(),
        }
