import sqlite3

from core.db.database import Database
from core.filter.manage import load_filters


class PostFilter:
    def __init__(self, db: Database):
        self.db = db

    def _reload(self):
        f = load_filters()
        self.AD_KEYWORDS = f.get("ad_keywords", [])
        self.EXTERNAL_SOURCE_PATTERNS = f.get("external_source_patterns", [])
        self.TEASER_PATTERNS = f.get("teaser_patterns", [])

    def _is_ad(self, text: str) -> bool:
        t = text.lower()
        return sum(1 for kw in self.AD_KEYWORDS if kw in t) >= 2

    def _is_external_source(self, text: str) -> bool:
        t = text.lower()
        return any(p in t for p in self.EXTERNAL_SOURCE_PATTERNS)

    def _is_teaser(self, text: str) -> bool:
        t = text.lower()
        return any(p in t for p in self.TEASER_PATTERNS)

    def _is_duplicate(self, text: str) -> bool:
        return self.db.content_exists(text)

    def update_engagement_scores(self):
        with sqlite3.connect(self.db.db_path) as conn:
            rows = conn.execute(
                "SELECT id, views, reactions_count FROM posts WHERE published = 0"
            ).fetchall()

        for post_id, views, reactions in rows:
            if reactions > 0 and views > 0:
                score = (reactions / views) * 100
            else:
                score = min(views / 10, 100)
            with sqlite3.connect(self.db.db_path) as conn:
                conn.execute(
                    "UPDATE posts SET engagement_score = ? WHERE id = ?",
                    (round(score, 4), post_id),
                )

    def get_top_posts(self, limit: int = 5, min_length: int = 50):
        self._reload()
        self.update_engagement_scores()
        posts = self.db.get_unpublished_posts(limit=limit * 5)
        clean = []
        for p in posts:
            if len(clean) >= limit:
                break
            text = p[1] or ""
            if len(text) < min_length:
                self.db.mark_skipped(p[0])
                print(f"[Filter] Too short (post #{p[0]})")
                continue
            if self._is_ad(text):
                self.db.mark_skipped(p[0])
                print(f"[Filter] Ad blocked (post #{p[0]})")
                continue
            if self._is_external_source(text):
                self.db.mark_skipped(p[0])
                print(f"[Filter] External source blocked (post #{p[0]})")
                continue
            if self._is_teaser(text):
                self.db.mark_skipped(p[0])
                print(f"[Filter] Teaser blocked (post #{p[0]})")
                continue
            if self._is_duplicate(text):
                self.db.mark_skipped(p[0])
                print(f"[Filter] Duplicate content blocked (post #{p[0]})")
                continue
            clean.append(p)
        return clean
