from mazyr.domain.memory_entry import MemoryQuery
from mazyr.domain.tool import ToolResult


def handle(params: dict, context: dict) -> ToolResult:
    memory = context.get("memory")
    if not memory:
        return ToolResult(success=False, error="Memory not available")

    query = params.get("query", "")
    limit = params.get("limit", 5)
    try:
        memory_query = MemoryQuery(query=query, limit=limit)
        entries = memory.search(memory_query)
        data = "\n".join(f"[{e.category.value}] {e.content}" for e in entries)
        return ToolResult(success=True, data=data or "(no results)")
    except Exception as e:
        return ToolResult(success=False, error=str(e))
