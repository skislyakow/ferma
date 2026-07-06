import asyncio
from telethon import TelegramClient


class LightningCollector:
    def __init__(self, api_id: int, api_hash: str, phone: str, session_path: str, poll_interval: int = 30):
        self.client = TelegramClient(session_path, api_id, api_hash)
        self.phone = phone
        self._handler = None
        self._channels = []
        self._last_msg_ids = {}
        self.poll_interval = poll_interval
        self._running = False

    def set_handler(self, handler):
        self._handler = handler

    async def start(self, channels: list[str]):
        await self.client.start(phone=self.phone)
        self._channels = channels
        self._running = True
        print(f"[Lightning] Polling {len(channels)} channels every {self.poll_interval}s...")

        while self._running:
            for ch in channels:
                try:
                    entity = await self.client.get_entity(ch)
                    last_id = self._last_msg_ids.get(ch, 0)
                    messages = await self.client.get_messages(entity, limit=5)

                    for msg in reversed(messages):
                        if msg.id <= last_id:
                            continue
                        self._last_msg_ids[ch] = max(self._last_msg_ids.get(ch, 0), msg.id)
                        if self._handler:
                            await self._handler(msg)

                except Exception as e:
                    print(f"[Lightning] Poll error {ch}: {e}")

            await asyncio.sleep(self.poll_interval)
