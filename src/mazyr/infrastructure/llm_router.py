from enum import Enum


class InferencePreference(str, Enum):
    """Preference for LLM inference routing."""

    LOCAL = "local"
    CLOUD = "cloud"
    HYBRID = "hybrid"


class LLMRouter:
    """Routes inference requests between local and cloud LLM."""

    def __init__(
        self, local_llm, cloud_llm, preference: InferencePreference = InferencePreference.HYBRID
    ):
        self.local = local_llm
        self.cloud = cloud_llm
        self.preference = preference
        self.local_available = False
        self.cloud_available = False

    def initialize(self):
        self.local_available = self.local.is_available() if self.local else False
        self.cloud_available = self.cloud.is_available() if self.cloud else False

    def generate(self, prompt: str, complexity: str = "auto") -> str:
        if self.preference == InferencePreference.LOCAL and self.local_available:
            return self.local.generate(prompt)

        if self.preference == InferencePreference.CLOUD and self.cloud_available:
            return self.cloud.generate(prompt)

        if complexity == "auto":
            complexity = self._estimate_complexity(prompt)

        if complexity == "simple" and self.local_available:
            return self.local.generate(prompt)

        if self.cloud_available:
            return self.cloud.generate(prompt)

        if self.local_available:
            return self.local.generate(prompt)

        raise RuntimeError("No LLM available. Check local model path and cloud API key.")

    def generate_stream(self, prompt: str):
        """Stream tokens from the preferred LLM."""
        if self.preference == InferencePreference.CLOUD and self.cloud_available:
            yield from self.cloud.generate_stream(prompt)
            return
        if self.preference == InferencePreference.LOCAL and self.local_available:
            yield from self.local.generate_stream(prompt)
            return
        if self.cloud_available:
            yield from self.cloud.generate_stream(prompt)
            return
        if self.local_available:
            yield from self.local.generate_stream(prompt)
            return
        raise RuntimeError("No LLM available for streaming.")

    def _estimate_complexity(self, prompt: str) -> str:
        if len(prompt) < 500 and "code" not in prompt.lower():
            return "simple"
        if len(prompt) > 2000 or "analyze" in prompt.lower():
            return "complex"
        return "medium"
