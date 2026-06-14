import os
import subprocess
import tempfile
from pathlib import Path

from mazyr.domain.tool import ToolResult


def handle(params: dict, context: dict) -> ToolResult:
    code = params.get("code", "")
    if not code:
        return ToolResult(success=False, error="code is required")

    language = params.get("language", "python")

    # Cap timeout to the configured sandbox maximum.
    tool_config = context.get("tool_config")
    max_timeout = getattr(tool_config, "sandbox", None)
    max_timeout = getattr(max_timeout, "run_code_timeout_seconds", 30) if max_timeout else 30
    timeout = min(params.get("timeout", 30), max_timeout)
    if timeout < 1:
        return ToolResult(success=False, error="timeout must be at least 1 second")

    # Map language to interpreter
    interpreters = {
        "python": ("python3", ".py"),
        "python3": ("python3", ".py"),
        "bash": ("bash", ".sh"),
        "sh": ("sh", ".sh"),
        "node": ("node", ".js"),
    }

    entry = interpreters.get(language)
    if not entry:
        return ToolResult(success=False, error=f"Unsupported language: {language}")

    interpreter, ext = entry

    sandbox_dir = Path(tempfile.gettempdir()) / "mazyr_sandbox"
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    # Restrict the sandbox directory to the owner only.
    os.chmod(sandbox_dir, 0o700)

    fd, script_path_str = tempfile.mkstemp(
        dir=str(sandbox_dir),
        suffix=ext,
        prefix="mazyr_script_",
    )
    script_path = Path(script_path_str)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(code)

        result = subprocess.run(
            [interpreter, str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(sandbox_dir),
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
        return ToolResult(success=False, error=f"Execution timed out after {timeout}s")
    except FileNotFoundError:
        return ToolResult(success=False, error=f"Interpreter not found: {interpreter}")
    except PermissionError as e:
        return ToolResult(success=False, error=f"Permission denied: {e}")
    finally:
        try:
            script_path.unlink(missing_ok=True)
        except OSError:
            pass
