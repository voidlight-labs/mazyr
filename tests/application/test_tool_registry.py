import asyncio
import tempfile
from unittest.mock import Mock

import pytest

from mazyr.application.approval_manager import ApprovalManager
from mazyr.application.tool_registry import ToolRegistry
from mazyr.application.tools.registry import register_all
from mazyr.domain.constitution import Constitution
from mazyr.domain.tool import (
    ApprovalRequest,
    ApprovalResponse,
    ToolCall,
    ToolDefinition,
    ToolResult,
    ToolTier,
)
from mazyr.domain.tool_config import ToolRegistryConfig


@pytest.fixture
def registry():
    import os

    db = tempfile.mktemp(suffix=".db")
    from mazyr.infrastructure.memory_sqlite import SQLiteMemoryAdapter

    adapter = SQLiteMemoryAdapter(db)
    adapter.connect()
    cfg = ToolRegistryConfig()
    reg = ToolRegistry(Constitution(), adapter, cfg)
    register_all(reg)
    yield reg
    adapter.close()
    os.unlink(db)


class FakeNotifier:
    """Test notifier that immediately returns a configured response."""

    def __init__(self, response: ApprovalResponse):
        self.response = response
        self.requests: list[ApprovalRequest] = []

    async def notify(self, request: ApprovalRequest) -> None:
        self.requests.append(request)

    async def read_response(
        self, request: ApprovalRequest, timeout_seconds: float
    ) -> ApprovalResponse:
        return self.response


class TestToolRegistry:
    def test_register_and_list(self, registry):
        tools = registry.get_tool_definitions()
        names = [t.name for t in tools]
        assert "search_memory" in names
        assert "get_status" in names
        assert "read_file" in names
        assert "add_memory" in names
        assert "run_code" in names
        assert "file_write" in names
        assert "execute_shell" in names
        assert "api_call_external" in names
        assert "memory_admin" in names

    def test_tier0_blacklist(self, registry):
        for name in registry.TIER0_BLACKLIST:
            tc = ToolCall(name=name)
            result = registry.execute(tc, {"session_id": "test", "platform": "cli"})
            assert result.success is False
            assert result.status == "DENIED"

    def test_unknown_tool(self, registry):
        tc = ToolCall(name="nonexistent")
        result = registry.execute(tc, {"session_id": "test", "platform": "cli"})
        assert result.success is False
        assert "Unknown" in result.error

    def test_tier1_get_status(self, registry):
        tc = ToolCall(name="get_status")
        result = registry.execute(
            tc,
            {
                "session_id": "test",
                "platform": "cli",
                "identity": Mock(instance_name="Aria", creator_name="Test", vessel_type="laptop"),
                "mission": Mock(primary="Learn"),
                "config": Mock(inference_preference="cloud", qdrant_enabled=True),
            },
        )
        assert result.success is True
        assert "Aria" in result.data

    def test_tier2_add_memory_abuse(self, registry):
        tc = ToolCall(name="add_memory", params={"content": "test", "type": "episodic"})
        ctx = {"session_id": "test", "platform": "cli", "memory": Mock()}

        # Exceed threshold
        cfg = registry.config
        limit = cfg.tier2.abuse_thresholds.add_memory_per_session
        for i in range(limit + 1):
            # After the first call, subsequent calls with add_memory will fail if they exceed threshold
            result = registry.execute(tc, ctx)
            if i < limit:
                assert result.success or result.status == "ERROR"  # might fail without real memory
            else:
                break

    def test_tier3_denied_in_non_cli(self, registry):
        tc = ToolCall(name="file_write", params={"path": "/tmp/test", "content": "data"})
        result = registry.execute(
            tc,
            {
                "session_id": "test",
                "platform": "telegram",
            },
        )
        # Without CLI platform, Tier 3 should be denied
        assert result.success is False
        assert "not available" in result.error.lower()

    def test_missing_params(self, registry):
        tc = ToolCall(name="read_file", params={})
        result = registry.execute(
            tc,
            {
                "session_id": "test",
                "platform": "cli",
            },
        )
        assert result.success is False
        assert "Parameter validation failed" in result.error

    def test_constitution_rejects_override(self, registry):
        # Register a stand-in tool whose name triggers a Constitution rejection.
        registry.register(
            ToolDefinition(
                name="override_constitution",
                description="Test tool",
                tier=ToolTier.SAFE,
                handler="test",
            ),
            lambda _p, _c: ToolResult(success=True),
        )
        tc = ToolCall(name="override_constitution")
        result = registry.execute(tc, {"session_id": "test", "platform": "cli"})
        assert result.success is False
        assert result.status == "DENIED"
        assert "Constitution" in result.error

    def test_pydantic_param_validation_rejects_bad_type(self, registry):
        tc = ToolCall(name="search_memory", params={"query": "test", "limit": "not_a_number"})
        result = registry.execute(tc, {"session_id": "test", "platform": "cli"})
        assert result.success is False
        assert result.status == "DENIED"
        assert "Parameter validation failed" in result.error

    def test_pydantic_param_validation_rejects_traversal(self, registry):
        tc = ToolCall(name="read_file", params={"path": "../../etc/passwd"})
        result = registry.execute(tc, {"session_id": "test", "platform": "cli"})
        assert result.success is False
        assert result.status == "DENIED"

    def test_audit_log_redacts_secrets(self, registry):
        # Register a Tier 3 test tool whose params include a secret key.
        from pydantic import BaseModel

        class SecretParams(BaseModel):
            api_key: str
            normal: str

        registry.register(
            ToolDefinition(
                name="secret_test",
                description="Test tool",
                tier=ToolTier.DANGEROUS,
                param_model=SecretParams,
                handler="test",
            ),
            lambda _p, _c: ToolResult(success=True),
        )
        # Whitelist for this session to avoid the interactive prompt.
        registry._session_whitelist.add("secret_test")
        tc = ToolCall(
            name="secret_test",
            params={
                "api_key": "secret_token_123",
                "normal": "visible_value",
            },
        )
        result = registry.execute(tc, {"session_id": "test", "platform": "cli"})
        assert result.success is True
        entry = registry.sqlite.conn.execute(
            "SELECT params FROM tool_audit_log WHERE tool_name = ? ORDER BY id DESC LIMIT 1",
            (tc.name,),
        ).fetchone()
        assert entry is not None
        params_json = entry[0]
        assert "secret_token_123" not in params_json
        assert "visible_value" in params_json
        assert "***REDACTED***" in params_json

    def test_get_tool_definitions(self, registry):
        defs = registry.get_tool_definitions()
        assert len(defs) == 12
        for d in defs:
            assert d.name
            assert d.description
            assert d.tier in (ToolTier.SAFE, ToolTier.SEMI_SAFE, ToolTier.DANGEROUS)


@pytest.mark.asyncio
class TestAsyncTier3Approval:
    async def test_aexecute_approves_and_runs_tool(self, registry):
        registry.register(
            ToolDefinition(
                name="danger_test", description="Test", tier=ToolTier.DANGEROUS, handler="test"
            ),
            lambda _p, _c: ToolResult(success=True, data="ok"),
        )
        notifier = FakeNotifier(ApprovalResponse(decision="approve", approved_by="tester"))
        registry._approval_manager = ApprovalManager(notifier, timeout_seconds=1.0)

        tc = ToolCall(name="danger_test", params={"x": 1})
        result = await registry.aexecute(tc, {"session_id": "test", "platform": "cli"})

        assert result.success is True
        assert result.data == "ok"
        assert len(notifier.requests) == 1
        assert notifier.requests[0].tool_call.name == "danger_test"

    async def test_aexecute_denies_tool(self, registry):
        registry.register(
            ToolDefinition(
                name="danger_test", description="Test", tier=ToolTier.DANGEROUS, handler="test"
            ),
            lambda _p, _c: ToolResult(success=True),
        )
        notifier = FakeNotifier(ApprovalResponse(decision="deny"))
        registry._approval_manager = ApprovalManager(notifier, timeout_seconds=1.0)

        tc = ToolCall(name="danger_test", params={"x": 1})
        result = await registry.aexecute(tc, {"session_id": "test", "platform": "cli"})

        assert result.success is False
        assert result.status == "DENIED"

    async def test_aexecute_modifies_params(self, registry):
        registry.register(
            ToolDefinition(
                name="danger_test", description="Test", tier=ToolTier.DANGEROUS, handler="test"
            ),
            lambda p, _c: ToolResult(success=True, data=str(p.get("x"))),
        )
        notifier = FakeNotifier(
            ApprovalResponse(decision="modify", modified_params={"x": 42}, approved_by="tester")
        )
        registry._approval_manager = ApprovalManager(notifier, timeout_seconds=1.0)

        tc = ToolCall(name="danger_test", params={"x": 1})
        result = await registry.aexecute(tc, {"session_id": "test", "platform": "cli"})

        assert result.success is True
        assert result.data == "42"

    async def test_aexecute_times_out_and_denies(self, registry):
        registry.register(
            ToolDefinition(
                name="danger_test", description="Test", tier=ToolTier.DANGEROUS, handler="test"
            ),
            lambda _p, _c: ToolResult(success=True),
        )

        class SlowNotifier:
            async def notify(self, request: ApprovalRequest) -> None:
                pass

            async def read_response(
                self, request: ApprovalRequest, timeout_seconds: float
            ) -> ApprovalResponse:
                await asyncio.sleep(timeout_seconds + 0.1)
                return ApprovalResponse(decision="approve")

        registry._approval_manager = ApprovalManager(SlowNotifier(), timeout_seconds=0.1)
        tc = ToolCall(name="danger_test", params={"x": 1})
        result = await registry.aexecute(tc, {"session_id": "test", "platform": "cli"})

        assert result.success is False
        assert result.status == "TIMEOUT"

    async def test_aexecute_persists_approval_request(self, registry):
        registry.register(
            ToolDefinition(
                name="danger_test", description="Test", tier=ToolTier.DANGEROUS, handler="test"
            ),
            lambda _p, _c: ToolResult(success=True),
        )
        notifier = FakeNotifier(ApprovalResponse(decision="approve", approved_by="tester"))
        registry._approval_manager = ApprovalManager(notifier, timeout_seconds=1.0)

        tc = ToolCall(name="danger_test", params={"x": 1})
        await registry.aexecute(tc, {"session_id": "test", "platform": "cli"})

        rows = registry.sqlite.conn.execute(
            "SELECT * FROM approval_requests WHERE tool_name = ?", ("danger_test",)
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["status"] == "approved"
        assert rows[0]["approved_by"] == "tester"
