import hashlib
import sqlite3
from datetime import datetime


class Database:
    def __init__(self, db_path="posts.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_channel TEXT,
                    source_message_id INTEGER,
                    text TEXT,
                    text_hash TEXT,
                    views INTEGER DEFAULT 0,
                    reactions_count INTEGER DEFAULT 0,
                    engagement_score REAL DEFAULT 0,
                    has_media INTEGER DEFAULT 0,
                    media_path TEXT,
                    image_url TEXT,
                    published INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    published_at TIMESTAMP,
                    UNIQUE(source_channel, source_message_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_posts_published
                ON posts(published)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_text_hash
                ON posts(text_hash)
            """)
            self._migrate()

    def _migrate(self):
        with sqlite3.connect(self.db_path) as conn:
            for col in ("text_hash", "media_type"):
                try:
                    conn.execute(f"ALTER TABLE posts ADD COLUMN {col} TEXT")
                except sqlite3.OperationalError:
                    pass

    @staticmethod
    def make_text_hash(text: str) -> str:
        if not text:
            return ""
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def content_exists(self, text: str) -> bool:
        if not text:
            return False
        h = self.make_text_hash(text)
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM posts WHERE text_hash = ? AND published = 1",
                (h,),
            ).fetchone()
            return row is not None

    def post_exists(self, source_channel, source_message_id):
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM posts WHERE source_channel = ? AND source_message_id = ?",
                (source_channel, source_message_id),
            ).fetchone()
            return row is not None

    def message_id_exists(self, source_message_id):
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM posts WHERE source_message_id = ?",
                (source_message_id,),
            ).fetchone()
            return row is not None

    def save_post(self, source_channel, source_message_id, text, views, reactions_count, has_media, media_path=None, image_url=None, media_type="photo", published=0):
        text_hash = self.make_text_hash(text)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR IGNORE INTO posts
                (source_channel, source_message_id, text, text_hash, views, reactions_count, has_media, media_path, image_url, media_type, published)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (source_channel, source_message_id, text, text_hash, views, reactions_count, int(has_media), media_path, image_url, media_type, published),
            )

    def get_unpublished_posts(self, limit=5):
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT id, text, has_media, media_path, engagement_score, image_url, media_type
                FROM posts
                WHERE published = 0 AND text IS NOT NULL AND text != ''
                ORDER BY source_message_id DESC
                LIMIT ?""",
                (limit,),
            ).fetchall()
            return rows

    def get_best_unpublished_post(self):
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """SELECT id, source_channel, text, has_media, media_path, image_url, media_type
                FROM posts
                WHERE published = 0 AND text IS NOT NULL AND text != ''
                ORDER BY views DESC, source_message_id DESC
                LIMIT 1""",
            ).fetchone()
            return row

    def mark_published(self, post_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE posts SET published = 1, published_at = ? WHERE id = ?",
                (datetime.now().isoformat(), post_id),
            )

    def mark_skipped(self, post_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE posts SET published = -1 WHERE id = ?", (post_id,))

    def get_stats(self):
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            published = conn.execute("SELECT COUNT(*) FROM posts WHERE published = 1").fetchone()[0]
            skipped = conn.execute("SELECT COUNT(*) FROM posts WHERE published = -1").fetchone()[0]
            return {"total": total, "published": published, "skipped": skipped}
