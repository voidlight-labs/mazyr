from mazyr.application.memory_extraction import MemoryExtractionEngine
from mazyr.application.memory_system import MemorySystem
from mazyr.infrastructure.logger import get_logger

log = get_logger("memory.consolidation")


class ConsolidationEngine:
    def __init__(self, memory: MemorySystem, llm_router, batch_size: int = 10):
        self.memory = memory
        self.extractor = MemoryExtractionEngine(llm_router)
        self.batch_size = batch_size

    def process(self, since: str = "24h") -> int:
        """Process unconsolidated episodic entries. Returns count processed."""
        entries = self.memory.episodic.get_unconsolidated(since=since)
        if not entries:
            return 0

        total = 0
        for i in range(0, len(entries), self.batch_size):
            batch = entries[i : i + self.batch_size]
            count = self._process_batch(batch)
            total += count

        return total

    def _process_batch(self, entries: list) -> int:
        """Extract and store from a batch of entries. Returns count successfully processed."""
        processed_ids = [entry.id for entry in entries]
        try:
            result = self.extractor.extract_from_batch(entries)
        except Exception as e:
            log.warning("Batch consolidation extraction failed: %s", e)
            return 0

        try:
            if result.facts:
                self.memory.semantic.add_batch(result.facts)
            if result.entities or result.relations:
                self.memory.graph.add_batch(result.entities, result.relations)
            log.debug(
                "Consolidated batch: %d facts, %d entities, %d relations",
                len(result.facts),
                len(result.entities),
                len(result.relations),
            )
        except Exception as e:
            log.warning("Batch consolidation storage failed: %s", e)
            return 0

        if processed_ids:
            self.memory.episodic.mark_consolidated(processed_ids)

        return len(processed_ids)
