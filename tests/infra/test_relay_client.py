import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from websockets.exceptions import ConnectionClosed

from mazyr.infrastructure.relay_client import RelayClient


class FakeWebSocket:
    def __init__(self):
        self.sent: list[str] = []
        self.closed = False
        self.messages = asyncio.Queue()

    async def send(self, data: str):
        self.sent.append(data)

    async def recv(self):
        item = await self.messages.get()
        if isinstance(item, Exception):
            raise item
        return item

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
class TestRelayClient:
    async def test_connect_starts_listening(self):
        ws = FakeWebSocket()
        ws.messages.put_nowait('{"type":"hello"}')
        ws.messages.put_nowait(ConnectionClosed(None, None))

        received = []

        def on_message(data):
            received.append(data)

        client = RelayClient(
            endpoint="wss://relay.example.com",
            instance_id="test-001",
            on_message=on_message,
        )

        with patch(
            "mazyr.infrastructure.relay_client.connect", new_callable=AsyncMock, return_value=ws
        ):
            await client.connect()

        assert len(received) == 1
        assert received[0]["type"] == "hello"

    async def test_send_serializes_data(self):
        ws = FakeWebSocket()
        client = RelayClient(
            endpoint="wss://relay.example.com",
            instance_id="test-001",
        )
        client.ws = ws

        await client.send({"type": "ping"})

        assert ws.sent == ['{"type": "ping"}']

    async def test_disconnect_closes_websocket(self):
        ws = FakeWebSocket()
        client = RelayClient(
            endpoint="wss://relay.example.com",
            instance_id="test-001",
        )
        client.ws = ws
        client.running = True

        await client.disconnect()

        assert client.running is False
        assert ws.closed is True

    async def test_update_state_posts_via_http_pool(self):
        client = RelayClient(
            endpoint="https://relay.example.com",
            instance_id="test-001",
        )
        mock_response = Mock()
        mock_response.status_code = 200
        mock_http = Mock(post=AsyncMock(return_value=mock_response))
        client._http = mock_http

        result = await client.update_state({"status": "active"})

        assert result is True
        mock_http.post.assert_awaited_once_with(
            "https://relay.example.com/state/test-001",
            json={"status": "active"},
        )
