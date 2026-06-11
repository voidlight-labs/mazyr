from mazyr.domain.memory_entry import MemoryEntry, MemoryQuery


class MemoryRouter:
    """Routes durable memory to SQLite and semantic retrieval to Qdrant."""

    def __init__(self, durable_memory, semantic_memory=None):
        self.durable = durable_memory
        self.semantic = semantic_memory

    def connect(self):
        self.durable.connect()
        if self.semantic:
            self.semantic.connect()

    def add(self, entry: MemoryEntry):
        self.durable.add(entry)
        if self.semantic:
            self.semantic.add(entry)

    def search(self, query: MemoryQuery) -> list[MemoryEntry]:
        if self.semantic:
            return self.semantic.search(query)
        return []

    def close(self):
        if hasattr(self.durable, "close"):
            self.durable.close()
        if self.semantic and hasattr(self.semantic, "close"):
            self.semantic.close()
