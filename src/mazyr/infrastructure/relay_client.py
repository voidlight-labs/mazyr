import asyncio
import json
from typing import Callable

from websockets import connect
from websockets.exceptions import ConnectionClosed

from mazyr.infrastructure.http_pool import get_async_client
from mazyr.infrastructure.logger import get_logger

log = get_logger("relay")


class RelayClient:
    """WebSocket client for the Mazyr cloud relay."""

    def __init__(
        self,
        endpoint: str,
        instance_id: str,
        on_message: Callable | None = None,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.instance_id = instance_id
        self.ws = None
        self.running = False
        self.on_message = on_message
        self._http = get_async_client()

    async def connect(self):
        uri = f"{self.endpoint}/ws/{self.instance_id}"
        self.ws = await connect(uri)
        self.running = True
        asyncio.create_task(self._heartbeat())
        await self._listen()

    async def _listen(self):
        while self.running:
            try:
                message = await self.ws.recv()
                data = json.loads(message)
                if self.on_message:
                    self.on_message(data)
            except ConnectionClosed:
                self.running = False
                break
            except json.JSONDecodeError as e:
                log.warning("Relay received invalid JSON: %s", e)

    async def _heartbeat(self):
        while self.running:
            await asyncio.sleep(60)
            if self.ws:
                try:
                    await self.ws.send(json.dumps({"type": "heartbeat"}))
                except ConnectionClosed:
                    self.running = False
                    break

    async def send(self, data: dict):
        if self.ws:
            await self.ws.send(json.dumps(data))

    async def disconnect(self):
        self.running = False
        if self.ws:
            await self.ws.close()

    async def update_state(self, state: dict) -> bool:
        """HTTP fallback to push state when WebSocket is not connected."""
        try:
            response = await self._http.post(
                f"{self.endpoint}/state/{self.instance_id}",
                json=state,
            )
            return response.status_code == 200
        except Exception as e:
            log.warning("Relay HTTP update failed: %s", e)
            return False
