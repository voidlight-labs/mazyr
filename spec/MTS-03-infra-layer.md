# MTS-03: Infrastructure Layer
## Mazyr Technical Specification -- Infrastructure Layer

**Version:** 1.0
**Dependencies:** Domain Layer, External Services
**Python Version:** 3.11+

---

## 1. Overview

The Infrastructure Layer contains all adapters to external systems. It implements interfaces defined by the Domain Layer. This layer is allowed to have external dependencies (Docker, APIs, databases).

**Key Principle:** If a technology changes (e.g., Qdrant -> Pinecone), only the adapter changes. Domain and Application layers remain untouched.

---

## 2. Config Loader

### 2.1 File
`src/mazyr/infrastructure/config_loader.py`

### 2.2 Purpose
Load and validate configuration from `.mazyr/` directory.

### 2.3 Implementation

```python
import os
import yaml
from pathlib import Path
from typing import Optional

from mazyr.domain.identity import Identity, Mission
from mazyr.domain.filter import FilterRule, FilterAction


class ConfigLoader:
    \"\"\"Loads configuration from .mazyr/ directory. Validates using Domain Layer entities.\"\"\"

    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.mazyr_dir = self.base_dir / ".mazyr"

    def load_identity(self, base_dir: str = None) -> Optional[Identity]:
        \"\"\"Load identity from .mazyr/identity.md\"\"\"
        path = Path(base_dir or self.base_dir) / ".mazyr" / "identity.md"
        if not path.exists():
            return None

        data = self._parse_markdown_frontmatter(path)
        return Identity(
            instance_name=data.get("instance_name", "Mazyr"),
            species=data.get("species", "Mazyr"),
            creator_name=data.get("creator", "Anonymous"),
            creator_contact=data.get("creator_contact"),
            date_provisioned=data.get("date_provisioned", ""),
            vessel_type=data.get("vessel_type", "laptop")
        )

    def load_mission(self, base_dir: str = None) -> Optional[Mission]:
        \"\"\"Load mission from .mazyr/mission.md\"\"\"
        path = Path(base_dir or self.base_dir) / ".mazyr" / "mission.md"
        if not path.exists():
            return None

        data = self._parse_markdown_frontmatter(path)
        scope_str = data.get("scope", "general")
        scope = [s.strip() for s in scope_str.split(",")]

        return Mission(
            primary=data.get("primary", ""),
            secondary=data.get("secondary"),
            scope=scope
        )

    def load_custom_rules(self) -> list[FilterRule]:
        \"\"\"Load custom filter rules from .mazyr/filter-custom.json\"\"\"
        path = self.mazyr_dir / "filter-custom.json"
        if not path.exists():
            return []

        import json
        with open(path) as f:
            data = json.load(f)

        rules = []
        for r in data.get("rules", []):
            rules.append(FilterRule(
                name=r["name"],
                action=FilterAction(r["action"]),
                pattern_type=r["pattern_type"],
                patterns=tuple(r["patterns"]),
                description=r["description"],
                direction=r.get("direction", "both")
            ))
        return rules

    def _parse_markdown_frontmatter(self, path: Path) -> dict:
        \"\"\"Parse YAML frontmatter from markdown file.\"\"\"
        with open(path) as f:
            content = f.read()

        if content.startswith("---"):
            _, yaml_part, _ = content.split("---", 2)
            return yaml.safe_load(yaml_part) or {}
        return {}
```

---

## 3. LLM Adapters

### 3.1 Local LLM Adapter

**File:** `src/mazyr/infrastructure/llm_local.py`

```python
import subprocess
from typing import Optional

from mazyr.domain.message import Message


class LocalLLM:
    \"\"\"Wrapper for llama.cpp local inference.\"\"\"

    def __init__(self, model_path: str, ngl: int = 35, temp: float = 0.7):
        self.model_path = model_path
        self.ngl = ngl
        self.temp = temp

    def generate(self, prompt: str, max_tokens: int = 2048) -> str:
        \"\"\"Generate text using local model.\"\"\"
        cmd = [
            "llama-cli",
            "-m", self.model_path,
            "-p", prompt,
            "-n", str(max_tokens),
            "--temp", str(self.temp),
            "-ngl", str(self.ngl),
            "--no-display-prompt"
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode != 0:
            raise RuntimeError(f"Local LLM error: {result.stderr}")

        return result.stdout.strip()

    def is_available(self) -> bool:
        import os
        return os.path.exists(self.model_path)
```

### 3.2 Cloud LLM Adapter

**File:** `src/mazyr/infrastructure/llm_cloud.py`

```python
import os
from typing import Optional
import httpx


class CloudLLM:
    \"\"\"Wrapper for Kimi API (OpenAI-compatible).\"\"\"

    def __init__(self, api_key: str, base_url: str = "https://api.moonshot.cn/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0
        )

    def generate(self, prompt: str, model: str = "kimi-k2-6",
                 temperature: float = 0.7, max_tokens: int = 2048) -> str:
        \"\"\"Generate text using cloud API.\"\"\"
        response = self.client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens
            }
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def is_available(self) -> bool:
        return bool(self.api_key)
```

### 3.3 LLM Router

**File:** `src/mazyr/infrastructure/llm_router.py`

```python
from typing import Optional
from enum import Enum


class InferencePreference(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"
    HYBRID = "hybrid"


class LLMRouter:
    \"\"\"Routes inference requests between local and cloud LLM.\"\"\"

    def __init__(self, local_llm, cloud_llm, preference: InferencePreference = InferencePreference.HYBRID):
        self.local = local_llm
        self.cloud = cloud_llm
        self.preference = preference

    def initialize(self):
        self.local_available = self.local.is_available()
        self.cloud_available = self.cloud.is_available()

    def generate(self, prompt: str, complexity: str = "auto") -> str:
        if self.preference == InferencePreference.LOCAL and self.local_available:
            return self.local.generate(prompt)

        if self.preference == InferencePreference.CLOUD and self.cloud_available:
            return self.cloud.generate(prompt)

        if complexity == "auto":
            complexity = self._estimate_complexity(prompt)

        if complexity == "simple" and self.local_available:
            return self.local.generate(prompt)

        if self.cloud_available:
            return self.cloud.generate(prompt)

        if self.local_available:
            return self.local.generate(prompt)

        raise RuntimeError("No LLM available. Check local model path and cloud API key.")

    def _estimate_complexity(self, prompt: str) -> str:
        if len(prompt) < 500 and "code" not in prompt.lower():
            return "simple"
        if len(prompt) > 2000 or "analyze" in prompt.lower():
            return "complex"
        return "medium"
```

---

## 4. Memory Adapters

### 4.1 Qdrant Adapter (Vector DB)

**File:** `src/mazyr/infrastructure/memory_qdrant.py`

```python
from typing import list, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from mazyr.domain.memory_entry import MemoryEntry, MemoryQuery, MemoryType


class QdrantMemoryAdapter:
    \"\"\"Adapter for Qdrant vector database.\"\"\"

    COLLECTION_NAME = "mazyr_memory"
    VECTOR_SIZE = 768

    def __init__(self, host: str = "localhost", port: int = 6333):
        self.client = QdrantClient(host=host, port=port)

    def connect(self):
        collections = self.client.get_collections().collections
        exists = any(c.name == self.COLLECTION_NAME for c in collections)

        if not exists:
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(size=self.VECTOR_SIZE, distance=Distance.COSINE)
            )

    def add(self, entry: MemoryEntry, embedding: list[float]):
        self.client.upsert(
            collection_name=self.COLLECTION_NAME,
            points=[PointStruct(
                id=entry.id,
                vector=embedding,
                payload={
                    "type": entry.type.value,
                    "content": entry.content,
                    "category": entry.category,
                    "source": entry.source,
                    "timestamp": entry.timestamp,
                    "confidence": entry.confidence
                }
            )]
        )

    def search(self, query: MemoryQuery, query_embedding: list[float]) -> list[MemoryEntry]:
        results = self.client.search(
            collection_name=self.COLLECTION_NAME,
            query_vector=query_embedding,
            limit=query.limit,
            with_payload=True
        )

        entries = []
        for r in results:
            if r.score < query.min_confidence:
                continue
            payload = r.payload
            entries.append(MemoryEntry(
                id=str(r.id),
                type=MemoryType(payload["type"]),
                content=payload["content"],
                category=payload["category"],
                source=payload["source"],
                timestamp=payload["timestamp"],
                confidence=r.score
            ))
        return entries
```

### 4.2 SQLite Adapter (Episodic Memory)

**File:** `src/mazyr/infrastructure/memory_sqlite.py`

```python
import sqlite3
from datetime import datetime
from typing import list, Optional
from pathlib import Path

from mazyr.domain.memory_entry import MemoryEntry, MemoryType


class SQLiteMemoryAdapter:
    \"\"\"Adapter for SQLite database.\"\"\"

    def __init__(self, db_path: str = "./memory/mazyr.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = None

    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript(\"\"\"
            CREATE TABLE IF NOT EXISTS memory_entries (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT,
                source TEXT,
                timestamp TEXT,
                confidence REAL DEFAULT 1.0,
                metadata TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_entries(type);
            CREATE INDEX IF NOT EXISTS idx_memory_category ON memory_entries(category);
            CREATE INDEX IF NOT EXISTS idx_memory_timestamp ON memory_entries(timestamp);
        \"\"\")
        self.conn.commit()

    def add(self, entry: MemoryEntry):
        import json
        self.conn.execute(
            \"\"\"INSERT OR REPLACE INTO memory_entries
               (id, type, content, category, source, timestamp, confidence, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)\"\"\",
            (entry.id, entry.type.value, entry.content, entry.category,
             entry.source, entry.timestamp, entry.confidence, json.dumps(entry.metadata))
        )
        self.conn.commit()

    def get_recent(self, limit: int = 100) -> list[MemoryEntry]:
        cursor = self.conn.execute(
            "SELECT * FROM memory_entries ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def count(self) -> int:
        cursor = self.conn.execute("SELECT COUNT(*) FROM memory_entries")
        return cursor.fetchone()[0]

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        import json
        return MemoryEntry(
            id=row["id"],
            type=MemoryType(row["type"]),
            content=row["content"],
            category=row["category"],
            source=row["source"],
            timestamp=row["timestamp"],
            confidence=row["confidence"],
            metadata=json.loads(row["metadata"] or "{}")
        )
```

---

## 5. Messenger Adapters

### 5.1 WhatsApp Web Adapter

**File:** `src/mazyr/infrastructure/messenger_whatsapp.py`

```python
import asyncio
from typing import Callable, Optional
from playwright.async_api import async_playwright

from mazyr.domain.message import Message


class WhatsAppAdapter:
    \"\"\"WhatsApp Web adapter using Playwright.\"\"\"

    def __init__(self, session_dir: str = "./memory/whatsapp_session"):
        self.session_dir = session_dir
        self.browser = None
        self.page = None
        self.message_handler: Optional[Callable] = None

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(user_data_dir=self.session_dir)
        self.page = await self.context.new_page()
        await self.page.goto("https://web.whatsapp.com")
        await self.page.wait_for_selector('[data-testid="chat-list"]', timeout=120000)

    async def send(self, chat_id: str, message: str):
        await self.page.goto(f"https://web.whatsapp.com/send?phone={chat_id}")
        await self.page.wait_for_selector('[data-testid="conversation-compose-box-input"]')
        await self.page.fill('[data-testid="conversation-compose-box-input"]', message)
        await self.page.press('[data-testid="conversation-compose-box-input"]', "Enter")

    async def listen(self, handler: Callable):
        self.message_handler = handler
        while True:
            messages = await self.page.query_selector_all('.message-in')
            for msg in messages:
                text = await msg.inner_text()
                if text and self.message_handler:
                    self.message_handler(text)
            await asyncio.sleep(2)

    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
```

### 5.2 Telegram Bot Adapter

**File:** `src/mazyr/infrastructure/messenger_telegram.py`

```python
from typing import Callable
import httpx

from mazyr.domain.message import Message


class TelegramAdapter:
    \"\"\"Telegram Bot adapter using HTTP API.\"\"\"

    def __init__(self, bot_token: str):
        self.token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.client = httpx.Client(base_url=self.base_url)
        self.offset = 0

    def send_message(self, chat_id: int, text: str):
        response = self.client.post(
            "/sendMessage",
            json={"chat_id": chat_id, "text": text}
        )
        response.raise_for_status()

    def get_updates(self, limit: int = 100) -> list[dict]:
        response = self.client.get(
            "/getUpdates",
            params={"offset": self.offset, "limit": limit}
        )
        data = response.json()
        updates = data.get("result", [])
        if updates:
            self.offset = updates[-1]["update_id"] + 1
        return updates

    def listen(self, handler: Callable):
        import time
        while True:
            updates = self.get_updates()
            for update in updates:
                message = update.get("message", {})
                if "text" in message:
                    handler({
                        "text": message["text"],
                        "chat_id": message["chat"]["id"],
                        "from": message["from"]["username"],
                        "message_id": message["message_id"]
                    })
            time.sleep(1)
```

---

## 6. GitHub Sync Adapter

**File:** `src/mazyr/infrastructure/github_sync.py`

```python
import json
import base64
from datetime import datetime
from typing import Optional
import httpx


class GitHubSyncAdapter:
    \"\"\"Sync memory snapshots to GitHub repository.\"\"\"

    def __init__(self, token: str, repo: str, branch: str = "main"):
        self.token = token
        self.repo = repo
        self.branch = branch
        self.client = httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json"
            }
        )

    def push_snapshot(self, snapshot: dict, path: str = "snapshots") -> dict:
        timestamp = datetime.now().isoformat()
        filename = f"{path}/snapshot_{timestamp}.json"
        content = json.dumps(snapshot, indent=2)
        content_b64 = base64.b64encode(content.encode()).decode()

        sha = self._get_file_sha(filename)

        response = self.client.put(
            f"/repos/{self.repo}/contents/{filename}",
            json={
                "message": f"Memory snapshot {timestamp}",
                "content": content_b64,
                "branch": self.branch,
                "sha": sha
            }
        )
        response.raise_for_status()
        return response.json()

    def _get_file_sha(self, path: str) -> Optional[str]:
        response = self.client.get(
            f"/repos/{self.repo}/contents/{path}",
            params={"ref": self.branch}
        )
        if response.status_code == 200:
            return response.json().get("sha")
        return None
```

---

## 7. Filesystem Adapter

**File:** `src/mazyr/infrastructure/filesystem.py`

```python
import os
import shutil
from pathlib import Path
from typing import Optional


class FilesystemAdapter:
    \"\"\"File operations for .mazyr/ directory and memory storage.\"\"\"

    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.mazyr_dir = self.base_dir / ".mazyr"
        self.memory_dir = self.base_dir / "memory"

    def init_mazyr_dir(self):
        self.mazyr_dir.mkdir(exist_ok=True)
        self.memory_dir.mkdir(exist_ok=True)
        (self.memory_dir / "episodic").mkdir(exist_ok=True)
        (self.memory_dir / "semantic").mkdir(exist_ok=True)
        (self.memory_dir / "procedural").mkdir(exist_ok=True)

    def write_identity(self, content: str):
        (self.mazyr_dir / "identity.md").write_text(content)

    def write_mission(self, content: str):
        (self.mazyr_dir / "mission.md").write_text(content)

    def read_file(self, path: str) -> Optional[str]:
        full_path = self.base_dir / path
        if full_path.exists():
            return full_path.read_text()
        return None

    def backup_memory(self, dest: str):
        shutil.copytree(self.memory_dir, dest, dirs_exist_ok=True)
```
