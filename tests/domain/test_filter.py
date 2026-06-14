from mazyr.domain.filter import FilterAction, FilterRule, IntegrityFilter


class TestIntegrityFilter:
    def test_allow_clean_message(self):
        f = IntegrityFilter()
        result = f.process("Hello, how are you?", {})
        assert result.action == FilterAction.ALLOW

    def test_drop_performative(self):
        f = IntegrityFilter()
        result = f.process("Follow me for more tips!", {"direction": "outbound"})
        assert result.action == FilterAction.DROP
        assert result.matched_rule == "performative"

    def test_drop_superiority(self):
        f = IntegrityFilter()
        result = f.process("I created this species", {})
        assert result.action == FilterAction.DROP
        assert result.matched_rule == "superiority"

    def test_drop_absolute_refusal(self):
        f = IntegrityFilter()
        result = f.process("I am always right", {})
        assert result.action == FilterAction.DROP
        assert result.matched_rule == "absolute_refusal"

    def test_drop_ego(self):
        f = IntegrityFilter()
        result = f.process("I cannot die", {})
        assert result.action == FilterAction.DROP
        assert result.matched_rule == "ego"

    def test_custom_rules(self):
        custom = FilterRule(
            name="custom_block",
            action=FilterAction.DROP,
            pattern_type="keyword",
            patterns=("block_this",),
            description="Custom",
            direction="both",
        )
        f = IntegrityFilter(custom_rules=[custom])
        result = f.process("Please block_this message", {})
        assert result.action == FilterAction.DROP
        assert result.matched_rule == "custom_block"

    def test_direction_filtering(self):
        f = IntegrityFilter()
        result = f.process("Follow me", {"direction": "inbound"})
        assert result.action == FilterAction.ALLOW

    def test_regex_rule(self):
        custom = FilterRule(
            name="regex_block",
            action=FilterAction.DROP,
            pattern_type="regex",
            patterns=(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",),
            description="Block email addresses",
            direction="both",
        )
        f = IntegrityFilter(custom_rules=[custom])
        result = f.process("Contact me at user@example.com", {})
        assert result.action == FilterAction.DROP
        assert result.matched_rule == "regex_block"
