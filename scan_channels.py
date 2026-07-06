from telethon.sync import TelegramClient
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
PHONE = os.getenv("TELEGRAM_PHONE", "")

DB_PATH = "quick_scan.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        title TEXT,
        subscribers INTEGER DEFAULT 0,
        avg_views INTEGER DEFAULT 0,
        avg_reactions INTEGER DEFAULT 0,
        engagement REAL DEFAULT 0,
        scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    return conn


def scan_channel(client, username):
    try:
        entity = client.get_entity(username)
        title = entity.title

        messages = client.get_messages(entity, limit=30)
        if not messages:
            return None

        total_views = 0
        total_reactions = 0
        count = 0

        for m in messages:
            if not hasattr(m, "views") or m.views is None:
                continue
            views = m.views or 0
            reactions = 0
            if m.reactions and m.reactions.results:
                reactions = sum(r.count for r in m.reactions.results if r.count)
            total_views += views
            total_reactions += reactions
            count += 1

        if count == 0:
            return None

        avg_views = total_views // count
        avg_reactions = total_reactions // count
        engagement = round((total_reactions / total_views) * 100, 2) if total_views > 0 else 0

        return {
            "username": username,
            "title": title,
            "avg_views": avg_views,
            "avg_reactions": avg_reactions,
            "engagement": engagement,
        }
    except Exception as e:
        print(f"  ✗ Error scanning {username}: {e}")
        return None


def main():
    print("=" * 60)
    print("TELEGRAM CHANNEL SCANNER — быстрая разведка доноров")
    print("=" * 60)

    if not API_ID or API_ID == 0:
        print("✗ TELEGRAM_API_ID не задан. Настрой .env файл.")
        return

    if not PHONE:
        print("✗ TELEGRAM_PHONE не задан.")
        return

    channels_input = input("\nВведите username'ы каналов через запятую (например @crypto, @tech):\n> ")
    usernames = [ch.strip() for ch in channels_input.split(",") if ch.strip()]

    if not usernames:
        print("Нет каналов для сканирования.")
        return

    conn = init_db()

    print("\nПодключаюсь к Telegram...")
    client = TelegramClient("scanner_session", API_ID, API_HASH)
    client.start(phone=PHONE)

    print("Начинаю сканирование...\n")

    for username in usernames:
        print(f"  → Сканирую {username}...")
        result = scan_channel(client, username)
        if result:
            conn.execute(
                """INSERT OR REPLACE INTO channels
                (username, title, avg_views, avg_reactions, engagement)
                VALUES (?, ?, ?, ?, ?)""",
                (result["username"], result["title"], result["avg_views"], result["avg_reactions"], result["engagement"]),
            )
            conn.commit()
            print(f"    ✓ {result['title']}")
            print(f"      Avg views: {result['avg_views']}, Reactions: {result['avg_reactions']}, ER: {result['engagement']}%")
        print()

    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ")
    print("=" * 60)
    rows = conn.execute(
        "SELECT username, title, avg_views, avg_reactions, engagement FROM channels ORDER BY engagement DESC"
    ).fetchall()

    print(f"{'Username':<25} {'Title':<30} {'Views':<10} {'Reactions':<10} {'ER%':<8}")
    print("-" * 83)
    for r in rows:
        print(f"{r[0]:<25} {r[1][:28]:<30} {r[2]:<10} {r[3]:<10} {r[4]:<8}")

    conn.close()
    client.disconnect()

    print("\nГотово. База сохранена в quick_scan.db")


if __name__ == "__main__":
    main()
