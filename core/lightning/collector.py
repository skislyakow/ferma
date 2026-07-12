import asyncio
import random
from telethon import TelegramClient
from telethon.errors import RPCError


class LightningCollector:
    def __init__(
        self,
        api_id: int,
        api_hash: str,
        phone: str,
        session_path: str,
        poll_interval: int = 30,
    ):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.session_path = session_path
        self.client = None
        self._handler = None
        self._channels: list[str] = []
        self._last_msg_ids: dict[str, int] = {}
        self.poll_interval = poll_interval
        self._running = False

    def set_handler(self, handler):
        self._handler = handler

    def _make_client(self):
        return TelegramClient(self.session_path, self.api_id, self.api_hash)

    async def _connect_with_retry(self):
        delay = 2
        max_delay = 60
        attempt = 0
        while True:
            try:
                self.client = self._make_client()
                await self.client.start(phone=self.phone)  # type: ignore[reportGeneralTypeIssues]
                print(f"[Lightning] Connected after {attempt} retries" if attempt else "[Lightning] Connected")
                return
            except Exception as e:
                attempt += 1
                jitter = random.uniform(0.5, 1.5)
                wait = min(delay * jitter, max_delay)
                print(f"[Lightning] Connection failed (attempt {attempt}): {e}. Retry in {wait:.0f}s")
                await asyncio.sleep(wait)
                delay = min(delay * 2, max_delay)

    async def _ensure_connected(self):
        if not self.client or not self.client.is_connected():
            print("[Lightning] Connection lost, reconnecting...")
            await self._connect_with_retry()

    async def start(self, channels: list[str]):
        await self._connect_with_retry()
        self._channels = channels
        self._running = True
        print(
            f"[Lightning] Polling {len(channels)} channels every {self.poll_interval}s..."
        )

        while self._running:
            await self._ensure_connected()

            for ch in channels:
                try:
                    entity = await self.client.get_entity(ch)  # type: ignore[union-attr]
                    last_id = self._last_msg_ids.get(ch, 0)
                    messages = await self.client.get_messages(entity, limit=5)  # type: ignore[union-attr]

                    for msg in reversed(messages):  # type: ignore[reportCallIssue]
                        if msg.id <= last_id:
                            continue
                        self._last_msg_ids[ch] = max(
                            self._last_msg_ids.get(ch, 0), msg.id
                        )
                        if self._handler:
                            try:
                                await self._handler(msg)
                            except Exception as e:
                                print(f"[Lightning] Handler error on {ch}:{msg.id}: {e}")

                except (OSError, asyncio.TimeoutError):
                    print(f"[Lightning] Connection error while polling {ch}, will reconnect")
                    await self._ensure_connected()
                except RPCError as e:
                    print(f"[Lightning] RPC error on {ch}: {e}")
                except Exception as e:
                    print(f"[Lightning] Poll error {ch}: {e}")

            await asyncio.sleep(self.poll_interval)

    async def stop(self):
        self._running = False
        if self.client:
            await self.client.disconnect()
