from dataclasses import dataclass

from mazyr.domain.message import Message
from mazyr.domain.filter import FilterResult
from mazyr.domain.constitution import ValidationResult
from mazyr.domain.tool import ToolCall, ToolResult


@dataclass(frozen=True)
class DomainEvent:
    """Base class for domain events."""

    event_type: str
    timestamp: str
    payload: dict


@dataclass(frozen=True)
class MessageReceived(DomainEvent):
    """Event: A message has been received."""

    message: Message


@dataclass(frozen=True)
class FilterTriggered(DomainEvent):
    """Event: Integrity filter has triggered."""

    result: FilterResult
    original_message: str


@dataclass(frozen=True)
class ConstitutionViolated(DomainEvent):
    """Event: An action violated the constitution."""

    result: ValidationResult
    action: str
    context: dict


@dataclass(frozen=True)
class ToolExecuted(DomainEvent):
    """Event: A tool has been executed."""

    tool_call: ToolCall
    tool_result: ToolResult


@dataclass(frozen=True)
class TierViolation(DomainEvent):
    """Event: A tier 0 or tier violation has occurred."""

    tool_call: ToolCall
    tier: int
    reason: str


@dataclass(frozen=True)
class ApprovalRequested(DomainEvent):
    """Event: Creator approval is requested for a tier 3 tool."""

    tool_call: ToolCall
    reason: str
