import re
from datetime import datetime

from mazyr.application.memory_system import MemorySystem
from mazyr.domain.memory_context import ContextItem, ContextQuery, ContextResult, ContextSource
from mazyr.domain.memory_entry import MemoryQuery
from mazyr.domain.ports import ProceduralMemoryPort
from mazyr.infrastructure.logger import get_logger

log = get_logger("memory.context")

TOKEN_ESTIMATE_RATIO = 4


class ContextAssembler:
    def __init__(
        self,
        memory: MemorySystem,
        skill_registry: ProceduralMemoryPort | None = None,
        max_tokens: int = 2000,
    ):
        self.memory = memory
        self.skill_registry = skill_registry
        self.max_tokens = max_tokens

    def assemble(self, query: ContextQuery) -> ContextResult:
        items: list[ContextItem] = []
        if query.include_working:
            items.extend(self._get_working_context(query))
        if query.include_semantic:
            items.extend(self._get_semantic_context(query))
        if query.include_episodic:
            items.extend(self._get_episodic_context(query))
        if query.include_graph:
            items.extend(self._get_graph_context(query))
        if query.include_procedural:
            items.extend(self._get_procedural_context())
        return self._finalize(items, query)

    def _get_procedural_context(self) -> list[ContextItem]:
        items = []
        if self.skill_registry and self.skill_registry.active_skill:
            skill = self.skill_registry.active_skill
            items.append(
                ContextItem(
                    content=f"Active skill: {skill.name}\n{skill.description}\n\n{skill.content}",
                    source=ContextSource.PROCEDURAL,
                    score=1.0,
                    metadata={"skill": skill.name, "version": skill.version},
                )
            )
        return items

    def _get_working_context(self, query: ContextQuery) -> list[ContextItem]:
        items = []
        for entry in self.memory.working.get_all():
            if len(items) >= query.working_limit:
                break
            items.append(
                ContextItem(
                    content=f"{entry.key}: {entry.value}",
                    source=ContextSource.WORKING,
                    score=1.0,
                    metadata={"key": entry.key, "ttl": entry.ttl_seconds},
                )
            )
        return items

    def _get_semantic_context(self, query: ContextQuery) -> list[ContextItem]:
        items = []
        try:
            mq = MemoryQuery(query=query.query, limit=query.semantic_limit)
            entries = self.memory.search(mq)
            for e in entries:
                items.append(
                    ContextItem(
                        content=e.content,
                        source=ContextSource.SEMANTIC,
                        score=e.importance_score,
                        metadata={
                            "category": e.category.value,
                            "confidence": e.confidence,
                            "importance": e.importance_score,
                        },
                    )
                )
        except Exception as e:
            log.warning("Semantic context fetch failed: %s", e)
        return items

    def _get_episodic_context(self, query: ContextQuery) -> list[ContextItem]:
        items = []
        try:
            entries = self.memory.episodic.get_recent(query.episodic_limit)
            for idx, e in enumerate(entries):
                ts = e.timestamp or e.created_at or ""
                label = ""
                if ts:
                    try:
                        dt = datetime.fromisoformat(ts)
                        delta = datetime.now() - dt
                        if delta.total_seconds() < 3600:
                            label = f"{int(delta.total_seconds() // 60)}m ago"
                        elif delta.total_seconds() < 86400:
                            label = f"{int(delta.total_seconds() // 3600)}h ago"
                        else:
                            label = f"{delta.days}d ago"
                    except ValueError:
                        label = ts[:10]
                line = (
                    f"[{label}] {e.role.value}: {e.content}"
                    if label
                    else f"{e.role.value}: {e.content}"
                )
                items.append(
                    ContextItem(
                        content=line,
                        source=ContextSource.EPISODIC,
                        score=max(0.1, 1.0 - idx * 0.1),
                        metadata={"role": e.role.value, "timestamp": ts},
                    )
                )
        except Exception as e:
            log.warning("Episodic context fetch failed: %s", e)
        return items

    def _get_graph_context(self, query: ContextQuery) -> list[ContextItem]:
        items = []
        try:
            terms = self._extract_entity_terms(query.query)
            if not terms:
                return items

            nodes, edges = self.memory.graph.traverse(
                start_labels=terms,
                max_depth=query.graph_depth,
                max_nodes=query.graph_max_nodes,
            )

            if nodes:
                node_lines = "\n".join(f"  {n.label} ({n.node_type})" for n in nodes)
                items.append(
                    ContextItem(
                        content=node_lines,
                        source=ContextSource.GRAPH,
                        score=0.8,
                        metadata={"node_count": len(nodes), "edge_count": len(edges)},
                    )
                )

            if edges:
                entity_map = self._build_entity_map(nodes, edges)
                items.append(
                    ContextItem(
                        content=entity_map,
                        source=ContextSource.GRAPH,
                        score=0.9,
                        metadata={"type": "entity_map"},
                    )
                )
        except Exception as e:
            log.warning("Graph context fetch failed: %s", e)
        return items

    def _extract_entity_terms(self, query: str) -> list[str]:
        words = re.findall(r"[a-zA-Z_]\w{2,}", query.lower())
        return list(set(words))[:10]

    def _resolve_label(self, node_id: str) -> str:
        try:
            node = self.memory.graph.get_node(node_id)
            return node.label if node else node_id
        except Exception:
            return node_id

    def _build_entity_map(self, nodes: list, edges: list) -> str:
        node_map = {n.id: n.label for n in nodes}
        lines = []
        for e in edges:
            src = node_map.get(e.source_id, e.source_id)
            tgt = node_map.get(e.target_id, e.target_id)
            lines.append(f"  {src} --[{e.relation}]--> {tgt}")
        return "\n".join(lines[:25])

    def _finalize(self, items: list[ContextItem], query: ContextQuery) -> ContextResult:
        tier_order = {
            ContextSource.WORKING: 0,
            ContextSource.SEMANTIC: 1,
            ContextSource.EPISODIC: 2,
            ContextSource.GRAPH: 3,
        }
        items.sort(key=lambda i: (tier_order.get(i.source, 99), -i.score))

        budget = min(query.max_tokens, self.max_tokens)
        kept: list[ContextItem] = []
        for item in items:
            estimated = max(1, len(item.content) // TOKEN_ESTIMATE_RATIO)
            if estimated > budget:
                continue
            kept.append(item)
            budget -= estimated

        formatted = self._format_context(kept)
        total = sum(max(1, len(i.content) // TOKEN_ESTIMATE_RATIO) for i in kept)

        return ContextResult(items=kept, total_tokens=total, formatted=formatted)

    def _format_context(self, items: list[ContextItem]) -> str:
        sections: dict[str, list[str]] = {}
        for item in items:
            source = item.source.value.capitalize()
            if source not in sections:
                sections[source] = []
            prefix = ""
            if item.score:
                prefix = f"[{item.score:.2f}] "
            sections[source].append(f"{prefix}{item.content}")

        parts = []
        for source in ["Working", "Procedural", "Semantic", "Episodic", "Graph"]:
            if source in sections:
                entries = "\n".join(sections[source])
                parts.append(f"=== {source} ===\n{entries}")

        return "\n\n".join(parts)
