import httpx


class CloudLLM:
    """Wrapper for Kimi API (OpenAI-compatible)."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.moonshot.cn/v1",
        model: str = "kimi-k2-6",
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )

    def generate(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Generate text using cloud API."""
        response = self.client.post(
            "/chat/completions",
            json={
                "model": model or self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def is_available(self) -> bool:
        return bool(self.api_key)
