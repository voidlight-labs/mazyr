# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
