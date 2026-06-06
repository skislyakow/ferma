import os
import requests
import random
import re


def _watermark_image(image_path, logo_path):
    try:
        from PIL import Image
    except ImportError:
        return image_path
    if not os.path.exists(logo_path):
        return image_path
    if os.path.abspath(image_path) == os.path.abspath(logo_path):
        return image_path
    try:
        img = Image.open(image_path).convert("RGBA")
        logo = Image.open(logo_path).convert("RGBA")
        ratio = img.width * 0.12 / logo.width
        logo = logo.resize((int(logo.width * ratio), int(logo.height * ratio)), Image.LANCZOS)
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        x = img.width - logo.width - 15
        y = img.height - logo.height - 15
        logo.putalpha(int(255 * 0.55))
        overlay.paste(logo, (x, y), logo)
        result = Image.alpha_composite(img, overlay)
        if image_path.lower().endswith((".jpg", ".jpeg")):
            result = result.convert("RGB")
        result.save(image_path, quality=95)
        print(f"[Watermark] Applied to {os.path.basename(image_path)}")
    except Exception as e:
        print(f"[Watermark] Failed: {e}")
    return image_path


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
                cpa_links: list[str] = None, cpa_every: int = 3,
                media_path: str = None, media_type: str = "photo",
                parse_mode: str = None) -> bool:
        if not self.bot_token:
            print("[Publisher] No bot token!")
            return False

        text = self._clean_footers(text)
        text = self._inject_cpa(text, total_published, cpa_links or [], cpa_every)

        try:
            if media_path and media_type == "photo":
                logo = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "repost2.png")
                media_path = _watermark_image(media_path, logo)

            if not media_path:
                payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": False}
                if parse_mode:
                    payload["parse_mode"] = parse_mode
                url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                resp = requests.post(url, json=payload, timeout=15)
                sent_type = "text"
            elif media_type == "video":
                if len(text) > 1024:
                    print("[Publisher] Text too long for video caption, skipping")
                    text = ""
                data = {"chat_id": chat_id, "caption": text, "supports_streaming": True}
                if parse_mode:
                    data["parse_mode"] = parse_mode
                url = f"https://api.telegram.org/bot{self.bot_token}/sendVideo"
                with open(media_path, 'rb') as video:
                    resp = requests.post(url, data=data, files={"video": video}, timeout=120)
                sent_type = "video"
            else:
                if len(text) > 1024:
                    print("[Publisher] Text too long for photo caption, skipping image")
                    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": False}
                    if parse_mode:
                        payload["parse_mode"] = parse_mode
                    url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                    resp = requests.post(url, json=payload, timeout=15)
                    sent_type = "text (photo fallback)"
                else:
                    data = {"chat_id": chat_id, "caption": text}
                    if parse_mode:
                        data["parse_mode"] = parse_mode
                    url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
                    with open(media_path, 'rb') as photo:
                        resp = requests.post(url, data=data, files={"photo": photo}, timeout=30)
                    sent_type = "photo"

            resp.raise_for_status()
            print(f"[Publisher] OK ({sent_type})")
            self._cleanup_media(media_path)
            return True
        except Exception as e:
            print(f"[Publisher] Failed: {e}")
            return False
