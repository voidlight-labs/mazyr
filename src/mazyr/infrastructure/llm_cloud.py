import json

import httpx

from mazyr.infrastructure.http_pool import get_sync_client
from mazyr.infrastructure.logger import get_logger
from mazyr.infrastructure.retry import retry_llm

log = get_logger("llm.cloud")


class CloudLLM:
    """Wrapper for Kimi API (OpenAI-compatible)."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.moonshot.cn/v1",
        model: str = "kimi-k2-6",
        client: httpx.Client | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.client = client or get_sync_client()
        self._headers = {"Authorization": f"Bearer {api_key}"}

    def _build_body(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
    ) -> dict:
        model_name = model or self.model
        body: dict = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
        }
        if model_name.startswith(("gpt-5", "o1", "o3")):
            body["max_completion_tokens"] = max_tokens
        else:
            body["temperature"] = temperature
            body["max_tokens"] = max_tokens
        if stream:
            body["stream"] = True
        return body

    @retry_llm
    def generate(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Generate text using cloud API (non-streaming)."""
        body = self._build_body(prompt, model, temperature, max_tokens, stream=False)
        model_name = model or self.model
        log.info("LLM request model=%s prompt_len=%d", model_name, len(prompt))
        response = self.client.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers,
            json=body,
        )
        if response.status_code != 200:
            log.error(
                "LLM API error: %d %s — %s",
                response.status_code,
                response.reason_phrase,
                response.text,
            )
            raise RuntimeError(
                f"LLM error: {response.status_code} {response.reason_phrase} — {response.text}"
            )
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        log.info("LLM response model=%s response_len=%d", model_name, len(content))
        return content

    @retry_llm
    def generate_stream(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ):
        """Generate text using cloud API (streaming). Yields tokens as they arrive."""
        body = self._build_body(prompt, model, temperature, max_tokens, stream=True)
        model_name = model or self.model
        log.info("LLM stream request model=%s prompt_len=%d", model_name, len(prompt))
        with self.client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers=self._headers,
            json=body,
        ) as response:
            if response.status_code != 200:
                log.error(
                    "LLM stream error: %d %s — %s",
                    response.status_code,
                    response.reason_phrase,
                    response.text,
                )
                raise RuntimeError(
                    f"LLM error: {response.status_code} {response.reason_phrase} — {response.text}"
                )
            for line in response.iter_lines():
                if not line:
                    continue
                text = line.decode() if isinstance(line, bytes) else line
                if text.startswith("data: "):
                    payload = text[6:]
                    if payload.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                        delta = chunk["choices"][0]["delta"]
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass

    def is_available(self) -> bool:
        return bool(self.api_key)
