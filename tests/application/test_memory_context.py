from unittest.mock import Mock

from mazyr.application.memory_context import ContextAssembler
from mazyr.domain.memory_context import ContextQuery, ContextSource
from mazyr.domain.memory_episodic import EpisodicEntry, MessageRole
from mazyr.domain.memory_graph import GraphEdge, GraphNode
from mazyr.domain.memory_semantic import MemoryCategory, SemanticEntry
from mazyr.domain.memory_working import WorkingMemoryEntry
from mazyr.domain.skills import Skill


def _mock_memory(working=None, semantic=None, episodic=None, graph_nodes=None, graph_edges=None):
    memory = Mock()
    memory.working.get_all.return_value = working or []
    memory.search.return_value = semantic or []
    memory.episodic.get_recent.return_value = episodic or []
    memory.graph.traverse.return_value = (graph_nodes or [], graph_edges or [])
    memory.graph.get_node.return_value = None
    return memory


class TestContextAssembler:
    def test_empty_memory_returns_empty(self):
        memory = _mock_memory()
        assembler = ContextAssembler(memory)
        result = assembler.assemble(ContextQuery(query="test"))
        assert result.items == []
        assert result.formatted == ""

    def test_working_memory_included(self):
        memory = _mock_memory(
            working=[
                WorkingMemoryEntry(key="skill", value="python"),
            ]
        )
        assembler = ContextAssembler(memory)
        result = assembler.assemble(ContextQuery(query="test"))
        items = [i for i in result.items if i.source == ContextSource.WORKING]
        assert len(items) == 1
        assert "skill" in items[0].content
        assert "python" in items[0].content

    def test_semantic_memory_included(self):
        memory = _mock_memory(
            semantic=[
                SemanticEntry(
                    id="s1",
                    content="sky is blue",
                    category=MemoryCategory.FACT,
                    importance_score=0.9,
                ),
            ]
        )
        assembler = ContextAssembler(memory)
        result = assembler.assemble(ContextQuery(query="sky"))
        items = [i for i in result.items if i.source == ContextSource.SEMANTIC]
        assert len(items) == 1
        assert items[0].score == 0.9

    def test_episodic_memory_included(self):
        memory = _mock_memory(
            episodic=[
                EpisodicEntry(
                    id="e1",
                    session_id="s1",
                    role=MessageRole.USER,
                    content="hello",
                    timestamp="2026-06-12T10:00:00",
                ),
            ]
        )
        assembler = ContextAssembler(memory)
        result = assembler.assemble(ContextQuery(query="test"))
        items = [i for i in result.items if i.source == ContextSource.EPISODIC]
        assert len(items) == 1
        assert "user" in items[0].content

    def test_graph_memory_included(self):
        memory = _mock_memory(
            graph_nodes=[GraphNode(id="n1", label="Python", node_type="language")],
            graph_edges=[GraphEdge(id="e1", source_id="n1", target_id="n2", relation="used_for")],
        )
        assembler = ContextAssembler(memory)
        result = assembler.assemble(ContextQuery(query="Python"))
        items = [i for i in result.items if i.source == ContextSource.GRAPH]
        assert len(items) >= 1

    def test_token_budget_truncates(self):
        memory = _mock_memory()
        # Each item ~39 chars -> ~9 tokens, so 50 tokens fits ~5 items
        working_items = [WorkingMemoryEntry(key=f"k{i}", value="x" * 35) for i in range(10)]
        memory.working.get_all.return_value = working_items
        assembler = ContextAssembler(memory, max_tokens=50)
        result = assembler.assemble(
            ContextQuery(
                query="test",
                working_limit=10,
                include_episodic=False,
                include_semantic=False,
                include_graph=False,
            )
        )
        assert 0 < len(result.items) < 10

    def test_working_priority_over_semantic(self):
        memory = _mock_memory(
            working=[WorkingMemoryEntry(key="z", value="last")],
            semantic=[
                SemanticEntry(
                    id="s1", content="fact", category=MemoryCategory.FACT, importance_score=0.1
                )
            ],
        )
        assembler = ContextAssembler(memory)
        # include nothing else
        q = ContextQuery(query="test", include_episodic=False, include_graph=False)
        result = assembler.assemble(q)
        sources = [i.source for i in result.items]
        assert sources.index(ContextSource.WORKING) < sources.index(ContextSource.SEMANTIC)

    def test_format_structure(self):
        memory = _mock_memory(
            working=[
                WorkingMemoryEntry(key="mode", value="focus"),
                WorkingMemoryEntry(key="task", value="coding"),
            ]
        )
        assembler = ContextAssembler(memory)
        q = ContextQuery(
            query="test", include_episodic=False, include_semantic=False, include_graph=False
        )
        result = assembler.assemble(q)
        assert "=== Working ===" in result.formatted
        assert "mode" in result.formatted
        assert "task" in result.formatted

    def test_procedural_skill_context_included(self):
        memory = _mock_memory()
        skill = Skill(
            name="python-craft",
            description="Python best practices",
            category="coding",
            content="Never use bare except.",
        )
        skill_registry = Mock()
        skill_registry.active_skill = skill
        assembler = ContextAssembler(memory, skill_registry=skill_registry)
        q = ContextQuery(
            query="test",
            include_working=False,
            include_episodic=False,
            include_semantic=False,
            include_graph=False,
        )
        result = assembler.assemble(q)
        items = [i for i in result.items if i.source == ContextSource.PROCEDURAL]
        assert len(items) == 1
        assert "python-craft" in items[0].content
        assert "Never use bare except" in items[0].content

    def test_procedural_context_skipped_when_no_active_skill(self):
        memory = _mock_memory()
        skill_registry = Mock()
        skill_registry.active_skill = None
        assembler = ContextAssembler(memory, skill_registry=skill_registry)
        q = ContextQuery(
            query="test",
            include_working=False,
            include_episodic=False,
            include_semantic=False,
            include_graph=False,
        )
        result = assembler.assemble(q)
        assert result.items == []
