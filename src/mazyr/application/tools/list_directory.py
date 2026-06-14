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
    dir_path = params.get("path", ".")
    if not dir_path:
        return ToolResult(success=False, error="path is required")

    # Reject obvious traversal attempts before resolution.
    if ".." in dir_path or "~" in dir_path:
        return ToolResult(
            success=False,
            error="path must not contain parent references ('..') or home expansion ('~')",
        )

    tool_config = context.get("tool_config")
    if tool_config:
        whitelist = tool_config.read_file_whitelist
        if whitelist:
            path = Path(dir_path).expanduser().resolve()
            if not _is_under_whitelist(path, whitelist):
                return ToolResult(
                    success=False,
                    error=f"Path not in whitelist. Allowed: {', '.join(whitelist)}",
                )
    else:
        # When no tool config is available, default to the current working directory
        # and require the resolved path to remain under it.
        cwd = Path.cwd().resolve()
        path = (cwd / dir_path).resolve()
        if not path.is_relative_to(cwd):
            return ToolResult(
                success=False,
                error="path escapes current working directory",
            )

    path = Path(dir_path).expanduser().resolve()
    if not path.exists():
        return ToolResult(success=False, error=f"Path not found: {dir_path}")
    if not path.is_dir():
        return ToolResult(success=False, error=f"Not a directory: {dir_path}")

    try:
        entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        lines = []
        for entry in entries:
            suffix = "/" if entry.is_dir() else ""
            lines.append(f"{entry.name}{suffix}")
        data = "\n".join(lines) if lines else "(empty directory)"
        return ToolResult(success=True, data=data)
    except PermissionError as e:
        return ToolResult(success=False, error=f"Permission denied: {e}")
    except OSError as e:
        return ToolResult(success=False, error=f"Filesystem error: {e}")
