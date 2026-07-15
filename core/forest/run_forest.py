"""
Симфония Леса — VK-only channel.
Parses r/Forest via RSS, translates to Russian, posts to VK wall.

Usage:
    python core/forest/run_forest.py channels/forest/.env
"""
import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.vk_common import run_cycle  # noqa: E402

MEDIA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media")


async def main(env_path: str):
    await run_cycle(env_path, name="Forest",
                    format_post=lambda title: f"\U0001f332 {title}",
                    media_dir=MEDIA_DIR,
                    default_subreddit="Forest", enable_translate=True,
                    skip_without_media=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    env_path = os.path.abspath(sys.argv[1])
    asyncio.run(main(env_path))
