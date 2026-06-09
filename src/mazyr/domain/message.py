from dataclasses import dataclass, field


@dataclass(frozen=True)
class Message:
    """A single message in a conversation."""

    id: str
    content: str
    sender: str  # "creator", "instance", "system", "unknown"
    platform: str  # "cli", "whatsapp", "telegram", "system"
    timestamp: str
    metadata: dict = field(default_factory=dict)

    @property
    def is_from_creator(self) -> bool:
        return self.sender == "creator"

    @property
    def is_from_instance(self) -> bool:
        return self.sender == "instance"


@dataclass
class Conversation:
    """A collection of messages."""

    id: str
    messages: list[Message] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def add_message(self, message: Message):
        self.messages.append(message)
        self.updated_at = message.timestamp

    def last_n(self, n: int) -> list[Message]:
        return self.messages[-n:]
