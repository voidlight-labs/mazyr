import os
import yaml
from pathlib import Path
from typing import Optional

from mazyr.domain.identity import Identity, Mission
from mazyr.domain.filter import FilterRule, FilterAction


class ConfigLoader:
    """Loads configuration from .mazyr/ directory. Validates using Domain Layer entities."""

    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.mazyr_dir = self.base_dir / ".mazyr"

    def load_identity(self, base_dir: str = None) -> Optional[Identity]:
        """Load identity from .mazyr/identity.md"""
        path = Path(base_dir or self.base_dir) / ".mazyr" / "identity.md"
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

    def load_mission(self, base_dir: str = None) -> Optional[Mission]:
        """Load mission from .mazyr/mission.md"""
        path = Path(base_dir or self.base_dir) / ".mazyr" / "mission.md"
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
