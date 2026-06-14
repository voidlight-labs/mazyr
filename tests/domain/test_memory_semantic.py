from mazyr.domain.memory_semantic import MemoryCategory, SemanticEntry


class TestSemanticEntry:
    def test_valid_entry(self):
        entry = SemanticEntry(id="1", content="Khayren pake Nuxt 4", category=MemoryCategory.FACT)
        assert entry.category == MemoryCategory.FACT
        assert entry.confidence == 0.8
        assert entry.importance_score == 0.5

    def test_touch_increases_access_count(self):
        entry = SemanticEntry(id="1", content="test", category=MemoryCategory.PREFERENCE)
        old_access = entry.access_count
        entry.touch()
        assert entry.access_count == old_access + 1

    def test_touch_bumps_importance(self):
        entry = SemanticEntry(
            id="1", content="test", category=MemoryCategory.PREFERENCE, importance_score=0.5
        )
        entry.touch()
        assert entry.importance_score > 0.5

    def test_touch_caps_importance(self):
        entry = SemanticEntry(
            id="1", content="test", category=MemoryCategory.PREFERENCE, importance_score=0.99
        )
        entry.touch()
        assert entry.importance_score == 1.0

    def test_apply_decay(self):
        entry = SemanticEntry(
            id="1",
            content="test",
            category=MemoryCategory.FACT,
            importance_score=1.0,
            decay_rate=0.1,
        )
        score = entry.apply_decay(7)
        assert score < 1.0
        assert score > 0.1

    def test_apply_decay_floor(self):
        entry = SemanticEntry(
            id="1",
            content="test",
            category=MemoryCategory.FACT,
            importance_score=0.1,
            decay_rate=0.5,
        )
        score = entry.apply_decay(30)
        assert score == 0.1

    def test_category_values(self):
        assert MemoryCategory.PREFERENCE.value == "preference"
        assert MemoryCategory.FACT.value == "fact"
        assert MemoryCategory.SKILL.value == "skill"
        assert MemoryCategory.RELATIONSHIP.value == "relationship"
        assert MemoryCategory.GOAL.value == "goal"
        assert MemoryCategory.CONSTRAINT.value == "constraint"
