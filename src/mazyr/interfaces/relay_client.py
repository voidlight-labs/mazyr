import asyncio
import json
from typing import Callable


class RelayClient:
    """WebSocket client for cloud relay."""

    def __init__(self, endpoint: str, instance_id: str):
        self.endpoint = endpoint
        self.instance_id = instance_id
        self.ws = None
        self.running = False
        self.on_message: Callable = None

    async def connect(self):
        import websockets
        uri = f"{self.endpoint}/ws/{self.instance_id}"
        self.ws = await websockets.connect(uri)
        self.running = True
        asyncio.create_task(self._heartbeat())
        await self._listen()

    async def _listen(self):
        import websockets
        while self.running:
            try:
                message = await self.ws.recv()
                data = json.loads(message)
                if self.on_message:
                    self.on_message(data)
            except websockets.exceptions.ConnectionClosed:
                self.running = False
                break

    async def _heartbeat(self):
        while self.running:
            await asyncio.sleep(60)
            if self.ws:
                await self.ws.send(json.dumps({"type": "heartbeat"}))

    async def send(self, data: dict):
        if self.ws:
            await self.ws.send(json.dumps(data))

    async def disconnect(self):
        self.running = False
        if self.ws:
            await self.ws.close()
