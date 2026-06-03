import re
import requests
import os
from html import unescape

from core.db.database import Database


class WebParser:
    def __init__(self, db: Database):
        self.db = db
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        })
        os.makedirs("media", exist_ok=True)

    def _extract_video_url(self, block: str) -> str | None:
        match = re.search(r'data-video="([^"]+)"', block)
        if match:
            return match.group(1)
        match = re.search(r'<video[^>]+src="([^"]+)"', block)
        if match:
            return match.group(1)
        return None

    def _download_video(self, url: str, msg_id: int) -> str | None:
        try:
            path = f"media/vid_{msg_id}.mp4"
            r = self.session.get(url, timeout=120, stream=True)
            r.raise_for_status()
            total = 0
            with open(path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    total += len(chunk)
            print(f"  Video saved ({total//1024//1024}MB): {path}")
            return path
        except Exception as e:
            print(f"  Video download failed: {e}")
            return None

    def _clean_text(self, html_text: str) -> str:
        text = re.sub(r'<br\s*/?>', '\n', html_text)
        text = re.sub(r'<[^>]+>', '', text)
        text = unescape(text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _extract_image_url(self, block: str) -> str | None:
        bg_match = re.search(
            r'background-image:\s*url\([\'"]?(https://[^\)\'"]+)[\'"]?\)',
            block
        )
        if bg_match:
            return bg_match.group(1)
        img_match = re.search(
            r'<img[^>]+src="(https://[^"]+)"',
            block
        )
        if img_match:
            return img_match.group(1)
        return None

    def _download_image(self, url: str, msg_id: int) -> str | None:
        try:
            ext = url.split('.')[-1].split('?')[0][:5]
            if ext not in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
                ext = 'jpg'
            path = f"media/img_{msg_id}.{ext}"
            r = self.session.get(url, timeout=15)
            r.raise_for_status()
            with open(path, 'wb') as f:
                f.write(r.content)
            return path
        except Exception:
            return None

    def _parse_tme_page(self, html: str, channel_username: str):
        raw_messages = html.split('class="tgme_widget_message_wrap')
        if len(raw_messages) < 2:
            raw_messages = html.split('class="message')

        found = []
        seen_ids = set()

        for block in raw_messages[1:]:
            try:
                msg_id_match = re.search(r'data-post="([^"]+)"', block)
                if not msg_id_match:
                    continue
                msg_id_str = msg_id_match.group(1)
                try:
                    msg_id = int(msg_id_str.split("/")[-1])
                except (ValueError, IndexError):
                    msg_id = abs(hash(msg_id_str))
                if msg_id in seen_ids:
                    continue
                seen_ids.add(msg_id)

                text_match = re.search(
                    r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>\s*<div',
                    block, re.DOTALL
                )
                if not text_match:
                    text_match = re.search(
                        r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
                        block, re.DOTALL
                    )
                raw_text = text_match.group(1) if text_match else ""
                text = self._clean_text(raw_text)
                image_url = self._extract_image_url(block)
                video_url = self._extract_video_url(block)

                if not text and not image_url and not video_url:
                    continue
                if text and len(text) < 15 and not image_url and not video_url:
                    continue

                views = 0
                views_match = re.search(
                    r'class="tgme_widget_message_views"[^>]*>([^<]+)',
                    block
                )
                if views_match:
                    try:
                        views = int(re.sub(r'[^\d]', '', views_match.group(1)))
                    except:
                        views = 0

                found.append({
                    "id": msg_id,
                    "text": text,
                    "views": views,
                    "image_url": image_url,
                    "video_url": video_url,
                })
            except Exception:
                continue

        return found

    def parse_channel(self, channel_username: str, limit: int = 20) -> int:
        username = channel_username.lstrip("@")
        url = f"https://t.me/s/{username}"

        try:
            resp = self.session.get(url, timeout=20)
            resp.raise_for_status()
            html = resp.text

            messages = self._parse_tme_page(html, username)
            if not messages:
                print(f"[WebParser] {channel_username}: нет сообщений")
                return 0

            new_count = 0
            for msg in messages[:limit]:
                if self.db.post_exists(channel_username, msg["id"]):
                    continue
                media_path = None
                media_type = "text"
                if msg["video_url"]:
                    media_path = self._download_video(msg["video_url"], msg["id"])
                    media_type = "video" if media_path else "text"
                elif msg["image_url"]:
                    media_path = self._download_image(msg["image_url"], msg["id"])
                    media_type = "photo" if media_path else "text"
                self.db.save_post(
                    source_channel=channel_username,
                    source_message_id=msg["id"],
                    text=msg["text"],
                    views=msg["views"],
                    reactions_count=0,
                    has_media=media_path is not None,
                    media_path=media_path,
                    image_url=msg["video_url"] or msg["image_url"],
                    media_type=media_type,
                )
                new_count += 1

            print(f"[WebParser] {channel_username}: +{new_count} новых (из {len(messages)})")
            return new_count

        except requests.exceptions.HTTPError as e:
            print(f"[WebParser] {channel_username}: HTTP {e.response.status_code}")
            return 0
        except Exception as e:
            print(f"[WebParser] {channel_username}: {e}")
            return 0

    def parse_all(self, channels: list[str], limit_per_channel: int = 20) -> int:
        total = 0
        for ch in channels:
            ch = ch.strip()
            if not ch:
                continue
            n = self.parse_channel(ch, limit_per_channel)
            total += n
        print(f"[WebParser] Done. Всего новых: {total}")
        return total
