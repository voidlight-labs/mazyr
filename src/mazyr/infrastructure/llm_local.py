import subprocess
from typing import Optional


class LocalLLM:
    """Wrapper for llama.cpp local inference."""

    def __init__(self, model_path: str, ngl: int = 35, temp: float = 0.7):
        self.model_path = model_path
        self.ngl = ngl
        self.temp = temp

    def generate(self, prompt: str, max_tokens: int = 2048) -> str:
        """Generate text using local model."""
        cmd = [
            "llama-cli",
            "-m", self.model_path,
            "-p", prompt,
            "-n", str(max_tokens),
            "--temp", str(self.temp),
            "-ngl", str(self.ngl),
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
        import os
        return os.path.exists(self.model_path)
