# MTS-08: Memory Mechanism (Mem0-Equivalent)

## Overview

Memory di Mazyr bukan cuma database yang nyimpen chat history. Memory adalah **layered intelligence system** yang memungkinkan Aria:

1. **Ingat** percakapan 3 bulan lalu (Episodic)
2. **Tahu** preferensi lo tanpa di-remind (Semantic)
3. **Bisa** handle task dengan SOP yang pernah dipelajari (Procedural)
4. **Mengerti** relasi antar entitas (Graph)
5. **Auto-inject** context relevan ke setiap LLM call tanpa explicit query (Auto-Context)

**Reference:** Mem0 (mem0.ai) --- tapi implementasi custom, zero vendor lock-in.

---

## 1. Memory Philosophy

### 1.1 The 5-Tier Stack

```
Tier 1: Working Memory      (RAM, ephemeral, in-context)
    | flush every session
Tier 2: Episodic Memory     (SQLite, time-indexed, raw)
    | consolidate nightly
Tier 3: Semantic Memory     (Qdrant, vector-indexed, facts)
    | deduplicate weekly
Tier 4: Graph Memory      (SQLite + Qdrant, entities + relasi)
    | prune monthly
Tier 5: Procedural Memory (File-based, skills + SOPs)
    | version controlled
```

**Key Insight:** Tiap tier punya lifecycle berbeda. Working memory hidup detik, procedural memory abadi.

### 1.2 Memory = Signal, Not Data

Dalam framework Mazyr, memory bukan data yang disimpan tapi **signal yang diperkuat atau diperlemah**:

- **Reinforcement:** Memory yang sering di-retrieve -> importance score naik
- **Decay:** Memory yang jarang diakses -> score turun -> consolidate ke ringkasan -> archive
- **Interference:** Memory baru yang kontradiksi memory lama -> flag untuk Creator review

---

## 2. Memory Architecture

### 2.1 Tier 1: Working Memory (Ephemeral)

**Storage:** In-memory Python dict / Redis
**Scope:** Single session / Single turn
**TTL:** Auto-clear setelah 30 menit idle atau session end
**Purpose:** Scratchpad untuk reasoning chain, tool results, intermediate calculations

```python
# src/mazyr/domain/memory_tier1.py
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime

@dataclass
class WorkingMemoryEntry:
    key: str
    value: Any
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    ttl_seconds: int = 1800
    access_count: int = 0

    def touch(self):
        self.access_count += 1
        self.created_at = datetime.now().isoformat()
```

### 2.2 Tier 2: Episodic Memory (Raw Experience)

**Storage:** SQLite
**Schema:** Pydantic validated
**Index:** session_id, timestamp, role
**Retention:** 90 hari raw, setelah itu di-consolidate ke Tier 3
**Purpose:** Kemarin kita ngobrolin apa?

```python
# src/mazyr/domain/memory_tier2.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class MessageRole(str, Enum):
    USER = 'user'
    ASSISTANT = 'assistant'
    SYSTEM = 'system'
    TOOL = 'tool'

@dataclass
class EpisodicEntry:
    id: str
    session_id: str
    role: MessageRole
    content: str
    timestamp: str
    tool_calls: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    extracted_facts: list[str] = field(default_factory=list)
    importance_score: float = 0.5

    def to_embedding_text(self) -> str:
        return f"[{self.role}] {self.content}"
```

**SQLite Schema:**
```sql
CREATE TABLE episodic_memory (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT CHECK(role IN ('user','assistant','system','tool')),
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    tool_calls TEXT,
    metadata TEXT,
    extracted_facts TEXT,
    importance_score REAL DEFAULT 0.5,
    consolidated BOOLEAN DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_episodic_session ON episodic_memory(session_id, timestamp);
CREATE INDEX idx_episodic_consolidated ON episodic_memory(consolidated) WHERE consolidated = 0;
```

### 2.3 Tier 3: Semantic Memory (Facts & Preferences)

**Storage:** Qdrant (vector) + SQLite (metadata)
**Schema:** Pydantic + Embeddings
**Index:** Cosine similarity + category + entity_tags
**Retention:** Permanent (kecuali explicitly deleted oleh Creator)
**Purpose:** Khayren pake Nuxt 4. Khayren suka kopi pake madu.

```python
# src/mazyr/domain/memory_tier3.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class MemoryCategory(str, Enum):
    PREFERENCE = 'preference'
    FACT = 'fact'
    SKILL = 'skill'
    RELATIONSHIP = 'relationship'
    GOAL = 'goal'
    CONSTRAINT = 'constraint'

@dataclass
class SemanticEntry:
    id: str
    content: str
    category: MemoryCategory
    embedding: Optional[list[float]] = None
    vector_id: Optional[str] = None
    source_session_id: Optional[str] = None
    source_message_id: Optional[str] = None
    confidence: float = 0.8
    importance_score: float = 0.5
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_accessed: str = field(default_factory=lambda: datetime.now().isoformat())
    access_count: int = 0
    decay_rate: float = 0.01
    duplicate_of: Optional[str] = None

    def touch(self):
        self.access_count += 1
        self.last_accessed = datetime.now().isoformat()
        self.importance_score = min(1.0, self.importance_score + 0.02)

    def apply_decay(self, days_elapsed: int) -> float:
        return max(0.1, self.importance_score * (1 - self.decay_rate) ** days_elapsed)
```

**Qdrant Collection Schema:**
- Collection: mazyr_semantic_memory
- Vector size: 384 (all-MiniLM) atau 1024 (BGE) --- auto-detect
- Distance: COSINE
- Payload fields (indexed): category, importance_score, created_at, entity_tags, source_session_id

### 2.4 Tier 4: Graph Memory (Entities & Relations)

**Storage:** SQLite (nodes + edges) + Qdrant (node embeddings)
**Purpose:** Khayren adalah CTO Doctic. Doctic adalah startup.
**Query:** Graph traversal untuk inferensi relasi

```python
# src/mazyr/domain/memory_tier4.py
@dataclass
class GraphNode:
    id: str
    label: str
    node_type: str
    embedding: Optional[list[float]] = None
    first_seen: str = field(default_factory=lambda: datetime.now().isoformat())
    last_mentioned: str = field(default_factory=lambda: datetime.now().isoformat())
    mention_count: int = 1

@dataclass
class GraphEdge:
    id: str
    source_id: str
    target_id: str
    relation: str
    confidence: float = 0.8
    source_session_id: Optional[str] = None
    first_seen: str = field(default_factory=lambda: datetime.now().isoformat())
```

**SQLite Schema:**
```sql
CREATE TABLE graph_nodes (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    node_type TEXT NOT NULL,
    embedding_id TEXT,
    first_seen TEXT,
    last_mentioned TEXT,
    mention_count INTEGER DEFAULT 1
);

CREATE TABLE graph_edges (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES graph_nodes(id),
    target_id TEXT NOT NULL REFERENCES graph_nodes(id),
    relation TEXT NOT NULL,
    confidence REAL DEFAULT 0.8,
    source_session_id TEXT,
    first_seen TEXT
);

CREATE INDEX idx_edge_source ON graph_edges(source_id);
CREATE INDEX idx_edge_target ON graph_edges(target_id);
CREATE INDEX idx_edge_relation ON graph_edges(relation);
```

### 2.5 Tier 5: Procedural Memory

**Storage:** File system (skills/) + Git version control
**Purpose:** Cara handle Vision client: brief -> parse -> generate -> validate -> save
**Already covered in MTS-09.**

---
## 3. Memory Lifecycle

### 3.1 Flow: User Message -> Memory

```
User Message
    |
[1] Working Memory: Store raw message + context
    |
[2] Episodic Memory: Persist ke SQLite (raw log)
    |
[3] Extraction Engine (LLM call):
    |-- Extract facts -> Semantic Memory (Qdrant + SQLite)
    |-- Extract entities -> Graph Memory (SQLite)
    |-- Update importance scores
    |
[4] Deduplication Check:
    |-- Similar fact exists? -> Update existing, jangan insert baru
    |-- New fact? -> Insert + embed
    |
[5] Auto-Context Update:
    |-- Refresh Creator Profile cache
```

### 3.2 Extraction Engine

**Task:** Dari setiap conversation turn, extract facts dan entities.

```python
# src/mazyr/app/memory_extraction.py
from typing import list
from mazyr.domain.memory_tier2 import EpisodicEntry
from mazyr.domain.memory_tier3 import SemanticEntry, MemoryCategory
from mazyr.domain.memory_tier4 import GraphNode, GraphEdge

class MemoryExtractionEngine:
    def __init__(self, llm_router, embedding_provider):
        self.llm = llm_router
        self.embedder = embedding_provider

    def extract_from_message(self, entry: EpisodicEntry) -> ExtractionResult:
        prompt = f"""
Extract facts and entities from this conversation turn.

Role: {entry.role}
Content: {entry.content}

Rules:
1. Extract only objective facts and preferences
2. Each fact must be standalone
3. Identify entities (people, organizations, technologies, concepts)
4. Identify relations between entities

Output JSON:
{
    "facts": [{"content": "...", "category": "...", "confidence": 0.0-1.0}],
    "entities": [{"label": "...", "type": "..."}],
    "relations": [{"source": "...", "target": "...", "relation": "..."}]
}
"""
        response = self.llm.generate(prompt, complexity="complex")
        extracted = json.loads(response)
        # Convert ke domain objects...
        return ExtractionResult(...)
```

**Key Design:** Extraction pake **cloud LLM** (GPT-5.5) karena butuh reasoning complex. Ini 1 call per message, tapi bisa di-batch untuk session recap.

### 3.3 Deduplication Engine

**Problem:** Khayren pake Nuxt 4 di-insert 5x dari 5 session berbeda.

**Solution:** Before insert semantic entry, check similarity dengan existing:

```python
# src/mazyr/app/memory_dedup.py

class MemoryDeduplicator:
    def __init__(self, qdrant_adapter, similarity_threshold=0.95):
        self.qdrant = qdrant_adapter
        self.threshold = similarity_threshold

    def deduplicate(self, new_entry: SemanticEntry) -> DeduplicationResult:
        similar = self.qdrant.search_similar(
            vector=new_entry.embedding,
            filter={"category": new_entry.category.value},
            limit=5,
            score_threshold=self.threshold,
        )
        if similar:
            existing = similar[0]
            existing.touch()
            existing.confidence = max(existing.confidence, new_entry.confidence)
            return DeduplicationResult(action="merged", canonical_id=existing.id)
        return DeduplicationResult(action="insert", canonical_id=new_entry.id)
```

---

## 4. Auto-Context Injection (Mem0 Killer Feature)

### 4.1 Problem

Tanpa auto-context, lo harus manual query memory tiap kali:
```python
# Manual (ribet)
memories = memory.search("Khayren tech stack")
prompt = f"Context: {memories}\nUser: {message}"
```

### 4.2 Solution: Transparent Context Assembly

Setiap LLM call, Mazyr **otomatis** assemble context dari semua tier:

```python
# src/mazyr/app/context_assembler.py

class ContextAssembler:
    TOKEN_BUDGETS = {
        "working": 500,
        "semantic": 1500,
        "episodic": 1000,
        "graph": 500,
        "procedural": 500,
    }

    def __init__(self, memory_system, embedding_provider):
        self.memory = memory_system
        self.embedder = embedding_provider

    def assemble(self, user_message: str, current_session_id: str) -> str:
        parts = []
        
        # 1. Working Memory (Tier 1) --- most recent, highest priority
        working = self.memory.working.get_all()
        if working:
            parts.append(self._format_working(working))
        
        # 2. Semantic Memory (Tier 3) --- facts relevant to query
        query_embedding = self.embedder.embed(user_message)
        semantic = self.memory.semantic.search(
            vector=query_embedding,
            limit=10,
            min_importance=0.3,
        )
        preferences = [s for s in semantic if s.category == MemoryCategory.PREFERENCE]
        facts = [s for s in semantic if s.category != MemoryCategory.PREFERENCE]
        
        if preferences:
            parts.append(self._format_preferences(preferences[:5]))
        if facts:
            parts.append(self._format_facts(facts[:10]))
        
        # 3. Episodic Memory (Tier 2) --- recent sessions yang relevan
        episodic = self.memory.episodic.search_relevant(
            query=user_message,
            session_id=current_session_id,
            limit=5,
            lookback_days=7,
        )
        if episodic:
            parts.append(self._format_episodic(episodic))
        
        # 4. Graph Memory (Tier 4) --- entity context
        entities = self._extract_entities_from_message(user_message)
        if entities:
            graph_context = self.memory.graph.get_subgraph(entities, depth=2)
            parts.append(self._format_graph(graph_context))
        
        # 5. Procedural Memory (Tier 5) --- active skill context
        active_skill = self.memory.working.get("active_skill")
        if active_skill:
            skill_context = self.memory.procedural.get_skill_context(active_skill)
            parts.append(self._format_procedural(skill_context))
        
        return "\n\n".join(parts)
    
    def _format_preferences(self, prefs: list[SemanticEntry]) -> str:
        lines = ["## Creator Preferences"]
        for p in prefs:
            lines.append(f"- {p.content}")
        return "\n".join(lines)
    
    def _format_facts(self, facts: list[SemanticEntry]) -> str:
        lines = ["## Known Facts"]
        for f in facts:
            lines.append(f"- {f.content} (confidence: {f.confidence:.0%})")
        return "\n".join(lines)
    
    def _format_episodic(self, episodes: list[EpisodicEntry]) -> str:
        lines = ["## Recent Relevant Conversations"]
        for e in episodes:
            lines.append(f"- [{e.timestamp}] {e.role}: {e.content[:100]}...")
        return "\n".join(lines)
    
    def _format_graph(self, subgraph) -> str:
        lines = ["## Entity Context"]
        for node in subgraph.nodes:
            lines.append(f"- {node.label} ({node.node_type})")
        for edge in subgraph.edges:
            lines.append(f"  -> {edge.relation} -> {edge.target_id}")
        return "\n".join(lines)
```

### 4.3 Integration dengan Chat Use Case

```python
# src/mazyr/app/chat.py --- modified

class ChatUseCase:
    def __init__(self, ..., context_assembler: ContextAssembler):
        ...
        self.context_assembler = context_assembler
    
    def receive(self, message: str, session_id: str) -> str:
        # 1. Assemble context
        memory_context = self.context_assembler.assemble(message, session_id)
        
        # 2. Build full prompt
        system_prompt = self._build_system_prompt(memory_context)
        
        # 3. LLM call dengan context
        response = self.llm.generate(
            system=system_prompt,
            user=message,
        )
        
        # 4. Log ke Episodic
        self.memory.episodic.add(EpisodicEntry(...))
        
        # 5. Extract facts (async / background)
        self.extraction_queue.submit(message, session_id)
        
        return response
```

---
## 5. Memory Consolidation (Nightly Ritual)

### 5.1 What

Tiap hari jam 3 pagi, Mazyr jalankan **consolidation ritual**:

1. **Episodic -> Semantic:** Summarize 24h conversation jadi facts
2. **Decay Application:** Turunin importance score untuk memory yang nggak diakses
3. **Archive:** Episodic entries > 90 hari di-archive ke file (bukan delete)
4. **Graph Pruning:** Hapus entity nodes dengan mention_count < 3 dan no edges
5. **Deduplication Pass:** Scan semantic memory untuk duplicates

### 5.2 Implementation

```python
# src/mazyr/app/memory_consolidation.py

class ConsolidationRitual:
    def __init__(self, memory_system, llm_router):
        self.memory = memory_system
        self.llm = llm_router
    
    def run(self):
        # 1. Summarize unconsolidated episodic entries
        unconsolidated = self.memory.episodic.get_unconsolidated(since="24h")
        if unconsolidated:
            summary = self._summarize_sessions(unconsolidated)
            for fact in summary.facts:
                self.memory.semantic.add(fact)
            self.memory.episodic.mark_consolidated([e.id for e in unconsolidated])
        
        # 2. Apply decay
        old_memories = self.memory.semantic.get_stale(threshold_days=7)
        for mem in old_memories:
            new_score = mem.apply_decay(days_elapsed=7)
            if new_score < 0.2:
                mem.decay_rate *= 2
            self.memory.semantic.update_importance(mem.id, new_score)
        
        # 3. Archive old episodic
        ancient = self.memory.episodic.get_older_than(days=90)
        self.memory.episodic.archive_to_file(ancient, path="~/.mazyr/memory/archive/")
        
        # 4. Prune graph orphans
        orphans = self.memory.graph.get_orphan_nodes(min_mentions=3)
        self.memory.graph.delete_nodes(orphans)
        
        # 5. Deduplication sweep
        duplicates = self.memory.semantic.find_duplicates(threshold=0.95)
        for dup in duplicates:
            self.memory.semantic.merge(dup.canonical_id, dup.duplicate_ids)
    
    def _summarize_sessions(self, entries: list[EpisodicEntry]) -> SummaryResult:
        conversation_text = "\n".join([f"[{e.role}] {e.content}" for e in entries])
        prompt = f"""
Summarize this conversation into standalone facts.

Conversation:
{conversation_text}

Rules:
1. Each fact must be self-contained
2. Focus on: preferences, decisions, facts, goals
3. Ignore: greetings, filler, temporary context
4. Output JSON array of facts

Output: [{{"content": "...", "category": "preference|fact|goal|constraint"}}]
"""
        response = self.llm.generate(prompt, complexity="complex")
        return SummaryResult(facts=json.loads(response))
```

---

## 6. Creator Profile (Special Semantic Section)

### 6.1 Concept

Creator Profile adalah **subset dari Semantic Memory** yang selalu di-prioritize dan nggak di-decay:

```python
# src/mazyr/domain/creator_profile.py

class CreatorProfile:
    CORE_FACTS = [
        MemoryCategory.PREFERENCE,
        MemoryCategory.CONSTRAINT,
        MemoryCategory.GOAL,
    ]
    
    def __init__(self, semantic_memory):
        self.semantic = semantic_memory
    
    def get(self) -> list[SemanticEntry]:
        return self.semantic.search(
            filter={"category": [c.value for c in self.CORE_FACTS]},
            min_importance=0.0,
            limit=50,
        )
    
    def add(self, entry: SemanticEntry):
        entry.decay_rate = 0.0
        entry.importance_score = 1.0
        self.semantic.add(entry)
```

**Contoh Creator Profile:**
- Khayren adalah CTO Doctic (fact, permanent)
- Khayren pake Nuxt 4 untuk frontend (preference, permanent)
- Khayren punya 3 anak (fact, permanent)
- Khayren nggak suka shallow symbolic thinking (preference, permanent)

---

## 7. Implementation Roadmap

### Phase A: Foundation (Week 1)

**Day 1:** Implement `memory_tier2.py` (Episodic) + SQLite schema
**Day 2:** Implement `memory_tier3.py` (Semantic) + Qdrant schema
**Day 3:** Implement `memory_tier4.py` (Graph) + SQLite schema
**Day 4:** Implement `memory_tier1.py` (Working) + in-memory store
**Day 5:** Wire all tiers ke `MemorySystem` facade
**Day 6:** Test: insert -> retrieve -> cross-tier query
**Day 7:** Lock Phase A

### Phase B: Extraction (Week 2)

**Day 1-2:** Implement `memory_extraction.py` (pake GPT-5.5)
**Day 3:** Implement `memory_dedup.py`
**Day 4:** Integrate extraction ke ChatUseCase (background queue)
**Day 5:** Test extraction accuracy
**Day 6:** Tune prompt untuk extraction
**Day 7:** Lock Phase B

### Phase C: Auto-Context (Week 3)

**Day 1-2:** Implement `context_assembler.py`
**Day 3:** Token budgeting + truncation
**Day 4:** Integration dengan ChatUseCase
**Day 5:** Test: Khayren pake apa? -> auto-retrieve Nuxt 4 fact
**Day 6:** Performance test (context assembly < 200ms)
**Day 7:** Lock Phase C

### Phase D: Consolidation (Week 4)

**Day 1-2:** Implement `memory_consolidation.py`
**Day 3:** Cron job / systemd timer untuk jam 3 pagi
**Day 4:** Archive mechanism
**Day 5:** Decay tuning
**Day 6:** E2E test: 7 hari conversation -> consolidated facts
**Day 7:** Lock Phase D

---

## 8. GPT-5.5 Specific Considerations

### 8.1 Extraction Call Optimization

GPT-5.5 via API = bayar per token. Extraction tiap message bisa mahal kalau nggak di-optimize:

```python
# Optimization: Batch extraction per session, bukan per message

class BatchedExtraction:
    def __init__(self, batch_size=5, max_wait_seconds=30):
        self.batch = []
        self.batch_size = batch_size
        self.max_wait = max_wait_seconds
    
    def submit(self, entry: EpisodicEntry):
        self.batch.append(entry)
        if len(self.batch) >= self.batch_size:
            self._flush()
    
    def _flush(self):
        if not self.batch:
            return
        combined = "\n\n".join([f"[{e.role}] {e.content}" for e in self.batch])
        facts = self.llm.extract_facts(combined)
        self.memory.semantic.add_batch(facts)
        self.batch = []
```

### 8.2 Context Assembly untuk GPT-5.5

GPT-5.5 support context window besar (128K+), tapi **cost naik linear**. Budget untuk memory context:

```python
GPT55_CONTEXT_BUDGET = {
    "max_total_tokens": 128000,
    "reserve_for_output": 4000,
    "reserve_for_user_message": 2000,
    "reserve_for_system": 1000,
    "available_for_memory": 121000,
}
```

Dengan budget segini, lo bisa inject **banyak** memory. Tapi tetap prioritize:
1. Creator Profile (always top)
2. Semantic facts dengan importance > 0.7
3. Recent episodic (7 hari)
4. Working memory

### 8.3 Fallback: Local Extraction

Kalau GPT-5.5 API down / rate limited, fallback ke local Gemma 4 dengan extraction prompt yang lebih simple:

```python
class ExtractionFallback:
    def extract(self, message: str) -> list[SemanticEntry]:
        facts = []
        for pattern in [r"(\w+) adalah (.+)", r"(\w+) pake (.+)", r"(\w+) suka (.+)"]:
            matches = re.findall(pattern, message)
            for m in matches:
                facts.append(SemanticEntry(
                    content=f"{m[0]} {m[1]}",
                    category=MemoryCategory.FACT,
                    confidence=0.6,
                ))
        return facts
```

---

## 9. Testing Strategy

### 9.1 Unit Tests

```python
# tests/memory/test_dedup.py
def test_dedup_merge_similar():
    existing = SemanticEntry(id="1", content="Khayren pake Nuxt 4", embedding=[0.1, 0.2])
    new = SemanticEntry(id="2", content="Khayren menggunakan Nuxt 4", embedding=[0.11, 0.21])
    result = deduplicator.deduplicate(new)
    assert result.action == "merged"
    assert result.canonical_id == "1"
```

### 9.2 Integration Tests

```python
# tests/memory/test_context_assembly.py
def test_assemble_retrieves_creator_preferences():
    memory.semantic.add(SemanticEntry(
        content="Khayren pake Nuxt 4",
        category=MemoryCategory.PREFERENCE,
        importance_score=1.0,
    ))
    context = assembler.assemble("Tech stack gue apa?", session_id="test")
    assert "Nuxt 4" in context
```

### 9.3 E2E Tests

```python
# tests/e2e/test_memory_flow.py
def test_full_memory_lifecycle():
    chat.receive("Gue pake Nuxt 4 untuk project baru", session_id="s1")
    time.sleep(2)
    facts = memory.semantic.search("Nuxt 4")
    assert any("Nuxt 4" in f.content for f in facts)
    response = chat.receive("Tech stack gue apa?", session_id="s2")
    assert "Nuxt 4" in response
```

---

## 10. Next Steps

1. **Phase A:** Start dengan Tier 2 (Episodic) + Tier 3 (Semantic) --- lo udah punya ini
2. **Phase B:** Implement Extraction Engine --- pake GPT-5.5, batch per session
3. **Phase C:** Auto-Context Assembly --- ini yang bikin Mazyr inget tanpa di-remind
4. **Phase D:** Consolidation Ritual --- cron job jam 3 pagi

**Lo mau gue generate starter code untuk Phase A (Tier 1 + MemorySystem facade)?** Atau lo mau fokus ke Phase B (Extraction Engine) karena Tier 2-3 udah ada?

---

*MTS-10 v1.0 | Mazyr Technical Specification | Memory Mechanism*
