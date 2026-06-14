from typing import Callable

import httpx

from mazyr.infrastructure.http_pool import get_sync_client
from mazyr.infrastructure.retry import retry_telegram


class TelegramAdapter:
    """Telegram Bot adapter using HTTP API."""

    def __init__(self, bot_token: str, client: httpx.Client | None = None):
        self.token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.client = client or get_sync_client()
        self.offset = 0

    @retry_telegram
    def send_message(self, chat_id: int, text: str):
        if not text:
            return
        response = self.client.post(
            f"{self.base_url}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )
        response.raise_for_status()

    @retry_telegram
    def get_updates(self, limit: int = 100) -> list[dict]:
        response = self.client.get(
            f"{self.base_url}/getUpdates",
            params={"offset": self.offset, "limit": limit},
        )
        data = response.json()
        updates = data.get("result", [])
        if updates:
            self.offset = updates[-1]["update_id"] + 1
        return updates

    def listen(self, handler: Callable):
        import time

        while True:
            updates = self.get_updates()
            for update in updates:
                message = update.get("message", {})
                if "text" in message:
                    handler(
                        {
                            "text": message["text"],
                            "chat_id": message["chat"]["id"],
                            "from": message["from"].get("username", "unknown"),
                            "message_id": message["message_id"],
                        }
                    )
            time.sleep(1)
