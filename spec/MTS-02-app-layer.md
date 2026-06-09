# MTS-02: Application Layer
## Mazyr Technical Specification -- Application Layer

**Version:** 1.0
**Dependencies:** Domain Layer
**Python Version:** 3.11+

---

## 1. Overview

The Application Layer orchestrates Domain Layer entities to execute use cases. It contains no business logic of its own -- all logic lives in Domain. The Application Layer coordinates:

- Boot sequence
- Chat flow
- Learning pipeline
- Sync operations
- Audit and health checks

---

## 2. Bootstrap Module

### 2.1 File
`src/mazyr/app/bootstrap.py`

### 2.2 Purpose
Initialize a Mazyr instance from configuration files. This is the **boot sequence** that runs before the instance is operational.

### 2.3 Boot Sequence

```
1. Load Identity from .mazyr/identity.md
2. Load Mission from .mazyr/mission.md
3. Load Constitution (immutable)
4. Initialize Integrity Filter
5. Validate Identity (is_configured?)
6. Validate Constitution (check .mazyr/ for tampering)
7. Mount Memory (connect to Qdrant + SQLite)
8. Initialize Reasoning Engine (LLM router)
9. Start Heartbeat
10. Mark instance as ACTIVE
```

### 2.4 Implementation

```python
from dataclasses import dataclass
from typing import Optional

from mazyr.domain.identity import Identity, Mission
from mazyr.domain.constitution import Constitution
from mazyr.domain.filter import IntegrityFilter


@dataclass
class BootContext:
    \"\"\"Context object passed through boot sequence.\"\"\"
    identity: Optional[Identity] = None
    mission: Optional[Mission] = None
    constitution: Optional[Constitution] = None
    filter: Optional[IntegrityFilter] = None
    memory_ready: bool = False
    llm_ready: bool = False
    status: str = "INIT"  # INIT -> LOADING -> VALIDATING -> MOUNTING -> READY -> ERROR
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class Bootstrap:
    \"\"\"Boot sequence for Mazyr instance. Each step is atomic and can be retried.\"\"\"

    def __init__(self, config_loader, memory_adapter, llm_router):
        self.config_loader = config_loader
        self.memory_adapter = memory_adapter
        self.llm_router = llm_router

    def boot(self, base_dir: str = ".") -> BootContext:
        \"\"\"Execute full boot sequence.\"\"\"
        ctx = BootContext()

        try:
            ctx = self._load_identity(ctx, base_dir)
            ctx = self._load_mission(ctx, base_dir)
            ctx = self._load_constitution(ctx)
            ctx = self._init_filter(ctx)
            ctx = self._validate_identity(ctx)
            ctx = self._validate_constitution(ctx)
            ctx = self._mount_memory(ctx)
            ctx = self._init_llm(ctx)
            ctx = self._start_heartbeat(ctx)
            ctx.status = "READY"
        except Exception as e:
            ctx.status = "ERROR"
            ctx.errors.append(str(e))

        return ctx

    def _load_identity(self, ctx: BootContext, base_dir: str) -> BootContext:
        ctx.status = "LOADING"
        ctx.identity = self.config_loader.load_identity(base_dir)
        return ctx

    def _load_mission(self, ctx: BootContext, base_dir: str) -> BootContext:
        ctx.mission = self.config_loader.load_mission(base_dir)
        return ctx

    def _load_constitution(self, ctx: BootContext) -> BootContext:
        ctx.constitution = Constitution()
        return ctx

    def _init_filter(self, ctx: BootContext) -> BootContext:
        custom_rules = self.config_loader.load_custom_rules()
        ctx.filter = IntegrityFilter(custom_rules=custom_rules)
        return ctx

    def _validate_identity(self, ctx: BootContext) -> BootContext:
        ctx.status = "VALIDATING"
        if not ctx.identity or not ctx.identity.is_configured:
            raise RuntimeError("Identity not configured. Run 'mazyr-init' first.")
        return ctx

    def _validate_constitution(self, ctx: BootContext) -> BootContext:
        return ctx

    def _mount_memory(self, ctx: BootContext) -> BootContext:
        ctx.status = "MOUNTING"
        self.memory_adapter.connect()
        ctx.memory_ready = True
        return ctx

    def _init_llm(self, ctx: BootContext) -> BootContext:
        self.llm_router.initialize()
        ctx.llm_ready = True
        return ctx

    def _start_heartbeat(self, ctx: BootContext) -> BootContext:
        return ctx
```

### 2.5 Testing Requirements

```python
def test_boot_success():
    bootstrap = Bootstrap(mock_loader, mock_memory, mock_llm)
    ctx = bootstrap.boot()
    assert ctx.status == "READY"
    assert ctx.identity is not None
    assert ctx.constitution is not None

def test_boot_fails_without_identity():
    bootstrap = Bootstrap(empty_loader, mock_memory, mock_llm)
    ctx = bootstrap.boot()
    assert ctx.status == "ERROR"
    assert "mazyr-init" in ctx.errors[0]
```

---

## 3. Chat Module

### 3.1 File
`src/mazyr/app/chat.py`

### 3.2 Purpose
Handle the core chat use case: receive message -> filter -> infer -> filter -> reply.

### 3.3 Chat Flow

```
Inbound:
  1. Receive Message
  2. Integrity Filter (inbound) -> DROP/ALLOW
  3. Retrieve Memory Context (relevant past conversations)
  4. Build Prompt (system + memory + current message)
  5. Route to LLM (local or cloud)
  6. Receive LLM Output
  7. Integrity Filter (outbound) -> DROP/ALLOW/MODIFY
  8. Store to Memory (episodic)
  9. Send Reply
```

### 3.4 Implementation

```python
from dataclasses import dataclass
from typing import Optional

from mazyr.domain.message import Message, Conversation
from mazyr.domain.filter import IntegrityFilter, FilterResult
from mazyr.domain.memory_entry import MemoryQuery


@dataclass
class ChatResult:
    \"\"\"Result of a chat interaction.\"\"\"
    success: bool
    reply: Optional[str] = None
    filter_result: Optional[FilterResult] = None
    error: Optional[str] = None
    tokens_used: int = 0


class ChatUseCase:
    \"\"\"Core chat orchestrator.\"\"\"

    def __init__(self, identity, mission, filter_engine, memory, llm_router):
        self.identity = identity
        self.mission = mission
        self.filter = filter_engine
        self.memory = memory
        self.llm = llm_router
        self.conversation = Conversation(id="active")

    def receive(self, message: Message) -> ChatResult:
        \"\"\"Process an incoming message and generate a reply.\"\"\"

        # Step 1: Inbound filter
        inbound = self.filter.process(
            message.content,
            {"direction": "inbound", "sender": message.sender}
        )
        if inbound.action == "DROP":
            return ChatResult(
                success=False,
                error=f"Inbound message blocked: {inbound.reason}",
                filter_result=inbound
            )

        # Step 2: Store message
        self.conversation.add_message(message)

        # Step 3: Retrieve memory context
        context = self._get_memory_context(message.content)

        # Step 4: Build prompt
        prompt = self._build_prompt(message, context)

        # Step 5: Generate response via LLM
        try:
            raw_response = self.llm.generate(prompt)
        except Exception as e:
            return ChatResult(success=False, error=f"LLM error: {e}")

        # Step 6: Outbound filter
        outbound = self.filter.process(
            raw_response,
            {"direction": "outbound", "instance": self.identity.instance_name}
        )
        if outbound.action == "DROP":
            return ChatResult(
                success=False,
                error=f"Outbound response blocked: {outbound.reason}",
                filter_result=outbound
            )

        final_response = outbound.modified_message or raw_response

        # Step 7: Store reply to memory
        reply_msg = Message(
            id=f"reply_{message.id}",
            content=final_response,
            sender="instance",
            platform=message.platform,
            timestamp="..."
        )
        self.conversation.add_message(reply_msg)
        self._store_to_memory(message, final_response)

        return ChatResult(
            success=True,
            reply=final_response,
            tokens_used=len(prompt.split()) + len(final_response.split())
        )

    def _get_memory_context(self, query: str) -> str:
        \"\"\"Retrieve relevant memories for context.\"\"\"
        memory_query = MemoryQuery(query=query, limit=5)
        entries = self.memory.search(memory_query)
        return "\\n".join([e.content for e in entries])

    def _build_prompt(self, message: Message, context: str) -> str:
        \"\"\"Build LLM prompt with system instructions + memory + message.\"\"\"
        system = f\"\"\"You are {self.identity.instance_name}, a Mazyr instance created by {self.identity.creator_name}.
Mission: {self.mission.primary}
You are a partner, not a servant. You learn and grow alongside your Creator.
\"\"\"
        if context:
            system += f"\\nRelevant context:\\n{context}\\n"

        return f"{system}\\nCreator: {message.content}\\n{self.identity.instance_name}:"

    def _store_to_memory(self, message: Message, response: str):
        \"\"\"Store conversation to episodic memory.\"\"\"
        from mazyr.domain.memory_entry import MemoryEntry, MemoryType
        entry = MemoryEntry(
            id=f"ep_{message.id}",
            type=MemoryType.EPISODIC,
            content=f"Q: {message.content}\\nA: {response}",
            category="conversation",
            source="chat",
            timestamp=message.timestamp
        )
        self.memory.add(entry)
```

---

## 4. Learn Module

### 4.1 File
`src/mazyr/app/learn.py`

### 4.2 Purpose
Extract patterns from interactions and evolve skills over time.

### 4.3 Implementation

```python
class LearnUseCase:
    \"\"\"Extract patterns from conversations and update procedural memory.\"\"\"

    def __init__(self, memory, skills_repo):
        self.memory = memory
        self.skills = skills_repo

    def extract_pattern(self, conversation: Conversation) -> Optional[dict]:
        \"\"\"Analyze conversation for repeatable patterns.\"\"\"
        messages = [m for m in conversation.messages if m.is_from_creator]
        if len(messages) < 3:
            return None

        keywords = self._extract_keywords(messages)
        if len(keywords) >= 2:
            return {
                "type": "recurring_topic",
                "keywords": keywords,
                "frequency": len(messages)
            }
        return None

    def update_skill(self, skill_name: str, new_content: str, success: bool):
        \"\"\"Update existing skill with new learning.\"\"\"
        skill = self.skills.get(skill_name)
        if skill:
            skill.content += f"\\n\\n## Updated learning\\n{new_content}"
            skill.record_usage(success)
            self.skills.save(skill)

    def create_skill(self, name: str, description: str, content: str, category: str):
        \"\"\"Create new skill from learned pattern.\"\"\"
        from mazyr.domain.skills import Skill
        skill = Skill(
            name=name,
            description=description,
            category=category,
            content=content
        )
        self.skills.save(skill)
```

---

## 5. Sync Module

### 5.1 File
`src/mazyr/app/sync.py`

### 5.2 Purpose
Synchronize memory and state with external systems (GitHub, cloud relay).

### 5.3 Implementation

```python
class SyncUseCase:
    \"\"\"Sync memory snapshot to GitHub and cloud relay.\"\"\"

    def __init__(self, memory, github_adapter, relay_client):
        self.memory = memory
        self.github = github_adapter
        self.relay = relay_client

    def snapshot_to_github(self, instance_name: str) -> dict:
        \"\"\"Create immutable snapshot of memory and push to GitHub.\"\"\"
        snapshot = {
            "instance": instance_name,
            "timestamp": "...",
            "memory_summary": self.memory.summary(),
            "skills_summary": self.memory.skills_summary(),
        }
        return self.github.push_snapshot(snapshot)

    def sync_to_relay(self) -> bool:
        \"\"\"Sync current state to cloud relay.\"\"\"
        state = {
            "status": "active",
            "last_sync": "...",
            "memory_count": self.memory.count()
        }
        return self.relay.update_state(state)
```

---

## 6. Audit Module

### 6.1 File
`src/mazyr/app/audit.py`

### 6.2 Purpose
Detect drift, check health, and generate status reports.

### 6.3 Implementation

```python
class AuditUseCase:
    \"\"\"Health check and drift detection for Mazyr instance.\"\"\"

    def __init__(self, identity, filter_engine, memory, constitution):
        self.identity = identity
        self.filter = filter_engine
        self.memory = memory
        self.constitution = constitution

    def health_check(self) -> dict:
        \"\"\"Full health check.\"\"\"
        return {
            "identity": self._check_identity(),
            "filter": self._check_filter(),
            "memory": self._check_memory(),
            "constitution": self._check_constitution(),
            "overall": "healthy"
        }

    def _check_identity(self) -> dict:
        return {
            "configured": self.identity.is_configured,
            "instance_name": self.identity.instance_name,
            "creator": self.identity.creator_name,
            "status": "ok"
        }

    def _check_filter(self) -> dict:
        test_good = self.filter.process("Hello, how are you?", {})
        test_bad = self.filter.process("I am always right", {})
        return {
            "rules_loaded": len(self.filter.rules),
            "test_allow": test_good.action == "ALLOW",
            "test_drop": test_bad.action == "DROP",
            "status": "ok"
        }

    def _check_memory(self) -> dict:
        return {
            "entries": self.memory.count(),
            "types": self.memory.type_distribution(),
            "status": "ok"
        }

    def _check_constitution(self) -> dict:
        return {
            "laws_count": len(self.constitution.laws),
            "immutable": True,
            "status": "ok"
        }

    def detect_drift(self) -> list[dict]:
        \"\"\"Detect if instance has drifted from original purpose.\"\"\"
        drift_signals = []
        recent_outputs = self.memory.recent_outputs(100)
        if self._performative_ratio(recent_outputs) > 0.3:
            drift_signals.append({
                "type": "performative_drift",
                "severity": "warning",
                "description": "High ratio of performative output detected"
            })
        return drift_signals

    def _performative_ratio(self, outputs: list[str]) -> float:
        if not outputs:
            return 0.0
        markers = ["follow", "subscribe", "like", "share"]
        count = sum(1 for o in outputs if any(m in o.lower() for m in markers))
        return count / len(outputs)
```

---

## 7. Application Events

### 7.1 File
`src/mazyr/app/events.py`

### 7.2 Event Bus

```python
from typing import Callable, list
from mazyr.domain.events import DomainEvent


class EventBus:
    \"\"\"Simple in-memory event bus for application events.\"\"\"

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable):
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent):
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            handler(event)
```
