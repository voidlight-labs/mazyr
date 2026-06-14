from mazyr.domain.memory_working import WorkingMemoryEntry


class TestWorkingMemoryEntry:
    def test_valid_entry(self):
        entry = WorkingMemoryEntry(key="active_skill", value="coding")
        assert entry.key == "active_skill"
        assert entry.value == "coding"
        assert entry.ttl_seconds == 1800
        assert entry.access_count == 0

    def test_touch(self):
        entry = WorkingMemoryEntry(key="k", value="v")
        entry.touch()
        assert entry.access_count == 1
