from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from mazyr.application.learn import LearnUseCase
from mazyr.application.skill_registry import SkillRegistry
from mazyr.domain.message import Conversation, Message
from mazyr.domain.skills import Skill
from mazyr.infrastructure.skill_loader import SkillLoader


class TestLearnUseCase:
    @pytest.fixture
    def learn(self):
        self.tmpdir = TemporaryDirectory()
        loader = SkillLoader(user_dir=Path(self.tmpdir.name))
        registry = SkillRegistry(loader)
        yield LearnUseCase(procedural_memory=registry)
        self.tmpdir.cleanup()

    def test_extract_pattern_requires_three_creator_messages(self, learn):
        conv = Conversation(id="test")
        conv.add_message(
            Message(id="1", content="hello", sender="creator", platform="cli", timestamp="")
        )
        conv.add_message(
            Message(id="2", content="world", sender="creator", platform="cli", timestamp="")
        )

        assert learn.extract_pattern(conv) is None

    def test_extract_pattern_finds_keywords(self, learn):
        conv = Conversation(id="test")
        for i in range(3):
            conv.add_message(
                Message(
                    id=str(i),
                    content="I enjoy programming with python and building tools",
                    sender="creator",
                    platform="cli",
                    timestamp="",
                )
            )

        pattern = learn.extract_pattern(conv)

        assert pattern is not None
        assert pattern["type"] == "recurring_topic"
        assert "python" in pattern["keywords"]
        assert "building" in pattern["keywords"] or "tools" in pattern["keywords"]

    def test_create_skill_persists_and_activates(self, learn):
        result = learn.create_skill(
            name="python_helper",
            description="Helps with Python questions",
            content="Always use type hints.",
            category="coding",
        )

        assert result is True
        active = learn.procedural_memory.active_skill
        assert active is not None
        assert active.name == "python_helper"
        assert learn.procedural_memory.get("python_helper") is not None

    def test_create_skill_returns_false_when_duplicate(self, learn):
        learn.create_skill("duplicate", "desc", "content", "general")

        result = learn.create_skill("duplicate", "desc", "content", "general")

        assert result is False

    def test_update_skill_appends_content(self, learn):
        learn.procedural_memory.save(
            Skill(name="editor", description="edit", category="general", content="Base.")
        )

        result = learn.update_skill("editor", "New learning", success=True)

        assert result is True
        skill = learn.procedural_memory.get("editor")
        assert "New learning" in skill.content
        assert skill.usage_count == 1
