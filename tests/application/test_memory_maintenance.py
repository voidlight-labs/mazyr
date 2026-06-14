from unittest.mock import Mock

from mazyr.application.memory_maintenance import MaintenanceEngine
from mazyr.domain.memory_semantic import MemoryCategory, SemanticEntry


class TestMaintenanceEngine:
    def test_run_decay_no_stale(self):
        memory = Mock()
        memory.semantic.get_stale.return_value = []
        engine = MaintenanceEngine(memory)
        result = engine.run_decay()
        assert result == 0

    def test_run_decay_applies_decay(self):
        memory = Mock()
        entry = SemanticEntry(
            id="s1", content="test", category=MemoryCategory.FACT, importance_score=0.8
        )
        memory.semantic.get_stale.return_value = [entry]
        engine = MaintenanceEngine(memory)
        result = engine.run_decay()
        assert result == 1
        assert memory.semantic.update_importance.called

    def test_run_prune_no_stale(self):
        memory = Mock()
        memory.semantic.get_stale.return_value = []
        memory.sqlite.get_orphan_nodes.return_value = []
        engine = MaintenanceEngine(memory)
        result = engine.run_prune()
        assert result["semantic"] == 0
        assert result["graph_nodes"] == 0

    def test_run_prune_removes_low_importance(self):
        memory = Mock()
        entry = SemanticEntry(
            id="s1", content="stale", category=MemoryCategory.FACT, importance_score=0.1
        )
        memory.semantic.get_stale.return_value = [entry]
        memory.sqlite.get_orphan_nodes.return_value = []
        memory.sqlite._prune_semantic = Mock()
        engine = MaintenanceEngine(memory)
        result = engine.run_prune()
        assert result["semantic"] == 1
        assert memory.sqlite._prune_semantic.called

    def test_run_prune_orphan_nodes(self):
        memory = Mock()
        memory.semantic.get_stale.return_value = []
        memory.sqlite.get_orphan_nodes.return_value = ["n1", "n2"]
        memory.sqlite.delete_nodes = Mock()
        engine = MaintenanceEngine(memory)
        result = engine.run_prune()
        assert result["graph_nodes"] == 2
        assert memory.sqlite.delete_nodes.called

    def test_run_expire(self):
        memory = Mock()
        memory.working.get_all.side_effect = [
            [Mock(), Mock(), Mock()],  # before: 3 entries
            [],  # after: 0 entries
        ]
        engine = MaintenanceEngine(memory)
        result = engine.run_expire()
        assert result == 3

    def test_run_expire_no_entries(self):
        memory = Mock()
        memory.working.get_all.return_value = []
        engine = MaintenanceEngine(memory)
        result = engine.run_expire()
        assert result == 0

    def test_run_all(self):
        memory = Mock()
        memory.semantic.get_stale.return_value = []
        memory.sqlite.get_orphan_nodes.return_value = []
        memory.working.get_all.return_value = []
        engine = MaintenanceEngine(memory)
        result = engine.run_all()
        assert "decay" in result
        assert "prune" in result
        assert "expire" in result
