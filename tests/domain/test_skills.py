from mazyr.domain.skills import Skill, SkillEvolution


class TestSkill:
    def test_record_usage_success(self):
        skill = Skill(
            name="test",
            description="test skill",
            category="test",
            content="content",
        )
        skill.record_usage(True)
        assert skill.usage_count == 1
        assert skill.success_rate > 0.9

    def test_record_usage_failure(self):
        skill = Skill(
            name="test",
            description="test skill",
            category="test",
            content="content",
        )
        skill.record_usage(False)
        assert skill.usage_count == 1
        assert skill.success_rate < 1.0


class TestSkillEvolution:
    def test_add_event(self):
        evo = SkillEvolution(skill_name="test")
        evo.add_event("created", "Initial creation", "2026-01-01")
        assert len(evo.events) == 1
        assert evo.events[0]["type"] == "created"
