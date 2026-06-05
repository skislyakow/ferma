"""
RE:POST — Lightning News Channel.
Real-time Telethon listener → keyword filter → Yandex Translate → Bot API publish.

Usage:
  1) Request code:     python core/lightning/run_lightning.py channels/repost/.env --auth
  2) Complete auth:    python core/lightning/run_lightning.py channels/repost/.env --auth 12345
  3) Run in screen:    python core/lightning/run_lightning.py channels/repost/.env
"""
import os
import sys
import hashlib
import re
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.config import load_channel_config
from core.lightning.collector import LightningCollector
from core.translator.translator import Translator
from core.publisher.publisher import Publisher
from core.db.database import Database

BREAKING_KEYWORDS = [
    "breaking", "just in", "alert", "update", "developing",
    "confirmed", "report", "announce", "happening now",
    "exclusive", "urgent", "flash",
    "🚨", "🔴", "⚠️", "‼️",
]

SESSION_FILE = "repost.session"


def has_breaking_keyword(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in BREAKING_KEYWORDS)


def format_post(headline: str, body: str) -> str:
    headline = re.sub(r'\s+', ' ', headline).strip()
    body = re.sub(r'\n{3,}', '\n\n', body).strip()
    parts = [f"👉 {headline}"]
    if body:
        parts.append(body)
    parts.append("")
    parts.append("⚡️ RE:POST")
    return "\n".join(parts)


def make_text_hash(text: str) -> str:
    if not text:
        return ""
    return hashlib.md5(text[:200].encode("utf-8")).hexdigest()


async def auth_once(env_path: str, code: str = None):
    channel_dir = os.path.dirname(os.path.abspath(env_path))
    os.chdir(channel_dir)
    cfg = load_channel_config(env_path)
    client = TelegramClient(SESSION_FILE, cfg["API_ID"], cfg["API_HASH"])
    await client.connect()

    if await client.is_user_authorized():
        print("[Lightning] Already authorized")

    elif code:
        state_path = ".auth_state"
        if not os.path.exists(state_path):
            print(f"[Lightning] Run --auth first (without code) to request code")
            return
        with open(state_path) as f:
            phone_code_hash = f.read().strip()
        await client.sign_in(phone=cfg["PHONE"], code=code, phone_code_hash=phone_code_hash)
        os.remove(state_path)
        print("[Lightning] Auth successful, session saved")

    else:
        sent = await client.send_code_request(cfg["PHONE"])
        with open(".auth_state", "w") as f:
            f.write(sent.phone_code_hash)
        print(f"[Lightning] Code sent to {cfg['PHONE']}")
        print(f"[Lightning] Run --auth <code> to complete")

    await client.disconnect()


async def main(env_path: str):
    channel_dir = os.path.dirname(os.path.abspath(env_path))
    os.chdir(channel_dir)

    cfg = load_channel_config(env_path)
    db = Database()
    translator = Translator(cfg)
    pub = Publisher()
    pub.set_token(cfg["BOT_TOKEN"])

    collector = LightningCollector(
        api_id=cfg["API_ID"],
        api_hash=cfg["API_HASH"],
        phone=cfg["PHONE"],
        session_path=SESSION_FILE,
        poll_interval=30,
    )

    async def on_message(msg):
        text = (msg.text or msg.message or "").strip()
        if not text:
            return

        if not has_breaking_keyword(text):
            return

        source_channel = getattr(msg.chat, "username", "") or str(msg.chat.id)
        source_msg_id = msg.id

        if db.post_exists(source_channel, source_msg_id):
            print(f"[Lightning] Duplicate message #{source_msg_id} from {source_channel}")
            return

        text_hash = make_text_hash(text)
        if db.content_exists(text):
            print(f"[Lightning] Duplicate content (hash match)")
            return

        print(f"[Lightning] >> {text[:80]}...")

        translated = translator.translate(text)
        if not translated or translated == text:
            print(f"[Lightning] Translation failed or skipped")
            return

        lines = translated.strip().split("\n")
        headline = lines[0]
        body = "\n".join(lines[1:])
        post = format_post(headline, body)

        total_published = db.get_stats()["published"]
        total_published += 1

        success = pub.publish(
            text=post,
            chat_id=cfg["TARGET_CHANNEL"],
            total_published=total_published,
            cpa_links=cfg["CPA_LINKS"],
            cpa_every=cfg["CPA_INSERT_EVERY"],
        )

        if success:
            db.save_post(
                source_channel=source_channel,
                source_message_id=source_msg_id,
                text=text,
                views=0,
                reactions_count=0,
                has_media=0,
                published=1,
            )
            print(f"[Lightning] Published: {headline[:50]}")

    collector.set_handler(on_message)

    print(f"[Lightning] === RE:POST ===")
    print(f"[Lightning] Target: {cfg['TARGET_CHANNEL']}")
    print(f"[Lightning] Donors ({len(cfg['SOURCE_CHANNELS'])}): {cfg['SOURCE_CHANNELS']}")
    print(f"[Lightning] Listening...")

    await collector.start(cfg["SOURCE_CHANNELS"])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    env_path = os.path.abspath(sys.argv[1])

    if "--auth" in sys.argv:
        from telethon import TelegramClient
        code = None
        for i, a in enumerate(sys.argv):
            if a == "--auth" and i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("-"):
                code = sys.argv[i + 1]
                break
        asyncio.run(auth_once(env_path, code))
    else:
        asyncio.run(main(env_path))
