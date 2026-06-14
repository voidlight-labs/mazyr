from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from mazyr.domain.filter import FilterAction, FilterRule
from mazyr.domain.identity import Identity, Mission
from mazyr.domain.instance_config import InstanceConfig
from mazyr.domain.tool_config import ToolRegistryConfig
from mazyr.infrastructure.paths import MAZYR_HOME


class ConfigLoader:
    """Loads configuration from .mazyr/ directory. Validates using Domain Layer entities."""

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else MAZYR_HOME
        self.mazyr_dir = self.base_dir

    def load_identity(self, base_dir: str | Path | None = None) -> Optional[Identity]:
        """Load identity from .mazyr/identity.md"""
        path = Path(base_dir) / "identity.md" if base_dir else self.mazyr_dir / "identity.md"
        if not path.exists():
            return None

        data = self._parse_markdown_frontmatter(path)
        date_provisioned = data.get("date_provisioned")
        if isinstance(date_provisioned, datetime):
            date_provisioned = date_provisioned.isoformat()

        return Identity(
            instance_name=data.get("instance_name") or "Mazyr",
            species=data.get("species") or "Mazyr",
            creator_name=data.get("creator") or "Anonymous",
            creator_contact=data.get("creator_contact"),
            date_provisioned=date_provisioned or "",
            vessel_type=data.get("vessel_type") or "laptop",
        )

    def load_mission(self, base_dir: str | Path | None = None) -> Optional[Mission]:
        """Load mission from .mazyr/mission.md"""
        path = Path(base_dir) / "mission.md" if base_dir else self.mazyr_dir / "mission.md"
        if not path.exists():
            return None

        data = self._parse_markdown_frontmatter(path)
        scope_str = data.get("scope", "general")
        if isinstance(scope_str, list):
            scope = scope_str
        else:
            scope = [s.strip() for s in scope_str.split(",")]

        return Mission(
            primary=data.get("primary", ""),
            secondary=data.get("secondary"),
            scope=scope,
        )

    def load_config(self) -> Optional[InstanceConfig]:
        """Load runtime config from .mazyr/config.yaml"""
        path = self.mazyr_dir / "config.yaml"
        if not path.exists():
            return None

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        sqlite_path = data.get("sqlite_path")
        if sqlite_path:
            sqlite_path = Path(sqlite_path)
            if not sqlite_path.is_absolute():
                data["sqlite_path"] = str(self.mazyr_dir / sqlite_path)
        else:
            data["sqlite_path"] = str(self.mazyr_dir / "memory" / "mazyr.db")

        return InstanceConfig(**data)

    def load_custom_rules(self) -> list[FilterRule]:
        """Load custom filter rules from .mazyr/filter-custom.json"""
        path = self.mazyr_dir / "filter-custom.json"
        if not path.exists():
            return []

        import json

        with open(path) as f:
            data = json.load(f)

        rules = []
        for r in data.get("rules", []):
            rules.append(
                FilterRule(
                    name=r["name"],
                    action=FilterAction(r["action"]),
                    pattern_type=r["pattern_type"],
                    patterns=tuple(r["patterns"]),
                    description=r["description"],
                    direction=r.get("direction", "both"),
                )
            )
        return rules

    def load_tool_registry_config(self) -> ToolRegistryConfig:
        """Load tool registry config from .mazyr/tool_registry.yaml"""
        path = self.mazyr_dir / "tool_registry.yaml"
        if not path.exists():
            return ToolRegistryConfig()

        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return ToolRegistryConfig(**data)

    def _parse_markdown_frontmatter(self, path: Path) -> dict:
        """Parse YAML frontmatter from markdown file."""
        with open(path) as f:
            content = f.read()

        if content.startswith("---"):
            _, yaml_part, _ = content.split("---", 2)
            return yaml.safe_load(yaml_part) or {}
        return {}
