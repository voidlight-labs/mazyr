import threading
import time
from typing import Optional

from mazyr.application.memory_consolidation import ConsolidationEngine
from mazyr.application.memory_maintenance import MaintenanceEngine
from mazyr.application.memory_system import MemorySystem
from mazyr.infrastructure.logger import get_logger

log = get_logger("memory.worker")

CONSOLIDATE_INTERVAL = 30  # seconds
DECAY_INTERVAL = 3600  # 1 hour
EXPIRE_INTERVAL = 300  # 5 minutes


class MaintenanceWorker:
    def __init__(self, memory: MemorySystem, llm_router, extraction_queue=None):
        self.memory = memory
        self.consolidation = ConsolidationEngine(memory, llm_router)
        self.maintenance = MaintenanceEngine(memory)
        self._extraction_queue = extraction_queue
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="memory-worker")
        self._thread.start()
        log.info("Maintenance worker started")

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        log.info("Maintenance worker stopped")

    def _run(self):
        last_decay = time.monotonic()
        last_expire = time.monotonic()
        last_consolidate = time.monotonic()

        while not self._stop_event.is_set():
            now = time.monotonic()
            try:
                if now - last_consolidate >= CONSOLIDATE_INTERVAL:
                    self._tick_consolidate()
                    last_consolidate = now

                if now - last_expire >= EXPIRE_INTERVAL:
                    self._tick_expire()
                    last_expire = now

                if now - last_decay >= DECAY_INTERVAL:
                    self._tick_decay_prune()
                    last_decay = now
            except Exception as e:
                log.error("Worker error: %s", e)

            self._stop_event.wait(timeout=10)

    def _tick_consolidate(self):
        count = self.consolidation.process()
        if count:
            log.info("Consolidated %d entries", count)

    def _tick_expire(self):
        count = self.maintenance.run_expire()
        if count:
            log.debug("Expired %d working entries", count)

    def _tick_decay_prune(self):
        decayed = self.maintenance.run_decay()
        pruned = self.maintenance.run_prune()
        total = decayed + sum(pruned.values())
        if total:
            log.info("Decay: %d entries, Prune: %s", decayed, pruned)
