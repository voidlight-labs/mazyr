import json
import re

from mazyr.domain.tool import ToolCall

TOOL_TAG_RE = re.compile(r'<tool\s+name="(\w+)"\s*>(.*?)</tool>', re.DOTALL)

MALFORMED_RE = re.compile(r"<tool", re.IGNORECASE)


def parse_tool_calls(llm_output: str) -> list[ToolCall]:
    """Extract <tool name="...">{...}</tool> calls from LLM output."""
    tools: list[ToolCall] = []
    for match in TOOL_TAG_RE.finditer(llm_output):
        name = match.group(1)
        raw_params = match.group(2).strip()
        params: dict = {}
        if raw_params:
            try:
                params = json.loads(raw_params)
            except json.JSONDecodeError:
                continue
        tools.append(ToolCall(name=name, params=params))
    return tools


def has_malformed_tag(text: str) -> bool:
    """Check if text contains malformed/incomplete <tool tags."""
    if not MALFORMED_RE.search(text):
        return False
    open_count = len(MALFORMED_RE.findall(text))
    close_count = text.count("</tool>")
    return open_count != close_count


def strip_tool_tags(text: str) -> str:
    """Remove <tool> tags and their content from text."""
    return TOOL_TAG_RE.sub("", text).strip()


def max_retries() -> int:
    return 2
