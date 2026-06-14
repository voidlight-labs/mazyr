from pathlib import Path

from mazyr.domain.tool import ToolResult


def _is_under_whitelist(path: Path, whitelist: list[str]) -> bool:
    """Check whether a resolved path stays within any whitelisted base directory."""
    for raw in whitelist:
        base = Path(raw).expanduser().resolve()
        try:
            if path.is_relative_to(base):
                return True
        except ValueError:
            continue
    return False


def handle(params: dict, context: dict) -> ToolResult:
    file_path = params.get("path", "")
    if not file_path:
        return ToolResult(success=False, error="path is required")

    tool_config = context.get("tool_config")
    if not tool_config:
        return ToolResult(success=False, error="Tool config not available")

    # Reject obvious traversal attempts before resolution.
    if ".." in file_path or "~" in file_path:
        return ToolResult(
            success=False,
            error="path must not contain parent references ('..') or home expansion ('~')",
        )

    whitelist = tool_config.read_file_whitelist
    if not whitelist:
        return ToolResult(success=False, error="No read_file whitelist configured")

    path = Path(file_path).expanduser().resolve()
    if not _is_under_whitelist(path, whitelist):
        return ToolResult(
            success=False,
            error=f"Path not in whitelist. Allowed: {', '.join(whitelist)}",
        )

    if not path.exists():
        return ToolResult(success=False, error=f"File not found: {file_path}")
    if not path.is_file():
        return ToolResult(success=False, error=f"Not a file: {file_path}")

    try:
        content = path.read_text(encoding="utf-8")
        return ToolResult(success=True, data=content)
    except PermissionError as e:
        return ToolResult(success=False, error=f"Permission denied: {e}")
    except OSError as e:
        return ToolResult(success=False, error=f"Filesystem error: {e}")
