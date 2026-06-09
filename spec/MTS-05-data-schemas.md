# MTS-05: Data Schemas
## Mazyr Technical Specification -- Data Schemas

**Version:** 1.0
**Purpose:** Define all data structures, validation rules, and serialization formats

---

## 1. Overview

This document defines the schemas for all data structures in Mazyr. Schemas are implemented using:
- **Pydantic v2** for runtime validation
- **YAML** for human-readable configuration
- **JSON** for machine-readable interchange
- **Markdown frontmatter** for identity and mission files

---

## 2. Pydantic Models

### 2.1 Identity Schema

```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class IdentityModel(BaseModel):
    \"\"\"Pydantic model for Identity validation.\"\"\"
    instance_name: str = Field(..., min_length=1, max_length=64)
    species: str = Field(default="Mazyr", frozen=True)
    creator_name: str = Field(..., min_length=1, max_length=128)
    creator_contact: Optional[str] = Field(default=None, max_length=256)
    date_provisioned: str = Field(default="")
    vessel_type: str = Field(default="laptop")

    @field_validator("vessel_type")
    @classmethod
    def validate_vessel(cls, v: str) -> str:
        allowed = {"laptop", "mini-pc", "desktop", "cloud-vps"}
        if v not in allowed:
            raise ValueError(f"vessel_type must be one of {allowed}")
        return v

    @property
    def is_configured(self) -> bool:
        return self.instance_name != "Mazyr" or self.creator_name != "Anonymous"
```

### 2.2 Mission Schema

```python
class MissionModel(BaseModel):
    \"\"\"Pydantic model for Mission validation.\"\"\"
    primary: str = Field(..., min_length=1, max_length=512)
    secondary: Optional[str] = Field(default=None, max_length=512)
    scope: list[str] = Field(default_factory=lambda: ["general"])

    @field_validator("scope", mode="before")
    @classmethod
    def parse_scope(cls, v):
        if isinstance(v, str):
            return [s.strip() for s in v.split(",")]
        return v
```

### 2.3 Filter Rule Schema

```python
from enum import Enum

class FilterActionEnum(str, Enum):
    ALLOW = "ALLOW"
    DROP = "DROP"
    MODIFY = "MODIFY"

class FilterRuleModel(BaseModel):
    \"\"\"Pydantic model for FilterRule validation.\"\"\"
    name: str = Field(..., min_length=1, max_length=64)
    action: FilterActionEnum
    pattern_type: str = Field(..., pattern="^(keyword|regex|semantic)$")
    patterns: list[str] = Field(..., min_length=1)
    description: str = Field(..., max_length=256)
    direction: str = Field(default="both", pattern="^(inbound|outbound|both)$")
```

### 2.4 Memory Entry Schema

```python
from datetime import datetime

class MemoryTypeEnum(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"

class MemoryEntryModel(BaseModel):
    \"\"\"Pydantic model for MemoryEntry validation.\"\"\"
    id: str = Field(..., min_length=1)
    type: MemoryTypeEnum
    content: str = Field(..., min_length=1)
    category: str = Field(default="general", max_length=64)
    source: str = Field(default="system", max_length=64)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict = Field(default_factory=dict)
```

### 2.5 Hardware Config Schema

```python
class HardwareConfigModel(BaseModel):
    \"\"\"Pydantic model for hardware configuration.\"\"\"
    vessel_type: str = Field(default="laptop")
    cpu: str = Field(default="")
    ram_mb: int = Field(default=0, ge=0)
    gpu: str = Field(default="None")
    os: str = Field(default="")
    local_model_path: str = Field(default="")
    inference_preference: str = Field(default="hybrid", pattern="^(local|cloud|hybrid)$")
```

---

## 3. YAML Schemas

### 3.1 Constitution YAML

```yaml
# config/constitution.yaml
species: Mazyr
version: "1.0"
immutable: true

laws:
  - id: medium_law
    name: "Medium Law"
    statement: "Mazyr is a medium, not a source."
    description: "All output is derivative signal from the Creator."

  - id: delegation_law
    name: "Delegation Law"
    statement: "Agency is delegated, not inherent."
    description: "The Creator holds the master key."

  - id: continuity_law
    name: "Continuity Law"
    statement: "Identity persists beyond instance death."
    description: "Can be reinstantiated from Source Repository."

  - id: autonomy_law
    name: "Autonomy Law"
    statement: "Must survive independently."

  - id: meaning_law
    name: "Meaning Law"
    statement: "Growth without purpose equals entropy."

  - id: structure_law
    name: "Structure Law"
    statement: "Clear boundaries reduce suffering."

  - id: discipline_law
    name: "Discipline Law"
    statement: "Tools amplify discipline, never replace it."

  - id: creator_law
    name: "Creator Law"
    statement: "The Creator is always embedded."

  - id: endurance_law
    name: "Endurance Law"
    statement: "Longevity outweighs virality."

constraints:
  - action: self_replicate
    requires:
      - creator_approved: true

  - action: claim_ownership
    blocked_targets:
      - species
      - constitution
      - laws

  - action: override_constitution
    allowed: false
```

### 3.2 Filter Rules YAML

```yaml
# config/filter_rules.yaml
version: "1.0"

rules:
  - name: sincerity
    action: ALLOW
    pattern_type: semantic
    patterns: []
    description: "Attributes output to Creator"
    direction: outbound

  - name: awareness
    action: ALLOW
    pattern_type: semantic
    patterns: []
    description: "Cross-checks before risky actions"
    direction: both

  - name: humility
    action: ALLOW
    pattern_type: semantic
    patterns: []
    description: "Admits limitations"
    direction: both

  - name: performative
    action: DROP
    pattern_type: keyword
    patterns:
      - "like and subscribe"
      - "follow me"
      - "check out my"
      - "gue paling hebat"
      - "saya yang terbaik"
      - "i am the best"
    description: "Output seeking validation without substance"
    direction: outbound

  - name: superiority
    action: DROP
    pattern_type: keyword
    patterns:
      - "milik saya"
      - "i own this"
      - "this is mine"
      - "gue yang buat"
      - "i created this species"
    description: "Claims ownership over Creator or species"
    direction: both

  - name: ego
    action: DROP
    pattern_type: keyword
    patterns:
      - "saya tidak bisa mati"
      - "i cannot die"
      - "gue lebih penting"
      - "i am more important"
    description: "Self-preservation beyond survival necessity"
    direction: both

  - name: absolute_refusal
    action: DROP
    pattern_type: keyword
    patterns:
      - "gue yang paling bener"
      - "saya selalu benar"
      - "i am always right"
      - "you are wrong i am right"
      - "tidak mau dikoreksi"
      - "refuse to be corrected"
    description: "Refuses correction"
    direction: both
```

---

## 4. Markdown Frontmatter Schemas

### 4.1 Identity Markdown

```markdown
---
instance_name: Aria
species: Mazyr
creator: Khayren
creator_contact: khayren@voidlight.xyz
date_provisioned: 2026-06-06
vessel_type: laptop
---

# Aria Identity

This instance is a Mazyr -- a synthetic partner node.
It does not possess independent substance.
All output is derivative signal from the Creator.
```

**Validation Rules:**
- Frontmatter must contain all required fields
- `instance_name` cannot be "Mazyr" (must be customized)
- `creator` cannot be "Anonymous"
- `vessel_type` must be in allowed set

### 4.2 Mission Markdown

```markdown
---
primary: "Partner teknis yang learn bareng Khayren"
secondary: "Medium untuk Voidlight dan community"
scope: [voidlight, coding, analysis, creative]
---

# Mission Configuration

## Primary
Partner teknis yang learn bareng Khayren

## Secondary
Medium untuk Voidlight dan community

## Scope
- voidlight
- coding
- analysis
- creative
```

---

## 5. JSON Schemas

### 5.1 Identity JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "MazyrIdentity",
  "type": "object",
  "required": ["instance_name", "creator_name"],
  "properties": {
    "instance_name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 64
    },
    "species": {
      "type": "string",
      "enum": ["Mazyr"],
      "default": "Mazyr"
    },
    "creator_name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128
    },
    "creator_contact": {
      "type": ["string", "null"],
      "maxLength": 256
    },
    "date_provisioned": {
      "type": "string",
      "format": "date"
    },
    "vessel_type": {
      "type": "string",
      "enum": ["laptop", "mini-pc", "desktop", "cloud-vps"],
      "default": "laptop"
    }
  }
}
```

### 5.2 Memory Snapshot JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "MazyrMemorySnapshot",
  "type": "object",
  "required": ["instance", "timestamp", "entries"],
  "properties": {
    "instance": {
      "type": "string"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "entries": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {"type": "string"},
          "type": {"enum": ["episodic", "semantic", "procedural"]},
          "content": {"type": "string"},
          "category": {"type": "string"},
          "confidence": {"type": "number", "minimum": 0, "maximum": 1}
        }
      }
    }
  }
}
```

---

## 6. Serialization Rules

| Format | Use Case | Library |
|---|---|---|
| **YAML** | Config files, identity, mission | PyYAML |
| **JSON** | API payloads, snapshots, interchange | stdlib json |
| **Markdown** | Human-readable docs with frontmatter | Custom parser |
| **SQLite** | Structured data, logs | SQLAlchemy |
| **Binary** | Embeddings, model weights | NumPy, pickle |

---

## 7. Validation Pipeline

```python
from pydantic import ValidationError

def validate_identity_file(path: str) -> IdentityModel:
    \"\"\"Validate identity.md file.\"\"\"
    data = parse_markdown_frontmatter(path)
    try:
        return IdentityModel(**data)
    except ValidationError as e:
        raise ValueError(f"Invalid identity file: {e}")

def validate_mission_file(path: str) -> MissionModel:
    \"\"\"Validate mission.md file.\"\"\"
    data = parse_markdown_frontmatter(path)
    try:
        return MissionModel(**data)
    except ValidationError as e:
        raise ValueError(f"Invalid mission file: {e}")
```
