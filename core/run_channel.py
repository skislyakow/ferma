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

    post_counter = 0
    for post in top_posts:
        post_id, text, has_media, media_path, score, image_url = post

        print(f"[{name}] Translating #{post_id}...")
        translated = translator.translate(text)

        print(f"[{name}] Publishing #{post_id}...")
        post_counter += 1
        success = pub.publish(
            text=translated,
            chat_id=cfg["TARGET_CHANNEL"],
            post_counter=post_counter,
            cpa_links=cfg["CPA_LINKS"],
            cpa_every=cfg["CPA_INSERT_EVERY"],
            media_path=media_path,
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
