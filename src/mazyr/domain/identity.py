from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Identity(BaseModel):
    """Core Identity of a Mazyr instance. Validated using Pydantic as per MTS-05."""

    model_config = ConfigDict(frozen=True)

    instance_name: str = Field(..., min_length=1, max_length=64)
    species: str = Field(default="Mazyr")
    creator_name: str = Field(..., min_length=1, max_length=128)
    creator_contact: Optional[str] = Field(default=None, max_length=256)
    date_provisioned: str = Field(default="")
    vessel_type: str = Field(default="laptop")

    @field_validator("vessel_type")
    @classmethod
    def validate_vessel(cls, v: str) -> str:
        allowed = {"laptop", "mini-pc", "desktop", "cloud-vps"}
        if v not in allowed:
            raise ValueError(f"vessel_type must be one of {allowed}")
        return v

    @property
    def is_configured(self) -> bool:
        """Returns True if identity has been customized beyond defaults."""
        return self.instance_name != "Mazyr" or self.creator_name != "Anonymous"


class Mission(BaseModel):
    """Mission configuration. Validated using Pydantic as per MTS-05."""

    primary: str = Field(..., min_length=1, max_length=512)
    secondary: Optional[str] = Field(default=None, max_length=512)
    scope: list[str] = Field(default_factory=lambda: ["general"])

    @field_validator("scope", mode="before")
    @classmethod
    def parse_scope(cls, v):
        if isinstance(v, str):
            return [s.strip() for s in v.split(",")]
        return v
