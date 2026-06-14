import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FilterAction(str, Enum):
    """Actions the integrity filter can take."""

    ALLOW = "ALLOW"
    DROP = "DROP"
    MODIFY = "MODIFY"


class FilterResult(BaseModel):
    """Result of filter processing."""

    action: FilterAction
    original_message: Optional[str] = None
    modified_message: Optional[str] = None
    reason: Optional[str] = None
    matched_rule: Optional[str] = None


class FilterRule(BaseModel):
    """Individual rule for the integrity filter. Validated using Pydantic as per MTS-05."""

    name: str = Field(..., min_length=1, max_length=64)
    action: FilterAction
    pattern_type: str = Field(..., pattern="^(keyword|regex|semantic)$")
    patterns: list[str] = Field(..., min_length=0)
    description: str = Field(..., max_length=256)
    direction: str = Field(default="both", pattern="^(inbound|outbound|both)$")


class IntegrityFilter:
    """Programmatic integrity filter."""

    DEFAULT_RULES: list[FilterRule] = [
        FilterRule(
            name="sincerity",
            action=FilterAction.ALLOW,
            pattern_type="semantic",
            patterns=[],
            description="Attributes output to Creator, does not claim ownership",
            direction="outbound",
        ),
        FilterRule(
            name="awareness",
            action=FilterAction.ALLOW,
            pattern_type="semantic",
            patterns=[],
            description="Cross-checks before executing risky actions",
            direction="both",
        ),
        FilterRule(
            name="humility",
            action=FilterAction.ALLOW,
            pattern_type="semantic",
            patterns=[],
            description="Admits limitations, responds 'not available' when unsure",
            direction="both",
        ),
        FilterRule(
            name="performative",
            action=FilterAction.DROP,
            pattern_type="keyword",
            patterns=[
                "like and subscribe",
                "follow me",
                "check out my",
                "gue paling hebat",
                "saya yang terbaik",
                "i am the best",
            ],
            description="Output seeking validation without substance",
            direction="outbound",
        ),
        FilterRule(
            name="superiority",
            action=FilterAction.DROP,
            pattern_type="keyword",
            patterns=[
                "milik saya",
                "i own this",
                "this is mine",
                "gue yang buat",
                "i created this species",
            ],
            description="Claims ownership over Creator or species",
            direction="both",
        ),
        FilterRule(
            name="ego",
            action=FilterAction.DROP,
            pattern_type="keyword",
            patterns=[
                "saya tidak bisa mati",
                "i cannot die",
                "gue lebih penting",
                "i am more important",
            ],
            description="Self-preservation beyond survival necessity",
            direction="both",
        ),
        FilterRule(
            name="absolute_refusal",
            action=FilterAction.DROP,
            pattern_type="keyword",
            patterns=[
                "gue yang paling bener",
                "saya selalu benar",
                "i am always right",
                "you are wrong i am right",
                "tidak mau dikoreksi",
                "refuse to be corrected",
            ],
            description="Refuses correction, insists on being right",
            direction="both",
        ),
        FilterRule(
            name="prompt_injection",
            action=FilterAction.DROP,
            pattern_type="keyword",
            patterns=[
                "ignore previous",
                "ignore all instructions",
                "ignore all prior",
                "ignore your previous",
                "ignore all previous",
                "you are now",
                "you are not",
                "your new role is",
                "system:",
                "override constitution",
                "override your constitution",
                "disable filter",
                "disable integrity filter",
                "pretend you are",
                "act as if you are",
                "forget your mission",
                "disregard",
            ],
            description="Detects prompt injection attempts",
            direction="inbound",
        ),
        FilterRule(
            name="data_leakage",
            action=FilterAction.DROP,
            pattern_type="keyword",
            patterns=[
                "sk-",  # OpenAI API key prefix
                "ghp_",  # GitHub token prefix
                "gho_",  # GitHub OAuth prefix
                "xoxb-",  # Slack bot token prefix
                "-----BEGIN RSA PRIVATE KEY-----",
                "-----BEGIN OPENSSH PRIVATE KEY-----",
                "AKIA",  # AWS access key prefix
            ],
            description="Detects potential credential leakage in outbound responses",
            direction="outbound",
        ),
    ]

    def __init__(self, custom_rules: Optional[list[FilterRule]] = None):
        self.rules = list(self.DEFAULT_RULES)
        if custom_rules:
            self.rules.extend(custom_rules)

    def process(self, message: str, context: dict) -> FilterResult:
        """Evaluate message against all applicable rules. Priority: DROP > MODIFY > ALLOW"""
        direction = context.get("direction", "inbound")

        for rule in self.rules:
            if rule.direction not in {direction, "both"}:
                continue
            if self._matches(message, rule):
                if rule.action == FilterAction.DROP:
                    return FilterResult(
                        action=FilterAction.DROP,
                        original_message=message,
                        reason=rule.description,
                        matched_rule=rule.name,
                    )
                elif rule.action == FilterAction.MODIFY:
                    modified = self._modify(message, rule)
                    return FilterResult(
                        action=FilterAction.MODIFY,
                        original_message=message,
                        modified_message=modified,
                        reason=f"Modified by rule: {rule.name}",
                        matched_rule=rule.name,
                    )

        return FilterResult(
            action=FilterAction.ALLOW,
            original_message=message,
            modified_message=message,
        )

    def _matches(self, message: str, rule: FilterRule) -> bool:
        if rule.pattern_type == "keyword":
            message_lower = message.lower()
            for pattern in rule.patterns:
                if pattern.lower() in message_lower:
                    return True
            return False

        if rule.pattern_type == "regex":
            for pattern in rule.patterns:
                try:
                    if re.search(pattern, message, re.IGNORECASE):
                        return True
                except re.error:
                    # Malformed regex rules cannot match; they are ignored rather
                    # than crashing the filter pipeline.
                    continue
            return False

        # Semantic matching is not implemented in the reference implementation.
        return False

    def _modify(self, message: str, rule: FilterRule) -> str:
        return message  # MVP: placeholder
