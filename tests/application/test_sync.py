from unittest.mock import AsyncMock, Mock

import pytest

from mazyr.application.sync import SyncUseCase


class TestSyncUseCase:
    def test_snapshot_without_github_adapter(self):
        memory = Mock()
        memory.summary.return_value = {"episodic": 10}
        sync = SyncUseCase(memory=memory)

        result = sync.snapshot_to_github("TestMazyr")

        assert result["status"] == "no_github_adapter"
        assert result["instance"] == "TestMazyr"
        assert "timestamp" in result

    def test_snapshot_with_github_adapter(self):
        memory = Mock()
        memory.summary.return_value = {"episodic": 10}
        github = Mock()
        github.push_snapshot.return_value = {"status": "ok", "content": {"sha": "abc"}}
        sync = SyncUseCase(memory=memory, github_adapter=github)

        result = sync.snapshot_to_github("TestMazyr")

        github.push_snapshot.assert_called_once()
        assert result["status"] == "ok"

    def test_snapshot_uses_memory_summary(self):
        memory = Mock()
        memory.summary.return_value = {"semantic": 3}
        github = Mock()
        github.push_snapshot.return_value = {"status": "ok"}
        sync = SyncUseCase(memory=memory, github_adapter=github)

        sync.snapshot_to_github("TestMazyr")

        snapshot = github.push_snapshot.call_args[0][0]
        assert snapshot["memory_summary"] == {"semantic": 3}

    @pytest.mark.asyncio
    async def test_sync_to_relay_without_relay(self):
        memory = Mock()
        memory.count.return_value = {"episodic": 1}
        sync = SyncUseCase(memory=memory)

        result = await sync.sync_to_relay()

        assert result is False

    @pytest.mark.asyncio
    async def test_sync_to_relay_sends_state(self):
        memory = Mock()
        memory.count.return_value = {"episodic": 2}
        relay = Mock()
        relay.send = AsyncMock()
        sync = SyncUseCase(memory=memory, relay_client=relay)

        result = await sync.sync_to_relay()

        assert result is True
        relay.send.assert_awaited_once()
        state = relay.send.await_args[0][0]
        assert state["status"] == "active"
        assert state["memory_count"] == {"episodic": 2}
