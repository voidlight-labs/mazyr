from dataclasses import dataclass

from mazyr.domain.message import Message
from mazyr.domain.filter import FilterResult
from mazyr.domain.constitution import ValidationResult


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
