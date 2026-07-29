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
        clean: list[str] = []
        for i, line in enumerate(lines):
            stripped = line.strip().lower()
            skip = False
            if i > 0:  # preserve first line (headline)
                for pat in footer_patterns:
                    if pat in stripped or stripped.startswith(pat):
                        skip = True
                        break
            if skip:
                continue
            if line.strip():
                clean.append(line)
        result = "\n".join(clean).strip()
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result

    def _inject_cpa(self, text: str, total_published: int, cpa_links: list[str], cpa_every: int) -> str:
        if not cpa_links:
            return text
        if total_published > 0 and total_published % cpa_every == 0:
            link = random.choice(cpa_links).strip()
            text += f"\n\n{link}"
        return text

    def publish(self, text: str, chat_id: str, total_published: int = 0,
                cpa_links: list[str] | None = None, cpa_every: int = 3,
                media_path: str | None = None, media_type: str = "photo",
                parse_mode: str | None = None) -> bool:
        if not self.bot_token:
            print("[Publisher] No bot token!")
            return False

        text = self._clean_footers(text)
        text = self._inject_cpa(text, total_published, cpa_links or [], cpa_every)

        # Minimum content guard — prevent empty/near-empty posts
        if len(text.strip()) < 20:
            if media_path:
                text = "👉 Кадр дня"
                print("[Publisher] Text too short, using 'Кадр дня' fallback")
            else:
                print("[Publisher] Text too short, skipping")
                return False

        try:
            if not media_path:
                payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
                if parse_mode:
                    payload["parse_mode"] = parse_mode
                url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                resp = requests.post(url, json=payload, timeout=15)
                sent_type = "text"
            elif media_type == "video":
                if len(text) > 1024:
                    print("[Publisher] Text too long for video caption, skipping")
                    text = ""
                data = {"chat_id": chat_id, "caption": text, "supports_streaming": True, "disable_web_page_preview": True}
                if parse_mode:
                    data["parse_mode"] = parse_mode
                url = f"https://api.telegram.org/bot{self.bot_token}/sendVideo"
                with open(media_path, 'rb') as video:
                    resp = requests.post(url, data=data, files={"video": video}, timeout=120)
                sent_type = "video"
            else:
                if len(text) > 1024:
                    print("[Publisher] Text too long for photo caption, skipping image")
                    self._cleanup_media(media_path)
                    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
                    if parse_mode:
                        payload["parse_mode"] = parse_mode
                    url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                    resp = requests.post(url, json=payload, timeout=15)
                    sent_type = "text (photo fallback)"
                else:
                    data = {"chat_id": chat_id, "caption": text, "disable_web_page_preview": True}
                    if parse_mode:
                        data["parse_mode"] = parse_mode
                    url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
                    with open(media_path, 'rb') as photo:
                        resp = requests.post(url, data=data, files={"photo": photo}, timeout=30)
                    sent_type = "photo"

            resp.raise_for_status()
            result = resp.json()
            if not result.get("ok"):
                print(f"[Publisher] API error: {result.get('description', 'unknown')}")
                self._cleanup_media(media_path)
                return False
            print(f"[Publisher] OK ({sent_type})")
            self._cleanup_media(media_path)
            return True
        except Exception as e:
            print(f"[Publisher] Failed: {e}")
            self._cleanup_media(media_path)
            return False
