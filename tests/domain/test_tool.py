import pytest
from pydantic import ValidationError

from mazyr.domain.tool import ToolTier, ToolDefinition, ToolCall, ToolResult, ToolAuditEntry


class TestToolTier:
    def test_tier_values(self):
        assert ToolTier.BLACKLIST == 0
        assert ToolTier.SAFE == 1
        assert ToolTier.SEMI_SAFE == 2
        assert ToolTier.DANGEROUS == 3

    def test_tier_comparison(self):
        assert ToolTier.SAFE < ToolTier.DANGEROUS
        assert ToolTier.BLACKLIST < ToolTier.SAFE


class TestToolDefinition:
    def test_valid_definition(self):
        td = ToolDefinition(
            name="test_tool",
            description="A test tool",
            tier=ToolTier.SAFE,
            handler="tools.test",
        )
        assert td.name == "test_tool"
        assert td.tier == ToolTier.SAFE

    def test_invalid_name_pattern(self):
        with pytest.raises(ValidationError):
            ToolDefinition(
                name="Test Tool!",
                description="bad name",
                tier=ToolTier.SAFE,
                handler="x",
            )

    def test_default_parallel_safe(self):
        td = ToolDefinition(
            name="my_tool",
            description="desc",
            tier=ToolTier.SAFE,
            handler="x",
        )
        assert td.parallel_safe is False


class TestToolCall:
    def test_valid_call(self):
        tc = ToolCall(name="my_tool", params={"key": "value"})
        assert tc.name == "my_tool"
        assert tc.params["key"] == "value"

    def test_empty_params(self):
        tc = ToolCall(name="my_tool")
        assert tc.params == {}


class TestToolResult:
    def test_success_result(self):
        tr = ToolResult(success=True, data="ok")
        assert tr.success is True
        assert tr.data == "ok"

    def test_error_result(self):
        tr = ToolResult(success=False, error="something went wrong")
        assert tr.success is False
        assert tr.error == "something went wrong"


class TestToolAuditEntry:
    def test_minimal_entry(self):
        entry = ToolAuditEntry(session_id="s1", tool_name="t1", tier=1)
        assert entry.session_id == "s1"
        assert entry.status == "ALLOWED"
        assert entry.duration_ms == 0
