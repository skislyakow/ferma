"""
VK-only Reddit RSS channel for Interesting.
Parses subreddits via RSS, translates to Russian, posts photos/videos to VK wall.

Usage:
    python core/interesting/run_interesting.py channels/<name>/.env
"""
import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import dotenv_values
from core.vk_common import run_cycle

MEDIA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media")


async def main(env_path: str):
    env = dotenv_values(env_path)
    channel_name = env.get("CHANNEL_NAME", "\u0418\u043d\u0442\u0435\u0440\u0435\u0441\u043d\u043e!")
    await run_cycle(env_path, name=channel_name,
                    format_post=lambda title: f"\U0001f525 {title}",
                    media_dir=MEDIA_DIR,
                    default_subreddit="interesting", enable_translate=True,
                    skip_without_media=True, interval_default=3600)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    env_path = os.path.abspath(sys.argv[1])
    asyncio.run(main(env_path))
