import os
import requests
import sqlite3
from datetime import datetime


class FarmAnalytics:
    def __init__(self):
        self.channels_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "channels")

    def _bot_api(self, token: str, method: str, params: dict = None):
        url = f"https://api.telegram.org/bot{token}/{method}"
        try:
            r = requests.get(url, params=params, timeout=10)
            return r.json()
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def channel_stats(self, name: str) -> dict:
        env_path = os.path.join(self.channels_dir, name, ".env")
        db_path = os.path.join(self.channels_dir, name, "posts.db")
        if not os.path.exists(env_path):
            return {"error": "no .env"}

        from dotenv import dotenv_values
        cfg = dotenv_values(env_path)
        token = cfg.get("BOT_TOKEN", "")
        target = cfg.get("TARGET_CHANNEL", "").lstrip("@")
        donors = cfg.get("SOURCE_CHANNELS", "").split(",")
        chan_type = cfg.get("CHANNEL_TYPE", "normal")
        rss_feeds = [x.strip() for x in cfg.get("RSS_FEEDS", "").split(",") if x.strip()]

        result = {
            "name": name,
            "target": target,
            "type": chan_type,
            "donors": len([d for d in donors if d.strip()]),
            "rss_feeds": rss_feeds,
            "subscribers": 0,
            "last_posts": [],
            "db": {"total": 0, "published": 0, "skipped": 0, "video": 0},
            "running": False,
        }

        # Subscribers
        r = self._bot_api(token, "getChatMembersCount", {"chat_id": f"@{target}"})
        if r.get("ok"):
            result["subscribers"] = r["result"]

        # Last 5 posts in channel
        r = self._bot_api(token, "getUpdates", {"timeout": 0})
        if r.get("ok") and r.get("result"):
            posts = []
            for update in reversed(r["result"]):
                msg = update.get("channel_post") or update.get("message", {})
                if msg.get("chat", {}).get("username", "").lower() == target.lower():
                    posts.append({
                        "id": msg["message_id"],
                        "date": datetime.fromtimestamp(msg["date"]).isoformat(),
                        "views": msg.get("views", 0),
                        "reactions": len(msg.get("reactions", {}).get("results", [])) if msg.get("reactions") else 0,
                    })
            result["last_posts"] = posts[-5:] if posts else []

        # DB stats
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            result["db"]["total"] = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            result["db"]["published"] = conn.execute("SELECT COUNT(*) FROM posts WHERE published = 1").fetchone()[0]
            result["db"]["skipped"] = conn.execute("SELECT COUNT(*) FROM posts WHERE published = -1").fetchone()[0]
            try:
                result["db"]["video"] = conn.execute("SELECT COUNT(*) FROM posts WHERE media_type = 'video'").fetchone()[0]
            except sqlite3.OperationalError:
                result["db"]["video"] = 0
            conn.close()

        return result

    def farm_status(self) -> list[dict]:
        results = []
        for entry in os.listdir(self.channels_dir):
            env_path = os.path.join(self.channels_dir, entry, ".env")
            if os.path.isfile(env_path):
                results.append(self.channel_stats(entry))
        return results

    def print_status(self):
        statuses = self.farm_status()
        print("=" * 60)
        print(f"FARM STATUS — {datetime.now().isoformat()}")
        print("=" * 60)
        for s in statuses:
            if "error" in s:
                print(f"\n[!] {s['name']}: {s['error']}")
                continue
            print(f"\n[{s['name'].upper()}] @{s['target']}")
            print(f"  Подписчиков: {s['subscribers']}")
            print(f"  Доноров: {s['donors']}")
            print(f"  БД: {s['db']['total']} всего | {s['db']['published']} опубл | {s['db']['skipped']} пропущ | {s['db']['video']} видео")
            if s["last_posts"]:
                print(f"  Последние посты:")
                for p in s["last_posts"][-3:]:
                    print(f"    #{p['id']} | {p['date']} | views:{p['views']} | reactions:{p['reactions']}")
        print("\n" + "=" * 60)


if __name__ == "__main__":
    FarmAnalytics().print_status()
