from pathlib import Path
from typing import Optional

import yaml

from mazyr.domain.filter import FilterAction, FilterRule
from mazyr.domain.identity import Identity, Mission
from mazyr.domain.instance_config import InstanceConfig
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
        return Identity(
            instance_name=data.get("instance_name", "Mazyr"),
            species=data.get("species", "Mazyr"),
            creator_name=data.get("creator", "Anonymous"),
            creator_contact=data.get("creator_contact"),
            date_provisioned=data.get("date_provisioned", ""),
            vessel_type=data.get("vessel_type", "laptop"),
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

    def _parse_markdown_frontmatter(self, path: Path) -> dict:
        """Parse YAML frontmatter from markdown file."""
        with open(path) as f:
            content = f.read()

        if content.startswith("---"):
            _, yaml_part, _ = content.split("---", 2)
            return yaml.safe_load(yaml_part) or {}
        return {}
