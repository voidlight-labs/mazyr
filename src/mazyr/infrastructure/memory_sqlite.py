import json
import queue
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from mazyr.domain.memory_episodic import EpisodicEntry, MessageRole
from mazyr.domain.memory_graph import GraphEdge, GraphNode
from mazyr.domain.memory_semantic import MemoryCategory, SemanticEntry
from mazyr.domain.tool import ToolAuditEntry
from mazyr.infrastructure.paths import MAZYR_HOME


class SQLiteMemoryAdapter:
    """SQLite adapter with a bounded connection pool and WAL mode.

    Write and read operations borrow a connection from the pool, while the
    legacy ``self.conn`` attribute remains available as the primary connection
    for callers that need direct SQL access (e.g. tests).
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        max_connections: int = 5,
        busy_timeout_ms: int = 5000,
    ):
        if db_path is None:
            db_path = MAZYR_HOME / "memory" / "mazyr.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._busy_timeout_ms = busy_timeout_ms
        self._max_connections = max_connections
        self._pool: queue.Queue[sqlite3.Connection] = queue.Queue(maxsize=max_connections)
        self._pool_lock = threading.Lock()
        self._created_count = 0
        self._closed = True
        self.conn: sqlite3.Connection | None = None

    def _new_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(f"PRAGMA busy_timeout = {self._busy_timeout_ms}")
        return conn

    def connect(self):
        self.conn = self._new_connection()
        self._create_tables(self.conn)
        self.conn.commit()
        self._closed = False

    def _create_tables(self, conn: sqlite3.Connection):
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS episodic_memory (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT,
                tool_calls TEXT,
                metadata TEXT,
                extracted_facts TEXT,
                importance_score REAL DEFAULT 0.5,
                consolidated BOOLEAN DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_episodic_session ON episodic_memory(session_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_episodic_consolidated ON episodic_memory(consolidated);

            CREATE TABLE IF NOT EXISTS semantic_memory (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                category TEXT NOT NULL,
                vector_id TEXT,
                source_session_id TEXT,
                source_message_id TEXT,
                confidence REAL DEFAULT 0.8,
                importance_score REAL DEFAULT 0.5,
                access_count INTEGER DEFAULT 0,
                decay_rate REAL DEFAULT 0.01,
                duplicate_of TEXT,
                created_at TEXT,
                last_accessed TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_semantic_category ON semantic_memory(category);
            CREATE INDEX IF NOT EXISTS idx_semantic_importance ON semantic_memory(importance_score DESC);

            CREATE TABLE IF NOT EXISTS graph_nodes (
                id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                node_type TEXT NOT NULL,
                embedding_id TEXT,
                first_seen TEXT,
                last_mentioned TEXT,
                mention_count INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS graph_edges (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL REFERENCES graph_nodes(id),
                target_id TEXT NOT NULL REFERENCES graph_nodes(id),
                relation TEXT NOT NULL,
                confidence REAL DEFAULT 0.8,
                source_session_id TEXT,
                first_seen TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_edge_source ON graph_edges(source_id);
            CREATE INDEX IF NOT EXISTS idx_edge_target ON graph_edges(target_id);
            CREATE INDEX IF NOT EXISTS idx_edge_relation ON graph_edges(relation);

            CREATE TABLE IF NOT EXISTS tool_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                session_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                tier INTEGER NOT NULL,
                params TEXT,
                result TEXT,
                status TEXT,
                approved_by TEXT,
                duration_ms INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_audit_session ON tool_audit_log(session_id);
            CREATE INDEX IF NOT EXISTS idx_audit_tool ON tool_audit_log(tool_name);
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON tool_audit_log(timestamp);

            CREATE TABLE IF NOT EXISTS approval_requests (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                params TEXT,
                reason TEXT,
                status TEXT,
                approved_by TEXT,
                created_at TEXT,
                expires_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_approval_session ON approval_requests(session_id);
            CREATE INDEX IF NOT EXISTS idx_approval_status ON approval_requests(status);
        """)

    @contextmanager
    def _connection(self):
        conn = self._get_connection()
        try:
            yield conn
        finally:
            self._return_connection(conn)

    def _get_connection(self) -> sqlite3.Connection:
        with self._pool_lock:
            if not self._pool.empty():
                return self._pool.get_nowait()
            if self._created_count < self._max_connections:
                self._created_count += 1
                return self._new_connection()
        return self._pool.get()

    def _return_connection(self, conn: sqlite3.Connection):
        if self._closed:
            conn.close()
            return
        try:
            self._pool.put_nowait(conn)
        except queue.Full:
            conn.close()
            with self._pool_lock:
                self._created_count -= 1

    # --- Episodic ---

    def add_episodic(self, entry: EpisodicEntry):
        self.add_episodic_batch([entry])

    def add_episodic_batch(self, entries: list[EpisodicEntry]):
        if not entries:
            return
        rows = [
            (
                entry.id,
                entry.session_id,
                entry.role.value,
                entry.content,
                entry.timestamp,
                json.dumps(entry.tool_calls),
                json.dumps(entry.metadata),
                json.dumps(entry.extracted_facts),
                entry.importance_score,
                int(entry.consolidated),
            )
            for entry in entries
        ]
        with self._connection() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO episodic_memory
                   (id, session_id, role, content, timestamp, tool_calls, metadata, extracted_facts, importance_score, consolidated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
            conn.commit()

    def get_recent_episodic(self, limit: int = 100) -> list[EpisodicEntry]:
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM episodic_memory ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
            return [self._row_to_episodic(row) for row in cursor.fetchall()]

    def get_unconsolidated_episodic(self, since: str = "24h") -> list[EpisodicEntry]:
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM episodic_memory WHERE consolidated = 0 AND created_at >= datetime('now', ?)",
                (f"-{since}",),
            )
            return [self._row_to_episodic(row) for row in cursor.fetchall()]

    def mark_consolidated(self, ids: list[str]):
        placeholders = ",".join("?" for _ in ids)
        with self._connection() as conn:
            conn.execute(
                f"UPDATE episodic_memory SET consolidated = 1 WHERE id IN ({placeholders})",
                ids,
            )
            conn.commit()

    def get_older_than(self, days: int) -> list[EpisodicEntry]:
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM episodic_memory WHERE timestamp < datetime('now', ?)",
                (f"-{days} days",),
            )
            return [self._row_to_episodic(row) for row in cursor.fetchall()]

    def count_episodic(self) -> int:
        with self._connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM episodic_memory")
            return cursor.fetchone()[0]

    # --- Semantic ---

    def add_semantic(self, entry: SemanticEntry):
        self.add_semantic_batch([entry])

    def add_semantic_batch(self, entries: list[SemanticEntry]):
        if not entries:
            return
        rows = [
            (
                entry.id,
                entry.content,
                entry.category.value,
                entry.vector_id,
                entry.source_session_id,
                entry.source_message_id,
                entry.confidence,
                entry.importance_score,
                entry.access_count,
                entry.decay_rate,
                entry.duplicate_of,
                entry.created_at,
                entry.last_accessed,
            )
            for entry in entries
        ]
        with self._connection() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO semantic_memory
                   (id, content, category, vector_id, source_session_id, source_message_id,
                    confidence, importance_score, access_count, decay_rate, duplicate_of,
                    created_at, last_accessed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
            conn.commit()

    def count_semantic(self) -> int:
        with self._connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM semantic_memory")
            return cursor.fetchone()[0]

    def get_stale_semantic(self, threshold_days: int = 7) -> list[SemanticEntry]:
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM semantic_memory WHERE last_accessed < datetime('now', ?)",
                (f"-{threshold_days} days",),
            )
            return [self._row_to_semantic(row) for row in cursor.fetchall()]

    # --- Graph ---

    def add_graph_node(self, node: GraphNode):
        self.add_graph_batch([node], [])

    def add_graph_edge(self, edge: GraphEdge):
        self.add_graph_batch([], [edge])

    def add_graph_batch(self, nodes: list[GraphNode], edges: list[GraphEdge]):
        with self._connection() as conn:
            if nodes:
                rows = [
                    (
                        node.id,
                        node.label,
                        node.node_type,
                        node.embedding_id,
                        node.first_seen,
                        node.last_mentioned,
                        node.mention_count,
                    )
                    for node in nodes
                ]
                conn.executemany(
                    """INSERT OR REPLACE INTO graph_nodes
                       (id, label, node_type, embedding_id, first_seen, last_mentioned, mention_count)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    rows,
                )
            if edges:
                rows = [
                    (
                        edge.id,
                        edge.source_id,
                        edge.target_id,
                        edge.relation,
                        edge.confidence,
                        edge.source_session_id,
                        edge.first_seen,
                    )
                    for edge in edges
                ]
                conn.executemany(
                    """INSERT OR REPLACE INTO graph_edges
                       (id, source_id, target_id, relation, confidence, source_session_id, first_seen)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    rows,
                )
            if nodes or edges:
                conn.commit()

    def count_graph_nodes(self) -> int:
        with self._connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM graph_nodes")
            return cursor.fetchone()[0]

    def count_graph_edges(self) -> int:
        with self._connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM graph_edges")
            return cursor.fetchone()[0]

    def search_graph_nodes(self, query: str, limit: int = 20) -> list[GraphNode]:
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM graph_nodes WHERE label LIKE ? ORDER BY mention_count DESC LIMIT ?",
                (f"%{query}%", limit),
            )
            return [self._row_to_graph_node(row) for row in cursor.fetchall()]

    def get_graph_node(self, node_id: str) -> GraphNode | None:
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM graph_nodes WHERE id = ?",
                (node_id,),
            )
            row = cursor.fetchone()
            return self._row_to_graph_node(row) if row else None

    def get_outgoing_edges(self, node_id: str) -> list[GraphEdge]:
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM graph_edges WHERE source_id = ?",
                (node_id,),
            )
            return [self._row_to_graph_edge(row) for row in cursor.fetchall()]

    def get_incoming_edges(self, node_id: str) -> list[GraphEdge]:
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM graph_edges WHERE target_id = ?",
                (node_id,),
            )
            return [self._row_to_graph_edge(row) for row in cursor.fetchall()]

    def get_orphan_nodes(self, min_mentions: int = 3) -> list[str]:
        with self._connection() as conn:
            cursor = conn.execute(
                """SELECT n.id FROM graph_nodes n
                   LEFT JOIN graph_edges e ON n.id = e.source_id OR n.id = e.target_id
                   WHERE e.id IS NULL AND n.mention_count < ?""",
                (min_mentions,),
            )
            return [row["id"] for row in cursor.fetchall()]

    def delete_nodes(self, ids: list[str]):
        placeholders = ",".join("?" for _ in ids)
        with self._connection() as conn:
            conn.execute(f"DELETE FROM graph_nodes WHERE id IN ({placeholders})", ids)
            conn.execute(
                f"DELETE FROM graph_edges WHERE source_id IN ({placeholders}) OR target_id IN ({placeholders})",
                ids,
            )
            conn.commit()

    # --- Tool audit ---

    def add_tool_audit_entry(self, entry: ToolAuditEntry):
        params_json = json.dumps(entry.params) if entry.params else None
        with self._connection() as conn:
            conn.execute(
                """INSERT INTO tool_audit_log
                   (session_id, tool_name, tier, params, result, status, approved_by, duration_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.session_id,
                    entry.tool_name,
                    entry.tier,
                    params_json,
                    entry.result,
                    entry.status,
                    entry.approved_by,
                    entry.duration_ms,
                ),
            )
            conn.commit()

    def get_recent_tool_calls(self, session_id: str, limit: int = 50) -> list[dict]:
        with self._connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM tool_audit_log
                   WHERE session_id = ? ORDER BY id DESC LIMIT ?""",
                (session_id, limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    # --- Approval requests ---

    def add_approval_request(self, request: dict):
        with self._connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO approval_requests
                   (id, session_id, tool_name, params, reason, status, approved_by, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    request["id"],
                    request["session_id"],
                    request["tool_name"],
                    json.dumps(request.get("params") or {}),
                    request.get("reason", ""),
                    request.get("status", "pending"),
                    request.get("approved_by"),
                    request.get("created_at"),
                    request.get("expires_at"),
                ),
            )
            conn.commit()

    def update_approval_request(self, request_id: str, status: str, approved_by: str | None = None):
        with self._connection() as conn:
            conn.execute(
                "UPDATE approval_requests SET status = ?, approved_by = ? WHERE id = ?",
                (status, approved_by, request_id),
            )
            conn.commit()

    def get_approval_request(self, request_id: str) -> dict | None:
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM approval_requests WHERE id = ?",
                (request_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    # --- Helpers ---

    def _prune_semantic(self, ids: list[str]):
        placeholders = ",".join("?" for _ in ids)
        with self._connection() as conn:
            conn.execute(
                f"DELETE FROM semantic_memory WHERE id IN ({placeholders})",
                ids,
            )
            conn.commit()

    def count_all(self) -> dict:
        return {
            "episodic": self.count_episodic(),
            "semantic": self.count_semantic(),
            "graph_nodes": self.count_graph_nodes(),
            "graph_edges": self.count_graph_edges(),
        }

    def close(self):
        self._closed = True
        if self.conn:
            self.conn.close()
            self.conn = None
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except queue.Empty:
                break
        with self._pool_lock:
            self._created_count = 0

    def _row_to_episodic(self, row: sqlite3.Row) -> EpisodicEntry:
        return EpisodicEntry(
            id=row["id"],
            session_id=row["session_id"],
            role=MessageRole(row["role"]),
            content=row["content"],
            timestamp=row["timestamp"],
            tool_calls=json.loads(row["tool_calls"] or "[]"),
            metadata=json.loads(row["metadata"] or "{}"),
            extracted_facts=json.loads(row["extracted_facts"] or "[]"),
            importance_score=row["importance_score"],
            consolidated=bool(row["consolidated"]),
        )

    def _row_to_graph_node(self, row: sqlite3.Row) -> GraphNode:
        return GraphNode(
            id=row["id"],
            label=row["label"],
            node_type=row["node_type"],
            embedding_id=row["embedding_id"],
            first_seen=row["first_seen"],
            last_mentioned=row["last_mentioned"],
            mention_count=row["mention_count"],
        )

    def _row_to_graph_edge(self, row: sqlite3.Row) -> GraphEdge:
        return GraphEdge(
            id=row["id"],
            source_id=row["source_id"],
            target_id=row["target_id"],
            relation=row["relation"],
            confidence=row["confidence"],
            source_session_id=row["source_session_id"],
            first_seen=row["first_seen"],
        )

    def _row_to_semantic(self, row: sqlite3.Row) -> SemanticEntry:
        return SemanticEntry(
            id=row["id"],
            content=row["content"],
            category=MemoryCategory(row["category"]),
            vector_id=row["vector_id"],
            source_session_id=row["source_session_id"],
            source_message_id=row["source_message_id"],
            confidence=row["confidence"],
            importance_score=row["importance_score"],
            access_count=row["access_count"],
            decay_rate=row["decay_rate"],
            duplicate_of=row["duplicate_of"],
            created_at=row["created_at"],
            last_accessed=row["last_accessed"],
        )
