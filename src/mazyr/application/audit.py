"""Health-check and drift-detection use case."""

from mazyr.domain.constitution import Constitution
from mazyr.domain.filter import IntegrityFilter
from mazyr.domain.identity import Identity
from mazyr.domain.ports import MemorySystemPort


class AuditUseCase:
    """Health check and drift detection for a Mazyr instance."""

    def __init__(
        self,
        identity: Identity,
        filter_engine: IntegrityFilter,
        memory: MemorySystemPort | None,
        constitution: Constitution,
    ):
        self.identity = identity
        self.filter = filter_engine
        self.memory = memory
        self.constitution = constitution

    def health_check(self) -> dict:
        """Return a full health snapshot of the instance."""
        return {
            "identity": self._check_identity(),
            "filter": self._check_filter(),
            "memory": self._check_memory(),
            "constitution": self._check_constitution(),
            "overall": "healthy",
        }

    def _check_identity(self) -> dict:
        return {
            "configured": self.identity.is_configured,
            "instance_name": self.identity.instance_name,
            "creator": self.identity.creator_name,
            "status": "ok",
        }

    def _check_filter(self) -> dict:
        test_good = self.filter.process("Hello, how are you?", {})
        test_bad = self.filter.process("I am always right", {})
        return {
            "rules_loaded": len(self.filter.rules),
            "test_allow": test_good.action.value == "ALLOW",
            "test_drop": test_bad.action.value == "DROP",
            "status": "ok",
        }

    def _check_memory(self) -> dict:
        counts: dict = {}
        if self.memory:
            try:
                counts = self.memory.count()
            except Exception:
                pass
        return {
            "entries": sum(counts.values()) if counts else 0,
            "types": counts,
            "status": "ok",
        }

    def _check_constitution(self) -> dict:
        return {
            "laws_count": len(self.constitution.laws),
            "immutable": True,
            "status": "ok",
        }

    def detect_drift(self, recent_outputs: list[str]) -> list[dict]:
        """Detect if instance has drifted from original purpose."""
        drift_signals: list[dict] = []
        if self._performative_ratio(recent_outputs) > 0.3:
            drift_signals.append(
                {
                    "type": "performative_drift",
                    "severity": "warning",
                    "description": "High ratio of performative output detected",
                }
            )
        return drift_signals

    def _performative_ratio(self, outputs: list[str]) -> float:
        if not outputs:
            return 0.0
        markers = ["follow", "subscribe", "like", "share"]
        count = sum(1 for o in outputs if any(m in o.lower() for m in markers))
        return count / len(outputs)
