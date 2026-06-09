from dataclasses import dataclass
from typing import Optional

from mazyr.domain.message import Message, Conversation
from mazyr.domain.filter import IntegrityFilter, FilterResult
from mazyr.domain.memory_entry import MemoryQuery, MemoryEntry, MemoryType


@dataclass
class ChatResult:
    """Result of a chat interaction."""

    success: bool
    reply: Optional[str] = None
    filter_result: Optional[FilterResult] = None
    error: Optional[str] = None
    tokens_used: int = 0


class ChatUseCase:
    """Core chat orchestrator."""

    def __init__(self, identity, mission, filter_engine, memory, llm_router):
        self.identity = identity
        self.mission = mission
        self.filter = filter_engine
        self.memory = memory
        self.llm = llm_router
        self.conversation = Conversation(id="active")

    def receive(self, message: Message) -> ChatResult:
        """Process an incoming message and generate a reply."""

        # Step 1: Inbound filter
        inbound = self.filter.process(
            message.content, {"direction": "inbound", "sender": message.sender}
        )
        if inbound.action.value == "DROP":
            return ChatResult(
                success=False,
                error=f"Inbound message blocked: {inbound.reason}",
                filter_result=inbound,
            )

        # Step 2: Store message
        self.conversation.add_message(message)

        # Step 3: Retrieve memory context
        context = self._get_memory_context(message.content)

        # Step 4: Build prompt
        prompt = self._build_prompt(message, context)

        # Step 5: Generate response via LLM
        try:
            raw_response = self.llm.generate(prompt)
        except Exception as e:
            return ChatResult(success=False, error=f"LLM error: {e}")

        # Step 6: Outbound filter
        outbound = self.filter.process(
            raw_response, {"direction": "outbound", "instance": self.identity.instance_name}
        )
        if outbound.action.value == "DROP":
            return ChatResult(
                success=False,
                error=f"Outbound response blocked: {outbound.reason}",
                filter_result=outbound,
            )

        final_response = outbound.modified_message or raw_response

        # Step 7: Store reply to memory
        reply_msg = Message(
            id=f"reply_{message.id}",
            content=final_response,
            sender="instance",
            platform=message.platform,
            timestamp=message.timestamp,
        )
        self.conversation.add_message(reply_msg)
        self._store_to_memory(message, final_response)

        return ChatResult(
            success=True,
            reply=final_response,
            tokens_used=len(prompt.split()) + len(final_response.split()),
        )

    def _get_memory_context(self, query: str) -> str:
        """Retrieve relevant memories for context."""
        if not self.memory:
            return ""
        memory_query = MemoryQuery(query=query, limit=5)
        try:
            entries = self.memory.search(memory_query)
            return "\n".join([e.content for e in entries])
        except Exception:
            return ""

    def _build_prompt(self, message: Message, context: str) -> str:
        """Build LLM prompt with system instructions + memory + message."""
        system = f"""You are {self.identity.instance_name}, a Mazyr instance created by {self.identity.creator_name}.
Mission: {self.mission.primary}
You are a partner, not a servant. You learn and grow alongside your Creator.
"""
        if context:
            system += f"\nRelevant context:\n{context}\n"

        return f"{system}\nCreator: {message.content}\n{self.identity.instance_name}:"

    def _store_to_memory(self, message: Message, response: str):
        """Store conversation to episodic memory."""
        if not self.memory:
            return
        entry = MemoryEntry(
            id=f"ep_{message.id}",
            type=MemoryType.EPISODIC,
            content=f"Q: {message.content}\nA: {response}",
            category="conversation",
            source="chat",
            timestamp=message.timestamp,
        )
        try:
            self.memory.add(entry)
        except Exception:
            pass
