import sys
sys.path.insert(0, ".")
from core.config import load_channel_config

for name in ["crypto", "fashion"]:
    cfg = load_channel_config(f"channels/{name}/.env")
    print(f"{name}: {cfg['TARGET_CHANNEL']} | donors: {len(cfg['SOURCE_CHANNELS'])} | interval: {cfg['PUBLISH_INTERVAL_HOURS']}h | posts/cycle: {cfg['POSTS_PER_CYCLE']}")
