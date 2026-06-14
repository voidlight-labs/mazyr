import tempfile
from pathlib import Path

from mazyr.infrastructure.skill_loader import SkillLoader


class TestSkillLoader:
    def test_load_skill_from_markdown_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            skill_path = tmp / "python-craft.md"
            skill_path.write_text("""---
name: python-craft
description: Python best practices
category: coding
version: "1.1"
---

# Python Craft

Never use bare except.
""")
            loader = SkillLoader(bundled_dir=tmp, user_dir=tmp / "empty")
            skill = loader.load("python-craft")
            assert skill is not None
            assert skill.name == "python-craft"
            assert skill.category == "coding"
            assert skill.version == "1.1"
            assert "Never use bare except" in skill.content

    def test_user_skill_overrides_bundled(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bundled = tmp / "bundled"
            user = tmp / "user"
            bundled.mkdir()
            user.mkdir()

            (bundled / "python-craft.md").write_text(
                "---\nname: python-craft\ndescription: bundled\ncategory: coding\n---\n\nbundled content"
            )
            (user / "python-craft.md").write_text(
                "---\nname: python-craft\ndescription: user\ncategory: coding\n---\n\nuser content"
            )

            loader = SkillLoader(bundled_dir=bundled, user_dir=user)
            skills = loader.load_all()
            assert "python-craft" in skills
            assert "user content" in skills["python-craft"].content

    def test_load_all_skips_invalid_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "invalid.md").write_text("no frontmatter here")
            loader = SkillLoader(bundled_dir=tmp, user_dir=tmp / "empty")
            skills = loader.load_all()
            assert "invalid" not in skills
