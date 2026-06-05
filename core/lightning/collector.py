import asyncio
from telethon import TelegramClient, events


class LightningCollector:
    def __init__(self, api_id: int, api_hash: str, phone: str, session_path: str):
        self.client = TelegramClient(session_path, api_id, api_hash)
        self.phone = phone
        self._handler = None

    def set_handler(self, handler):
        self._handler = handler

    async def start(self, channels: list[str]):
        await self.client.start(phone=self.phone)

        @self.client.on(events.NewMessage(chats=channels))
        async def handle(event):
            if self._handler:
                await self._handler(event.message)

        print(f"[Lightning] Listening to {len(channels)} channels...")
        await self.client.run_until_disconnected()

    async def stop(self):
        await self.client.disconnect()
