from datetime import datetime

from mazyr.domain.memory_episodic import EpisodicEntry, MessageRole
from mazyr.domain.memory_semantic import MemoryCategory, SemanticEntry
from mazyr.domain.tool import ToolResult


def handle(params: dict, context: dict) -> ToolResult:
    memory = context.get("memory")
    if not memory:
        return ToolResult(success=False, error="Memory not available")

    content = params.get("content", "")
    if not content:
        return ToolResult(success=False, error="content is required")

    category_str = params.get("category", "fact")
    memory_type_str = params.get("type", "episodic")

    try:
        if memory_type_str.lower() == "semantic":
            cat = (
                MemoryCategory(category_str.lower())
                if category_str in MemoryCategory._value2member_
                else MemoryCategory.FACT
            )
            entry = SemanticEntry(
                id=f"tool_{datetime.now().timestamp()}",
                content=content,
                category=cat,
            )
            dedup = context.get("deduplicator")
            if dedup:
                result = dedup.deduplicate(entry)
                if result.action == "merged":
                    return ToolResult(
                        success=True, data=f"Memory merged with existing ({result.canonical_id})"
                    )
            memory.add(entry)
        else:
            entry = EpisodicEntry(
                id=f"tool_{datetime.now().timestamp()}",
                session_id=context.get("session_id", "unknown"),
                role=MessageRole.SYSTEM,
                content=content,
            )
            memory.add(entry)
        return ToolResult(success=True, data=f"Memory stored ({memory_type_str}/{category_str})")
    except Exception as e:
        return ToolResult(success=False, error=str(e))
