"""
RE:POST → VK Crossposter.
Monitors the RE:POST Telegram channel via Bot API and crossposts photos to VK.

Usage:
    python core/crosspost/run_vk.py channels/repost/.env
"""
import os
import sys
import time
import json
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.crosspost.vk_poster import VKPoster
from dotenv import dotenv_values

MEDIA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vk_media")
os.makedirs(MEDIA_DIR, exist_ok=True)

TRACKER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vk_offset.json")


def load_offset():
    if os.path.exists(TRACKER_PATH):
        with open(TRACKER_PATH) as f:
            return json.load(f).get("offset", 0)
    return 0


def save_offset(offset):
    with open(TRACKER_PATH, "w") as f:
        json.dump({"offset": offset}, f)


def download_photo(bot_token, file_id, filename):
    resp = requests.get(
        f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}",
        timeout=15
    )
    data = resp.json()
    if not data.get("ok"):
        return None
    file_path = data["result"]["file_path"]
    ext = os.path.splitext(file_path)[1] or ".jpg"
    local = os.path.join(MEDIA_DIR, f"{filename}{ext}")
    dl = requests.get(f"https://api.telegram.org/file/bot{bot_token}/{file_path}", timeout=30)
    with open(local, "wb") as f:
        f.write(dl.content)
    return local


def main(env_path: str):
    env = dotenv_values(env_path)
    bot_token = env.get("BOT_TOKEN", "")
    target_channel = env.get("TARGET_CHANNEL", "")
    vk_token = env.get("VK_TOKEN", "")
    vk_group_id = env.get("VK_GROUP_ID", "")

    if not all([bot_token, target_channel, vk_token, vk_group_id]):
        print("[VK] Missing config: BOT_TOKEN, TARGET_CHANNEL, VK_TOKEN, VK_GROUP_ID")
        sys.exit(1)

    vk = VKPoster(vk_token, vk_group_id)
    offset = load_offset()

    chan = target_channel.lstrip("@")
    chat_resp = requests.get(
        f"https://api.telegram.org/bot{bot_token}/getChat?chat_id=@{chan}",
        timeout=15
    ).json()
    if not chat_resp.get("ok"):
        print(f"[VK] Cannot resolve channel @{chan}: {chat_resp}")
        sys.exit(1)
    chat_id = str(chat_resp["result"]["id"])
    print(f"[VK] Watching @{chan} ({chat_id}) for photos...")

    while True:
        try:
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
            params = {"offset": offset, "timeout": 30, "allowed_updates": ["message"]}
            resp = requests.get(url, params=params, timeout=35)
            data = resp.json()

            if not data.get("ok"):
                print(f"[VK] Telegram API error: {data}")
                time.sleep(60)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message")
                if not msg:
                    continue

                chat = msg.get("chat", {})
                if str(chat.get("id", "")) != chat_id:
                    continue

                photos = msg.get("photo")
                if not photos:
                    continue

                file_id = photos[-1]["file_id"]
                caption = msg.get("text") or msg.get("caption") or ""
                headline = caption.split("\n")[0][:100] if caption else "Кадр дня"

                print(f"[VK] Photo: {headline[:50]}...")
                local = download_photo(bot_token, file_id, f"vk_{msg['message_id']}")
                if not local:
                    continue

                post_text = (
                    f"📸 {headline}\n\n"
                    f"Больше новостей и кадров дня — в нашем Telegram-канале "
                    f"https://t.me/{target_channel.replace('@', '')}"
                )

                attachment = vk.upload_photo(local)
                vk.post_to_wall(message=post_text, attachment=attachment)
                print(f"[VK] Posted to VK (msg #{msg['message_id']})")

                try:
                    os.remove(local)
                except OSError:
                    pass

            save_offset(offset)

        except Exception as e:
            print(f"[VK] Error: {e}")
            time.sleep(60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    env_path = os.path.abspath(sys.argv[1])
    main(env_path)
