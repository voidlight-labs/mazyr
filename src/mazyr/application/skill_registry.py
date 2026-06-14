"""Skill registry: loads, tracks, and injects procedural memory at runtime."""

from typing import Optional

from mazyr.domain.skills import Skill
from mazyr.infrastructure.skill_loader import SkillLoader


class SkillRegistry:
    """Runtime registry for Mazyr skills (procedural memory).

    The registry loads skills from bundled and user directories. Exactly one
    skill can be active per session; its content is injected into the prompt
    context by the ContextAssembler.
    """

    def __init__(self, loader: SkillLoader | None = None):
        self._loader = loader or SkillLoader()
        self._skills: dict[str, Skill] = {}
        self._active: Skill | None = None
        self._load_skills()

    def _load_skills(self):
        self._skills = self._loader.load_all()

    @property
    def active_skill(self) -> Optional[Skill]:
        return self._active

    def list_skills(self) -> list[Skill]:
        """Return all loaded skills."""
        return list(self._skills.values())

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def activate(self, name: str) -> bool:
        """Activate a skill by name. Returns True on success."""
        skill = self._skills.get(name)
        if skill is None:
            return False
        self._active = skill
        return True

    def deactivate(self):
        """Clear the active skill."""
        self._active = None

    def reload(self):
        """Reload skills from disk. Preserves active skill if it still exists."""
        previous = self._active.name if self._active else None
        self._load_skills()
        if previous and previous in self._skills:
            self._active = self._skills[previous]
        else:
            self._active = None

    def record_usage(self, name: str, success: bool):
        """Record a usage hit/miss for a skill."""
        skill = self._skills.get(name)
        if skill is None:
            return
        skill.record_usage(success)

    def save(self, skill: Skill) -> bool:
        """Persist a new skill to disk and load it into the registry.

        Returns True on success. Existing skills are not overwritten.
        """
        if skill.name in self._skills:
            return False
        self._loader.save(skill)
        self._skills[skill.name] = skill
        return True
