import tempfile
from pathlib import Path

from mazyr.application.skill_registry import SkillRegistry
from mazyr.infrastructure.skill_loader import SkillLoader


def _make_registry(tmp: Path) -> SkillRegistry:
    skill_path = tmp / "python-craft.md"
    skill_path.write_text("""---
name: python-craft
description: Python best practices
category: coding
version: "1.0"
---

# Python Craft

Never use bare except.
""")
    return SkillRegistry(SkillLoader(bundled_dir=tmp, user_dir=tmp / "empty"))


class TestSkillRegistry:
    def test_loads_skills_on_init(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = _make_registry(Path(tmp))
            skills = registry.list_skills()
            assert len(skills) == 1
            assert skills[0].name == "python-craft"

    def test_activate_and_deactivate(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = _make_registry(Path(tmp))
            assert registry.active_skill is None

            assert registry.activate("python-craft") is True
            assert registry.active_skill is not None
            assert registry.active_skill.name == "python-craft"

            registry.deactivate()
            assert registry.active_skill is None

    def test_activate_unknown_skill_returns_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = _make_registry(Path(tmp))
            assert registry.activate("unknown") is False

    def test_reload_preserves_active_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = _make_registry(Path(tmp))
            registry.activate("python-craft")
            registry.reload()
            assert registry.active_skill is not None
            assert registry.active_skill.name == "python-craft"
