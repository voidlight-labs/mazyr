from unittest.mock import Mock

from mazyr.application.memory_worker import MaintenanceWorker


class TestMaintenanceWorker:
    def test_start_stop(self):
        memory = Mock()
        memory.episodic.get_unconsolidated.return_value = []
        memory.semantic.get_stale.return_value = []
        memory.sqlite.get_orphan_nodes.return_value = []
        memory.working.get_all.return_value = []
        worker = MaintenanceWorker(memory, Mock())
        worker.start()
        assert worker._thread is not None
        assert worker._thread.is_alive()
        worker.stop()
        assert worker._thread is None

    def test_double_start_noop(self):
        memory = Mock()
        memory.episodic.get_unconsolidated.return_value = []
        memory.semantic.get_stale.return_value = []
        memory.sqlite.get_orphan_nodes.return_value = []
        memory.working.get_all.return_value = []
        worker = MaintenanceWorker(memory, Mock())
        worker.start()
        thread_id = id(worker._thread)
        worker.start()
        assert id(worker._thread) == thread_id
        worker.stop()
