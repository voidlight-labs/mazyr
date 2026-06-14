import shlex
import subprocess

from mazyr.domain.tool import ToolResult


def handle(params: dict, context: dict) -> ToolResult:
    command = params.get("command", "")
    if not command:
        return ToolResult(success=False, error="command is required")

    # Cap timeout to the configured sandbox maximum.
    tool_config = context.get("tool_config")
    max_timeout = getattr(tool_config, "sandbox", None)
    max_timeout = getattr(max_timeout, "run_code_timeout_seconds", 30) if max_timeout else 30
    timeout = min(params.get("timeout", 30), max_timeout)
    if timeout < 1:
        return ToolResult(success=False, error="timeout must be at least 1 second")

    try:
        argv = shlex.split(command)
    except ValueError as e:
        return ToolResult(success=False, error=f"Invalid shell command: {e}")

    if not argv:
        return ToolResult(success=False, error="command parsed to empty argument list")

    try:
        result = subprocess.run(
            argv,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            if output:
                output += "\n"
            output += f"[stderr]\n{result.stderr}"

        if result.returncode != 0:
            return ToolResult(
                success=False,
                data=output,
                error=f"Exit code {result.returncode}",
            )
        return ToolResult(success=True, data=output.strip() or "(no output)")
    except subprocess.TimeoutExpired:
        return ToolResult(success=False, error=f"Command timed out after {timeout}s")
    except FileNotFoundError as e:
        return ToolResult(success=False, error=f"Command not found: {e.filename}")
    except PermissionError as e:
        return ToolResult(success=False, error=f"Permission denied: {e}")
