"""
RE:POST → VK Crossposter.
Uses Telethon to read photos from the RE:POST Telegram channel and crossposts them to VK.

Usage:
    python core/crosspost/run_vk.py channels/repost/.env
"""
import os
import sys
import time
import json
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.crosspost.vk_poster import VKPoster
from dotenv import dotenv_values

MEDIA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vk_media")
os.makedirs(MEDIA_DIR, exist_ok=True)

TRACKER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vk_posted.json")


def load_posted():
    if os.path.exists(TRACKER_PATH):
        with open(TRACKER_PATH) as f:
            return set(json.load(f))
    return set()


def save_posted(posted):
    with open(TRACKER_PATH, "w") as f:
        json.dump(list(posted), f)


async def main(env_path: str):
    from telethon import TelegramClient

    env = dotenv_values(env_path)
    bot_token = env.get("BOT_TOKEN", "")
    target_channel = env.get("TARGET_CHANNEL", "")
    vk_token = env.get("VK_TOKEN", "")
    vk_group_id = env.get("VK_GROUP_ID", "")
    api_id = int(env.get("TELEGRAM_API_ID", "0"))
    api_hash = env.get("TELEGRAM_API_HASH", "")

    if not all([bot_token, target_channel, vk_token, vk_group_id]):
        print("[VK] Missing config: BOT_TOKEN, TARGET_CHANNEL, VK_TOKEN, VK_GROUP_ID")
        sys.exit(1)

    vk = VKPoster(vk_token, vk_group_id)
    posted = load_posted()
    chan = target_channel.lstrip("@")

    print(f"[VK] Starting. Watching @{chan} via Telethon...")
    print(f"[VK] Already posted: {len(posted)} photos")

    channel_dir = os.path.dirname(os.path.abspath(env_path))
    session_path = os.path.join(channel_dir, "repost.session")

    async with TelegramClient(session_path, api_id, api_hash) as client:
        if not await client.is_user_authorized():
            print("[VK] Telethon not authorized! Run --auth first")
            return

        entity = await client.get_entity(target_channel)
        print(f"[VK] Connected to @{chan}")

        while True:
            try:
                msgs = await client.get_messages(entity, limit=10)
                for msg in reversed(msgs):
                    msg_id = msg.id
                    if msg_id in posted:
                        continue
                    if not msg.photo:
                        continue

                    caption = msg.text or ""
                    if caption:
                        post_text = f"{caption}\n\nБольше новостей — https://t.me/{chan}"
                    else:
                        post_text = f"📸 Кадр дня\n\nБольше новостей — https://t.me/{chan}"
                    print(f"[VK] Photo #{msg_id}: {caption[:50] if caption else 'no text'}...")

                    local = await client.download_media(msg, file=MEDIA_DIR)
                    if not local:
                        print(f"[VK] Failed to download #{msg_id}")
                        continue

                    try:
                        attachment = vk.upload_photo(local)
                        vk.post_to_wall(message=post_text, attachment=attachment)
                        print(f"[VK] Posted #{msg_id} to VK")
                        posted.add(msg_id)
                        save_posted(posted)
                    except Exception as e:
                        print(f"[VK] Failed to post #{msg_id}: {e}")

                    try:
                        os.remove(local)
                    except OSError:
                        pass

            except Exception as e:
                print(f"[VK] Error: {e}")

            await asyncio.sleep(30)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    env_path = os.path.abspath(sys.argv[1])
    asyncio.run(main(env_path))
