from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Identity:
    """Core Identity of a Mazyr instance. Frozen = immutable after creation."""

    instance_name: str
    species: str = "Mazyr"
    creator_name: str = ""
    creator_contact: Optional[str] = None
    date_provisioned: str = ""
    vessel_type: str = "laptop"

    def __post_init__(self):
        if not self.instance_name or not self.instance_name.strip():
            raise ValueError("instance_name is required and cannot be empty")
        if not self.creator_name or not self.creator_name.strip():
            raise ValueError("creator_name is required and cannot be empty")
        if self.vessel_type not in {"laptop", "mini-pc", "desktop", "cloud-vps"}:
            raise ValueError(f"Invalid vessel_type: {self.vessel_type}")

    @property
    def is_configured(self) -> bool:
        """Returns True if identity has been customized beyond defaults."""
        return self.instance_name != "Mazyr" or self.creator_name != "Anonymous"


@dataclass
class Mission:
    """Mission configuration determines execution branching."""

    primary: str
    secondary: Optional[str] = None
    scope: list[str] = field(default_factory=lambda: ["general"])

    def __post_init__(self):
        if not self.primary or not self.primary.strip():
            raise ValueError("primary mission is required")
        if self.scope is None:
            self.scope = ["general"]
