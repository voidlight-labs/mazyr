from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from mazyr.domain.filter import FilterResult
from mazyr.domain.tool import ToolCall, ToolResult


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    """Base class for immutable domain events."""

    event_type: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class MessageReceived(DomainEvent):
    """A new message has been received from the Creator."""

    event_type: str = field(default="message.received", init=False)


@dataclass(frozen=True, kw_only=True)
class FilterTriggered(DomainEvent):
    """The integrity filter has triggered on inbound or outbound content."""

    event_type: str = field(default="filter.triggered", init=False)
    result: FilterResult
    original_message: str


@dataclass(frozen=True, kw_only=True)
class ToolExecuted(DomainEvent):
    """A tool has been executed by the ToolRegistry."""

    event_type: str = field(default="tool.executed", init=False)
    tool_call: ToolCall
    tool_result: ToolResult


@dataclass(frozen=True, kw_only=True)
class ApprovalRequested(DomainEvent):
    """Creator approval is requested for a Tier-3 tool."""

    event_type: str = field(default="approval.requested", init=False)
    request_id: str
    tool_name: str
    params: dict[str, Any]


@dataclass(frozen=True, kw_only=True)
class ApprovalResolved(DomainEvent):
    """Creator has responded to an approval request."""

    event_type: str = field(default="approval.resolved", init=False)
    request_id: str
    decision: str
    approved_by: str | None


@dataclass(frozen=True, kw_only=True)
class ConstitutionViolated(DomainEvent):
    """An action was denied by the Constitution validator."""

    event_type: str = field(default="constitution.violated", init=False)
    action: str
    reason: str
