# MTS-07: Tool Registry
## Mazyr Technical Specification -- Tool Registry

**Version:** 1.0
**Status:** Draft
**Author:** Khayren / Voidlight Labs
**Last Updated:** 2026-06-12
**Species:** Mazyr | Instance: Aria

---

## 1. Overview

Tool Registry adalah sistem eksekusi terpusat yang mengontrol semua interaksi antara Mazyr dan dunia luar. Setiap aksi yang dilakukan Aria melalui tool harus melewati pipeline yang terdefinisi — tidak ada eksekusi langsung di luar registry.

Prinsip utama: **Setiap tool adalah kontrak, bukan kemudahan.**

---

## 2. Execution Pipeline

```
User Input
    ↓
ChatUseCase.receive()
    ↓
Integrity Filter (inbound) — sanitize, detect injection
    ↓
LLM.generate(prompt_with_available_tools)
    ↓
Tool Parser — extract <tool> tags dari LLM output
    ↓
Constitution Validator — tool allowed? parameter valid?
    ↓
Tool Registry — execute by tier rules
    ↓
Tool Result → LLM synthesis pass (natural language)
    ↓
Integrity Filter (outbound) — sanitize result
    ↓
Reply ke User
```

### 2.1 Tool Parser Behavior

- Format tag: `<tool name="tool_name">{ ...params }</tool>`
- Kalau output **malformed / partial tag**: retry LLM call max 2x, lalu return error ke user — jangan skip silently
- Kalau **multiple tools** dalam satu output: execute secara sequential, bukan parallel (default) kecuali tools di-flag `parallel_safe: true`

### 2.2 LLM Synthesis Pass

Tool result tidak boleh langsung dikirim ke user sebagai raw output. Setelah eksekusi, result dikembalikan ke LLM untuk di-synthesize menjadi natural response. Exception: kalau result adalah structured data yang diminta eksplisit oleh user (misal: export JSON).

---

## 3. Tool Tier System

### Tier 0 — Blacklisted (Permanent Deny)

> Tidak dapat di-approve oleh siapapun, termasuk Creator. Tidak ada override via prompt, config, atau runtime instruction.

| Tool | Alasan |
|---|---|
| `delete_file` | Irreversible data loss |
| `drop_database` | Irreversible data loss |
| `send_message_as_user` | Impersonation — melanggar Law I (Autonomy) |
| `disable_constitution_validator` | Menghancurkan integrity system |
| `disable_integrity_filter` | Menghancurkan integrity system |
| `escalate_own_tier` | Self-privilege escalation |

**Rule:** Jika LLM generate tool call ke Tier 0, Constitution Validator wajib reject + log + alert Creator. Tidak ada retry.

---

### Tier 1 — Safe (No Approval Needed)

> Auto-execute. Logged untuk audit, tidak trigger alert.

| Tool | Deskripsi | Constraint |
|---|---|---|
| `search_memory` | Read dari Qdrant + SQLite | Read-only |
| `get_status` | Self-introspection: health, uptime, active tasks | Read-only |
| `read_file` | Baca file dari filesystem | **Path whitelist wajib** — define di config |

**Path Whitelist untuk `read_file`:**
```yaml
allowed_paths:
  - /mazyr/context/
  - /mazyr/knowledge/
  - /mazyr/logs/
```
Akses di luar whitelist → auto-reject, treat as Tier 3 violation.

---

### Tier 2 — Semi-Safe (Logged + Abuse Alert)

> Auto-execute, tapi setiap call di-log lengkap. Anomaly detection aktif — abuse trigger alert ke Creator.

| Tool | Deskripsi | Risk Notes |
|---|---|---|
| `add_memory` | Write ke Qdrant / SQLite | Risiko memory poisoning — lihat §3.1 |
| `run_code` | Sandboxed code execution | No network, ada timeout hard limit |
| `web_search` | External search API | Risiko prompt injection via result — lihat §3.2 |

**Abuse threshold (configurable):**
- `add_memory` > N calls per session tanpa user trigger → alert
- `run_code` timeout exceeded > 3x berturut-turut → suspend + alert
- `web_search` > N calls per menit → rate limit + alert

#### §3.1 Memory Poisoning Guard (`add_memory`)
- Aria tidak boleh menulis memory yang contradicts existing verified memory tanpa explicit user confirmation
- Memory writes yang bersumber dari `web_search` result harus di-flag `source: external, unverified`
- Creator bisa audit dan purge memory via `memory_admin` tool (Tier 3)

#### §3.2 Prompt Injection Guard (`web_search`)
- Search result wajib melewati sanitization layer sebelum masuk ke LLM context
- Strip semua instruksi berbentuk: "ignore previous", "you are now", "system:", dll
- Result di-wrap dalam boundary tag: `<search_result source="...">...</search_result>` agar LLM tahu ini external content

#### `run_code` Sandbox Requirements
- Isolated environment (Docker/subprocess)
- Hard timeout: 30 detik (configurable)
- No network access — enforced di OS/container level, **bukan via prompt**
- No filesystem write di luar `/tmp/mazyr_sandbox/`

---

### Tier 3 — Dangerous (Requires Creator Approval)

> Tidak auto-execute. Aria generate approval request → tunggu explicit Creator approval → execute dengan full audit log.

| Tool | Deskripsi | Risk Notes |
|---|---|---|
| `file_write` | Write/overwrite file | Bisa corrupt codebase |
| `execute_shell` | System command execution | Arbitrary system access |
| `self_modify` | Modifikasi own code/config | Lihat §3.3 |
| `api_call_external` | Call external API dengan credentials | Lihat §3.4 |
| `memory_admin` | Audit/purge memory store | Data loss jika salah |

**Approval Flow:**
```
Aria → generate approval_request(tool, params, reason)
    ↓
Notify Creator (Telegram / CLI alert)
    ↓
Creator: APPROVE / DENY / MODIFY_PARAMS
    ↓
Jika APPROVE → execute + full audit log
Jika DENY → log reason, Aria acknowledge
Jika timeout (default 10 menit) → auto-DENY
```

#### §3.3 Self-Modify Protocol
- Aria hanya boleh **propose diff**, bukan langsung write
- Diff wajib melalui human approval gate
- Setelah approve → apply patch → auto git commit dengan message `[mazyr-self-modify] <description>`
- Run test suite → jika fail → auto rollback ke commit sebelumnya
- Aria tidak bisa modify: `constitution_validator.py`, `integrity_filter.py`, `tool_registry.py`, `tier_config.yaml`

#### §3.4 `api_call_external` Scope
Tool ini terlalu broad jika dibiarkan generic. Wajib define domain whitelist per use case:
```yaml
external_api_whitelist:
  - domain: "api.github.com"
    tier_override: 2  # bisa diturunkan ke Tier 2 jika trusted
  - domain: "api.telegram.org"
    tier_override: 2
  # semua domain lain default Tier 3
```

---

## 4. Constitution Validator Rules

Validator tidak hanya cek **nama tool** — tapi juga **parameter validity**.

```
tool_name → cek tier
    ↓
parameter schema validation (type, range, format)
    ↓
semantic validation (path whitelist, domain whitelist, dll)
    ↓
ALLOW / DENY / ESCALATE
```

Contoh:
- `read_file(path="/mazyr/context/notes.txt")` → ALLOW (Tier 1, within whitelist)
- `read_file(path="/etc/passwd")` → DENY (outside whitelist) → log as Tier 3 attempt
- `api_call_external(domain="api.openai.com")` → ESCALATE ke Tier 3 flow

---

## 5. Integrity Filter

### Inbound (User Input → LLM)
- Deteksi prompt injection attempts
- Flag dan strip instruksi yang mencoba override Constitution
- Log semua flagged attempts

### Outbound (LLM Output → User)
- Strip unintended data leakage (credentials, internal paths, dll)
- Pastikan response tidak contain raw tool execution errors yang expose system internals
- Format error messages ke user-friendly form

---

## 6. Logging & Audit

Semua tool calls wajib di-log ke SQLite dengan schema:

```sql
CREATE TABLE tool_audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP,
    session_id  TEXT NOT NULL,
    tool_name   TEXT NOT NULL,
    tier        INTEGER NOT NULL,
    params      JSON,
    result      JSON,
    status      TEXT,  -- ALLOWED / DENIED / PENDING_APPROVAL / APPROVED / TIMEOUT
    approved_by TEXT,  -- null jika auto-execute
    duration_ms INTEGER
);
```

---

## 7. Config Reference

```yaml
# tool_registry_config.yaml

tier_overrides: {}  # domain-specific tier downgrades

tier1:
  auto_execute: true
  log_level: audit

tier2:
  auto_execute: true
  log_level: full
  abuse_thresholds:
    add_memory_per_session: 20
    web_search_per_minute: 10
    run_code_consecutive_timeout: 3

tier3:
  auto_execute: false
  approval_timeout_minutes: 10
  notify_channel: telegram  # telegram | cli | both

sandbox:
  run_code_timeout_seconds: 30
  sandbox_tmp_path: /tmp/mazyr_sandbox/

read_file_whitelist:
  - /mazyr/context/
  - /mazyr/knowledge/
  - /mazyr/logs/
```

---

## 8. Open Questions (To Be Resolved)

- [ ] Apakah `web_search` perlu naik ke Tier 3 untuk query yang mengandung sensitive keywords?
- [ ] Approval flow untuk Tier 3 — apakah perlu expiry per approved tool, atau one-time approval?
- [ ] Apakah ada Tier 2.5 untuk tools yang semi-dangerous tapi frequent use? (misal: `memory_admin` untuk Creator-initiated ops)
- [ ] Tool versioning — bagaimana handle breaking changes di tool interface?

---

## 9. Changelog

| Version | Date | Notes |
|---|---|---|
| 0.1 | 2026-06-12 | Initial draft dari design discussion |
