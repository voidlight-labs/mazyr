import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional

from mazyr.application.memory_context import ContextAssembler
from mazyr.domain.filter import FilterResult
from mazyr.domain.memory_context import ContextQuery
from mazyr.domain.memory_episodic import EpisodicEntry, MessageRole
from mazyr.domain.events import FilterTriggered, MessageReceived
from mazyr.domain.message import Conversation, Message
from mazyr.domain.tool import ToolCall, ToolResult
from mazyr.infrastructure.logger import get_logger
from mazyr.infrastructure.tool_parser import (
    has_malformed_tag,
    max_retries,
    parse_tool_calls,
    strip_tool_tags,
)

log = get_logger("chat")


MAX_AGENT_ITERATIONS = 10


@dataclass
class ChatResult:
    success: bool
    reply: Optional[str] = None
    filter_result: Optional[FilterResult] = None
    error: Optional[str] = None
    tokens_used: int = 0


class ChatUseCase:
    def __init__(
        self,
        identity,
        mission,
        filter_engine,
        memory,
        llm_router,
        tool_registry=None,
        config=None,
        tool_config=None,
        extraction_queue=None,
        deduplicator=None,
        skill_registry=None,
        event_bus=None,
        learn_use_case=None,
        executor: Optional[ThreadPoolExecutor] = None,
    ):
        self.identity = identity
        self.mission = mission
        self.filter = filter_engine
        self.memory = memory
        self.llm = llm_router
        self.registry = tool_registry
        self._config = config
        self._tool_config = tool_config
        self._extraction_queue = extraction_queue
        self._deduplicator = deduplicator
        self._skill_registry = skill_registry
        self._event_bus = event_bus
        self._learn_use_case = learn_use_case
        self._context_assembler = (
            ContextAssembler(memory, skill_registry=skill_registry) if memory else None
        )
        self.conversation = Conversation(id="active")
        self._executor = executor

    def receive(self, message: Message) -> ChatResult:
        self._publish(MessageReceived(payload={"message": message}))

        # Step 1: Inbound filter
        inbound = self.filter.process(
            message.content, {"direction": "inbound", "sender": message.sender}
        )
        if inbound.action.value == "DROP":
            self._publish(FilterTriggered(result=inbound, original_message=message.content))
            return ChatResult(
                success=False,
                error=f"Inbound message blocked: {inbound.reason}",
                filter_result=inbound,
            )

        # Step 2: Store message
        self.conversation.add_message(message)

        # Step 3: Retrieve memory context
        context = self._get_memory_context(message.content)

        # Step 4: Initial prompt
        prompt = self._build_prompt(message, context)
        tool_history: list[tuple[ToolCall, ToolResult]] = []

        # Step 5: Agent loop — LLM can call tools iteratively
        for iteration in range(MAX_AGENT_ITERATIONS):
            try:
                raw_response = self._generate_with_retry(prompt)
            except RuntimeError as e:
                return ChatResult(
                    success=False,
                    error=f"LLM error after retries: {e}",
                )
            if raw_response is None:
                return ChatResult(
                    success=False,
                    error="LLM failed to produce valid output after retries",
                )

            tool_calls = parse_tool_calls(raw_response)
            if not tool_calls or not self.registry:
                # LLM responded naturally — done
                final_response = self._apply_outbound_filter(raw_response)
                self._store_reply(message, final_response)
                return ChatResult(
                    success=True,
                    reply=final_response,
                    tokens_used=0,
                )

            # Execute tool calls
            for tc in tool_calls:
                ctx = self._tool_context(message)
                result = self.registry.execute(tc, ctx)
                tool_history.append((tc, result))

            # Build continuation prompt with tool results
            prompt = self._build_continuation_prompt(message, prompt, tool_history, iteration, None)

        return ChatResult(
            success=False,
            error=f"Agent loop exceeded {MAX_AGENT_ITERATIONS} iterations",
        )

    async def areceive(self, message: Message) -> ChatResult:
        self._publish(MessageReceived(payload={"message": message}))

        inbound = await self._run(
            self.filter.process, message.content, {"direction": "inbound", "sender": message.sender}
        )
        if inbound.action.value == "DROP":
            self._publish(FilterTriggered(result=inbound, original_message=message.content))
            return ChatResult(
                success=False,
                error=f"Inbound message blocked: {inbound.reason}",
                filter_result=inbound,
            )

        self.conversation.add_message(message)
        context = await self._run(self._get_memory_context, message.content)
        prompt = self._build_prompt(message, context)
        tool_history: list[tuple[ToolCall, ToolResult]] = []

        for iteration in range(MAX_AGENT_ITERATIONS):
            try:
                raw_response = await self._run(self._generate_with_retry, prompt)
            except RuntimeError as e:
                return ChatResult(
                    success=False,
                    error=f"LLM error after retries: {e}",
                )
            if raw_response is None:
                return ChatResult(
                    success=False,
                    error="LLM failed to produce valid output after retries",
                )

            tool_calls = parse_tool_calls(raw_response)
            if not tool_calls or not self.registry:
                final_response = await self._run(self._apply_outbound_filter, raw_response)
                await self._run(self._store_reply, message, final_response)
                return ChatResult(
                    success=True,
                    reply=final_response,
                    tokens_used=0,
                )

            for tc in tool_calls:
                ctx = self._tool_context(message)
                result = await self.registry.aexecute(tc, ctx)
                tool_history.append((tc, result))

            prompt = self._build_continuation_prompt(message, prompt, tool_history, iteration, None)

        return ChatResult(
            success=False,
            error=f"Agent loop exceeded {MAX_AGENT_ITERATIONS} iterations",
        )

    def receive_stream(self, message: Message):
        self._publish(MessageReceived(payload={"message": message}))

        inbound = self.filter.process(
            message.content, {"direction": "inbound", "sender": message.sender}
        )
        if inbound.action.value == "DROP":
            self._publish(FilterTriggered(result=inbound, original_message=message.content))
            yield ("error", f"Inbound message blocked: {inbound.reason}")
            return

        self.conversation.add_message(message)
        context = self._get_memory_context(message.content)
        prompt = self._build_prompt(message, context)
        tool_history: list[tuple[ToolCall, ToolResult]] = []

        for iteration in range(MAX_AGENT_ITERATIONS):
            buffer = ""
            printed_len = 0
            in_tool_block = False
            try:
                for token in self.llm.generate_stream(prompt):
                    buffer += token
                    if in_tool_block:
                        continue
                    if "<tool" in buffer:
                        in_tool_block = True
                        idx = buffer.find("<tool")
                        if printed_len < idx:
                            yield ("token", buffer[printed_len:idx])
                            printed_len = idx
                        continue
                    printed_len = len(buffer)
                    yield ("token", token)
            except Exception as e:
                yield ("error", f"LLM error: {e}")
                return

            tool_calls = parse_tool_calls(buffer)
            if not tool_calls or not self.registry:
                if in_tool_block and printed_len < len(buffer):
                    yield ("token", buffer[printed_len:])
                final_response = self._apply_outbound_filter(buffer)
                self._store_reply(message, final_response)
                yield ("done", final_response)
                return

            for tc in tool_calls:
                ctx = {
                    "session_id": self.conversation.id,
                    "platform": message.platform,
                    "identity": self.identity,
                    "mission": self.mission,
                    "filter": self.filter,
                    "memory": self.memory,
                    "config": getattr(self, "_config", None),
                    "tool_config": getattr(self, "_tool_config", None),
                    "deduplicator": self._deduplicator,
                    "skill_registry": self._skill_registry,
                }
                yield ("tool_call", tc.name, tc.params)
                result = self.registry.execute(tc, ctx)
                tool_history.append((tc, result))
                yield ("tool_result", result)

            prompt = self._build_continuation_prompt(message, prompt, tool_history, iteration, None)

        yield ("error", f"Agent loop exceeded {MAX_AGENT_ITERATIONS} iterations")

    async def areceive_stream(self, message: Message):
        self._publish(MessageReceived(payload={"message": message}))

        inbound = await self._run(
            self.filter.process, message.content, {"direction": "inbound", "sender": message.sender}
        )
        if inbound.action.value == "DROP":
            self._publish(FilterTriggered(result=inbound, original_message=message.content))
            yield ("error", f"Inbound message blocked: {inbound.reason}")
            return

        self.conversation.add_message(message)
        context = await self._run(self._get_memory_context, message.content)
        prompt = self._build_prompt(message, context)
        tool_history: list[tuple[ToolCall, ToolResult]] = []

        for iteration in range(MAX_AGENT_ITERATIONS):
            buffer = ""
            printed_len = 0
            in_tool_block = False
            try:
                async for token in self._generate_stream_async(prompt):
                    buffer += token
                    if in_tool_block:
                        continue
                    if "<tool" in buffer:
                        in_tool_block = True
                        idx = buffer.find("<tool")
                        if printed_len < idx:
                            yield ("token", buffer[printed_len:idx])
                            printed_len = idx
                        continue
                    printed_len = len(buffer)
                    yield ("token", token)
            except Exception as e:
                yield ("error", f"LLM error: {e}")
                return

            tool_calls = parse_tool_calls(buffer)
            if not tool_calls or not self.registry:
                if in_tool_block and printed_len < len(buffer):
                    yield ("token", buffer[printed_len:])
                final_response = await self._run(self._apply_outbound_filter, buffer)
                await self._run(self._store_reply, message, final_response)
                yield ("done", final_response)
                return

            for tc in tool_calls:
                ctx = self._tool_context(message)
                yield ("tool_call", tc.name, tc.params)
                result = await self.registry.aexecute(tc, ctx)
                tool_history.append((tc, result))
                yield ("tool_result", result)

            prompt = self._build_continuation_prompt(message, prompt, tool_history, iteration, None)

        yield ("error", f"Agent loop exceeded {MAX_AGENT_ITERATIONS} iterations")

    async def _generate_stream_async(self, prompt: str):
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[str | Exception | None] = asyncio.Queue()

        def producer():
            try:
                for token in self.llm.generate_stream(prompt):
                    loop.call_soon_threadsafe(queue.put_nowait, token)
                loop.call_soon_threadsafe(queue.put_nowait, None)
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, e)

        loop.run_in_executor(self._executor, producer)

        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item

    def _tool_context(self, message: Message) -> dict:
        return {
            "session_id": self.conversation.id,
            "platform": message.platform,
            "identity": self.identity,
            "mission": self.mission,
            "filter": self.filter,
            "memory": self.memory,
            "config": getattr(self, "_config", None),
            "tool_config": getattr(self, "_tool_config", None),
            "deduplicator": self._deduplicator,
            "skill_registry": self._skill_registry,
        }

    async def _run(self, fn, *args):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, fn, *args)

    def _publish(self, event) -> None:
        if self._event_bus is None:
            return
        try:
            self._event_bus.publish(event)
        except Exception:
            log.exception("Failed to publish event %s", getattr(event, "event_type", "?"))

    def _maybe_learn(self) -> None:
        if self._learn_use_case is None:
            return
        try:
            pattern = self._learn_use_case.extract_pattern(self.conversation)
            if pattern:
                log.info("Learned pattern: %s", pattern)
        except Exception:
            log.exception("Learning extraction failed")

    def _build_continuation_prompt(
        self,
        message: Message,
        previous_prompt: str,
        tool_history: list[tuple[ToolCall, ToolResult]],
        iteration: int,
        prior_natural: str | None = None,
    ) -> str:
        tool_block = ""
        for tc, tr in tool_history[-5:]:
            status = "succeeded" if tr.success else "failed"
            tool_block += f'\n<tool_result name="{tc.name}" status="{status}">'
            if tr.data:
                tool_block += f"\n{tr.data}"
            if tr.error:
                tool_block += f"\nError: {tr.error}"
            tool_block += "\n</tool_result>"

        remaining = MAX_AGENT_ITERATIONS - iteration - 1
        continuation = f"---\nTool results:{tool_block}\n\n"
        continuation += (
            f"You may call more tools if needed "
            f"({remaining} iterations remaining), or respond naturally to the Creator.\n"
            f"{self.identity.instance_name}:"
        )
        return f"{previous_prompt}\n\n{continuation}"

    def _generate_with_retry(self, prompt: str) -> Optional[str]:
        last_error: str | None = None
        for attempt in range(max_retries() + 1):
            current_prompt = prompt
            if attempt > 0:
                current_prompt = (
                    f"{prompt}\n\n---\n"
                    f"Note: Your previous response contained an incomplete tool tag. "
                    f"When using a tool, the format must be exactly:\n"
                    f'<tool name="tool_name">{{"param": "value"}}</tool>\n'
                    f"Make sure every <tool> has a matching </tool>.\n"
                    f"{self.identity.instance_name}:"
                )
            try:
                raw = self.llm.generate(current_prompt)
            except Exception as e:
                last_error = str(e)
                log.warning("LLM attempt %d raised: %s", attempt, last_error)
                if attempt < max_retries():
                    continue
                return None

            malformed = has_malformed_tag(raw)
            log.debug("LLM attempt %d malformed=%s len=%d", attempt, malformed, len(raw))

            if malformed:
                cleaned = strip_tool_tags(raw)
                log.debug(
                    "Strip result: malformed=%s len=%d",
                    has_malformed_tag(cleaned),
                    len(cleaned),
                )
                if cleaned and not has_malformed_tag(cleaned):
                    return cleaned
                continue

            return raw

        if last_error:
            raise RuntimeError(last_error)
        return None

    def _apply_outbound_filter(self, text: str) -> str:
        outbound = self.filter.process(
            text, {"direction": "outbound", "instance": self.identity.instance_name}
        )
        if outbound.action.value == "DROP":
            self._publish(FilterTriggered(result=outbound, original_message=text))
            return "I'm sorry, I couldn't generate an appropriate response."
        return outbound.modified_message or text

    def _get_memory_context(self, query: str) -> str:
        if not self._context_assembler:
            return ""
        try:
            ctx_query = ContextQuery(query=query)
            result = self._context_assembler.assemble(ctx_query)
            return result.formatted
        except Exception as e:
            log.warning("Context assembly failed: %s", e)
            return ""

    def _build_prompt(self, message: Message, context: str) -> str:
        system = f"""You are {self.identity.instance_name}, a Mazyr instance created by {self.identity.creator_name}.
Mission: {self.mission.primary}
You are a partner, not a servant. You learn and grow alongside your Creator.
Always respond in the same language as the Creator.

You have tools available to explore and gather information autonomously.
Use them to answer the Creator's questions — you can call multiple tools in sequence
until you have enough information, then respond naturally.

STRICT TURN RULES:
1. For questions about your capabilities, status, or memory, use the available tools to answer accurately.
2. If you already have enough information, respond naturally with reasoning and final answer.
3. If you need tool results, write at most one short sentence as a transition, then output ONLY the tool tags.
   Do not write the full answer before the tool tags.
4. After tool results arrive, respond naturally with the full answer. Do not repeat the transition sentence or the pre-tool text."""

        if self.registry:
            tools_block = "\n\nAVAILABLE TOOLS:\n"
            for td in self.registry.get_tool_definitions():
                schema_desc = ", ".join(f"{k}: {v}" for k, v in td.param_schema.items())
                tools_block += (
                    f'  <tool name="{td.name}">{{{schema_desc}}}</tool>  — {td.description}\n'
                )
            tools_block += (
                "\nTo use a tool, output EXACTLY:\n"
                '<tool name="tool_name">{"param": "value"}</tool>\n'
                "After the tool executes, you will see the result and can decide what to do next.\n"
                "Keep calling tools until you have enough info, then respond naturally."
            )
            system += tools_block

        if context:
            system += f"\n\n{context}\n"

        return f"{system}\n\nCreator: {message.content}\n{self.identity.instance_name}:"

    def _store_reply(self, message: Message, response: str):
        reply_msg = Message(
            id=f"reply_{message.id}",
            content=response,
            sender="instance",
            platform=message.platform,
            timestamp=message.timestamp,
        )
        self.conversation.add_message(reply_msg)
        self._store_to_memory(message, response)
        self._maybe_learn()

    def _store_to_memory(self, message: Message, response: str):
        if not self.memory:
            return
        entry = EpisodicEntry(
            id=f"ep_{message.id}",
            session_id=self.conversation.id,
            role=MessageRole.ASSISTANT,
            content=f"Q: {message.content}\nA: {response}",
            timestamp=message.timestamp,
        )
        try:
            self.memory.add(entry)
        except Exception:
            pass
        if self._extraction_queue:
            try:
                user_entry = EpisodicEntry(
                    id=f"ep_{message.id}_user",
                    session_id=self.conversation.id,
                    role=MessageRole.USER,
                    content=message.content,
                    timestamp=message.timestamp,
                )
                self._extraction_queue.submit(user_entry)
            except Exception:
                pass

    def flush(self):
        if self._extraction_queue:
            try:
                self._extraction_queue.flush_all()
            except Exception:
                pass

    def close(self):
        self.flush()
        if self.memory:
            try:
                self.memory.close()
            except Exception:
                pass
