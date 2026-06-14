import tempfile
from pathlib import Path

from mazyr.application.tools import file_write, list_directory, read_file
from mazyr.application.tools.execute_shell import handle as execute_shell
from mazyr.domain.tool_config import ToolRegistryConfig


class TestFileWriteSecurity:
    def test_rejects_parent_directory_traversal(self):
        ctx = {"tool_config": ToolRegistryConfig(file_write_base_dir="/tmp/mazyr_test")}
        result = file_write.handle({"path": "../escape.txt", "content": "x"}, ctx)
        assert result.success is False
        assert "parent references" in result.error

    def test_rejects_absolute_path_outside_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = {"tool_config": ToolRegistryConfig(file_write_base_dir=tmp)}
            result = file_write.handle({"path": "/etc/passwd", "content": "x"}, ctx)
            assert result.success is False
            assert "escapes" in result.error

    def test_allows_write_inside_base_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = {"tool_config": ToolRegistryConfig(file_write_base_dir=tmp)}
            result = file_write.handle({"path": "notes.txt", "content": "hello"}, ctx)
            assert result.success is True
            assert (Path(tmp) / "notes.txt").read_text() == "hello"


class TestReadFileSecurity:
    def test_rejects_traversal_bypass(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            allowed = tmp / "allowed"
            allowed.mkdir()
            secret = tmp / "secret.txt"
            secret.write_text("secret")
            ctx = {"tool_config": ToolRegistryConfig(read_file_whitelist=[str(allowed)])}
            result = read_file.handle({"path": str(allowed / "../secret.txt")}, ctx)
            assert result.success is False

    def test_allows_read_within_whitelist(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            allowed = tmp / "allowed"
            allowed.mkdir()
            (allowed / "notes.txt").write_text("hello")
            ctx = {"tool_config": ToolRegistryConfig(read_file_whitelist=[str(allowed)])}
            result = read_file.handle({"path": str(allowed / "notes.txt")}, ctx)
            assert result.success is True
            assert result.data == "hello"


class TestListDirectorySecurity:
    def test_rejects_traversal_bypass(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            allowed = tmp / "allowed"
            allowed.mkdir()
            ctx = {"tool_config": ToolRegistryConfig(read_file_whitelist=[str(allowed)])}
            result = list_directory.handle({"path": str(allowed / "..")}, ctx)
            assert result.success is False


class TestExecuteShellSecurity:
    def test_uses_shell_false_no_metacharacters(self):
        # With shell=False and shlex.split, a ';' becomes a literal argument
        # to the first command rather than a shell separator.
        result = execute_shell({"command": "echo hello ; echo world"}, {})
        assert result.success is True
        # shell=True would have produced two lines: "hello" then "world".
        # shell=False produces one line because the second echo is an argument.
        assert "hello\nworld" not in result.data
        assert "hello ; echo world" in result.data

    def test_rejects_empty_command(self):
        result = execute_shell({"command": ""}, {})
        assert result.success is False

    def test_timeout_capped_by_config(self):
        tool_config = ToolRegistryConfig(sandbox={"run_code_timeout_seconds": 1})
        ctx = {"tool_config": tool_config}
        result = execute_shell({"command": "sleep 5", "timeout": 10}, ctx)
        assert result.success is False
        assert "timed out" in result.error.lower()
