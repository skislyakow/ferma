import os
import requests
import random
import re


class Publisher:
    def __init__(self):
        self.bot_token = ""

    def set_token(self, token: str):
        self.bot_token = token

    def _cleanup_media(self, media_path):
        if media_path and os.path.exists(media_path):
            try:
                os.remove(media_path)
                print(f"[Publisher] Deleted local media: {media_path}")
            except Exception as e:
                print(f"[Publisher] Failed to delete {media_path}: {e}")

    def _clean_footers(self, text: str) -> str:
        from core.filter.manage import load_filters
        _f = load_filters()
        footer_patterns = _f.get("footer_patterns", [])
        lines = text.split("\n")
        clean = []
        for line in lines:
            stripped = line.strip().lower()
            skip = False
            for pat in footer_patterns:
                if pat in stripped or stripped.startswith(pat):
                    skip = True
                    break
            if skip:
                continue
            line = re.sub(r'https?://\S+', '', line).strip()
            if line:
                clean.append(line)
        result = "\n".join(clean).strip()
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result

    def _inject_cpa(self, text: str, post_counter: int, cpa_links: list[str], cpa_every: int) -> str:
        if not cpa_links:
            return text
        if post_counter > 0 and post_counter % cpa_every == 0:
            link = random.choice(cpa_links).strip()
            text += f"\n\n{link}"
        return text

    def publish(self, text: str, chat_id: str, post_counter: int = 0,
                cpa_links: list[str] = None, cpa_every: int = 3,
                media_path: str = None, media_type: str = "photo") -> bool:
        if not self.bot_token:
            print("[Publisher] No bot token!")
            return False

        text = self._clean_footers(text)
        text = self._inject_cpa(text, post_counter, cpa_links or [], cpa_every)

        try:
            if not media_path:
                url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                resp = requests.post(url, json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False,
                }, timeout=15)
            elif media_type == "video":
                if len(text) > 1024:
                    print("[Publisher] Text too long for video caption, skipping")
                    text = ""
                url = f"https://api.telegram.org/bot{self.bot_token}/sendVideo"
                with open(media_path, 'rb') as video:
                    resp = requests.post(url, data={
                        "chat_id": chat_id,
                        "caption": text,
                        "parse_mode": "HTML",
                        "supports_streaming": True,
                    }, files={"video": video}, timeout=120)
            else:
                if len(text) > 1024:
                    print("[Publisher] Text too long for photo caption, skipping image")
                    url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                    resp = requests.post(url, json={
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": False,
                    }, timeout=15)
                else:
                    url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
                    with open(media_path, 'rb') as photo:
                        resp = requests.post(url, data={
                            "chat_id": chat_id,
                            "caption": text,
                            "parse_mode": "HTML",
                        }, files={"photo": photo}, timeout=30)

            resp.raise_for_status()
            print(f"[Publisher] OK ({media_type})")
            self._cleanup_media(media_path)
            return True
        except Exception as e:
            print(f"[Publisher] Failed: {e}")
            return False
