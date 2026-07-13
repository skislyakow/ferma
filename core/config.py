from dotenv import dotenv_values
import os


def load_channel_config(env_path: str | None = None):
    if env_path and os.path.exists(env_path):
        env = dotenv_values(env_path)
    else:
        env = dotenv_values()

    return {
        "API_ID": int(env.get("TELEGRAM_API_ID") or "0"),
        "API_HASH": env.get("TELEGRAM_API_HASH") or "",
        "PHONE": env.get("TELEGRAM_PHONE") or "",
        "YC_TRANSLATE_API_KEY": env.get("YC_TRANSLATE_API_KEY") or "",
        "YC_FOLDER_ID": env.get("YC_FOLDER_ID") or "",
        "BOT_TOKEN": env.get("BOT_TOKEN") or "",
        "SOURCE_CHANNELS": [x.strip() for x in (env.get("SOURCE_CHANNELS") or "").split(",") if x.strip()],
        "TARGET_CHANNEL": env.get("TARGET_CHANNEL") or "",
        "PUBLISH_INTERVAL_HOURS": float(env.get("PUBLISH_INTERVAL_HOURS") or "3"),
        "POSTS_PER_CYCLE": int(env.get("POSTS_PER_CYCLE") or "2"),
        "SOURCE_LANG": env.get("SOURCE_LANG") or "en",
        "TARGET_LANG": env.get("TARGET_LANG") or "ru",
        "CPA_LINKS": [x.strip() for x in (env.get("CPA_LINKS") or "").split(",") if x.strip()],
        "CPA_INSERT_EVERY": int(env.get("CPA_INSERT_EVERY") or "3"),
        "REQUIRE_MEDIA": (env.get("REQUIRE_MEDIA") or "").lower() in ("1", "true", "yes"),
        "REDDIT_INTERVAL": env.get("REDDIT_INTERVAL") or "300",
        "VK_TOKEN": env.get("VK_TOKEN") or "",
        "VK_GROUP_ID": env.get("VK_GROUP_ID") or "",
    }
