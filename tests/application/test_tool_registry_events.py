import asyncio
import tempfile
from unittest.mock import Mock

import pytest

from mazyr.application.approval_manager import ApprovalManager
from mazyr.application.event_bus import EventBus
from mazyr.application.tool_registry import ToolRegistry
from mazyr.application.tools.registry import register_all
from mazyr.domain.constitution import Constitution
from mazyr.domain.events import ApprovalRequested, ApprovalResolved, ToolExecuted
from mazyr.domain.tool import (
    ApprovalResponse,
    ToolCall,
    ToolDefinition,
    ToolResult,
    ToolTier,
)
from mazyr.domain.tool_config import ToolRegistryConfig
from mazyr.infrastructure.memory_sqlite import SQLiteMemoryAdapter


@pytest.fixture
def eventful_registry():
    db = tempfile.mktemp(suffix=".db")
    adapter = SQLiteMemoryAdapter(db)
    adapter.connect()
    bus = EventBus()
    cfg = ToolRegistryConfig()
    reg = ToolRegistry(Constitution(), adapter, cfg, event_bus=bus)
    register_all(reg)
    yield reg, bus
    adapter.close()
    import os

    os.unlink(db)


class TestToolRegistryEvents:
    def test_tier1_execution_publishes_tool_executed(self, eventful_registry):
        registry, bus = eventful_registry
        handler = Mock()
        bus.subscribe("tool.executed", handler)

        tc = ToolCall(name="get_status")
        registry.execute(
            tc,
            {
                "session_id": "test",
                "platform": "cli",
                "identity": Mock(instance_name="Aria", creator_name="Test", vessel_type="laptop"),
                "mission": Mock(primary="Learn"),
                "config": Mock(inference_preference="cloud", qdrant_enabled=True),
            },
        )

        handler.assert_called_once()
        event = handler.call_args[0][0]
        assert isinstance(event, ToolExecuted)
        assert event.tool_call.name == "get_status"

    def test_tier3_denied_publishes_tool_executed(self, eventful_registry):
        registry, bus = eventful_registry
        handler = Mock()
        bus.subscribe("tool.executed", handler)

        tc = ToolCall(name="file_write", params={"path": "/tmp/test", "content": "data"})
        registry.execute(tc, {"session_id": "test", "platform": "telegram"})

        event = handler.call_args[0][0]
        assert event.tool_result.status == "DENIED"

    @pytest.mark.asyncio
    async def test_aexecute_publishes_approval_events(self, eventful_registry):
        registry, bus = eventful_registry
        registry.register(
            ToolDefinition(
                name="danger_test", description="Test", tier=ToolTier.DANGEROUS, handler="test"
            ),
            lambda _p, _c: ToolResult(success=True),
        )

        requested_handler = Mock()
        resolved_handler = Mock()
        bus.subscribe("approval.requested", requested_handler)
        bus.subscribe("approval.resolved", resolved_handler)

        class Notifier:
            async def notify(self, request):
                pass

            async def read_response(self, request, timeout_seconds):
                return ApprovalResponse(decision="approve", approved_by="tester")

        registry._approval_manager = ApprovalManager(Notifier(), timeout_seconds=1.0)

        tc = ToolCall(name="danger_test", params={"x": 1})
        await registry.aexecute(tc, {"session_id": "test", "platform": "cli"})

        requested_handler.assert_called_once()
        resolved_handler.assert_called_once()
        req_event = requested_handler.call_args[0][0]
        assert isinstance(req_event, ApprovalRequested)
        assert req_event.tool_name == "danger_test"
        res_event = resolved_handler.call_args[0][0]
        assert isinstance(res_event, ApprovalResolved)
        assert res_event.decision == "approve"

    @pytest.mark.asyncio
    async def test_aexecute_timeout_publishes_approval_resolved(self, eventful_registry):
        registry, bus = eventful_registry
        registry.register(
            ToolDefinition(
                name="danger_test", description="Test", tier=ToolTier.DANGEROUS, handler="test"
            ),
            lambda _p, _c: ToolResult(success=True),
        )

        resolved_handler = Mock()
        bus.subscribe("approval.resolved", resolved_handler)

        class SlowNotifier:
            async def notify(self, request):
                pass

            async def read_response(self, request, timeout_seconds):
                await asyncio.sleep(timeout_seconds + 0.1)
                return ApprovalResponse(decision="approve")

        registry._approval_manager = ApprovalManager(SlowNotifier(), timeout_seconds=0.1)

        tc = ToolCall(name="danger_test", params={"x": 1})
        await registry.aexecute(tc, {"session_id": "test", "platform": "cli"})

        event = resolved_handler.call_args[0][0]
        assert event.decision == "timeout"
