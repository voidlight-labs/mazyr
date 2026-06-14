from pathlib import Path

from mazyr.domain.tool import ToolResult


def _resolve_base_dir(context: dict) -> Path:
    """Determine the canonical base directory for file_write operations."""
    tool_config = context.get("tool_config")
    base_str = getattr(tool_config, "file_write_base_dir", None) if tool_config else None
    if not base_str:
        base_str = "~/.mazyr/workspace"
    return Path(base_str).expanduser().resolve()


def handle(params: dict, context: dict) -> ToolResult:
    file_path = params.get("path", "")
    content = params.get("content", "")

    if not file_path:
        return ToolResult(success=False, error="path is required")
    if content is None:
        return ToolResult(success=False, error="content is required")

    # Reject obvious traversal attempts before resolution.
    if ".." in file_path or "~" in file_path:
        return ToolResult(
            success=False,
            error="path must not contain parent references ('..') or home expansion ('~')",
        )

    base_dir = _resolve_base_dir(context)
    try:
        base_dir.mkdir(parents=True, exist_ok=True)
        target = (base_dir / file_path).resolve()
        # Ensure the resolved path is still under the allowed base.
        if not target.is_relative_to(base_dir):
            return ToolResult(
                success=False,
                error=f"path escapes allowed base directory: {base_dir}",
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return ToolResult(success=True, data=f"Written {len(content)} bytes to {target}")
    except PermissionError as e:
        return ToolResult(success=False, error=f"Permission denied: {e}")
    except OSError as e:
        return ToolResult(success=False, error=f"Filesystem error: {e}")
