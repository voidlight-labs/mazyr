"""Load skill files from ~/.mazyr/skills/.

Skills are markdown files with YAML frontmatter, matching the format used for
identity.md and mission.md (MTS-08 Tier 5: Procedural Memory).

During `mazyr init`, bundled skills are copied into ~/.mazyr/skills/ so that
skills live with the instance data rather than the source tree.
"""

from pathlib import Path
from typing import Optional

import yaml

from mazyr.domain.skills import Skill
from mazyr.infrastructure.paths import MAZYR_HOME


class SkillLoader:
    """Load Skill objects from markdown files with YAML frontmatter."""

    def __init__(
        self,
        user_dir: Path | str | None = None,
        bundled_dir: Path | str | None = None,
    ):
        self.user_dir = Path(user_dir) if user_dir else MAZYR_HOME / "skills"
        self.bundled_dir = Path(bundled_dir) if bundled_dir else None

    def load_all(self) -> dict[str, Skill]:
        """Load all skills from the user skills directory.

        If a bundled_dir was provided explicitly (e.g. during tests or init),
        bundled skills are loaded first and user skills override them.
        """
        skills: dict[str, Skill] = {}
        sources = [self.user_dir]
        if self.bundled_dir:
            sources.insert(0, self.bundled_dir)
        for source_dir in sources:
            if source_dir.exists():
                for path in source_dir.glob("*.md"):
                    skill = self._load_one(path)
                    if skill:
                        skills[skill.name] = skill
        return skills

    def load(self, name: str) -> Optional[Skill]:
        """Load a single skill by name from the user skills directory."""
        path = self.user_dir / f"{name}.md"
        if path.exists():
            return self._load_one(path)
        if self.bundled_dir:
            path = self.bundled_dir / f"{name}.md"
            if path.exists():
                return self._load_one(path)
        return None

    def _load_one(self, path: Path) -> Optional[Skill]:
        content = path.read_text(encoding="utf-8")
        meta, body = self._parse_frontmatter(content)
        if not meta or not meta.get("name"):
            return None

        return Skill(
            name=meta["name"],
            description=meta.get("description", "").strip(),
            category=meta.get("category", "general"),
            content=body.strip(),
            version=str(meta.get("version", "1.0")),
        )

    def save(self, skill: Skill) -> None:
        """Persist a skill to the user skills directory.

        Skills are stored as markdown files with YAML frontmatter.
        """
        self.user_dir.mkdir(parents=True, exist_ok=True)
        path = self.user_dir / f"{skill.name}.md"
        content = self._dump(skill)
        path.write_text(content, encoding="utf-8")

    def _dump(self, skill: Skill) -> str:
        meta = {
            "name": skill.name,
            "description": skill.description,
            "category": skill.category,
            "version": skill.version,
        }
        frontmatter = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True)
        return f"---\n{frontmatter}---\n\n{skill.content}\n"

    def _parse_frontmatter(self, content: str) -> tuple[dict, str]:
        """Parse YAML frontmatter and return (metadata, body)."""
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                meta = yaml.safe_load(parts[1]) or {}
                body = parts[2]
                return meta, body
        return {}, content
