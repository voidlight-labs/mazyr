import json
import re
from datetime import datetime
from typing import Optional

from mazyr.domain.memory_episodic import EpisodicEntry
from mazyr.domain.memory_extraction import ExtractionResult
from mazyr.domain.memory_graph import GraphEdge, GraphNode
from mazyr.domain.memory_semantic import MemoryCategory, SemanticEntry
from mazyr.infrastructure.logger import get_logger

log = get_logger("memory.extraction")

EXTRACTION_PROMPT = """Extract facts, entities, and relations from this conversation turn.

Role: {role}
Content: {content}

Rules:
1. Extract only objective facts and preferences
2. Each fact must be standalone and self-contained
3. Identify entities (people, organizations, technologies, concepts)
4. Identify relations between entities
5. category must be one of: preference, fact, skill, relationship, goal, constraint

Output valid JSON only (no markdown):
{{
    "facts": [{{"content": "...", "category": "fact", "confidence": 0.9}}],
    "entities": [{{"label": "...", "type": "person|organization|technology|concept"}}],
    "relations": [{{"source": "...", "target": "...", "relation": "..."}}]
}}"""

BATCH_PROMPT = """Extract facts, entities, and relations from these conversation turns.

Conversation:
{conversation}

Rules:
1. Extract only objective facts and preferences that are NEW or SIGNIFICANT
2. Each fact must be standalone
3. Identify entities and relations
4. category must be one of: preference, fact, skill, relationship, goal, constraint

Output valid JSON only:
{{
    "facts": [{{"content": "...", "category": "fact", "confidence": 0.9}}],
    "entities": [{{"label": "...", "type": "person|organization|technology|concept"}}],
    "relations": [{{"source": "...", "target": "...", "relation": "..."}}]
}}"""


class MemoryExtractionEngine:
    def __init__(self, llm_router):
        self.llm = llm_router

    def extract_from_entry(self, entry: EpisodicEntry) -> ExtractionResult:
        prompt = EXTRACTION_PROMPT.format(
            role=entry.role.value,
            content=entry.content,
        )
        return self._call_and_parse(prompt, entry)

    def extract_from_batch(self, entries: list[EpisodicEntry]) -> ExtractionResult:
        combined = "\n\n".join(f"[{e.role.value}] {e.content}" for e in entries)
        prompt = BATCH_PROMPT.format(conversation=combined)
        return self._call_and_parse(prompt, entries[0] if entries else None)

    def _call_and_parse(self, prompt: str, ref_entry: Optional[EpisodicEntry]) -> ExtractionResult:
        try:
            raw = self.llm.generate(prompt, complexity="complex")
        except Exception as e:
            log.warning("Extraction LLM call failed: %s", e)
            return ExtractionResult()

        data = self._try_parse_json(raw)
        if data is None:
            log.warning("Extraction JSON parse failed, raw=%s", raw[:200])
            return ExtractionResult()

        session_id = ref_entry.session_id if ref_entry else None
        return self._build_result(data, session_id)

    def _try_parse_json(self, raw: str) -> Optional[dict]:
        # Try parsing directly first
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        # Try extracting JSON from markdown code blocks
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return None

    def _build_result(self, data: dict, session_id: Optional[str]) -> ExtractionResult:
        now = datetime.now().isoformat()
        facts = []
        for f in data.get("facts", []):
            try:
                cat = MemoryCategory(f.get("category", "fact"))
            except ValueError:
                cat = MemoryCategory.FACT
            facts.append(
                SemanticEntry(
                    id=f"ext_{datetime.now().timestamp()}_{hash(f['content']) & 0xFFFF}",
                    content=f["content"],
                    category=cat,
                    confidence=f.get("confidence", 0.8),
                    source_session_id=session_id,
                    created_at=now,
                    last_accessed=now,
                )
            )

        entities = []
        for e in data.get("entities", []):
            entities.append(
                GraphNode(
                    id=f"node_{hash(e['label']) & 0xFFFFFFFF:08x}",
                    label=e["label"],
                    node_type=e.get("type", "concept"),
                )
            )

        relations = []
        for r in data.get("relations", []):
            src_id = f"node_{hash(r['source']) & 0xFFFFFFFF:08x}"
            tgt_id = f"node_{hash(r['target']) & 0xFFFFFFFF:08x}"
            relation_key = f"{r['source']}-{r['target']}-{r['relation']}"
            relations.append(
                GraphEdge(
                    id=f"edge_{hash(relation_key) & 0xFFFFFFFF:08x}",
                    source_id=src_id,
                    target_id=tgt_id,
                    relation=r["relation"],
                    source_session_id=session_id,
                )
            )

        return ExtractionResult(facts=facts, entities=entities, relations=relations)


class BatchedExtraction:
    def __init__(self, llm_router, memory, embedder, batch_size: int = 5):
        self.engine = MemoryExtractionEngine(llm_router)
        self.memory = memory
        self.embedder = embedder
        self.batch_size = batch_size
        self._batch: list[EpisodicEntry] = []

    def submit(self, entry: EpisodicEntry):
        self._batch.append(entry)
        if len(self._batch) >= self.batch_size:
            self.flush()

    def flush(self):
        if not self._batch:
            return
        entries = self._batch[:]
        self._batch = []
        result = self.engine.extract_from_batch(entries)
        self._store_result(result)

    def flush_all(self):
        if self._batch:
            self.flush()

    def _store_result(self, result: ExtractionResult):
        try:
            if result.facts:
                self.memory.semantic.add_batch(result.facts)
        except Exception as e:
            log.warning("Failed to store extracted facts: %s", e)
        # TODO: Migrate graph storage to Qdrant (MTS-10 Phase C)
        # Graph nodes/edges currently live in SQLite only.
        # Future: add Qdrant collection for graph embeddings + semantic search.
        try:
            if result.entities or result.relations:
                self.memory.graph.add_batch(result.entities, result.relations)
        except Exception as e:
            log.warning("Failed to store graph nodes/edges: %s", e)
