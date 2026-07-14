import os
import sys
import time
import json
import re
import asyncio
import tempfile
import traceback
from html import unescape


def load_published(tracker_path):
    if os.path.exists(tracker_path):
        with open(tracker_path) as f:
            return set(json.load(f))
    return set()


def save_published(posted, tracker_path):
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=os.path.dirname(tracker_path), suffix=".tmp"
    )
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(list(posted), f)
        os.replace(tmp_path, tracker_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def translate_text(text, api_key, folder_id, name="VK"):
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
        print(f"[{name}] Translate error: {e}")
    return text


def is_russian(text):
    return bool(re.search(r"[\u0400-\u04FF]", text))


def detect_video(entry):
    summary = entry.get("summary") or entry.get("description") or ""
    m = re.search(r'href="(https?://v\.redd\.it/[^"]+)"', summary)
    if m:
        return m.group(1).split("?")[0].rstrip("/")
    return None


def fetch_entries(subreddit, name="VK"):
    import feedparser

    url = f"https://www.reddit.com/r/{subreddit}/new/.rss"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    for attempt in range(3):
        feed = feedparser.parse(url, agent=headers["User-Agent"])
        if feed.entries:
            return feed.entries
        if attempt < 2:
            print(
                f"[{name}] RSS empty (attempt {attempt + 1}/3), retrying in 30s..."
            )
            time.sleep(30)
    return feed.entries


def _normalize_image_url(url: str) -> str | None:
    url = unescape(url)
    url = re.sub(r"\?width=\d+&.*", "", url)
    url = url.replace("external-i.redd.it", "i.redd.it").replace(
        "preview.redd.it", "i.redd.it"
    )
    return url


def extract_image_urls(entry: dict) -> list[str]:
    urls: list[str] = []
    summary = entry.get("summary") or entry.get("description") or ""
    for m in re.finditer(r'<img[^>]+src="([^"]+)"', summary):
        url = unescape(m.group(1))
        if "external-preview.redd.it" in url:
            if url not in urls:
                urls.append(url)
        else:
            url = _normalize_image_url(url)
            if url not in urls:
                urls.append(url)

    for m in re.finditer(r'<a\s[^>]*href="([^"]+)"', summary):
        url = unescape(m.group(1))
        url = re.sub(r"\?.*", "", url)
        if any(url.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp")):
            if url not in urls:
                urls.append(url)

    if not urls:
        link = entry.get("link", "")
        if any(
            link.endswith(ext)
            for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp")
        ):
            urls.append(link)
        elif "i.redd.it" in link:
            urls.append(link)

    return urls


def fetch_reddit_images(post_url, name="VK"):
    import requests

    try:
        old_url = post_url.replace("www.reddit.com", "old.reddit.com")
        json_url = old_url.rstrip("/") + ".json"
        r = requests.get(
            json_url,
            timeout=15,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )
        if r.status_code != 200:
            print(f"[{name}] Reddit JSON returned {r.status_code}")
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
                    if "external-preview.redd.it" not in img_url:
                        img_url = img_url.replace(
                            "preview.redd.it", "i.redd.it"
                        ).replace("external-i.redd.it", "i.redd.it")
                        img_url = re.sub(r"\?width=\d+&.*", "", img_url)
                    if img_url and img_url not in images:
                        images.append(img_url)
        else:
            preview = post_data.get("preview", {}).get("images", [])
            if preview:
                src = preview[0].get("source", {})
                img_url = unescape(src.get("url", ""))
                if "external-preview.redd.it" not in img_url:
                    img_url = img_url.replace(
                        "preview.redd.it", "i.redd.it"
                    ).replace("external-i.redd.it", "i.redd.it")
                    img_url = re.sub(r"\?width=\d+&.*", "", img_url)
                if img_url:
                    images.append(img_url)
            post_url_str = post_data.get(
                "url_overridden_by_dest"
            ) or post_data.get("url", "")
            if post_url_str and "i.redd.it" in post_url_str:
                base = post_url_str.split("?")[0]
                if base not in images:
                    images.append(base)
        return images
    except Exception as e:
        print(f"[{name}] Reddit JSON fetch failed: {e}")
        return []


def download_image(url, filename, media_dir, name="VK"):
    import requests

    try:
        ext = url.rsplit(".", 1)[-1].split("?")[0] or "jpg"
        if ext not in ("jpg", "jpeg", "png", "gif", "webp"):
            ext = "jpg"
        local = os.path.join(media_dir, f"{filename}.{ext}")
        r = requests.get(
            url, timeout=20, headers={"User-Agent": "Mozilla/5.0"}
        )
        r.raise_for_status()
        ct = r.headers.get("content-type", "")
        if "text/html" in ct or len(r.content) < 1000:
            return None
        with open(local, "wb") as f:
            f.write(r.content)
        return local
    except Exception as e:
        print(f"[{name}] Image download failed: {e}")
        return None


def download_reddit_video(video_url, filename, media_dir, name="VK"):
    import requests as _req

    video_file = None
    audio_file = None
    merged = None
    try:
        video_id = video_url.rstrip("/").split("/")[-1]
        manifest_url = f"https://v.redd.it/{video_id}/DASHPlaylist.mpd"
        r = _req.get(
            manifest_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15
        )
        if r.status_code != 200:
            print(f"[{name}] DASH manifest {r.status_code}")
            return None

        text = r.text
        has_audio = 'contentType="audio"' in text

        video_rep = re.findall(
            r'<Representation[^>]+bandwidth="(\d+)"[^>]+height="(\d+)"[^>]*>.*?<BaseURL>([^<]+)</BaseURL>',
            text,
            re.DOTALL,
        )
        if not video_rep:
            print(f"[{name}] No video representations found")
            return None

        best = max(video_rep, key=lambda x: int(x[1]))
        video_base = best[2]
        video_height = best[1]

        audio_base = None
        if has_audio:
            audio_section = text[text.index('contentType="audio"') :]
            audio_rep = re.findall(
                r'<Representation[^>]+bandwidth="(\d+)"[^>]*>.*?<BaseURL>([^<]+)</BaseURL>',
                audio_section,
                re.DOTALL,
            )
            if audio_rep:
                best_audio = max(audio_rep, key=lambda x: int(x[0]))
                audio_base = best_audio[1]

        merged = os.path.join(media_dir, f"{filename}.mp4")

        url = f"https://v.redd.it/{video_id}/{video_base}"
        vr = _req.get(
            url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30, stream=True
        )
        vr.raise_for_status()
        video_file = os.path.join(media_dir, f"{filename}_video.mp4")
        with open(video_file, "wb") as f:
            for chunk in vr.iter_content(8192):
                f.write(chunk)

        if audio_base:
            url = f"https://v.redd.it/{video_id}/{audio_base}"
            ar = _req.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=30,
                stream=True,
            )
            ar.raise_for_status()
            audio_file = os.path.join(media_dir, f"{filename}_audio.mp4")
            with open(audio_file, "wb") as f:
                for chunk in ar.iter_content(8192):
                    f.write(chunk)

        if video_file and audio_file:
            import subprocess

            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    video_file,
                    "-i",
                    audio_file,
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    "-strict",
                    "experimental",
                    merged,
                ],
                capture_output=True,
                timeout=60,
            )
            if result.returncode == 0:
                os.remove(video_file)
                os.remove(audio_file)
                print(f"[{name}] Merged {video_height}p video + audio")
                return merged
            else:
                print(f"[{name}] ffmpeg merge failed: {result.stderr[:200]}")

        if video_file:
            os.rename(video_file, merged)
            if audio_file and os.path.exists(audio_file):
                os.remove(audio_file)
            print(f"[{name}] Downloaded {video_height}p video (no audio)")
            return merged

        return None
    except Exception as e:
        for f in [video_file, audio_file, merged]:
            if f and os.path.exists(f):
                try:
                    os.remove(f)
                except OSError:
                    pass
        print(f"[{name}] Video download failed: {e}")
        return None


async def process_entry(
    entry,
    *,
    name,
    vk,
    published,
    tracker_path,
    media_dir,
    format_post,
    media_prefix="media_",
    enable_translate=False,
    yc_api_key="",
    yc_folder_id="",
    skip_without_media=True,
    resolve_images_with_fallback=False,
):
    pid = (
        entry.get("id", "").split("/")[-1]
        or entry.get("link", "").split("/")[-2]
    )
    if pid in published:
        return 0

    title = (entry.get("title") or "").strip()
    link = entry.get("link", "")

    if not title:
        return 0

    title = re.sub(r"\s+", " ", title).strip()

    if enable_translate and not is_russian(title):
        title = await asyncio.to_thread(
            translate_text, title, yc_api_key, yc_folder_id, name
        )

    post_text = format_post(title)

    video_url = detect_video(entry)
    media_path = None
    media_type = "photo"

    if video_url:
        media_path = await asyncio.to_thread(
            download_reddit_video,
            video_url,
            f"{media_prefix}{pid}",
            media_dir,
            name,
        )
        if media_path:
            media_type = "video"

    if not media_path:
        image_urls = extract_image_urls(entry)
        if resolve_images_with_fallback and len(image_urls) <= 1 and link:
            reddit_images = await asyncio.to_thread(
                fetch_reddit_images, link, name
            )
            if reddit_images:
                image_urls = reddit_images
        if image_urls:
            media_path = await asyncio.to_thread(
                download_image,
                image_urls[0],
                f"{media_prefix}{pid}",
                media_dir,
                name,
            )

    if not media_path and link and not resolve_images_with_fallback:
        reddit_images = await asyncio.to_thread(
            fetch_reddit_images, link, name
        )
        if reddit_images:
            media_path = await asyncio.to_thread(
                download_image,
                reddit_images[0],
                f"{media_prefix}{pid}",
                media_dir,
                name,
            )

    if not media_path and skip_without_media:
        return 0

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
        label = (
            "video"
            if media_type == "video"
            else "photo"
            if media_path
            else "text"
        )
        print(f"[{name}] Posted ({label}): {title[:60]}...")
        return 1
    except Exception as e:
        print(f"[{name}] Failed to post: {e}")
        return 0
    finally:
        if media_path and os.path.exists(media_path):
            try:
                os.remove(media_path)
            except OSError:
                pass


async def run_cycle(
    env_path,
    *,
    name,
    format_post,
    media_dir,
    default_subreddit="interesting",
    enable_translate=True,
    skip_without_media=True,
    media_prefix="media_",
    interval_default=600,
):
    env_path = os.path.abspath(env_path)
    from dotenv import dotenv_values
    from core.crosspost.vk_poster import VKPoster

    env = dotenv_values(env_path)
    vk_token = env.get("VK_TOKEN", "")
    vk_group_id = env.get("VK_GROUP_ID", "")
    subreddits_raw = env.get("REDDIT_SUBREDDITS", "") or env.get(
        "REDDIT_SUBREDDIT", default_subreddit
    )
    subreddits = [s.strip() for s in subreddits_raw.split(",") if s.strip()]
    if not subreddits:
        subreddits = [default_subreddit]
    interval = int(env.get("REDDIT_INTERVAL", str(interval_default)))
    yc_api_key = env.get("YC_TRANSLATE_API_KEY", "")
    yc_folder_id = env.get("YC_FOLDER_ID", "")

    if not vk_token or not vk_group_id:
        print(f"[{name}] Missing VK_TOKEN or VK_GROUP_ID in .env")
        sys.exit(1)

    vk = VKPoster(vk_token, vk_group_id)
    tracker_path = os.path.join(os.path.dirname(env_path), "published.json")
    published = load_published(tracker_path)
    os.makedirs(media_dir, exist_ok=True)
    sub_idx = 0

    print(
        f"[{name}] Starting. Subreddits: {', '.join('r/' + s for s in subreddits)}"
    )
    print(f"[{name}] VK group: {vk_group_id}")
    print(f"[{name}] Already published: {len(published)} posts")
    print(f"[{name}] Interval: {interval}s")

    while True:
        try:
            subreddit = subreddits[sub_idx % len(subreddits)]
            sub_idx += 1
            entries = await asyncio.to_thread(fetch_entries, subreddit, name)
            new_count = 0

            for entry in entries:
                result = await process_entry(
                    entry,
                    name=name,
                    vk=vk,
                    published=published,
                    tracker_path=tracker_path,
                    media_dir=media_dir,
                    format_post=format_post,
                    media_prefix=media_prefix,
                    enable_translate=enable_translate,
                    yc_api_key=yc_api_key,
                    yc_folder_id=yc_folder_id,
                    skip_without_media=skip_without_media,
                    resolve_images_with_fallback=not skip_without_media,
                )
                new_count += result
                if result:
                    await asyncio.sleep(3)

            if new_count == 0:
                print(
                    f"[{name}] No new posts (checked {len(entries)} entries)"
                )

        except Exception as e:
            print(f"[{name}] Error: {e}")
            traceback.print_exc()

        await asyncio.sleep(interval)
