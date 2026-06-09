import asyncio
from typing import Callable, Optional


class WhatsAppAdapter:
    """WhatsApp Web adapter using Playwright."""

    def __init__(self, session_dir: str = "./memory/whatsapp_session"):
        self.session_dir = session_dir
        self.browser = None
        self.page = None
        self.message_handler: Optional[Callable] = None

    async def start(self):
        from playwright.async_api import async_playwright
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(user_data_dir=self.session_dir)
        self.page = await self.context.new_page()
        await self.page.goto("https://web.whatsapp.com")
        await self.page.wait_for_selector('[data-testid="chat-list"]', timeout=120000)

    async def send(self, chat_id: str, message: str):
        await self.page.goto(f"https://web.whatsapp.com/send?phone={chat_id}")
        await self.page.wait_for_selector('[data-testid="conversation-compose-box-input"]')
        await self.page.fill('[data-testid="conversation-compose-box-input"]', message)
        await self.page.press('[data-testid="conversation-compose-box-input"]', "Enter")

    async def listen(self, handler: Callable):
        self.message_handler = handler
        while True:
            messages = await self.page.query_selector_all('.message-in')
            for msg in messages:
                text = await msg.inner_text()
                if text and self.message_handler:
                    self.message_handler(text)
            await asyncio.sleep(2)

    async def stop(self):
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright') and self.playwright:
            await self.playwright.stop()
