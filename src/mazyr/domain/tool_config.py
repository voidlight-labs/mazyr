from pydantic import BaseModel, Field


class AbuseThresholds(BaseModel):
    add_memory_per_session: int = 20
    web_search_per_minute: int = 10
    run_code_consecutive_timeout: int = 3


class Tier2Config(BaseModel):
    auto_execute: bool = True
    log_level: str = "full"
    abuse_thresholds: AbuseThresholds = Field(default_factory=AbuseThresholds)


class Tier3Config(BaseModel):
    auto_execute: bool = False
    approval_timeout_minutes: int = 10
    notify_channel: str = "cli"


class SandboxConfig(BaseModel):
    run_code_timeout_seconds: int = 30


class ToolRegistryConfig(BaseModel):
    tier_overrides: dict[str, int] = Field(default_factory=dict)
    tier1: dict = Field(default_factory=lambda: {"auto_execute": True, "log_level": "audit"})
    tier2: Tier2Config = Field(default_factory=Tier2Config)
    tier3: Tier3Config = Field(default_factory=Tier3Config)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    read_file_whitelist: list[str] = Field(
        default_factory=lambda: [
            "/mazyr/context/",
            "/mazyr/knowledge/",
            "/mazyr/logs/",
        ]
    )
    file_write_base_dir: str = Field(default="~/.mazyr/workspace")
    external_api_whitelist: dict[str, int] = Field(
        default_factory=lambda: {
            "api.github.com": 2,
            "api.telegram.org": 2,
        }
    )
