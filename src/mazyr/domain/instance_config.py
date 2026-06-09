from dataclasses import dataclass, field
from typing import Optional


@dataclass
class InstanceConfig:
    """Runtime configuration for a Mazyr instance.

    All values are collected during `mazyr-init` and persisted in
    `.mazyr/config.yaml`. No environment variables or .env files are used.

    SQLite path and Qdrant connection are fixed (managed by Docker Compose).
    """

    # LLM Configuration
    api_key: Optional[str] = None
    base_url: str = "https://api.moonshot.cn/v1"
    model: str = "kimi-k2-6"

    # Local LLM
    local_model_path: str = ""

    # Inference Preference: local, cloud, hybrid
    inference_preference: str = "hybrid"

    # Memory (fixed paths, managed by Docker Compose)
    sqlite_path: str = field(default="./memory/mazyr.db", repr=False)
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_enabled: bool = False

    # Messenger
    telegram_bot_token: Optional[str] = None

    # GitHub Sync
    github_token: Optional[str] = None
    github_repo: Optional[str] = None

    # Relay
    relay_endpoint: Optional[str] = None
    instance_id: str = "mazyr-001"

    def __post_init__(self):
        if self.inference_preference not in {"local", "cloud", "hybrid"}:
            raise ValueError(
                f"inference_preference must be one of local/cloud/hybrid, "
                f"got {self.inference_preference}"
            )
        if self.qdrant_port < 1 or self.qdrant_port > 65535:
            raise ValueError(f"qdrant_port must be 1-65535, got {self.qdrant_port}")

    @property
    def use_cloud_llm(self) -> bool:
        return self.inference_preference in ("cloud", "hybrid") and bool(self.api_key)

    @property
    def use_local_llm(self) -> bool:
        return self.inference_preference in ("local", "hybrid") and bool(self.local_model_path)
