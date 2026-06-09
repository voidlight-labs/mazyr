from typing import Callable
import httpx


class TelegramAdapter:
    """Telegram Bot adapter using HTTP API."""

    def __init__(self, bot_token: str):
        self.token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.client = httpx.Client(base_url=self.base_url)
        self.offset = 0

    def send_message(self, chat_id: int, text: str):
        response = self.client.post(
            "/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )
        response.raise_for_status()

    def get_updates(self, limit: int = 100) -> list[dict]:
        response = self.client.get(
            "/getUpdates",
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
                    handler({
                        "text": message["text"],
                        "chat_id": message["chat"]["id"],
                        "from": message["from"].get("username", "unknown"),
                        "message_id": message["message_id"],
                    })
            time.sleep(1)
