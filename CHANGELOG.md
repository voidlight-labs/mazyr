# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Async Tier-3 approval flow** — `ApprovalManager` with notification-based async approval, `MODIFY_PARAMS` support, and auto-deny on timeout (default 10 minutes). Includes `CLIApprovalNotifier` and `TelegramApprovalNotifier` stub.
- **HTTP connection pooling** — Shared `httpx.Client` / `httpx.AsyncClient` via `HTTPPool` for Cloud LLM, embeddings, Telegram, GitHub, and relay adapters.
- **Local LLM server path** — `LocalLLM` now supports calling a running `llama-server` via HTTP POST `/completion`; subprocess fallback remains.
- **Tier 5 Procedural Memory** — Formalized `ProceduralMemoryPort`, `SkillRegistry` alias as `ProceduralMemoryStore`, and `ContextAssembler` typed against the port.
- **Restored application modules** — `EventBus`, `AuditUseCase`, `SyncUseCase`, `LearnUseCase`, and `RelayClient` reintroduced from archive.
- **Event-driven wiring** — `ToolRegistry` publishes `ToolExecuted`, `ApprovalRequested`, and `ApprovalResolved` events; `ChatUseCase` publishes `MessageReceived` and `FilterTriggered`; `Bootstrap` wires the bus into audit, sync, learn, and chat paths.
- **CLI integration for restored modules**:
  - `mazyr status` now runs `AuditUseCase.health_check()`.
  - `mazyr sync` pushes memory snapshots to GitHub and/or the configured WebSocket relay.
  - `mazyr chat` supports `/learn` to inspect learned patterns.
- **Streaming tool-aware output** — `receive_stream` / `areceive_stream` now suppress natural text after the first `<tool>` tag in a tool turn, preventing duplicated answers while preserving tool execution.
- **Skill persistence** — `SkillLoader.save()` and `SkillRegistry.save()` allow `LearnUseCase` to persist newly learned skills to `~/.mazyr/skills/`.
- **Tests** — Added `test_event_bus.py`, `test_audit.py`, `test_sync.py`, `test_learn.py`, `test_relay_client.py`, `test_tool_registry_events.py`, and `test_chat_events.py`. Total suite now **266 tests passing**.

### Changed

- **System prompt** — Clarified turn rules so the model uses tools for capability/status questions while avoiding repeated full answers across tool turns.
- **MemorySystem** — Exposes the underlying SQLite adapter via a `sqlite` property so `ToolRegistry` can write audit logs.

### Fixed

- **Audit error** — `AttributeError: 'MemorySystem' object has no attribute 'add_tool_audit_entry'` resolved by routing `ToolRegistry` to the SQLite adapter.
- **Duplicate chat output** — Fixed duplicated natural text before/after tool tags in streaming chat.
- **`websockets` v16 compatibility** — `RelayClient` imports `connect` and `ConnectionClosed` correctly for the installed websockets version.

- **MTS-08: Tool Registry** — Centralized tool execution system with tier-based routing, approval flow, audit logging, and constitution validation.
  - **Domain models** — `ToolTier`, `ToolDefinition`, `ToolCall`, `ToolResult`, `ToolAuditEntry`, `ToolRegistryConfig` with Pydantic validation.
  - **Tool Parser** — Extracts `<tool name="...">{...}</tool>` tags from LLM output with retry on malformed tags.
  - **ToolRegistry** — Central execution engine: Tier 0 hard reject → Tier 1 auto → Tier 2 auto + abuse detection → Tier 3 Creator approval (blocking CLI prompt).
  - **10 built-in tools**: `search_memory` (T1), `get_status` (T1), `read_file` (T1 + path whitelist), `list_directory` (T1), `add_memory` (T2 + poison guard), `run_code` (T2 + timeout), `file_write` (T3), `execute_shell` (T3), `api_call_external` (T3 + domain whitelist), `memory_admin` (T3).
  - **Chat pipeline integration** — LLM prompt injected with tool definitions; agent loop parses and executes tool calls iteratively (up to 10 rounds), preserving natural text across iterations for coherent multi-step responses.
  - **Audit log** — `tool_audit_log` table in SQLite with full schema per MTS-08 §6.
  - **Config** — `ToolRegistryConfig` with configurable thresholds, whitelists, and sandbox settings.
  - **Filter enhancement** — New inbound `prompt_injection` rule and outbound `data_leakage` rule.
- **Agent loop** — `ChatUseCase.receive()` now iterates up to 10 rounds, feeding tool results back to the LLM for autonomous multi-step exploration. Natural text is preserved across iterations for continuity.
- **`list_directory` tool** — Tier 1 tool to list file system contents with path whitelist support.
- **Memory `list_all` action** — New `memory_admin` action + `SQLiteMemoryAdapter.get_all_metadata()` to enumerate all entries with type, category, and summary.
- **File-based logging** — `infrastructure/logger.py` writes rotating logs to `~/.mazyr/logs/mazyr.log` (10 MB, 3 backups).
- **Model-compatible LLM config** — gpt-5.x and o-series models automatically omit unsupported `temperature` parameter and use `max_completion_tokens`.
- **`mazyr qdrant enable`** — New subcommand to start Qdrant container and enable semantic memory in config post-init; prompts for missing embedding config.
- **Pydantic v2 Validation** — All domain models (`Identity`, `Mission`, `MemoryEntry`, `FilterRule`, `InstanceConfig`) now use Pydantic for strict schema validation as per MTS-05.
- **Memory Metadata Support** — `QdrantMemoryAdapter` now correctly handles and persists the `metadata` field.
- **Modern CLI** — Single `mazyr` entry point with subcommands (`init`, `boot`, `status`, `stop`, `chat`, `sync`).
- **Global flags** — `mazyr --version` and `mazyr --help`.
- **`~/.mazyr` default directory** — Instance data lives in home directory following Unix conventions.
- **Docker Compose auto-setup** — `mazyr init` auto-detects Docker and starts Qdrant container.
- **`DockerComposeManager`** — Infrastructure class for managing Qdrant via `docker compose`.
- **`InstanceConfig` domain model** — Runtime configuration with validation (no `.env` files).
- **Config persistence** — All config stored in `~/.mazyr/config.yaml` via interactive `mazyr init`.
- **LLM config prompts** — API key, base URL, model, inference preference collected during init.
- **Integration prompts** — Telegram bot token, GitHub token/repo, WebSocket relay endpoint.
- **Qdrant health check** — Wait-for-healthy logic with timeout during boot.
- **Graceful fallback** — SQLite-only mode when Docker is unavailable.
- **Rich CLI output** — Banner, grouped prompts, colored status panels.
- **Tests** — `test_instance_config.py`, `test_docker_manager.py`, `test_config_loader` expanded.

### Changed

- **Domain Entities** — Migrated from standard `dataclasses` to `pydantic.BaseModel` for improved integrity.
- **CLI commands** — `mazyr-init` → `mazyr init`, `mazyr-boot` → `mazyr boot`, etc.
- **Entry points** — Consolidated from 6 scripts to single `mazyr` script in `pyproject.toml`.
- **Default base directory** — Changed from `./.mazyr` to `~/.mazyr`.
- **Config loading** — `ConfigLoader` now loads `InstanceConfig` from YAML.
- **Bootstrap sequence** — Added config validation step (`_validate_config`).
- **Filesystem adapter** — `write_config()` method for YAML persistence.
- **SQLite path** — Fixed to `~/.mazyr/memory/mazyr.db` (no longer prompted).
- **Qdrant connection** — Fixed to `localhost:6333` (no longer prompted).

### Removed

- **`.env.example`** — No longer needed; all config via interactive init.
- **`python-dotenv` dependency** — Removed from `pyproject.toml`.
- **SQLite path prompt** — Now auto-managed.
- **Qdrant host/port prompts** — Now auto-managed via Docker Compose.
