"""
Популярная Наука — VK-only channel.
Parses r/Popular_Science_Ru via RSS and posts to VK wall.

Usage:
    python core/science/run_science.py channels/science/.env
"""
import os
import sys
import time
import json
import re
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import dotenv_values
from core.crosspost.vk_poster import VKPoster

MEDIA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media")
os.makedirs(MEDIA_DIR, exist_ok=True)

TRACKER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "published.json")


def load_published():
    if os.path.exists(TRACKER_PATH):
        with open(TRACKER_PATH) as f:
            return set(json.load(f))
    return set()


def save_published(posted):
    with open(TRACKER_PATH, "w") as f:
        json.dump(list(posted), f)


def fetch_entries(subreddit):
    import feedparser
    url = f"https://www.reddit.com/r/{subreddit}/new/.rss"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    feed = feedparser.parse(url, agent=headers["User-Agent"])
    return feed.entries


def extract_image_url(entry):
    summary = (entry.get("summary") or entry.get("description") or "")
    m = re.search(r'<img[^>]+src="([^"]+)"', summary)
    if m:
        from html import unescape
        return unescape(m.group(1))

    link = entry.get("link", "")
    if any(link.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp")):
        return link

    if "i.redd.it" in link:
        return link

    return None


def download_image(url, filename):
    import requests
    try:
        ext = url.rsplit(".", 1)[-1].split("?")[0] or "jpg"
        if ext not in ("jpg", "jpeg", "png", "gif", "webp"):
            ext = "jpg"
        local = os.path.join(MEDIA_DIR, f"{filename}.{ext}")
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        with open(local, "wb") as f:
            f.write(r.content)
        return local
    except Exception as e:
        print(f"[Science] Image download failed: {e}")
        return None


def format_post(title, url, subreddit):
    link = f"https://www.reddit.com{url}" if url.startswith("/") else url
    text = f"🔬 {title}\n\n🔗 Источник: Reddit r/{subreddit}\n\n{link}"
    return text


async def main(env_path: str):
    env = dotenv_values(env_path)
    vk_token = env.get("VK_TOKEN", "")
    vk_group_id = env.get("VK_GROUP_ID", "")
    subreddit = env.get("REDDIT_SUBREDDIT", "Popular_Science_Ru")
    interval = int(env.get("REDDIT_INTERVAL", "600"))

    if not vk_token or not vk_group_id:
        print("[Science] Missing VK_TOKEN or VK_GROUP_ID in .env")
        sys.exit(1)

    vk = VKPoster(vk_token, vk_group_id)
    published = load_published()
    channel_name = env.get("CHANNEL_NAME", subreddit)

    print(f"[Science] Starting. Subreddit: r/{subreddit}")
    print(f"[Science] VK group: {vk_group_id}")
    print(f"[Science] Already published: {len(published)} posts")
    print(f"[Science] Interval: {interval}s")

    while True:
        try:
            entries = await asyncio.to_thread(fetch_entries, subreddit)
            new_count = 0

            for entry in entries:
                pid = entry.get("id", "").split("/")[-1] or entry.get("link", "").split("/")[-2]
                if pid in published:
                    continue

                title = (entry.get("title") or "").strip()
                link = entry.get("link", "")
                summary = (entry.get("summary") or entry.get("description") or "")

                if not title:
                    continue

                title = re.sub(r'\s+', ' ', title).strip()

                image_url = extract_image_url(entry)
                media_path = None
                if image_url:
                    media_path = await asyncio.to_thread(download_image, image_url, f"sci_{pid}")

                post_text = format_post(title, link, subreddit)

                try:
                    attachment = None
                    if media_path:
                        attachment = vk.upload_photo(media_path)
                    vk.post_to_wall(message=post_text, attachment=attachment)
                    published.add(pid)
                    save_published(published)
                    new_count += 1
                    print(f"[Science] Posted: {title[:60]}...")
                except Exception as e:
                    print(f"[Science] Failed to post: {e}")

                if media_path and os.path.exists(media_path):
                    try:
                        os.remove(media_path)
                    except OSError:
                        pass

                await asyncio.sleep(3)

            if new_count == 0:
                print(f"[Science] No new posts (checked {len(entries)} entries)")

        except Exception as e:
            print(f"[Science] Error: {e}")
            import traceback
            traceback.print_exc()

        await asyncio.sleep(interval)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    env_path = os.path.abspath(sys.argv[1])
    asyncio.run(main(env_path))
