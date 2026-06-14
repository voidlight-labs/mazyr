from typing import Optional

from mazyr.domain.memory_graph import GraphEdge, GraphNode
from mazyr.infrastructure.memory_sqlite import SQLiteMemoryAdapter


class GraphStore:
    def __init__(self, sqlite: SQLiteMemoryAdapter):
        self._sqlite = sqlite

    def add_batch(self, nodes: list[GraphNode], edges: list[GraphEdge]):
        self._sqlite.add_graph_batch(nodes, edges)

    def search_nodes(self, query: str, limit: int = 20) -> list[GraphNode]:
        return self._sqlite.search_graph_nodes(query, limit)

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        return self._sqlite.get_graph_node(node_id)

    def get_outgoing_edges(self, node_id: str) -> list[GraphEdge]:
        return self._sqlite.get_outgoing_edges(node_id)

    def get_incoming_edges(self, node_id: str) -> list[GraphEdge]:
        return self._sqlite.get_incoming_edges(node_id)

    def traverse(
        self, start_labels: list[str], max_depth: int = 2, max_nodes: int = 30
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        collected_nodes: dict[str, GraphNode] = {}
        collected_edges: dict[str, GraphEdge] = {}
        seen: set[str] = set()
        queue: list[tuple[str, int]] = []

        for label in start_labels:
            for node in self.search_nodes(label, limit=5):
                if node.id not in seen:
                    seen.add(node.id)
                    collected_nodes[node.id] = node
                    queue.append((node.id, 0))

        while queue and len(collected_nodes) < max_nodes:
            node_id, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            for edge in self.get_outgoing_edges(node_id):
                if edge.id not in collected_edges:
                    collected_edges[edge.id] = edge
                if edge.target_id not in seen:
                    tgt = self.get_node(edge.target_id)
                    if tgt:
                        seen.add(tgt.id)
                        collected_nodes[tgt.id] = tgt
                        queue.append((tgt.id, depth + 1))

            for edge in self.get_incoming_edges(node_id):
                if edge.id not in collected_edges:
                    collected_edges[edge.id] = edge
                if edge.source_id not in seen:
                    src = self.get_node(edge.source_id)
                    if src:
                        seen.add(src.id)
                        collected_nodes[src.id] = src
                        queue.append((src.id, depth + 1))

            if len(collected_nodes) >= max_nodes:
                break

        return list(collected_nodes.values()), list(collected_edges.values())
