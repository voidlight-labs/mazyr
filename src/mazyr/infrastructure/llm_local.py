import os
import subprocess

import httpx

from mazyr.infrastructure.http_pool import get_sync_client


class LocalLLM:
    """Wrapper for llama.cpp local inference.

    Supports two modes:
    1. Direct ``llama-cli`` subprocess per call (legacy, slow for repeated calls).
    2. Persistent ``llama-server`` endpoint: set ``server_url`` and the adapter
       will POST to ``/completion`` using the shared HTTP pool.
    """

    def __init__(
        self,
        model_path: str,
        ngl: int = 35,
        temp: float = 0.7,
        server_url: str = "",
        client: httpx.Client | None = None,
    ):
        self.model_path = model_path
        self.ngl = ngl
        self.temp = temp
        self.server_url = server_url
        self.client = client or get_sync_client()

    def generate(self, prompt: str, max_tokens: int = 2048) -> str:
        """Generate text using local model or a persistent local server."""
        if self.server_url:
            return self._generate_via_server(prompt, max_tokens)
        return self._generate_via_subprocess(prompt, max_tokens)

    def _generate_via_server(self, prompt: str, max_tokens: int) -> str:
        response = self.client.post(
            f"{self.server_url}/completion",
            json={
                "prompt": prompt,
                "n_predict": max_tokens,
                "temperature": self.temp,
            },
            timeout=300.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["content"].strip()

    def _generate_via_subprocess(self, prompt: str, max_tokens: int) -> str:
        cmd = [
            "llama-cli",
            "-m",
            self.model_path,
            "-p",
            prompt,
            "-n",
            str(max_tokens),
            "--temp",
            str(self.temp),
            "-ngl",
            str(self.ngl),
            "--no-display-prompt",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Local LLM error: {result.stderr}")

        return result.stdout.strip()

    def is_available(self) -> bool:
        if self.server_url:
            try:
                response = self.client.get(f"{self.server_url}/health", timeout=5.0)
                return response.status_code == 200
            except httpx.HTTPError:
                return False
        return os.path.exists(self.model_path)
