"""
Урбанистика — VK-only channel.
Parses r/UrbanHell via RSS, translates to Russian, posts to VK wall.

Usage:
    python core/urbanistika/run_urbanistika.py channels/urbanistika/.env
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


def translate_text(text, api_key, folder_id):
    import requests
    if not text or not api_key:
        return text
    try:
        r = requests.post(
            "https://translate.api.cloud.yandex.net/translate/v2/translate",
            json={
                "sourceLanguageCode": "en",
                "targetLanguageCode": "ru",
                "texts": [text],
                "folderId": folder_id,
            },
            headers={"Authorization": f"Api-Key {api_key}"},
            timeout=15,
        )
        data = r.json()
        if "translations" in data and data["translations"]:
            return data["translations"][0]["text"]
    except Exception as e:
        print(f"[Urbanistika] Translate error: {e}")
    return text


def is_russian(text):
    return bool(re.search(r'[\u0400-\u04FF]', text))


def fetch_entries(subreddit):
    import feedparser
    url = f"https://www.reddit.com/r/{subreddit}/new/.rss"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    for attempt in range(3):
        feed = feedparser.parse(url, agent=headers["User-Agent"])
        if feed.entries:
            return feed.entries
        if attempt < 2:
            print(f"[Urbanistika] RSS empty (attempt {attempt+1}/3), retrying in 30s...")
            time.sleep(30)
    return feed.entries


def extract_image_urls(entry):
    urls: list[str] = []
    summary = (entry.get("summary") or entry.get("description") or "")
    for m in re.finditer(r'<img[^>]+src="([^"]+)"', summary):
        url = unescape(m.group(1))
        url = re.sub(r'\?width=\d+&.*', '', url)
        url = url.replace("preview.redd.it", "i.redd.it").replace("external-i.redd.it", "i.redd.it")
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
            return []
        data = r.json()
        post_data = data[0]["data"]["children"][0]["data"]
        images: list[str] = []
        if post_data.get("is_gallery"):
            media_metadata = post_data.get("media_metadata", {})
            for item_id, meta in media_metadata.items():
                if meta.get("status") == "valid":
                    s = meta.get("s", {})
                    img_url = s.get("u") or s.get("gif") or ""
                    img_url = unescape(img_url)
                    img_url = img_url.replace("preview.redd.it", "i.redd.it").replace("external-i.redd.it", "i.redd.it")
                    img_url = re.sub(r'\?width=\d+&.*', '', img_url)
                    if img_url and img_url not in images:
                        images.append(img_url)
        else:
            preview = post_data.get("preview", {}).get("images", [])
            if preview:
                src = preview[0].get("source", {})
                img_url = unescape(src.get("url", ""))
                img_url = img_url.replace("preview.redd.it", "i.redd.it").replace("external-i.redd.it", "i.redd.it")
                img_url = re.sub(r'\?width=\d+&.*', '', img_url)
                if img_url:
                    images.append(img_url)
            post_url_str = post_data.get("url_overridden_by_dest") or post_data.get("url", "")
            if post_url_str and "i.redd.it" in post_url_str:
                base = post_url_str.split("?")[0]
                if base not in images:
                    images.append(base)
        return images
    except Exception:
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
        ct = r.headers.get("content-type", "")
        if "text/html" in ct or len(r.content) < 1000:
            return None
        with open(local, "wb") as f:
            f.write(r.content)
        return local
    except Exception as e:
        print(f"[Urbanistika] Image download failed: {e}")
        return None


def format_post(title):
    return f"🏙 {title}"


async def main(env_path: str):
    env = dotenv_values(env_path)
    vk_token = env.get("VK_TOKEN", "")
    vk_group_id = env.get("VK_GROUP_ID", "")
    subreddits_raw = env.get("REDDIT_SUBREDDITS", "") or env.get("REDDIT_SUBREDDIT", "UrbanHell")
    subreddits = [s.strip() for s in subreddits_raw.split(",") if s.strip()]
    if not subreddits:
        subreddits = ["UrbanHell"]
    interval = int(env.get("REDDIT_INTERVAL", "600"))
    yc_api_key = env.get("YC_TRANSLATE_API_KEY", "")
    yc_folder_id = env.get("YC_FOLDER_ID", "")

    if not vk_token or not vk_group_id:
        print("[Urbanistika] Missing VK_TOKEN or VK_GROUP_ID in .env")
        sys.exit(1)

    vk = VKPoster(vk_token, vk_group_id)
    published = load_published()
    sub_idx = 0

    print(f"[Urbanistika] Starting. Subreddits: {', '.join('r/' + s for s in subreddits)}")
    print(f"[Urbanistika] VK group: {vk_group_id}")
    print(f"[Urbanistika] Already published: {len(published)} posts")
    print(f"[Urbanistika] Interval: {interval}s")

    while True:
        try:
            subreddit = subreddits[sub_idx % len(subreddits)]
            sub_idx += 1
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

                if not is_russian(title):
                    title = await asyncio.to_thread(translate_text, title, yc_api_key, yc_folder_id)

                post_text = format_post(title)

                image_urls = extract_image_urls(entry)
                media_path = None
                if image_urls:
                    media_path = await asyncio.to_thread(download_image, image_urls[0], f"urb_{pid}")

                if not media_path and link:
                    reddit_images = await asyncio.to_thread(fetch_reddit_images, link)
                    if reddit_images:
                        image_urls = reddit_images
                        media_path = await asyncio.to_thread(download_image, image_urls[0], f"urb_{pid}")

                if not media_path:
                    continue

                try:
                    attachment = None
                    if media_path:
                        attachment = vk.upload_photo(media_path)
                    vk.post_to_wall(message=post_text, attachment=attachment)
                    published.add(pid)
                    save_published(published)
                    new_count += 1
                    print(f"[Urbanistika] Posted (photo): {title[:60]}...")
                except Exception as e:
                    print(f"[Urbanistika] Failed to post: {e}")

                if media_path and os.path.exists(media_path):
                    try:
                        os.remove(media_path)
                    except OSError:
                        pass

                await asyncio.sleep(3)

            if new_count == 0:
                print(f"[Urbanistika] No new posts (checked {len(entries)} entries)")

        except Exception as e:
            print(f"[Urbanistika] Error: {e}")
            import traceback
            traceback.print_exc()

        await asyncio.sleep(interval)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    env_path = os.path.abspath(sys.argv[1])
    asyncio.run(main(env_path))
