"""
Запуск одного канала.
Использование: python core/run_channel.py channels/crypto/.env [--once]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import load_channel_config
from core.db.database import Database
from core.parser.web_parser import WebParser
from core.filter.filters import PostFilter
from core.translator.translator import Translator
from core.publisher.publisher import Publisher


def run_channel(env_path: str, once: bool = False):
    env_path = os.path.abspath(env_path)
    channel_dir = os.path.dirname(env_path)
    os.chdir(channel_dir)

    cfg = load_channel_config(env_path)

    name = os.path.basename(channel_dir)
    print(f"[{name}] Starting channel...")

    db = Database()
    post_filter = PostFilter(db)
    translator = Translator(cfg)
    pub = Publisher()
    pub.set_token(cfg["BOT_TOKEN"])

    print(f"[{name}] Parsing {len(cfg['SOURCE_CHANNELS'])} donors...")
    parser = WebParser(db)
    parser.parse_all(cfg["SOURCE_CHANNELS"], limit_per_channel=20)

    print(f"[{name}] Selecting posts...")
    top_posts = post_filter.get_top_posts(limit=cfg["POSTS_PER_CYCLE"])

    if not top_posts:
        print(f"[{name}] No new posts")
        return 0

    if cfg["REQUIRE_MEDIA"]:
        before = len(top_posts)
        top_posts = [p for p in top_posts if p[2]]
        skipped = before - len(top_posts)
        if skipped:
            print(f"[{name}] Skipped {skipped} text-only posts (REQUIRE_MEDIA=1)")

    if not top_posts:
        print(f"[{name}] No posts with media")
        return 0

    total_published = db.get_stats()["published"]
    for post in top_posts:
        post_id, text, has_media, media_path, score, image_url, media_type = post

        print(f"[{name}] Translating #{post_id}...")
        translated = translator.translate(text)
        if not translated or translated == text:
            print(f"[{name}] Translation failed or skipped for #{post_id}, marking as skipped")
            db.mark_skipped(post_id)
            continue

        print(f"[{name}] Publishing #{post_id}...")
        total_published += 1
        success = pub.publish(
            text=translated,
            chat_id=cfg["TARGET_CHANNEL"],
            total_published=total_published,
            cpa_links=cfg["CPA_LINKS"],
            cpa_every=cfg["CPA_INSERT_EVERY"],
            media_path=media_path,
            media_type=media_type,
        )
        if success:
            db.mark_published(post_id)

    stats = db.get_stats()
    print(f"[{name}] Stats: {stats}")
    return stats["published"]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python core/run_channel.py channels/crypto/.env [--once]")
        sys.exit(1)

    env_path = sys.argv[1]
    once = "--once" in sys.argv

    if once:
        run_channel(env_path, once=True)
    else:
        env_path = os.path.abspath(env_path)
        cfg = load_channel_config(env_path)
        import time
        interval = cfg["PUBLISH_INTERVAL_HOURS"] * 3600
        print(f"Loop every {cfg['PUBLISH_INTERVAL_HOURS']}h")
        while True:
            try:
                run_channel(env_path, once=True)
            except Exception as e:
                print(f"[ERROR] {e}")
                import traceback
                traceback.print_exc()
            print(f"Sleeping {interval}s...")
            time.sleep(interval)
