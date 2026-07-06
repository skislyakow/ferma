from dotenv import dotenv_values
import os


def load_channel_config(env_path: str | None = None):
    if env_path and os.path.exists(env_path):
        env = dotenv_values(env_path)
    else:
        env = dotenv_values()

    return {
        "API_ID": int(env.get("TELEGRAM_API_ID", "0")),
        "API_HASH": env.get("TELEGRAM_API_HASH", ""),
        "PHONE": env.get("TELEGRAM_PHONE", ""),
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
        "REQUIRE_MEDIA": env.get("REQUIRE_MEDIA", "").lower() in ("1", "true", "yes"),
        "REDDIT_INTERVAL": env.get("REDDIT_INTERVAL", "300"),
        "VK_TOKEN": env.get("VK_TOKEN", ""),
        "VK_GROUP_ID": env.get("VK_GROUP_ID", ""),
    }
