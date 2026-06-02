#!/usr/bin/env python3
"""
Scheduler — главный планировщик фермы.
Запускает все каналы по их расписанию.
Каждый канал исполняется в отдельном процессе.

Использование: python scheduler.py
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

FARM_DIR = Path(__file__).parent
CHANNELS_DIR = FARM_DIR / "channels"
CORE = FARM_DIR / "core"


def load_channel_config(channel_name):
    env_path = CHANNELS_DIR / channel_name / ".env"
    if not env_path.exists():
        return None

    from dotenv import load_dotenv
    load_dotenv(str(env_path))

    return {
        "PUBLISH_INTERVAL_HOURS": float(os.getenv("PUBLISH_INTERVAL_HOURS", "3")),
        "TARGET_CHANNEL": os.getenv("TARGET_CHANNEL", ""),
    }


def get_channels():
    channels = []
    for d in CHANNELS_DIR.iterdir():
        if d.is_dir() and (d / ".env").exists() and d.name != "template":
            channels.append(d.name)
    return sorted(channels)


def run_channel(channel_name):
    env_path = str(CHANNELS_DIR / channel_name / ".env")
    log_path = str(CHANNELS_DIR / channel_name / "bot.log")
    with open(log_path, "a") as log:
        subprocess.run(
            [sys.executable, "-u", str(CORE / "run_channel.py"), env_path, "--once"],
            stdout=log, stderr=log,
            cwd=CHANNELS_DIR / channel_name,
            timeout=300,
        )


def main():
    print("=" * 50)
    print("TG FARM SCHEDULER — запущен")
    print("=" * 50)

    channels = get_channels()
    if not channels:
        print("Нет каналов. Создай: python manage.py add <name>")
        return

    print(f"Каналов: {len(channels)}")
    for ch in channels:
        cfg = load_channel_config(ch)
        interval = cfg["PUBLISH_INTERVAL_HOURS"] if cfg else "?"
        print(f"  • {ch} (каждые {interval}ч)")
    print()

    last_run = {ch: 0 for ch in channels}

    while True:
        now = time.time()
        for ch in channels:
            cfg = load_channel_config(ch)
            if not cfg:
                continue

            interval = cfg["PUBLISH_INTERVAL_HOURS"] * 3600
            if now - last_run[ch] >= interval:
                print(f"[{now:.0f}] Запуск {ch}...")
                try:
                    run_channel(ch)
                except Exception as e:
                    print(f"[{ch}] Ошибка: {e}")
                last_run[ch] = now

        time.sleep(30)


if __name__ == "__main__":
    main()
