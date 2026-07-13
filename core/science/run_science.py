"""
Популярная Наука — VK-only channel.
Parses r/Popular_Science_Ru via RSS and posts to VK wall.

Usage:
    python core/science/run_science.py channels/science/.env
"""
import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import dotenv_values  # noqa: E402
from core.vk_common import run_cycle  # noqa: E402

MEDIA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media")


async def main(env_path: str):
    env = dotenv_values(env_path)
    channel_name = env.get("CHANNEL_NAME", "Science")
    await run_cycle(env_path, name=channel_name,
                    format_post=lambda title: f"\U0001f52c {title}",
                    media_dir=MEDIA_DIR,
                    default_subreddit="Popular_Science_Ru",
                    enable_translate=False, skip_without_media=False,
                    media_prefix="sci_")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    env_path = os.path.abspath(sys.argv[1])
    asyncio.run(main(env_path))
