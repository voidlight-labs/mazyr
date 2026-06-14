from mazyr.infrastructure.tool_parser import (
    parse_tool_calls,
    has_malformed_tag,
    strip_tool_tags,
    max_retries,
)


class TestParseToolCalls:
    def test_single_tool(self):
        output = '<tool name="test_tool">{"key": "value"}</tool>'
        calls = parse_tool_calls(output)
        assert len(calls) == 1
        assert calls[0].name == "test_tool"
        assert calls[0].params == {"key": "value"}

    def test_multiple_tools(self):
        output = (
            '<tool name="tool_a">{"x": 1}</tool>' "some text" '<tool name="tool_b">{"y": 2}</tool>'
        )
        calls = parse_tool_calls(output)
        assert len(calls) == 2
        assert calls[0].name == "tool_a"
        assert calls[1].name == "tool_b"

    def test_no_tool(self):
        output = "Hello, how can I help you?"
        calls = parse_tool_calls(output)
        assert len(calls) == 0

    def test_empty_params(self):
        output = '<tool name="no_params"></tool>'
        calls = parse_tool_calls(output)
        assert len(calls) == 1
        assert calls[0].params == {}

    def test_malformed_json(self):
        output = '<tool name="bad_json">{invalid</tool>'
        calls = parse_tool_calls(output)
        assert len(calls) == 0

    def test_multiline_params(self):
        output = '<tool name="multi">\n{"a": 1}\n</tool>'
        calls = parse_tool_calls(output)
        assert len(calls) == 1
        assert calls[0].params == {"a": 1}


class TestHasMalformedTag:
    def test_no_tag(self):
        assert has_malformed_tag("hello") is False

    def test_complete_tag(self):
        assert has_malformed_tag('<tool name="x">{"a":1}</tool>') is False

    def test_missing_close(self):
        assert has_malformed_tag('<tool name="x">{"a":1}') is True

    def test_extra_close(self):
        assert has_malformed_tag('<tool name="x">{"a":1}</tool></tool>') is True


class TestStripToolTags:
    def test_strip_single(self):
        result = strip_tool_tags('<tool name="x">{"a":1}</tool>and some text')
        assert result == "and some text"

    def test_no_tags(self):
        result = strip_tool_tags("hello world")
        assert result == "hello world"


class TestMaxRetries:
    def test_value(self):
        assert max_retries() == 2
