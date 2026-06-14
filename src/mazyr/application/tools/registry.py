import importlib

from mazyr.application.tool_registry import ToolRegistry
from mazyr.application.tools.params import (
    AddMemoryParams,
    ApiCallExternalParams,
    ExecuteShellParams,
    FileWriteParams,
    ListDirectoryParams,
    MemoryAdminParams,
    ReadFileParams,
    RunCodeParams,
    SearchMemoryParams,
    SetActiveSkillParams,
)
from mazyr.domain.tool import ToolDefinition, ToolTier


def _handler(mod_path: str):
    mod = importlib.import_module(mod_path)
    return mod.handle


def register_all(registry: ToolRegistry):
    tools: list[tuple[ToolDefinition, str]] = [
        (
            ToolDefinition(
                name="list_directory",
                description="List files and directories at a given path",
                tier=ToolTier.SAFE,
                param_schema={"path": "string"},
                param_model=ListDirectoryParams,
                handler="list_directory",
            ),
            "mazyr.application.tools.list_directory",
        ),
        (
            ToolDefinition(
                name="search_memory",
                description="Search memory (Qdrant + SQLite) for relevant context",
                tier=ToolTier.SAFE,
                param_schema={"query": "string", "limit": "integer"},
                param_model=SearchMemoryParams,
                handler="memory_search",
            ),
            "mazyr.application.tools.memory_search",
        ),
        (
            ToolDefinition(
                name="get_status",
                description="Get instance status, health, and configuration",
                tier=ToolTier.SAFE,
                handler="get_status",
            ),
            "mazyr.application.tools.get_status",
        ),
        (
            ToolDefinition(
                name="read_file",
                description="Read a file from the filesystem (path whitelist enforced)",
                tier=ToolTier.SAFE,
                param_schema={"path": "string"},
                param_model=ReadFileParams,
                handler="read_file",
            ),
            "mazyr.application.tools.read_file",
        ),
        (
            ToolDefinition(
                name="add_memory",
                description="Store a new entry in memory",
                tier=ToolTier.SEMI_SAFE,
                param_schema={
                    "content": "string",
                },
                param_model=AddMemoryParams,
                handler="memory_add",
            ),
            "mazyr.application.tools.memory_add",
        ),
        (
            ToolDefinition(
                name="run_code",
                description="Execute code in a subprocess with timeout",
                tier=ToolTier.SEMI_SAFE,
                param_schema={
                    "code": "string",
                    "language": "string",
                    "timeout": "integer",
                },
                param_model=RunCodeParams,
                handler="run_code",
            ),
            "mazyr.application.tools.run_code",
        ),
        (
            ToolDefinition(
                name="file_write",
                description="Write or overwrite a file on the filesystem",
                tier=ToolTier.DANGEROUS,
                param_schema={"path": "string", "content": "string"},
                param_model=FileWriteParams,
                handler="file_write",
            ),
            "mazyr.application.tools.file_write",
        ),
        (
            ToolDefinition(
                name="execute_shell",
                description="Execute a shell command on the system",
                tier=ToolTier.DANGEROUS,
                param_schema={"command": "string", "timeout": "integer"},
                param_model=ExecuteShellParams,
                handler="execute_shell",
            ),
            "mazyr.application.tools.execute_shell",
        ),
        (
            ToolDefinition(
                name="api_call_external",
                description="Make an HTTP request to an external API",
                tier=ToolTier.DANGEROUS,
                param_schema={
                    "url": "string",
                    "method": "string",
                    "headers": "object",
                    "body": "any",
                },
                param_model=ApiCallExternalParams,
                handler="api_call",
            ),
            "mazyr.application.tools.api_call",
        ),
        (
            ToolDefinition(
                name="memory_admin",
                description="Administer memory: count, type distribution, recent entries, list_all",
                tier=ToolTier.DANGEROUS,
                param_schema={"action": "string", "limit": "integer"},
                param_model=MemoryAdminParams,
                handler="memory_admin",
            ),
            "mazyr.application.tools.memory_admin",
        ),
        (
            ToolDefinition(
                name="list_skills",
                description="List available procedural skills and the active skill",
                tier=ToolTier.SAFE,
                handler="list_skills",
            ),
            "mazyr.application.tools.list_skills",
        ),
        (
            ToolDefinition(
                name="set_active_skill",
                description="Activate a skill by name, or deactivate with empty name",
                tier=ToolTier.SEMI_SAFE,
                param_schema={"name": "string"},
                param_model=SetActiveSkillParams,
                handler="set_active_skill",
            ),
            "mazyr.application.tools.set_active_skill",
        ),
    ]

    for td, mod_path in tools:
        registry.register(td, _handler(mod_path))
