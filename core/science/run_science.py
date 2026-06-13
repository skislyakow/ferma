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
from html import unescape

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


def extract_image_urls(entry):
    urls = []
    summary = (entry.get("summary") or entry.get("description") or "")
    for m in re.finditer(r'<img[^>]+src="([^"]+)"', summary):
        url = unescape(m.group(1))
        url = re.sub(r'\?width=\d+&.*', '', url)
        if url not in urls:
            urls.append(url)

    if not urls:
        link = entry.get("link", "")
        if any(link.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp")):
            urls.append(link)
        elif "i.redd.it" in link:
            urls.append(link)

    return urls


def fetch_reddit_images(post_url):
    import requests
    try:
        old_url = post_url.replace("www.reddit.com", "old.reddit.com")
        json_url = old_url.rstrip("/") + ".json"
        r = requests.get(json_url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        if r.status_code != 200:
            print(f"[Science] Reddit JSON {r.status_code}, skipping")
            return []
        data = r.json()
        post_data = data[0]["data"]["children"][0]["data"]

        images = []

        if post_data.get("is_gallery"):
            media_metadata = post_data.get("media_metadata", {})
            for item_id, meta in media_metadata.items():
                if meta.get("status") == "valid":
                    s = meta.get("s", {})
                    img_url = s.get("u") or s.get("gif") or ""
                    img_url = unescape(img_url)
                    if img_url and img_url not in images:
                        images.append(img_url)
        else:
            preview = post_data.get("preview", {}).get("images", [])
            if preview:
                src = preview[0].get("source", {})
                img_url = unescape(src.get("url", ""))
                if img_url:
                    images.append(img_url)

            post_url_str = post_data.get("url_overridden_by_dest") or post_data.get("url", "")
            if post_url_str and "i.redd.it" in post_url_str:
                base = post_url_str.split("?")[0]
                if base not in images:
                    images.append(base)

        return images
    except Exception as e:
        print(f"[Science] Reddit JSON fetch failed: {e}")
        return []


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


def format_post(title):
    return f"🔬 {title}"


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

                if not title:
                    continue

                title = re.sub(r'\s+', ' ', title).strip()

                image_urls = extract_image_urls(entry)

                if len(image_urls) <= 1 and link:
                    reddit_images = await asyncio.to_thread(fetch_reddit_images, link)
                    if reddit_images:
                        image_urls = reddit_images

                downloaded = []
                for i, img_url in enumerate(image_urls):
                    suffix = f"_{i}" if len(image_urls) > 1 else ""
                    path = await asyncio.to_thread(download_image, img_url, f"sci_{pid}{suffix}")
                    if path:
                        downloaded.append(path)

                post_text = format_post(title)

                try:
                    attachments = []
                    for path in downloaded:
                        att = vk.upload_photo(path)
                        attachments.append(att)

                    att_str = ",".join(attachments) if attachments else None
                    vk.post_to_wall(message=post_text, attachment=att_str)
                    published.add(pid)
                    save_published(published)
                    new_count += 1
                    photo_count = len(attachments)
                    print(f"[Science] Posted ({photo_count} photo{'s' if photo_count != 1 else ''}): {title[:60]}...")
                except Exception as e:
                    print(f"[Science] Failed to post: {e}")

                for path in downloaded:
                    if os.path.exists(path):
                        try:
                            os.remove(path)
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
