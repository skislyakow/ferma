#!/usr/bin/env python3
"""Deploy script — creates all project files in /opt/tg-farm"""
import os, sys

BASE = "/opt/tg-farm"
FILES = {}

FILES["core/config.py"] = '''import os
from dotenv import dotenv_values

def load_channel_config(env_path: str = None):
    if env_path and os.path.exists(env_path):
        env = dotenv_values(env_path)
    else:
        env = dotenv_values()
    return {
        "YC_TRANSLATE_API_KEY": env.get("YC_TRANSLATE_API_KEY", ""),
        "YC_FOLDER_ID": env.get("YC_FOLDER_ID", ""),
        "BOT_TOKEN": env.get("BOT_TOKEN", ""),
        "SOURCE_CHANNELS": [x.strip() for x in env.get("SOURCE_CHANNELS", "").split(",") if x.strip()],
        "TARGET_CHANNEL": env.get("TARGET_CHANNEL", ""),
        "PUBLISH_INTERVAL_HOURS": float(env.get("PUBLISH_INTERVAL_HOURS", "3")),
        "POSTS_PER_CYCLE": int(env.get("POSTS_PER_CYCLE", "2")),
        "SOURCE_LANG": env.get("SOURCE_LANG", "en"),
        "TARGET_LANG": env.get("TARGET_LANG", "ru"),
        "CPA_LINKS": [x.strip() for x in env.get("CPA_LINKS", "").split(",") if x.strip()],
        "CPA_INSERT_EVERY": int(env.get("CPA_INSERT_EVERY", "3")),
    }
'''

FILES["core/db/database.py"] = '''import hashlib, sqlite3
from datetime import datetime

class Database:
    def __init__(self, db_path="posts.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_channel TEXT, source_message_id INTEGER,
                text TEXT, text_hash TEXT, views INTEGER DEFAULT 0,
                reactions_count INTEGER DEFAULT 0,
                engagement_score REAL DEFAULT 0,
                has_media INTEGER DEFAULT 0, media_path TEXT,
                image_url TEXT, published INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                published_at TIMESTAMP,
                UNIQUE(source_channel, source_message_id)
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_published ON posts(published)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_text_hash ON posts(text_hash)")
            self._migrate()

    def _migrate(self):
        with sqlite3.connect(self.db_path) as conn:
            try: conn.execute("ALTER TABLE posts ADD COLUMN text_hash TEXT")
            except: pass

    @staticmethod
    def make_text_hash(text):
        return hashlib.md5(text[:200].encode("utf-8")).hexdigest() if text else ""

    def content_exists(self, text):
        if not text: return False
        h = self.make_text_hash(text)
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT 1 FROM posts WHERE text_hash = ? AND published = 1", (h,)).fetchone() is not None

    def post_exists(self, source_channel, source_message_id):
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT 1 FROM posts WHERE source_channel = ? AND source_message_id = ?",
                (source_channel, source_message_id)).fetchone() is not None

    def save_post(self, source_channel, source_message_id, text, views, reactions, has_media, media_path=None, image_url=None):
        h = self.make_text_hash(text)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR IGNORE INTO posts (source_channel, source_message_id, text, text_hash, views, reactions_count, has_media, media_path, image_url) VALUES (?,?,?,?,?,?,?,?,?)",
                (source_channel, source_message_id, text, h, views, reactions, int(has_media), media_path, image_url))

    def get_unpublished_posts(self, limit=5):
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("""SELECT id, text, has_media, media_path, engagement_score, image_url
                FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY source_channel ORDER BY engagement_score DESC, views DESC) as rn
                FROM posts WHERE published = 0 AND text IS NOT NULL AND text != '')
                WHERE rn = 1 ORDER BY engagement_score DESC LIMIT ?""", (limit,)).fetchall()

    def mark_published(self, post_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE posts SET published = 1, published_at = ? WHERE id = ?", (datetime.now().isoformat(), post_id))

    def mark_skipped(self, post_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE posts SET published = -1 WHERE id = ?", (post_id,))

    def get_stats(self):
        with sqlite3.connect(self.db_path) as conn:
            return {"total": conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0],
                    "published": conn.execute("SELECT COUNT(*) FROM posts WHERE published = 1").fetchone()[0],
                    "skipped": conn.execute("SELECT COUNT(*) FROM posts WHERE published = -1").fetchone()[0]}
'''

FILES["core/parser/web_parser.py"] = '''import re, requests, os
from html import unescape

class WebParser:
    def __init__(self, db):
        self.db = db
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept-Language": "en-US,en;q=0.9,ru;q=0.8"})
        os.makedirs("media", exist_ok=True)

    def _clean_text(self, html_text):
        text = re.sub(r'<br\\s*/?>', '\\n', html_text)
        text = re.sub(r'<[^>]+>', '', text)
        text = unescape(text)
        return re.sub(r'\\n{3,}', '\\n\\n', text).strip()

    def _extract_image_url(self, block):
        bg = re.search(r'background-image:\\s*url\\([\\'"]?(https://[^\\)\\'"]+)[\\'"]?\\)', block)
        if bg: return bg.group(1)
        img = re.search(r'<img[^>]+src="(https://[^"]+)"', block)
        return img.group(1) if img else None

    def _download_image(self, url, msg_id):
        ext = url.split('.')[-1].split('?')[0][:5]
        if ext not in ('jpg', 'jpeg', 'png', 'gif', 'webp'): ext = 'jpg'
        path = f"media/img_{msg_id}.{ext}"
        try:
            r = self.session.get(url, timeout=15); r.raise_for_status()
            with open(path, 'wb') as f: f.write(r.content)
            return path
        except: return None

    def _parse_tme_page(self, html, channel_username):
        raw = html.split('class="tgme_widget_message_wrap')
        if len(raw) < 2: raw = html.split('class="message')
        found, seen = [], set()
        for block in raw[1:]:
            try:
                m = re.search(r'data-post="([^"]+)"', block)
                if not m: continue
                mid = int(m.group(1).split("/")[-1]) if "/" in m.group(1) else abs(hash(m.group(1)))
                if mid in seen: continue
                seen.add(mid)
                tm = re.search(r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', block, re.DOTALL)
                text = self._clean_text(tm.group(1)) if tm else ""
                img = self._extract_image_url(block)
                if not text and not img: continue
                if text and len(text) < 15 and not img: continue
                views = 0
                v = re.search(r'class="tgme_widget_message_views"[^>]*>([^<]+)', block)
                if v:
                    try: views = int(re.sub(r'[^\\d]', '', v.group(1)))
                    except: pass
                found.append({"id": mid, "text": text, "views": views, "image_url": img})
            except: continue
        return found

    def parse_channel(self, channel_username, limit=20):
        username = channel_username.lstrip("@")
        try:
            resp = self.session.get(f"https://t.me/s/{username}", timeout=20)
            resp.raise_for_status()
            msgs = self._parse_tme_page(resp.text, username)
            if not msgs: print(f"[WebParser] {channel_username}: no messages"); return 0
            new = 0
            for msg in msgs[:limit]:
                if self.db.post_exists(channel_username, msg["id"]): continue
                mp = self._download_image(msg["image_url"], msg["id"]) if msg["image_url"] else None
                self.db.save_post(channel_username, msg["id"], msg["text"], msg["views"], 0, mp is not None, mp, msg["image_url"])
                new += 1
            print(f"[WebParser] {channel_username}: +{new} new (of {len(msgs)})")
            return new
        except requests.exceptions.HTTPError as e:
            print(f"[WebParser] {channel_username}: HTTP {e.response.status_code}"); return 0
        except Exception as e:
            print(f"[WebParser] {channel_username}: {e}"); return 0

    def parse_all(self, channels, limit_per_channel=20):
        total = 0
        for ch in channels:
            ch = ch.strip()
            if not ch: continue
            total += self.parse_channel(ch, limit_per_channel)
        print(f"[WebParser] Done. Total new: {total}")
        return total
'''

FILES["core/translator/translator.py"] = '''import requests

class Translator:
    def __init__(self, cfg):
        self.api_key = cfg.get("YC_TRANSLATE_API_KEY", "")
        self.folder_id = cfg.get("YC_FOLDER_ID", "")
        self.target = cfg.get("TARGET_LANG", "ru")
        self.source = cfg.get("SOURCE_LANG", "en")

    def translate(self, text):
        if not text or not self.api_key: return text
        try:
            r = requests.post("https://translate.api.cloud.yandex.net/translate/v2/translate",
                headers={"Authorization": f"Api-Key {self.api_key}", "Content-Type": "application/json"},
                json={"texts": [text], "targetLanguageCode": self.target, "sourceLanguageCode": self.source},
                timeout=15)
            r.raise_for_status()
            return r.json().get("translations", [{}])[0].get("text", text)
        except Exception as e:
            print(f"[Translator] Error: {e}"); return text
'''

FILES["core/publisher/publisher.py"] = '''import requests, random, re

class Publisher:
    def __init__(self):
        self.bot_token = ""

    def set_token(self, token):
        self.bot_token = token

    def _clean_footers(self, text):
        lines = text.split("\\n")
        clean = []
        for line in lines:
            s = line.strip().lower()
            if re.search(r"^(\u043c\u044b \u0432|\u043f\u043e\u0434\u043f\u0438\u0448\u0438\u0441\u044c|\u043f\u0440\u0438\u0441\u043e\u0435\u0434\u0438\u043d\u044f\u0439\u0441\u044f|\u0431\u043e\u043b\u044c\u0448\u0435 \u043d\u043e\u0432\u043e\u0441\u0442\u0435\u0439|\u043d\u0430\u0448 (\u043a\u0430\u043d\u0430\u043b|\u0431\u043b\u043e\u0433|\u0441\u0430\u0439\u0442)|\u0432\u0441\u0435 \u043d\u043e\u0432\u043e\u0441\u0442\u0438|\u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a|\u0447\u0438\u0442\u0430\u0442\u044c \u0434\u0430\u043b\u0435\u0435|\u043f\u043e \u0432\u0441\u0435\u043c \u0432\u043e\u043f\u0440\u043e\u0441\u0430\u043c|\u0440\u0435\u043a\u043b\u0430\u043c\u0430|\u0441\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u0447\u0435\u0441\u0442\u0432\u043e)", s):
                continue
            if re.search(r"^(\u0447\u0438\u0442\u0430\u0439\u0442\u0435|\u0441\u043c\u043e\u0442\u0440\u0438\u0442\u0435|\u0431\u043e\u043b\u044c\u0448\u0435|\u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a|via|source)", s):
                continue
            line = re.sub(r'https?://\\S+', '', line).strip()
            if line: clean.append(line)
        result = re.sub(r"\\n{3,}", "\\n\\n", "\\n".join(clean)).strip()
        return result

    def _inject_cpa(self, text, post_counter, cpa_links, cpa_every):
        if not cpa_links: return text
        if post_counter > 0 and post_counter % cpa_every == 0:
            text += f"\\n\\n{random.choice(cpa_links).strip()}"
        return text

    def publish(self, text, chat_id, post_counter=0, cpa_links=None, cpa_every=3, media_path=None):
        if not self.bot_token: print("[Publisher] No bot token!"); return False
        text = self._clean_footers(text)
        text = self._inject_cpa(text, post_counter, cpa_links or [], cpa_every)
        if media_path and len(text) > 1024:
            print("[Publisher] Text too long for photo caption, skipping image")
            media_path = None
        try:
            if media_path:
                with open(media_path, 'rb') as p:
                    r = requests.post(f"https://api.telegram.org/bot{self.bot_token}/sendPhoto",
                        data={"chat_id": chat_id, "caption": text, "parse_mode": "HTML"},
                        files={"photo": p}, timeout=30)
            else:
                r = requests.post(f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                    json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                          "disable_web_page_preview": False}, timeout=15)
            r.raise_for_status()
            print(f"[Publisher] OK{{' (with image)' if media_path else ''}}")
            return True
        except Exception as e:
            print(f"[Publisher] Failed: {e}"); return False
'''

FILES["core/filter/filters.py"] = '''import sqlite3

class PostFilter:
    AD_KEYWORDS = ["\u0440\u0435\u0442\u0432\u0438\u0442", "retweet", "\u0440\u0435\u043f\u043e\u0441\u0442", "repost",
        "\u0434\u0435\u0441\u0430\u043d\u0442", "\u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0430 \u0434\u0435\u0441\u0430\u043d\u0442",
        "\u043d\u0438\u043a\u043e\u0433\u0434\u0430 \u043d\u0435 \u043f\u043b\u0430\u0442\u0438\u0442\u0435", "never pay",
        "\u043f\u0440\u0435\u0434\u043f\u0440\u043e\u0434\u0430\u0436", "presale", "\u0437\u0430\u043a\u0440\u0435\u043f\u043b\u0435\u043d", "pinned",
        "\u0432\u044b\u043f\u043e\u043b\u043d\u044f\u0439 \u0437\u0430\u0434\u0430\u0447\u0438", "complete tasks",
        "fragment.com", "\u043b\u043e\u0433\u0438\u043d \u043d\u0430 \u043f\u0440\u043e\u0434\u0430\u0436\u0443", "username",
        "\u0444\u0440\u0430\u0433\u043c\u0435\u043d\u0442", "\u0430\u0443\u043a\u0446\u0438\u043e\u043d", "prime",
        "\u043c\u044b \u0432 ", "\u0431\u043e\u043b\u044c\u0448\u0435 \u0432 ", "\u043d\u0430\u0448 \u0442\u0435\u043b\u0435\u0433\u0440\u0430\u043c", "\u043d\u0430\u0448 \u043a\u0430\u043d\u0430\u043b",
        "\u043f\u043e\u0434\u043f\u0438\u0448\u0438\u0441\u044c \u043d\u0430", "\u043f\u0440\u0438\u0441\u043e\u0435\u0434\u0438\u043d\u044f\u0439\u0441\u044f", "vk.com", "\u0432\u043a\u043e\u043d\u0442\u0430\u043a\u0442\u0435"]

    EXTERNAL_SOURCE_PATTERNS = ["\u0447\u0438\u0442\u0430\u0439\u0442\u0435 \u043d\u0430", "\u0447\u0438\u0442\u0430\u0439\u0442\u0435 \u0432",
        "\u043f\u043e\u0434\u0440\u043e\u0431\u043d\u0435\u0435 \u043d\u0430", "\u043f\u043e\u0434\u0440\u043e\u0431\u043d\u0435\u0435 \u0432",
        "\u043d\u0430 \u0441\u0430\u0439\u0442\u0435", "\u043d\u0430 \u043d\u0430\u0448\u0435\u043c \u0441\u0430\u0439\u0442\u0435",
        "\u0441\u0442\u0430\u0442\u044c\u044f \u043d\u0430", "\u0441\u0442\u0430\u0442\u044c\u044f \u043e\u043f\u0443\u0431\u043b\u0438\u043a\u043e\u0432\u0430\u043d\u0430",
        "\u043c\u0430\u0442\u0435\u0440\u0438\u0430\u043b \u043d\u0430", "\u043c\u0430\u0442\u0435\u0440\u0438\u0430\u043b \u043e\u043f\u0443\u0431\u043b\u0438\u043a\u043e\u0432\u0430\u043d",
        "\u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a:", "\u043f\u043e \u0441\u0441\u044b\u043b\u043a\u0435", "\u043f\u0435\u0440\u0435\u0445\u043e\u0434\u0438\u0442\u0435 \u043f\u043e",
        "\u0432\u0441\u0435 \u043f\u043e\u0434\u0440\u043e\u0431\u043d\u043e\u0441\u0442\u0438 \u043d\u0430",
        "\u0434\u0430\u0439\u0434\u0436\u0435\u0441\u0442", "\u0441\u0430\u043c\u044b\u0435 \u044f\u0440\u043a\u0438\u0435",
        "\u043f\u0435\u0440\u0435\u0441\u044b\u043b\u0430\u0435\u043c\u044b\u0435 \u043f\u043e\u0441\u0442\u044b",
        "\u043b\u0438\u0441\u0442\u0430\u0439\u0442\u0435, \u0435\u0441\u043b\u0438", "\u0437\u0430 \u043d\u0435\u0434\u0435\u043b\u044e"]

    def __init__(self, db):
        self.db = db

    def _is_ad(self, text):
        t = text.lower()
        return sum(1 for kw in self.AD_KEYWORDS if kw in t) >= 2

    def _is_external_source(self, text):
        t = text.lower()
        return any(p in t for p in self.EXTERNAL_SOURCE_PATTERNS)

    def _is_duplicate(self, text):
        return self.db.content_exists(text)

    def update_engagement_scores(self):
        with sqlite3.connect(self.db.db_path) as conn:
            rows = conn.execute("SELECT id, views, reactions_count FROM posts WHERE published = 0").fetchall()
        for pid, v, r in rows:
            score = (r / v * 100) if r > 0 and v > 0 else min(v / 10, 100)
            with sqlite3.connect(self.db.db_path) as conn:
                conn.execute("UPDATE posts SET engagement_score = ? WHERE id = ?", (round(score, 4), pid))

    def get_top_posts(self, limit=5, min_length=50):
        self.update_engagement_scores()
        posts = self.db.get_unpublished_posts(limit=limit * 5)
        clean = []
        for p in posts:
            if len(clean) >= limit: break
            text = p[1] or ""
            if len(text) < min_length:
                self.db.mark_skipped(p[0]); print(f"[Filter] Too short (post #{p[0]})"); continue
            if self._is_ad(text):
                self.db.mark_skipped(p[0]); print(f"[Filter] Ad blocked (post #{p[0]})"); continue
            if self._is_external_source(text):
                self.db.mark_skipped(p[0]); print(f"[Filter] External source blocked (post #{p[0]})"); continue
            if self._is_duplicate(text):
                self.db.mark_skipped(p[0]); print(f"[Filter] Duplicate content blocked (post #{p[0]})"); continue
            clean.append(p)
        return clean
'''

FILES["core/run_channel.py"] = '''import os, sys, time, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import load_channel_config
from core.db.database import Database
from core.parser.web_parser import WebParser
from core.filter.filters import PostFilter
from core.translator.translator import Translator
from core.publisher.publisher import Publisher

def run_channel(env_path, once=False):
    env_path = os.path.abspath(env_path)
    channel_dir = os.path.dirname(env_path)
    os.chdir(channel_dir)
    cfg = load_channel_config(env_path)
    name = os.path.basename(channel_dir)
    print(f"[{name}] Starting channel...")
    db = Database()
    pf = PostFilter(db)
    tr = Translator(cfg)
    pub = Publisher()
    pub.set_token(cfg["BOT_TOKEN"])
    print(f"[{name}] Parsing {len(cfg['SOURCE_CHANNELS'])} donors...")
    WebParser(db).parse_all(cfg["SOURCE_CHANNELS"], limit_per_channel=20)
    print(f"[{name}] Selecting posts...")
    top = pf.get_top_posts(limit=cfg["POSTS_PER_CYCLE"])
    if not top: print(f"[{name}] No new posts"); return 0
    for i, post in enumerate(top, 1):
        pid, text, hm, mp, score, iu = post
        print(f"[{name}] Translating #{pid}...")
        t = tr.translate(text)
        print(f"[{name}] Publishing #{pid}...")
        ok = pub.publish(text=t, chat_id=cfg["TARGET_CHANNEL"], post_counter=i, cpa_links=cfg["CPA_LINKS"], cpa_every=cfg["CPA_INSERT_EVERY"], media_path=mp)
        if ok: db.mark_published(pid)
    s = db.get_stats()
    print(f"[{name}] Stats: {s}")
    return s["published"]

if __name__ == "__main__":
    if len(sys.argv) < 2: print("Usage: python core/run_channel.py channels/crypto/.env [--once]"); sys.exit(1)
    env_path = sys.argv[1]
    once = "--once" in sys.argv
    if once: run_channel(env_path, once=True)
    else:
        cfg = load_channel_config(env_path)
        interval = cfg["PUBLISH_INTERVAL_HOURS"] * 3600
        print(f"Loop every {cfg['PUBLISH_INTERVAL_HOURS']}h")
        while True:
            try: run_channel(env_path, once=True)
            except Exception as e:
                print(f"[ERROR] {e}"); traceback.print_exc()
            print(f"Sleeping {interval}s..."); time.sleep(interval)
'''

def main():
    for path, content in FILES.items():
        full = os.path.join(BASE, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  Created {path}")
    print(f"\\nAll files created in {BASE}")

if __name__ == "__main__":
    main()
