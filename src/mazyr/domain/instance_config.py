from typing import Optional
from pydantic import BaseModel, Field, field_validator
from mazyr.infrastructure.paths import MAZYR_HOME


class InstanceConfig(BaseModel):
    """Runtime configuration for a Mazyr instance. Validated using Pydantic as per MTS-05."""

    # LLM Configuration
    api_key: Optional[str] = None
    base_url: str = "https://api.moonshot.cn/v1"
    model: str = "kimi-k2-6"

    # Local LLM
    local_model_path: str = ""

    # Inference Preference: local, cloud, hybrid
    inference_preference: str = Field(default="hybrid", pattern="^(local|cloud|hybrid)$")

    # Memory (fixed paths, managed by Docker Compose)
    sqlite_path: str = Field(
        default_factory=lambda: str(MAZYR_HOME / "memory" / "mazyr.db")
    )
    qdrant_host: str = "localhost"
    qdrant_port: int = Field(default=6333, ge=1, le=65535)
    qdrant_enabled: bool = False
    embedding_api_key: Optional[str] = None
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = Field(default=1536, ge=1)

    # Messenger
    telegram_bot_token: Optional[str] = None

    # GitHub Sync
    github_token: Optional[str] = None
    github_repo: Optional[str] = None

    # Relay
    relay_endpoint: Optional[str] = None
    instance_id: str = "mazyr-001"

    @property
    def use_cloud_llm(self) -> bool:
        return self.inference_preference in ("cloud", "hybrid") and bool(self.api_key)

    @property
    def use_local_llm(self) -> bool:
        return self.inference_preference in ("local", "hybrid") and bool(self.local_model_path)
