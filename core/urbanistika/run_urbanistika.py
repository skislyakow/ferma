"""
VK-only Reddit RSS channel.
Parses subreddits via RSS, translates to Russian, posts photos/videos to VK wall.

Usage:
    python core/urbanistika/run_urbanistika.py channels/<name>/.env
"""
import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import dotenv_values  # noqa: E402
from core.vk_common import run_cycle  # noqa: E402

MEDIA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media")


def _channel_icon(name):
    icons = {
        "Урбанистика": "🏙",
        "Интересно!": "🔥",
    }
    return icons.get(name, "🔥")


async def main(env_path: str):
    env = dotenv_values(env_path)
    channel_name = env.get("CHANNEL_NAME", "Канал")
    icon = _channel_icon(channel_name)
    format_post = lambda title: f"{icon} {title}"
    await run_cycle(env_path, name=channel_name, format_post=format_post,
                    media_dir=MEDIA_DIR,
                    default_subreddit="UrbanHell", enable_translate=True,
                    skip_without_media=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    env_path = os.path.abspath(sys.argv[1])
    asyncio.run(main(env_path))

