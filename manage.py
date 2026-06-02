#!/usr/bin/env python3
"""
Telegram Farm Manager.
Управление фермой каналов: запуск, остановка, логи, добавление.

Использование:
  python manage.py list              — список каналов
  python manage.py start crypto      — запустить канал
  python manage.py stop crypto       — остановить
  python manage.py restart crypto    — перезапустить
  python manage.py run crypto        — запустить один цикл
  python manage.py logs crypto       — логи канала
  python manage.py add [name]        — создать новый канал из шаблона
  python manage.py stats             — статистика всех каналов
  python manage.py status            — статус процессов
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

FARM_DIR = Path(__file__).parent
CHANNELS_DIR = FARM_DIR / "channels"
TEMPLATE_DIR = CHANNELS_DIR / "template"
PID_FILE = FARM_DIR / "farm_pids.json"


def get_channels():
    channels = []
    for d in CHANNELS_DIR.iterdir():
        if d.is_dir() and (d / ".env").exists() and d.name != "template":
            channels.append(d.name)
    return sorted(channels)


def load_pids():
    if PID_FILE.exists():
        with open(PID_FILE) as f:
            return json.load(f)
    return {}


def save_pids(pids):
    with open(PID_FILE, "w") as f:
        json.dump(pids, f, indent=2)


def cmd_list():
    channels = get_channels()
    pids = load_pids()
    print(f"Каналы ({len(channels)}):")
    print(f"{'Название':<20} {'Статус':<15} {'PID':<8} {'env':<25}")
    print("-" * 68)
    for ch in channels:
        pid = pids.get(ch)
        if pid and pid_exists(pid):
            status = "[ON]"
        else:
            status = "[OFF]"
            pid = "-"
        env_file = f"channels/{ch}/.env"
        print(f"{ch:<20} {status:<15} {str(pid):<8} {env_file:<25}")


def cmd_start(name):
    if name not in get_channels():
        print(f"Канал '{name}' не найден")
        return
    pids = load_pids()
    if name in pids and pid_exists(pids[name]):
        print(f"Канал '{name}' уже работает (PID {pids[name]})")
        return

    env_path = str(CHANNELS_DIR / name / ".env")
    log_path = str(CHANNELS_DIR / name / "bot.log")
    with open(log_path, "a") as log:
        proc = subprocess.Popen(
            [sys.executable, "-u", str(FARM_DIR / "core" / "run_channel.py"), env_path],
            stdout=log, stderr=log,
            cwd=CHANNELS_DIR / name
        )
    pids[name] = proc.pid
    save_pids(pids)
    print(f"✅ Запущен '{name}' (PID {proc.pid})")


def cmd_stop(name):
    pids = load_pids()
    if name not in pids:
        print(f"Канал '{name}' не запущен")
        return
    pid = pids[name]
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"⏹ Остановлен '{name}' (PID {pid})")
    except ProcessLookupError:
        print(f"⚠ Процесс '{name}' не найден")
    if name in pids:
        del pids[name]
        save_pids(pids)


def cmd_run(name):
    if name not in get_channels():
        print(f"Канал '{name}' не найден")
        return
    env_path = str(CHANNELS_DIR / name / ".env")
    subprocess.run([sys.executable, str(FARM_DIR / "core" / "run_channel.py"), env_path, "--once"])


def cmd_logs(name):
    log_path = CHANNELS_DIR / name / "bot.log"
    if not log_path.exists():
        print("Логов нет")
        return
    with open(log_path) as f:
        lines = f.readlines()
    for line in lines[-30:]:
        print(line.rstrip())


def cmd_add(name=None):
    if not name:
        name = input("Имя нового канала: ").strip()
    if not name:
        print("Имя не может быть пустым")
        return
    target = CHANNELS_DIR / name
    if target.exists():
        print(f"Канал '{name}' уже существует")
        return
    shutil.copytree(TEMPLATE_DIR, target)
    (target / "posts.db").unlink(missing_ok=True)
    os.makedirs(target / "media", exist_ok=True)
    print(f"✅ Канал '{name}' создан. Настрой: channels/{name}/.env")


def cmd_stats():
    channels = get_channels()
    for ch in channels:
        db_path = CHANNELS_DIR / ch / "posts.db"
        if not db_path.exists():
            print(f"{ch}: БД не найдена")
            continue
        import sqlite3
        try:
            conn = sqlite3.connect(str(db_path))
            total = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            pub = conn.execute("SELECT COUNT(*) FROM posts WHERE published = 1").fetchone()[0]
            conn.close()
            print(f"{ch:<20} всего: {total:<5} опубликовано: {pub}")
        except:
            print(f"{ch}: ошибка БД")


def cmd_status():
    pids = load_pids()
    for ch in get_channels():
        pid = pids.get(ch)
        mark = "[ON]" if (pid and pid_exists(pid)) else "[OFF]"
        print(f"{mark} {ch}")


def pid_exists(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__.strip())
        sys.exit(0)

    command = args[0]
    arg = args[1] if len(args) > 1 else None

    commands = {
        "list": cmd_list,
        "start": lambda: cmd_start(arg) if arg else print("Укажи имя канала"),
        "stop": lambda: cmd_stop(arg) if arg else print("Укажи имя канала"),
        "restart": lambda: (cmd_stop(arg), time.sleep(1), cmd_start(arg)) if arg else print("Укажи имя канала"),
        "run": lambda: cmd_run(arg) if arg else print("Укажи имя канала"),
        "logs": lambda: cmd_logs(arg) if arg else print("Укажи имя канала"),
        "add": lambda: cmd_add(arg),
        "stats": cmd_stats,
        "status": cmd_status,
    }

    if command in commands:
        commands[command]()
    else:
        print(f"Неизвестная команда: {command}")
        print("Доступно: list, start, stop, restart, run, logs, add, stats, status")
