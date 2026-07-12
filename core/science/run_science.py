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

from dotenv import dotenv_values  # noqa: E402
from core.crosspost.vk_poster import VKPoster  # noqa: E402

MEDIA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media")
os.makedirs(MEDIA_DIR, exist_ok=True)

def load_published(tracker_path):
    if os.path.exists(tracker_path):
        with open(tracker_path) as f:
            return set(json.load(f))
    return set()


def save_published(posted, tracker_path):
    import tempfile
    tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(tracker_path), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(list(posted), f)
        os.replace(tmp_path, tracker_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def fetch_entries(subreddit):
    import feedparser
    url = f"https://www.reddit.com/r/{subreddit}/new/.rss"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    for attempt in range(3):
        feed = feedparser.parse(url, agent=headers["User-Agent"])
        if feed.entries:
            return feed.entries
        if attempt < 2:
            print(f"[Science] RSS empty (attempt {attempt+1}/3), retrying in 30s...")
            time.sleep(30)
    return feed.entries


def extract_image_urls(entry: dict) -> list[str]:
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
            print(f"[Science] Reddit JSON {r.status_code}, skipping")
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


def detect_video(entry):
    summary = (entry.get("summary") or entry.get("description") or "")
    m = re.search(r'href="(https?://v\.redd\.it/[^"]+)"', summary)
    if m:
        url = m.group(1).split("?")[0].rstrip("/")
        return url
    return None


def download_reddit_video(video_url, filename):
    import requests
    try:
        video_id = video_url.rstrip("/").split("/")[-1]
        manifest_url = f"https://v.redd.it/{video_id}/DASHPlaylist.mpd"
        r = requests.get(manifest_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if r.status_code != 200:
            print(f"[Science] DASH manifest {r.status_code}")
            return None

        text = r.text
        has_audio = 'contentType="audio"' in text

        video_rep = re.findall(
            r'<Representation[^>]+bandwidth="(\d+)"[^>]+height="(\d+)"[^>]*>.*?<BaseURL>([^<]+)</BaseURL>',
            text, re.DOTALL
        )
        if not video_rep:
            print("[Science] No video representations found")
            return None

        best = max(video_rep, key=lambda x: int(x[1]))
        video_base = best[2]
        video_height = best[1]

        audio_base = None
        if has_audio:
            audio_section = text[text.index('contentType="audio"'):]
            audio_rep = re.findall(
                r'<Representation[^>]+bandwidth="(\d+)"[^>]*>.*?<BaseURL>([^<]+)</BaseURL>',
                audio_section, re.DOTALL
            )
            if audio_rep:
                best_audio = max(audio_rep, key=lambda x: int(x[0]))
                audio_base = best_audio[1]

        video_file = None
        audio_file = None
        merged = os.path.join(MEDIA_DIR, f"{filename}.mp4")

        url = f"https://v.redd.it/{video_id}/{video_base}"
        vr = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30, stream=True)
        vr.raise_for_status()
        video_file = os.path.join(MEDIA_DIR, f"{filename}_video.mp4")
        with open(video_file, "wb") as f:
            for chunk in vr.iter_content(8192):
                f.write(chunk)

        if audio_base:
            url = f"https://v.redd.it/{video_id}/{audio_base}"
            ar = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30, stream=True)
            ar.raise_for_status()
            audio_file = os.path.join(MEDIA_DIR, f"{filename}_audio.mp4")
            with open(audio_file, "wb") as f:
                for chunk in ar.iter_content(8192):
                    f.write(chunk)

        if video_file and audio_file:
            import subprocess
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", video_file, "-i", audio_file,
                 "-c:v", "copy", "-c:a", "aac", "-strict", "experimental", merged],
                capture_output=True, timeout=60
            )
            if result.returncode == 0:
                os.remove(video_file)
                os.remove(audio_file)
                print(f"[Science] Merged {video_height}p video + audio")
                return merged
            else:
                print(f"[Science] ffmpeg merge failed: {result.stderr[:200]}")

        if video_file:
            os.rename(video_file, merged)
            if audio_file and os.path.exists(audio_file):
                os.remove(audio_file)
            print(f"[Science] Downloaded {video_height}p video (no audio)")
            return merged

        return None
    except Exception as e:
        print(f"[Science] Video download failed: {e}")
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
    tracker_path = os.path.join(os.path.dirname(env_path), "published.json")
    published = load_published(tracker_path)
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
                post_text = format_post(title)

                video_url = detect_video(entry)
                media_path = None
                media_type = "photo"

                if video_url:
                    media_path = await asyncio.to_thread(download_reddit_video, video_url, f"sci_{pid}")
                    if media_path:
                        media_type = "video"

                if not media_path:
                    image_urls = extract_image_urls(entry)
                    if len(image_urls) <= 1 and link:
                        reddit_images = await asyncio.to_thread(fetch_reddit_images, link)
                        if reddit_images:
                            image_urls = reddit_images
                    if image_urls:
                        media_path = await asyncio.to_thread(download_image, image_urls[0], f"sci_{pid}")

                try:
                    attachment = None
                    if media_path:
                        if media_type == "video":
                            attachment = vk.upload_video(media_path, title=title[:100])
                        else:
                            attachment = vk.upload_photo(media_path)
                    vk.post_to_wall(message=post_text, attachment=attachment)
                    published.add(pid)
                    save_published(published, tracker_path)
                    new_count += 1
                    label = "video" if media_type == "video" else "photo"
                    print(f"[Science] Posted ({label}): {title[:60]}...")
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
