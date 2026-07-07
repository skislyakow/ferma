import os
import json
import requests
import sqlite3
from datetime import datetime


class FarmAnalytics:
    def __init__(self):
        self.channels_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "channels",
        )

    def _bot_api(self, token: str, method: str, params: dict | None = None):
        url = f"https://api.telegram.org/bot{token}/{method}"
        try:
            r = requests.get(url, params=params, timeout=10)
            return r.json()
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _resolve_channel_name(self, token: str, username: str) -> str:
        r = self._bot_api(token, "getChat", {"chat_id": f"@{username}"})
        if r.get("ok"):
            return r["result"].get("title", username)
        return username

    def _parse_channel_list(self, raw: str) -> list[str]:
        return [x.strip().lstrip("@") for x in raw.split(",") if x.strip()]

    def _vk_api(self, token: str, method: str, params: dict | None = None):
        url = f"https://api.vk.com/method/{method}"
        try:
            r = requests.get(
                url,
                params={**(params or {}), "access_token": token, "v": "5.199"},
                timeout=10,
            )
            return r.json()
        except Exception:
            return {"error": "request failed"}

    def _read_vk_log(self, name: str, limit: int = 10) -> list:
        log_path = os.path.join(self.channels_dir, name, "logs", f"{name}.log")
        if not os.path.exists(log_path):
            return []
        posts = []
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if "Posted" in line or "Failed to post" in line:
                        posts.append(line.strip())
        except Exception:
            pass
        return posts[-limit:]

    def channel_stats(self, name: str) -> dict:
        env_path = os.path.join(self.channels_dir, name, ".env")
        db_path = os.path.join(self.channels_dir, name, "posts.db")
        if not os.path.exists(env_path):
            return {"error": "no .env"}

        from dotenv import dotenv_values

        cfg = dotenv_values(env_path)
        token = cfg.get("BOT_TOKEN", "")
        target = cfg.get("TARGET_CHANNEL", "").lstrip("@")
        chan_type = cfg.get("CHANNEL_TYPE", "normal")
        vk_token = cfg.get("VK_TOKEN", "")
        vk_group_id = cfg.get("VK_GROUP_ID", "")

        is_vk_only = bool(vk_token and vk_group_id and not token)
        if is_vk_only:
            chan_type = "vk"

        source_channels_raw = self._parse_channel_list(
            cfg.get("SOURCE_CHANNELS", "")
        )
        rss_feeds = [
            x.strip() for x in cfg.get("RSS_FEEDS", "").split(",") if x.strip()
        ]
        ru_sources_raw = self._parse_channel_list(
            cfg.get("RU_SOURCE_CHANNELS", "")
        )
        reddit_subreddits = [
            x.strip()
            for x in cfg.get("REDDIT_SUBREDDITS", "").split(",")
            if x.strip()
        ]
        if not reddit_subreddits:
            single = cfg.get("REDDIT_SUBREDDIT", "").strip()
            if single:
                reddit_subreddits = [single]

        source_channels: list[dict[str, str]] = []
        for ch in source_channels_raw:
            if token:
                name_resolved = self._resolve_channel_name(token, ch)
            else:
                name_resolved = ch
            source_channels.append({"username": ch, "title": name_resolved})

        ru_source_channels: list[dict[str, str]] = []
        for ch in ru_sources_raw:
            if token:
                name_resolved = self._resolve_channel_name(token, ch)
            else:
                name_resolved = ch
            ru_source_channels.append({"username": ch, "title": name_resolved})

        result = {
            "name": name,
            "target": target or f"VK {vk_group_id}",
            "type": chan_type,
            "donors": len(source_channels)
            + len(rss_feeds)
            + len(reddit_subreddits),
            "source_channels": source_channels,
            "rss_feeds": rss_feeds,
            "ru_source_channels": ru_source_channels,
            "reddit_subreddits": reddit_subreddits,
            "subscribers": 0,
            "last_posts": [],
            "vk_posts": [],
            "db": {"total": 0, "published": 0, "skipped": 0, "video": 0},
            "running": False,
        }

        if is_vk_only:
            r = self._vk_api(
                vk_token,
                "groups.getById",
                {"group_id": vk_group_id, "fields": "members_count"},
            )
            if "response" in r and r["response"].get("groups"):
                result["subscribers"] = r["response"]["groups"][0].get(  # type: ignore[index]
                    "members_count", 0
                )  # type: ignore

            published_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "core",
                name,
                "published.json",
            )
            if os.path.exists(published_path):
                try:
                    with open(published_path) as f:
                        published_ids = json.load(f)
                    result["db"]["total"] = len(published_ids)
                    result["db"]["published"] = len(published_ids)
                except Exception:
                    pass

            vk_log = self._read_vk_log(name, 10)
            result["vk_posts"] = []
            for line in vk_log:
                if "Posted" in line:
                    tag = (
                        "photo"
                        if "(photo)" in line
                        else "video"
                        if "(video)" in line
                        else "text"
                    )
                    title = (
                        line.split("...", 1)[0].split("): ", 1)[-1]
                        if "): " in line
                        else line
                    )
                    result["vk_posts"].append(
                        {"type": tag, "title": title, "ok": True}
                    )
                elif "Failed" in line:
                    err = (
                        line.split("VK API error ", 1)[-1]
                        if "VK API error" in line
                        else line
                    )
                    result["vk_posts"].append(
                        {"type": "error", "title": err, "ok": False}
                    )
        else:
            if token:
                r = self._bot_api(
                    token, "getChatMembersCount", {"chat_id": f"@{target}"}
                )
                if r.get("ok"):
                    result["subscribers"] = r["result"]

                r = self._bot_api(token, "getUpdates", {"timeout": 0})
                if r.get("ok") and r.get("result"):
                    posts: list[dict] = []
                    for update in reversed(r["result"]):
                        msg = update.get("channel_post") or update.get(
                            "message", {}
                        )
                        if (
                            msg.get("chat", {}).get("username", "").lower()
                            == target.lower()
                        ):
                            posts.append(
                                {
                                    "id": msg["message_id"],
                                    "date": datetime.fromtimestamp(
                                        msg["date"]
                                    ).isoformat(),
                                    "views": msg.get("views", 0),
                                    "reactions": len(
                                        msg.get("reactions", {}).get(
                                            "results", []
                                        )
                                    )
                                    if msg.get("reactions")
                                    else 0,
                                }
                            )
                    result["last_posts"] = posts[-5:] if posts else []

            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                result["db"]["total"] = conn.execute(
                    "SELECT COUNT(*) FROM posts"
                ).fetchone()[0]
                result["db"]["published"] = conn.execute(
                    "SELECT COUNT(*) FROM posts WHERE published = 1"
                ).fetchone()[0]
                result["db"]["skipped"] = conn.execute(
                    "SELECT COUNT(*) FROM posts WHERE published = -1"
                ).fetchone()[0]
                try:
                    result["db"]["video"] = conn.execute(
                        "SELECT COUNT(*) FROM posts WHERE media_type = 'video'"
                    ).fetchone()[0]
                except sqlite3.OperationalError:
                    result["db"]["video"] = 0
                conn.close()

        return result

    def farm_status(self) -> list[dict]:
        results: list[dict] = []
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
            print(
                f"  БД: {s['db']['total']} всего | {s['db']['published']} опубл | {s['db']['skipped']} пропущ | {s['db']['video']} видео"
            )
            if s["last_posts"]:
                print("  Последние посты:")
                for p in s["last_posts"][-3:]:
                    print(
                        f"    #{p['id']} | {p['date']} | views:{p['views']} | reactions:{p['reactions']}"
                    )
        print("\n" + "=" * 60)


if __name__ == "__main__":
    FarmAnalytics().print_status()
