"""
RE:POST — Lightning News Channel.
Telegram (Telethon) + RSS → keyword filter → Yandex Translate → Bot API publish.

Usage:
  1) Request code:     python core/lightning/run_lightning.py channels/repost/.env --auth
  2) Complete auth:    python core/lightning/run_lightning.py channels/repost/.env --auth 12345
  3) Run:              python core/lightning/run_lightning.py channels/repost/.env
"""
import os
import sys
import zlib
import re
import asyncio

from dotenv import dotenv_values

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.config import load_channel_config
from core.lightning.collector import LightningCollector
from core.translator.translator import Translator
from core.publisher.publisher import Publisher
from core.db.database import Database
from core.filter.manage import load_filters

BREAKING_KEYWORDS = [
    "breaking", "just in", "alert", "update", "developing",
    "confirmed", "report", "announce", "happening now",
    "exclusive", "urgent", "flash",
    "срочно", "эксклюзив", "важно", "подтверждено",
    "сообщает", "объявляет", "происходит", "внимание",
    "🚨", "🔴", "⚠️", "‼️",
]

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPOST_BANNER = os.path.join(PROJECT_ROOT, "repost2.png")
SESSION_FILE = "repost.session"


def has_breaking_keyword(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in BREAKING_KEYWORDS)


def is_russian(text: str) -> bool:
    return bool(re.search(r'[\u0400-\u04FF]', text))


def format_post(headline: str, body: str) -> str:
    headline = re.sub(r'\s+', ' ', headline).strip()
    body = re.sub(r'\n{3,}', '\n\n', body).strip()
    parts = [f"👉 {headline}"]
    if body:
        parts.append(body)
    parts.append("")
    parts.append("⚡️ RE:POST")
    return "\n".join(parts)


AD_BLOCKLIST = [
    "news app", "follow news", "match your interests",
    "download the app", "download our app", "get the app",
    "available on", "subscribe for", "sign up",
]

SOURCE_FOOTER_PATTERNS = [
    r"\s*[—\-–|]\s*(abc news|reuters|bbc|associated press|ap news|the guardian|cnn|npr|the hill|sky news|al jazeera|bloomberg|financial times|the economist|washington post|the independent|the telegraph|usa today|nbc news|cbs news|fox news|newsweek|time magazine)\b.*$",
    r"\s*[—\-–|]\s*(последние новости|latest news|breaking news|news videos|video|photos?\b|фото|видео).*$",
    r"\s*(abc news|reuters)\s*[—\-–|].*$",
    r"^\s*(последние новости|latest news|breaking news)\s*[—\-–|]",
    r"\[\d{2}\.\d{2}\.\d{4}\]\[(?:Фото|Photo|Видео|Video):.*?\]",
    r"\s*\[(?:Фото|Photo|Видео|Video):.*?\]",
]


def strip_html(text: str) -> str:
    import html
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def clean_source_footer(text: str) -> str:
    for pat in SOURCE_FOOTER_PATTERNS:
        text = re.sub(pat, '', text, flags=re.IGNORECASE)
    return text.strip()


def is_blocked_content(text: str) -> bool:
    t = text.lower()
    f = load_filters()
    for kw in f.get("ad_keywords", []) + f.get("teaser_patterns", []):
        if kw in t:
            return True
    for pat in AD_BLOCKLIST:
        if pat in t:
            return True
    return False


async def process_news(source_channel: str, source_msg_id: int, text: str,
                       translator, pub, db, cfg, media_path=None, media_type="photo"):
    """Shared pipeline: filter → translate → format → publish → save."""
    if not text:
        return False
    text = strip_html(text)
    if not has_breaking_keyword(text):
        return False
    if is_blocked_content(text):
        print(f"[RE:POST] Blocked (ad/promo): {text[:60]}...")
        return False

    if db.post_exists(source_channel, source_msg_id):
        print(f"[RE:POST] Duplicate #{source_msg_id} from {source_channel}")
        return False

    if db.content_exists(text):
        print(f"[RE:POST] Duplicate content (hash match)")
        return False

    print(f"[RE:POST] >> {text[:80]}...")

    if is_russian(text):
        translated = text
    else:
        translated = translator.translate(text)
        if not translated:
            print(f"[RE:POST] Translation failed")
            return False

    translated = clean_source_footer(translated)

    if not translated.strip():
        print(f"[RE:POST] Empty after footer cleaning, skipping")
        return False

    lines = translated.strip().split("\n")
    headline = lines[0]
    body = "\n".join(lines[1:])
    post = format_post(headline, body)

    has_media = 1 if media_path else 0

    # Use repost.png as fallback image
    if not media_path and os.path.exists(REPOST_BANNER):
        media_path = REPOST_BANNER
        media_type = "photo"

    total_published = db.get_stats()["published"]
    total_published += 1

    success = pub.publish(
        text=post,
        chat_id=cfg["TARGET_CHANNEL"],
        total_published=total_published,
        cpa_links=cfg["CPA_LINKS"],
        cpa_every=cfg["CPA_INSERT_EVERY"],
        media_path=media_path,
        media_type=media_type,
    )

    if success:
        db.save_post(
            source_channel=source_channel,
            source_message_id=source_msg_id,
            text=text,
            views=0,
            reactions_count=0,
            has_media=has_media,
            published=1,
        )
        print(f"[RE:POST] Published: {headline[:50]}")
    return success


async def auth_once(env_path: str, code: str = None):
    channel_dir = os.path.dirname(os.path.abspath(env_path))
    os.chdir(channel_dir)
    cfg = load_channel_config(env_path)
    from telethon import TelegramClient
    client = TelegramClient(SESSION_FILE, cfg["API_ID"], cfg["API_HASH"])
    await client.connect()

    if await client.is_user_authorized():
        print("[RE:POST] Already authorized")
    elif code:
        state_path = ".auth_state"
        if not os.path.exists(state_path):
            print("[RE:POST] Run --auth first (without code) to request code")
            return
        with open(state_path) as f:
            phone_code_hash = f.read().strip()
        await client.sign_in(phone=cfg["PHONE"], code=code, phone_code_hash=phone_code_hash)
        os.remove(state_path)
        print("[RE:POST] Auth successful, session saved")
    else:
        sent = await client.send_code_request(cfg["PHONE"])
        with open(".auth_state", "w") as f:
            f.write(sent.phone_code_hash)
        print(f"[RE:POST] Code sent to {cfg['PHONE']}")
        print(f"[RE:POST] Run --auth <code> to complete")
    await client.disconnect()


async def rss_poller(feed_urls, cfg, translator, pub, db):
    """Poll RSS feeds for breaking news."""
    import feedparser

    if not feed_urls:
        return

    seen = set()
    print(f"[RSS] Monitoring {len(feed_urls)} feeds...")

    while True:
        for url in feed_urls:
            try:
                feed = feedparser.parse(url)
                for entry in reversed(feed.entries):
                    link = entry.get("link") or entry.get("id", "")
                    if not link or link in seen:
                        continue

                    title = (entry.get("title") or "").strip()
                    desc = (entry.get("description") or "").strip()
                    summary = (entry.get("summary") or "").strip()
                    text = f"{title}\n\n{desc or summary}".strip()
                    text = strip_html(text)

                    if not text:
                        continue

                    seen.add(link)
                    msg_id = zlib.crc32(link.encode()) & 0x7FFFFFFF
                    await process_news(f"rss:{url.split('/')[2]}", msg_id, text,
                                       translator, pub, db, cfg)

            except Exception as e:
                print(f"[RSS] Error: {e}")

        await asyncio.sleep(120)


async def ru_source_poller(ru_channels, cfg, pub, db):
    """Poll Russian Telegram channels for posts."""
    from core.parser.web_parser import WebParser

    if not ru_channels:
        return

    parser = WebParser(db)
    print(f"[RU] Monitoring {len(ru_channels)} Russian channels...")

    while True:
        try:
            parser.parse_all(ru_channels, limit_per_channel=10)
            post = db.get_best_unpublished_post()
            if not post:
                await asyncio.sleep(300)
                continue

            post_id, source_channel, text, _, media_path, _, media_type = post

            if not text or not text.strip():
                db.mark_skipped(post_id)
                await asyncio.sleep(300)
                continue

            text = text.strip()
            text = re.sub(r'(\n@\w+)+$', '', text)
            text = re.sub(r'[\u200b\u200c\u200d\ufeff\u00a0]', '', text)

            if len(text) < 40:
                print(f"[RU] Too short ({len(text)} chars) from {source_channel}, skipping")
                db.mark_skipped(post_id)
                await asyncio.sleep(300)
                continue

            if not re.search(r'[a-zA-Z\u0400-\u04FF\u0500-\u052F]', text):
                print(f"[RU] No visible text from {source_channel}, skipping")
                db.mark_skipped(post_id)
                await asyncio.sleep(300)
                continue

            if is_blocked_content(text):
                print(f"[RU] Blocked content from {source_channel}")
                db.mark_skipped(post_id)
                await asyncio.sleep(300)
                continue

            if db.content_exists(text):
                print(f"[RU] Duplicate content from {source_channel}")
                db.mark_skipped(post_id)
                await asyncio.sleep(300)
                continue

            post_text = f'{text}\n\n{source_channel}\n\n⚡️ RE:POST'

            # Use fallback image if no media
            m_path, m_type = media_path, media_type or "photo"
            if not m_path:
                m_path = REPOST_BANNER if os.path.exists(REPOST_BANNER) else None
                m_type = "photo"

            total_published = db.get_stats()["published"]
            total_published += 1

            success = pub.publish(
                text=post_text,
                chat_id=cfg["TARGET_CHANNEL"],
                total_published=total_published,
                cpa_links=cfg["CPA_LINKS"],
                cpa_every=cfg["CPA_INSERT_EVERY"],
                media_path=m_path,
                media_type=m_type,
            )

            if success:
                db.mark_published(post_id)
                print(f"[RU] Published from {source_channel}: {text[:50]}...")

        except Exception as e:
            print(f"[RU] Error: {e}")
            import traceback
            traceback.print_exc()

        await asyncio.sleep(300)


async def reddit_poller(subreddits, cfg, translator, pub, db):
    import feedparser
    import time

    if not subreddits:
        return

    last_ts = {}
    seen = set()

    print(f"[REDDIT] Monitoring {len(subreddits)} subreddits via RSS...")

    def fetch_entries(sub):
        url = f"https://www.reddit.com/r/{sub}/new/.rss"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        feed = feedparser.parse(url, agent=headers["User-Agent"])
        return feed.entries

    while True:
        for sub in subreddits:
            try:
                entries = await asyncio.to_thread(fetch_entries, sub)
                if not entries:
                    continue

                newest_ts = 0
                for e in entries:
                    ts = int(time.mktime(e.get("published_parsed", time.gmtime(0))))
                    newest_ts = max(newest_ts, ts)

                prev_ts = last_ts.get(sub, 0)
                if prev_ts and newest_ts <= prev_ts:
                    continue

                for entry in reversed(entries):
                    ts = int(time.mktime(entry.get("published_parsed", time.gmtime(0))))
                    if prev_ts and ts <= prev_ts:
                        continue

                    pid = entry.get("id", "").split("/")[-1] or entry.get("link", "").split("/")[-2]
                    if pid in seen:
                        continue
                    seen.add(pid)

                    title = (entry.get("title") or "").strip()
                    summary = (entry.get("summary") or "").strip()
                    desc = (entry.get("description") or "").strip()

                    if not title:
                        continue

                    # Extract image URL from summary BEFORE strip_html
                    media_path = None
                    media_type = "photo"
                    try:
                        import re as _re
                        _src = summary or desc or ""
                        _m = _re.search(r'<img[^>]+src="([^"]+)"', _src)
                        if _m:
                            def _dl():
                                import requests as _req
                                r = _req.get(_m.group(1), timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                                if r.status_code == 200:
                                    os.makedirs("media", exist_ok=True)
                                    ext = _m.group(1).rsplit(".", 1)[-1].split("?")[0]
                                    fname = f"reddit_{pid}.{ext}"
                                    fpath = os.path.join("media", fname)
                                    with open(fpath, "wb") as f:
                                        f.write(r.content)
                                    return fpath
                                return None
                            media_path = await asyncio.to_thread(_dl)
                    except Exception as e:
                        print(f"[REDDIT] Media download failed: {e}")
                        media_path = None

                    text = title
                    body = summary or desc
                    if body:
                        text = f"{title}\n\n{body}"
                    text = strip_html(text)
                    text = re.sub(r'(?:\b(?:submitted|posted|published|provided|sent|by)\s+(?:by\s+)?/?u/\S+|comments?\s*(?:share|save|report)?)\s*', '', text, flags=re.IGNORECASE).strip()
                    text = re.sub(r'\s*\[link\]\s*\[\]\s*', '', text).strip()
                    text = re.sub(r'\s*\(paywall\)\s*', '', text, flags=re.IGNORECASE).strip()
                    text = re.sub(r'\s{2,}', ' ', text).strip()

                    if not text:
                        continue

                    source_channel = f'reddit/r/{sub}'
                    source_msg_id = zlib.crc32(pid.encode()) & 0x7FFFFFFF

                    if db.post_exists(source_channel, source_msg_id):
                        continue
                    if db.content_exists(text):
                        continue
                    if is_blocked_content(text):
                        print(f"[REDDIT] Blocked r/{sub}: {text[:60]}...")
                        continue

                    print(f"[REDDIT] >> {text[:60]}...")

                    if is_russian(text):
                        translated = text
                    else:
                        translated = translator.translate(text)
                        if not translated:
                            print(f"[REDDIT] Translation failed")
                            continue

                    translated = clean_source_footer(translated)
                    translated = re.sub(r'(?:(?:представленн[ыо][ейм]|опубликован[оа]|отправлен[оа]|предоставленн[ыо][ейм]|по данным)\s+\S+|\[ссылка\]\s*\[\])\s*', '', translated, flags=re.IGNORECASE).strip()
                    translated = re.sub(r'\s{2,}', ' ', translated).strip()
                    if not translated.strip():
                        continue

                    lines = translated.strip().split("\n")
                    headline = lines[0].strip()
                    if not headline or len(headline) < 10 or headline.lower().startswith('reddit') or re.match(r'^[rR]/\w+$', headline) or 'reddit:' in headline.lower():
                        print(f"[REDDIT] Empty/useless headline, skipping")
                        continue
                    body = "\n".join(lines[1:]).strip()

                    import html as _html
                    headline = _html.escape(headline)
                    body = _html.escape(body)

                    post_text = f"👉 {headline}"
                    if body:
                        post_text += f"\n\n{body}"
                    post_text += f"\n\n{source_channel}\n\n⚡️ RE:POST"

                    total_published = db.get_stats()["published"]
                    total_published += 1

                    if not media_path:
                        media_path = REPOST_BANNER if os.path.exists(REPOST_BANNER) else None
                        media_type = "photo"

                    success = pub.publish(
                        text=post_text,
                        chat_id=cfg["TARGET_CHANNEL"],
                        total_published=total_published,
                        cpa_links=cfg["CPA_LINKS"],
                        cpa_every=cfg["CPA_INSERT_EVERY"],
                        media_path=media_path,
                        media_type=media_type,
                        parse_mode="HTML",
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
                        print(f"[REDDIT] Published: {headline[:50]}")

                last_ts[sub] = newest_ts

            except Exception as e:
                print(f"[REDDIT] Error r/{sub}: {e}")
                import traceback
                traceback.print_exc()

        interval = int(cfg.get("REDDIT_INTERVAL", 300))
        if len(seen) > 5000:
            seen.clear()
            print("[REDDIT] Seen set cleared")
        await asyncio.sleep(interval)


async def main(env_path: str):
    channel_dir = os.path.dirname(os.path.abspath(env_path))
    os.chdir(channel_dir)

    cfg = load_channel_config(env_path)
    db = Database()
    translator = Translator(cfg)
    pub = Publisher()
    pub.set_token(cfg["BOT_TOKEN"])

    tasks = []

    # Start Telegram collector
    collector = LightningCollector(
        api_id=cfg["API_ID"],
        api_hash=cfg["API_HASH"],
        phone=cfg["PHONE"],
        session_path=SESSION_FILE,
        poll_interval=30,
    )

    async def on_telegram(msg):
        text = strip_html((msg.text or msg.message or "").strip())
        if not text:
            return

        source_channel = getattr(msg.chat, "username", "") or str(msg.chat.id)
        source_msg_id = msg.id

        media_path = None
        media_type = "photo"

        if msg.photo:
            try:
                os.makedirs("media", exist_ok=True)
                fname = f"repost_{source_msg_id}.jpg"
                path = await msg.download_media(file=f"media/{fname}")
                if path and os.path.exists(path):
                    media_path = path
            except Exception as e:
                print(f"[RE:POST] Media download failed: {e}")

        await process_news(source_channel, source_msg_id, text,
                           translator, pub, db, cfg,
                           media_path=media_path, media_type=media_type)

    collector.set_handler(on_telegram)

    async def run_telegram():
        await collector.start(cfg["SOURCE_CHANNELS"])

    # Parse RSS feeds from .env
    rss_feeds = [x.strip() for x in dotenv_values(env_path).get("RSS_FEEDS", "").split(",") if x.strip()]

    # Parse Russian source channels from .env
    ru_channels = [x.strip() for x in dotenv_values(env_path).get("RU_SOURCE_CHANNELS", "").split(",") if x.strip()]

    # Parse Reddit subreddits from .env
    reddit_subs = [x.strip() for x in dotenv_values(env_path).get("REDDIT_SUBREDDITS", "").split(",") if x.strip()]

    tasks.append(asyncio.create_task(run_telegram()))
    if rss_feeds:
        tasks.append(asyncio.create_task(rss_poller(rss_feeds, cfg, translator, pub, db)))
    if ru_channels:
        tasks.append(asyncio.create_task(ru_source_poller(ru_channels, cfg, pub, db)))
    if reddit_subs:
        tasks.append(asyncio.create_task(reddit_poller(reddit_subs, cfg, translator, pub, db)))

    print(f"[RE:POST] === RE:POST ===")
    print(f"[RE:POST] Target: {cfg['TARGET_CHANNEL']}")
    print(f"[RE:POST] Donors: {len(cfg['SOURCE_CHANNELS'])} Telegram + {len(rss_feeds)} RSS + {len(ru_channels)} RU + {len(reddit_subs)} Reddit")
    print(f"[RE:POST] Running...")

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    env_path = os.path.abspath(sys.argv[1])

    if "--auth" in sys.argv:
        code = None
        for i, a in enumerate(sys.argv):
            if a == "--auth" and i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("-"):
                code = sys.argv[i + 1]
                break
        asyncio.run(auth_once(env_path, code))
    else:
        asyncio.run(main(env_path))
