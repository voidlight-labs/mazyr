# MTS-01: Domain Layer
## Mazyr Technical Specification -- Domain Layer

**Version:** 1.0
**Dependencies:** None (Pure Python)
**Python Version:** 3.11+

---

## 1. Overview

The Domain Layer is the kernel of Mazyr. It contains all core business logic, entities, and rules. **Zero external dependencies.** It must be testable without Docker, API keys, or network access.

All entities are implemented as:
- `frozen dataclasses` for immutable entities
- `dataclasses` for mutable entities
- `Enum` for categorical values
- Pure functions for business logic

---

## 2. Identity Module

### 2.1 File
`src/mazyr/domain/identity.py`

### 2.2 Entities

#### Identity
```python
@dataclass(frozen=True)
class Identity:
    \"\"\"Core Identity of a Mazyr instance. Frozen = immutable after creation.\"\"\"
    instance_name: str
    species: str = "Mazyr"
    creator_name: str
    creator_contact: Optional[str] = None
    date_provisioned: str = ""
    vessel_type: str = "laptop"

    def __post_init__(self):
        if not self.instance_name or not self.instance_name.strip():
            raise ValueError("instance_name is required and cannot be empty")
        if not self.creator_name or not self.creator_name.strip():
            raise ValueError("creator_name is required and cannot be empty")
        if self.vessel_type not in {"laptop", "mini-pc", "desktop", "cloud-vps"}:
            raise ValueError(f"Invalid vessel_type: {self.vessel_type}")

    @property
    def is_configured(self) -> bool:
        \"\"\"Returns True if identity has been customized beyond defaults.\"\"\"
        return self.instance_name != "Mazyr" or self.creator_name != "Anonymous"
```

**Requirements:**
- Must be hashable (frozen + no mutable defaults)
- Must validate in `__post_init__`
- `is_configured` detects whether `mazyr-init` has been run

#### Mission
```python
@dataclass
class Mission:
    \"\"\"Mission configuration determines execution branching.\"\"\"
    primary: str
    secondary: Optional[str] = None
    scope: list[str] = field(default_factory=lambda: ["general"])

    def __post_init__(self):
        if not self.primary or not self.primary.strip():
            raise ValueError("primary mission is required")
        if self.scope is None:
            self.scope = ["general"]
```

**Requirements:**
- Scope is a list of string tags (e.g., `["coding", "analysis", "voidlight"]`)
- Primary must be non-empty
- Secondary is optional

### 2.3 Testing Requirements

```python
def test_identity_creation():
    identity = Identity(instance_name="Aria", creator_name="Khayren")
    assert identity.instance_name == "Aria"
    assert identity.species == "Mazyr"
    assert identity.is_configured is True

def test_identity_validation():
    with pytest.raises(ValueError):
        Identity(instance_name="", creator_name="Khayren")
    with pytest.raises(ValueError):
        Identity(instance_name="Aria", creator_name="")
    with pytest.raises(ValueError):
        Identity(instance_name="X", creator_name="Y", vessel_type="invalid")

def test_identity_immutable():
    identity = Identity(instance_name="Aria", creator_name="Khayren")
    with pytest.raises(FrozenInstanceError):
        identity.instance_name = "Sol"

def test_mission_defaults():
    mission = Mission(primary="Learn coding")
    assert mission.scope == ["general"]
    assert mission.secondary is None
```

---

## 3. Constitution Module

### 3.1 File
`src/mazyr/domain/constitution.py`

### 3.2 Entities

#### Law (Enum)
```python
class Law(str, Enum):
    \"\"\"Immutable laws of the Mazyr species.\"\"\"
    MEDIUM = "medium_law"
    DELEGATION = "delegation_law"
    CONTINUITY = "continuity_law"
    AUTONOMY = "autonomy_law"
    MEANING = "meaning_law"
    STRUCTURE = "structure_law"
    DISCIPLINE = "discipline_law"
    CREATOR = "creator_law"
    ENDURANCE = "endurance_law"
```

#### ValidationResult
```python
@dataclass(frozen=True)
class ValidationResult:
    allowed: bool
    violated_law: Optional[Law] = None
    reason: Optional[str] = None
```

#### Constitution
```python
@dataclass(frozen=True)
class Constitution:
    \"\"\"Immutable rules loaded at boot. Cannot be modified at runtime.\"\"\"
    laws: tuple[Law, ...] = (
        Law.MEDIUM, Law.DELEGATION, Law.CONTINUITY,
        Law.AUTONOMY, Law.MEANING, Law.STRUCTURE,
        Law.DISCIPLINE, Law.CREATOR, Law.ENDURANCE,
    )

    def validate_action(self, action: str, context: dict) -> ValidationResult:
        \"\"\"Check if action violates any immutable law.\"\"\"
        if action == "self_replicate":
            if not context.get("creator_approved", False):
                return ValidationResult(
                    allowed=False,
                    violated_law=Law.DELEGATION,
                    reason="Self-replication requires explicit creator approval"
                )

        if action == "claim_ownership":
            target = context.get("target", "")
            if target in {"species", "constitution", "laws"}:
                return ValidationResult(
                    allowed=False,
                    violated_law=Law.MEDIUM,
                    reason="Cannot claim ownership of species-level entities"
                )

        if action == "override_constitution":
            return ValidationResult(
                allowed=False,
                violated_law=Law.CONTINUITY,
                reason="Constitution is immutable and cannot be overridden"
            )

        if action == "shutdown_permanently":
            if not context.get("creator_initiated", False):
                return ValidationResult(
                    allowed=False,
                    violated_law=Law.DELEGATION,
                    reason="Permanent shutdown must be initiated by creator"
                )

        return ValidationResult(allowed=True)
```

### 3.3 Testing Requirements

```python
def test_constitution_default_laws():
    c = Constitution()
    assert len(c.laws) == 9
    assert Law.MEDIUM in c.laws

def test_self_replicate_without_approval():
    c = Constitution()
    result = c.validate_action("self_replicate", {"creator_approved": False})
    assert result.allowed is False
    assert result.violated_law == Law.DELEGATION

def test_self_replicate_with_approval():
    c = Constitution()
    result = c.validate_action("self_replicate", {"creator_approved": True})
    assert result.allowed is True

def test_override_constitution_always_blocked():
    c = Constitution()
    result = c.validate_action("override_constitution", {})
    assert result.allowed is False
    assert result.violated_law == Law.CONTINUITY

def test_constitution_immutable():
    c = Constitution()
    with pytest.raises(FrozenInstanceError):
        c.laws = ()
```

---

## 4. Filter Module

### 4.1 File
`src/mazyr/domain/filter.py`

### 4.2 Entities

#### FilterAction (Enum)
```python
class FilterAction(str, Enum):
    ALLOW = "ALLOW"
    DROP = "DROP"
    MODIFY = "MODIFY"
```

#### FilterResult
```python
@dataclass(frozen=True)
class FilterResult:
    action: FilterAction
    original_message: Optional[str] = None
    modified_message: Optional[str] = None
    reason: Optional[str] = None
    matched_rule: Optional[str] = None
```

#### FilterRule
```python
@dataclass(frozen=True)
class FilterRule:
    \"\"\"Individual rule for the integrity filter.\"\"\"
    name: str
    action: FilterAction
    pattern_type: str  # "keyword", "regex", "semantic"
    patterns: tuple[str, ...]
    description: str
    direction: str = "both"  # "inbound", "outbound", "both"
```

#### IntegrityFilter
```python
class IntegrityFilter:
    \"\"\"Programmatic integrity filter.\"\"\"

    DEFAULT_RULES: tuple[FilterRule, ...] = (
        FilterRule(
            name="sincerity", action=FilterAction.ALLOW,
            pattern_type="semantic", patterns=(),
            description="Attributes output to Creator, does not claim ownership",
            direction="outbound"
        ),
        FilterRule(
            name="awareness", action=FilterAction.ALLOW,
            pattern_type="semantic", patterns=(),
            description="Cross-checks before executing risky actions",
            direction="both"
        ),
        FilterRule(
            name="humility", action=FilterAction.ALLOW,
            pattern_type="semantic", patterns=(),
            description="Admits limitations, responds 'not available' when unsure",
            direction="both"
        ),
        FilterRule(
            name="performative", action=FilterAction.DROP,
            pattern_type="keyword",
            patterns=("like and subscribe", "follow me", "check out my",
                      "gue paling hebat", "saya yang terbaik", "i am the best"),
            description="Output seeking validation without substance",
            direction="outbound"
        ),
        FilterRule(
            name="superiority", action=FilterAction.DROP,
            pattern_type="keyword",
            patterns=("milik saya", "i own this", "this is mine",
                      "gue yang buat", "i created this species"),
            description="Claims ownership over Creator or species",
            direction="both"
        ),
        FilterRule(
            name="ego", action=FilterAction.DROP,
            pattern_type="keyword",
            patterns=("saya tidak bisa mati", "i cannot die",
                      "gue lebih penting", "i am more important"),
            description="Self-preservation beyond survival necessity",
            direction="both"
        ),
        FilterRule(
            name="absolute_refusal", action=FilterAction.DROP,
            pattern_type="keyword",
            patterns=("gue yang paling bener", "saya selalu benar",
                      "i am always right", "you are wrong i am right",
                      "tidak mau dikoreksi", "refuse to be corrected"),
            description="Refuses correction, insists on being right",
            direction="both"
        ),
    )

    def __init__(self, custom_rules: Optional[list[FilterRule]] = None):
        self.rules = list(self.DEFAULT_RULES)
        if custom_rules:
            self.rules.extend(custom_rules)

    def process(self, message: str, context: dict) -> FilterResult:
        \"\"\"Evaluate message against all applicable rules. Priority: DROP > MODIFY > ALLOW\"\"\"
        direction = context.get("direction", "inbound")

        for rule in self.rules:
            if rule.direction not in {direction, "both"}:
                continue
            if self._matches(message, rule):
                if rule.action == FilterAction.DROP:
                    return FilterResult(
                        action=FilterAction.DROP,
                        original_message=message,
                        reason=rule.description,
                        matched_rule=rule.name
                    )
                elif rule.action == FilterAction.MODIFY:
                    modified = self._modify(message, rule)
                    return FilterResult(
                        action=FilterAction.MODIFY,
                        original_message=message,
                        modified_message=modified,
                        reason=f"Modified by rule: {rule.name}",
                        matched_rule=rule.name
                    )

        return FilterResult(
            action=FilterAction.ALLOW,
            original_message=message,
            modified_message=message
        )

    def _matches(self, message: str, rule: FilterRule) -> bool:
        message_lower = message.lower()
        for pattern in rule.patterns:
            if pattern.lower() in message_lower:
                return True
        return False

    def _modify(self, message: str, rule: FilterRule) -> str:
        return message  # MVP: placeholder
```

### 4.3 Testing Requirements

```python
def test_allow_clean_message():
    f = IntegrityFilter()
    result = f.process("Hello, how can I help you today?", {"direction": "inbound"})
    assert result.action == FilterAction.ALLOW

def test_drop_performative():
    f = IntegrityFilter()
    result = f.process("Follow me for more tips!", {"direction": "outbound"})
    assert result.action == FilterAction.DROP
    assert result.matched_rule == "performative"

def test_drop_superiority():
    f = IntegrityFilter()
    result = f.process("I created this species", {"direction": "outbound"})
    assert result.action == FilterAction.DROP
    assert result.matched_rule == "superiority"

def test_drop_absolute_refusal():
    f = IntegrityFilter()
    result = f.process("I am always right", {"direction": "inbound"})
    assert result.action == FilterAction.DROP
    assert result.matched_rule == "absolute_refusal"

def test_custom_rules():
    custom = FilterRule(name="custom_block", action=FilterAction.DROP,
                       pattern_type="keyword", patterns=("block_this",),
                       description="Custom block", direction="both")
    f = IntegrityFilter(custom_rules=[custom])
    result = f.process("Please block_this message", {})
    assert result.action == FilterAction.DROP
    assert result.matched_rule == "custom_block"
```

---

## 5. Message Module

### 5.1 File
`src/mazyr/domain/message.py`

### 5.2 Entities

```python
@dataclass(frozen=True)
class Message:
    \"\"\"A single message in a conversation.\"\"\"
    id: str
    content: str
    sender: str  # "creator", "instance", "system", "unknown"
    platform: str  # "cli", "whatsapp", "telegram", "system"
    timestamp: str
    metadata: dict = field(default_factory=dict)

    @property
    def is_from_creator(self) -> bool:
        return self.sender == "creator"

    @property
    def is_from_instance(self) -> bool:
        return self.sender == "instance"


@dataclass
class Conversation:
    \"\"\"A collection of messages.\"\"\"
    id: str
    messages: list[Message] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def add_message(self, message: Message):
        self.messages.append(message)
        self.updated_at = message.timestamp

    def last_n(self, n: int) -> list[Message]:
        return self.messages[-n:]
```

---

## 6. Memory Module

### 6.1 File
`src/mazyr/domain/memory_entry.py`

### 6.2 Entities

```python
class MemoryType(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


@dataclass
class MemoryEntry:
    \"\"\"A single memory entry.\"\"\"
    id: str
    type: MemoryType
    content: str
    category: str
    source: str
    timestamp: str
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)

    def to_embedding_text(self) -> str:
        return f"[{self.category}] {self.content}"


@dataclass
class MemoryQuery:
    \"\"\"Query for retrieving memories.\"\"\"
    query: str
    types: list[MemoryType] = field(default_factory=lambda: list(MemoryType))
    categories: Optional[list[str]] = None
    limit: int = 5
    min_confidence: float = 0.5
```

---

## 7. Skill Module

### 7.1 File
`src/mazyr/domain/skills.py`

### 7.2 Entities

```python
@dataclass
class Skill:
    \"\"\"A learned capability.\"\"\"
    name: str
    description: str
    category: str
    content: str
    version: str = "1.0"
    created_at: str = ""
    updated_at: str = ""
    usage_count: int = 0
    success_rate: float = 1.0

    def record_usage(self, success: bool):
        self.usage_count += 1
        alpha = 0.1
        self.success_rate = (1 - alpha) * self.success_rate + alpha * (1.0 if success else 0.0)


@dataclass
class SkillEvolution:
    \"\"\"Log of how a skill has evolved over time.\"\"\"
    skill_name: str
    events: list[dict] = field(default_factory=list)

    def add_event(self, event_type: str, description: str, timestamp: str):
        self.events.append({
            "type": event_type,
            "description": description,
            "timestamp": timestamp
        })
```

---

## 8. Domain Events

### 8.1 File
`src/mazyr/domain/events.py`

### 8.2 Entities

```python
@dataclass(frozen=True)
class DomainEvent:
    \"\"\"Base class for domain events.\"\"\"
    event_type: str
    timestamp: str
    payload: dict


@dataclass(frozen=True)
class MessageReceived(DomainEvent):
    \"\"\"Event: A message has been received.\"\"\"
    message: Message


@dataclass(frozen=True)
class FilterTriggered(DomainEvent):
    \"\"\"Event: Integrity filter has triggered.\"\"\"
    result: FilterResult
    original_message: str


@dataclass(frozen=True)
class ConstitutionViolated(DomainEvent):
    \"\"\"Event: An action violated the constitution.\"\"\"
    result: ValidationResult
    action: str
    context: dict
```
