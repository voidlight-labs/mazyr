from mazyr.domain.tool import ToolResult


def handle(params: dict, context: dict) -> ToolResult:
    memory = context.get("memory")
    if not memory:
        return ToolResult(success=False, error="Memory not available")

    action = params.get("action", "")

    if action == "count":
        try:
            counts = memory.count()
            return ToolResult(success=True, data=str(counts))
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    if action == "recent":
        limit = params.get("limit", 10)
        try:
            entries = memory.episodic.get_recent(limit=limit)
            data = "\n".join(f"[{e.role.value}] {e.content[:100]}" for e in entries)
            return ToolResult(success=True, data=data or "(no entries)")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    if action == "list_all":
        limit = params.get("limit", 200)
        try:
            entries = memory.episodic.get_recent(limit=limit)
            if not entries:
                return ToolResult(success=True, data="(no entries)")
            lines = []
            for e in entries:
                lines.append(f"[{e.role.value}] {e.content[:80]}...")
            return ToolResult(success=True, data="\n".join(lines))
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    return ToolResult(success=False, error=f"Unknown action: {action}")
