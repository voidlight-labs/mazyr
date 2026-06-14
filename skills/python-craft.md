---
name: python-craft
description: |
  Best-practice Python coding skill tailored for Mazyr. Counteracts common
  free-tier LLM artifacts (DeepSeek V4 Flash Free style) by enforcing explicit
  validation, layered architecture, and defensive I/O.
category: coding
version: "1.0"
author: Mazyr Core
tags:
  - python
  - architecture
  - code-quality
  - free-tier-llm-defense
---

# Python Craft Skill

When generating or editing Python code for Mazyr, follow these rules. They are
ranked by severity: **MUST** rules are non-negotiable; **SHOULD** rules are the
default unless the user explicitly asks otherwise.

## 1. Defensive Error Handling (MUST)

- **Never use bare `except:` or `except Exception: pass`.** Always catch the
  specific exception(s) you can handle. If you must log and continue, log at
  the appropriate level and include context.
- **Do not swallow errors to return a string.** Convert failures into typed
  results (`ToolResult`, `ChatResult`, domain exceptions) so callers can
  distinguish failure modes.
- **Avoid catch-all `except Exception` around large blocks.** Wrap only the
  statement that can raise the expected exception.

Example:

```python
# BAD
except Exception as e:
    return str(e)

# GOOD
except PermissionError as e:
    log.warning("Cannot read %s: %s", path, e)
    return ToolResult(success=False, error=f"Permission denied: {path}")
```

## 2. Input Validation Boundaries (MUST)

- **All external inputs must be validated.** Use Pydantic v2 models at every
  boundary: CLI args, webhook payloads, tool params, config files.
- **Do not trust `dict.get()` without defaults and constraints.** Prefer typed
  Pydantic models over raw dict access.
- **Validate paths before use.** Resolve with `Path.resolve()`, check
  `is_relative_to(base)`, and reject `..`, `~`, and symlinks that escape the
  allowed root.

## 3. Layer Separation (MUST)

- Respect Mazyr's layered architecture:
  - **Domain** (`mazyr.domain`): pure entities, no infrastructure imports.
  - **Application** (`mazyr.application`): use cases, orchestration.
  - **Infrastructure** (`mazyr.infrastructure`): adapters for DB, HTTP, FS, LLM.
  - **Interfaces** (`mazyr.interfaces`): CLI, webhooks, API.
- Tool handlers in `application/tools/` may call infrastructure, but they must
  not contain business rules. Business rules live in domain or application
  services.
- Do not leak concrete adapters (e.g., `SQLiteMemoryAdapter`) into domain
  classes.

## 4. Enums and Constants (MUST)

- Replace magic strings and numbers with named constants or enums.
- Use `StrEnum` / `IntEnum` for categorical values (tool tiers, filter actions,
  message roles).
- Keep constants near their point of use or in a dedicated `constants` module;
  do not sprinkle literals through business logic.

Example:

```python
# BAD
if tier == 3:
    ...

# GOOD
if tool.tier == ToolTier.DANGEROUS:
    ...
```

## 5. Async and I/O Discipline (MUST)

- Do not call synchronous blocking code (subprocess, SQLite, HTTP, LLM) from
  `async def` handlers without `asyncio.to_thread` or an executor.
- Keep infrastructure adapters synchronous unless explicitly designed as async;
  let interface layers handle the thread boundary.
- Always close network clients, file handles, and database connections. Prefer
  context managers (`with`) over manual `.close()`.

## 6. Resilience Patterns (SHOULD)

- External calls (LLM, embedding, Telegram, Qdrant) should have retry with
  exponential backoff, timeout ceilings, and circuit-breaker semantics where
  appropriate. Use `tenacity` or a small wrapper.
- Do not retry dangerous/idempotent mutations blindly; retry only safe or
  idempotent operations.

## 7. Type Hints (MUST)

- Use concrete types everywhere. Avoid `Any` except for genuinely dynamic data
  (e.g., raw JSON from an external API).
- Annotate function signatures and return types.
- Use `Optional[T]` or `T | None` for nullable values.

## 8. Docstrings: Why, Not What (MUST)

- Docstrings must explain *why* a function exists and *what invariants* it
  maintains, not merely repeat the function name.
- Use Google-style or NumPy-style consistently.

Example:

```python
# BAD
def redact_params(params):
    """Redact params."""

# GOOD
def redact_params(params: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of tool params with sensitive values masked.

    Keys matching known secret patterns (api_key, token, password, etc.)
    are replaced with '***REDACTED***' before the audit log is written.
    """
```

## 9. Minimal, Tested Changes (MUST)

- Make the smallest change that achieves the requirement. Do not refactor
  unrelated code.
- Every behavior change needs a test. Update existing tests only when the
  public interface changes.
- Run `pytest -q` after editing and fix regressions before declaring done.

## 10. Security Defaults (MUST)

- Dangerous tools (`file_write`, `execute_shell`, `api_call_external`) must
  enforce allow-lists, timeouts, and audit logging.
- Never log secrets. Redact tokens, API keys, and passwords before writing
  audit or debug logs.
- Prefer `shell=False` for subprocess. If shell is unavoidable, sanitize with
  `shlex.quote` and limit to trusted inputs.

## 11. Free-Tier LLM Smell Checklist

Before finishing a code block, verify it does NOT contain:

- [ ] Bare `except:` / `except Exception: pass`
- [ ] `Any` or missing type hints
- [ ] Magic strings/numbers
- [ ] Synchronous I/O inside `async def`
- [ ] Trust of raw user/LLM input without validation
- [ ] `shell=True` with unsanitized input
- [ ] Path traversal vulnerabilities
- [ ] Duplicate validation logic instead of Pydantic models
- [ ] "What" docstrings without "why"
- [ ] Broad try/except blocks that hide root causes

## 12. Mazyr-Specific Conventions

- Use Pydantic v2 `BaseModel` for domain entities that cross boundaries.
- Use dataclasses only for purely internal, mutable state.
- Reuse `ToolResult`, `FilterResult`, and other domain result types; do not
  invent new ad-hoc result shapes.
- Keep configuration in `~/.mazyr/config.yaml` (no `.env` files).
- Log to `mazyr.infrastructure.logger.get_logger(name)`; do not configure
  loggers inside libraries.

## 13. Project Specification Override (SHOULD)

If a project provides its own technical specification (e.g., `MTS-*.md`, 
`ARCHITECTURE.md`, `SPEC.md`), treat it as **authoritative override** to this 
skill. 

Priority order:
1. Project spec (most specific)
2. This skill (generic Python craft)
3. Common conventions (PEP 8, etc.)

When conflict arises between project spec and this skill, follow project spec 
and log the deviation rationale.
