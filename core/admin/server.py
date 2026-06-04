import os
import sys
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import FastAPI, Query, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import uvicorn

from core.analytics import FarmAnalytics

AUTH_TOKEN = os.environ.get("ADMIN_TOKEN", "ferma2026")
FARM_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHANNELS_DIR = os.path.join(FARM_DIR, "channels")
PYTHON = os.path.join(FARM_DIR, "venv", "bin", "python")

app = FastAPI(title="Ferma Admin")

CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,system-ui,sans-serif; background:#0d1117; color:#c9d1d9; padding:20px; max-width:1200px; margin:0 auto; }
a { color:#58a6ff; text-decoration:none; }
a:hover { text-decoration:underline; }
h1 { margin-bottom:20px; font-size:24px; color:#f0f6fc; }
h2 { margin:20px 0 10px; font-size:18px; color:#f0f6fc; }
.card { background:#161b22; border:1px solid #30363d; border-radius:8px; padding:16px; margin-bottom:16px; }
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:16px; }
.stat { display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid #21262d; }
.stat:last-child { border:none; }
.label { color:#8b949e; }
.value { color:#f0f6fc; font-weight:600; }
pre { background:#0d1117; padding:12px; border-radius:6px; overflow-x:auto; font-size:12px; line-height:1.5; }
table { width:100%; border-collapse:collapse; }
th { text-align:left; padding:8px 12px; border-bottom:2px solid #30363d; color:#8b949e; font-size:12px; text-transform:uppercase; }
td { padding:8px 12px; border-bottom:1px solid #21262d; }
tr:hover { background:#1c2128; }
.nav { margin-bottom:20px; padding:10px 0; border-bottom:1px solid #30363d; display:flex; align-items:center; gap:16px; }
.nav a { margin-right:0; font-size:14px; }
.nav-right { margin-left:auto; }
.btn { display:inline-block; padding:6px 12px; border-radius:6px; font-size:13px; border:none; cursor:pointer; text-decoration:none; }
.btn-primary { background:#238636; color:#fff; }
.btn-primary:hover { background:#2ea043; }
.btn-danger { background:#da3633; color:#fff; }
.btn-danger:hover { background:#f85149; }
.btn-warning { background:#9e6a03; color:#fff; }
.btn-warning:hover { background:#bb8009; }
.btn-sm { padding:4px 8px; font-size:12px; }
input,select { width:100%; padding:8px 12px; background:#0d1117; border:1px solid #30363d; border-radius:6px; color:#c9d1d9; font-size:14px; margin-bottom:12px; }
input:focus { outline:none; border-color:#58a6ff; }
label { display:block; margin-bottom:4px; color:#8b949e; font-size:13px; text-transform:uppercase; letter-spacing:0.5px; }
.form-row { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
.form-group { margin-bottom:4px; }
.msg { padding:12px 16px; border-radius:6px; margin-bottom:16px; font-size:14px; }
.msg-success { background:#1b3d1f; border:1px solid #238636; color:#7ee787; }
.msg-error { background:#3d1b1b; border:1px solid #da3633; color:#f85149; }
form { max-width:600px; }
"""

def head(title, token):
    return f"""<!DOCTYPE html><html lang='ru'><head><meta charset='utf-8'><title>{title}</title><style>{CSS}</style></head><body>
<div class='nav'><a href='/?token={token}'>Панель</a><a href='/channels?token={token}'>Каналы</a><a href='/filters?token={token}'>Фильтры</a><a href='/add?token={token}'>+ Добавить канал</a></div>"""

def foot():
    return "</body></html>"

def check_auth(token):
    if token != AUTH_TOKEN:
        raise HTTPException(401, "Invalid token")

def screen_running(name: str) -> bool:
    r = subprocess.run(
        ["screen", "-ls", name],
        capture_output=True, text=True, timeout=5
    )
    return name in r.stdout

def get_bot_name(token: str) -> str:
    import requests
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        data = r.json()
        if data.get("ok"):
            return data["result"]["username"]
    except:
        pass
    return "?"


@app.get("/", response_class=HTMLResponse)
async def dashboard(token: str = Query(None), msg: str = None):
    check_auth(token)
    analytics = FarmAnalytics()
    statuses = analytics.farm_status()
    msg_html = ""
    if msg:
        cls = "msg-error" if msg.startswith("Ошибка") else "msg-success"
        msg_html = f"<div class='{cls}'>{msg}</div>"
    cards = ""
    for s in statuses:
        if "error" in s:
            cards += f"<div class='card'><h2>{s['name']}</h2><p>Ошибка: {s['error']}</p></div>"
            continue
        running = screen_running(s["name"])
        status_tag = "<span style='color:#3fb950'>● Работает</span>" if running else "<span style='color:#f85149'>● Остановлен</span>"
        cards += f"""
        <div class='card'>
            <h2 style='margin-top:0'><a href='/channel/{s['name']}?token={token}'>{s['name']}</a> <span style='float:right;font-size:13px;color:#8b949e'>@{s['target']}</span></h2>
            <div class='stat'><span class='label'>Статус</span><span class='value'>{status_tag}</span></div>
            <div class='stat'><span class='label'>Подписчики</span><span class='value'>{s['subscribers']}</span></div>
            <div class='stat'><span class='label'>Доноры</span><span class='value'>{s['donors']}</span></div>
            <div class='stat'><span class='label'>БД всего</span><span class='value'>{s['db']['total']}</span></div>
            <div class='stat'><span class='label'>Опубликовано</span><span class='value'>{s['db']['published']}</span></div>
            <div class='stat'><span class='label'>Пропущено</span><span class='value'>{s['db']['skipped']}</span></div>
            <div class='stat'><span class='label'>Видео</span><span class='value'>{s['db']['video']}</span></div>
            <p style='margin-top:10px'>
                <a href='/logs/{s['name']}?token={token}'>[логи]</a>
                <a href='/channel/{s['name']}?token={token}' class='btn btn-primary btn-sm'>Управление</a>
            </p>
        </div>"""
    body = f"<h1>Панель управления</h1>{msg_html}<div class='grid'>{cards}</div>"
    return head("Панель — Ferma", token) + body + foot()


@app.get("/add", response_class=HTMLResponse)
async def add_channel_form(token: str = Query(None)):
    check_auth(token)
    body = f"""
    <h1>Добавить канал</h1>
    <form action='/api/channel/create?token={token}' method='post'>
        <div class='form-group'><label>Название (папка)</label><input type='text' name='name' placeholder='например: tech' required></div>
        <div class='form-group'><label>BOT_TOKEN</label><input type='text' name='bot_token' placeholder='123456:ABC-DEF1234' required></div>
        <div class='form-group'><label>TARGET_CHANNEL</label><input type='text' name='target_channel' placeholder='@moy_kal' required></div>
        <div class='form-group'><label>Доноры (через запятую)</label><input type='text' name='source_channels' placeholder='@donor1,@donor2' required></div>
        <div class='form-row'>
            <div class='form-group'><label>Интервал (часы)</label><input type='number' name='publish_interval_hours' value='0.5' step='0.1'></div>
            <div class='form-group'><label>Постов за цикл</label><input type='number' name='posts_per_cycle' value='2'></div>
        </div>
        <div class='form-row'>
            <div class='form-group'><label>Язык источника</label><input type='text' name='source_lang' value='en'></div>
            <div class='form-group'><label>Язык перевода</label><input type='text' name='target_lang' value='ru'></div>
        </div>
        <div class='form-group'><label>CPA-ссылки (опционально, через запятую)</label><input type='text' name='cpa_links' placeholder='https://...'></div>
        <div class='form-row'>
            <div class='form-group'><label>CPA каждые N постов</label><input type='number' name='cpa_insert_every' value='3'></div>
            <div class='form-group'><label>Запустить после создания</label><input type='checkbox' name='start_now' value='1' style='width:auto;margin-top:8px' checked></div>
        </div>
        <p style='margin-top:16px'><button type='submit' class='btn btn-primary'>Создать</button> <a href='/?token={token}' class='btn btn-warning'>Отмена</a></p>
    </form>"""
    return head("Добавить канал — Ferma", token) + body + foot()


@app.post("/api/channel/create")
async def api_create_channel(
    token: str = Query(None),
    name: str = Form(...),
    bot_token: str = Form(...),
    target_channel: str = Form(...),
    source_channels: str = Form(...),
    publish_interval_hours: float = Form(0.5),
    posts_per_cycle: int = Form(2),
    source_lang: str = Form("en"),
    target_lang: str = Form("ru"),
    cpa_links: str = Form(""),
    cpa_insert_every: int = Form(3),
    start_now: str = Form("0"),
):
    check_auth(token)

    name = name.strip().lower().replace(" ", "_")
    ch_dir = os.path.join(CHANNELS_DIR, name)
    env_path = os.path.join(ch_dir, ".env")

    if os.path.exists(ch_dir):
        return RedirectResponse(f"/?token={token}&msg=Ошибка%3A+канал+%27{name}%27+уже+существует", 302)

    bot_username = get_bot_name(bot_token)
    if bot_username == "?":
        return RedirectResponse(f"/?token={token}&msg=Ошибка%3A+неверный+BOT_TOKEN+для+%27{name}%27", 302)

    target = target_channel.strip().lstrip("@")
    sources = ",".join(x.strip() for x in source_channels.split(",") if x.strip())

    os.makedirs(ch_dir, exist_ok=True)

    cpa_list = ",".join(x.strip() for x in cpa_links.split(",") if x.strip())

    env_content = f"""BOT_TOKEN={bot_token}

# Yandex Translate (optional - uses defaults from other channels)
YC_TRANSLATE_API_KEY=
YC_FOLDER_ID=

SOURCE_CHANNELS={sources}
TARGET_CHANNEL=@{target}

PUBLISH_INTERVAL_HOURS={publish_interval_hours}
POSTS_PER_CYCLE={posts_per_cycle}

SOURCE_LANG={source_lang}
TARGET_LANG={target_lang}

CPA_LINKS={cpa_list}
CPA_INSERT_EVERY={cpa_insert_every}
"""

    with open(env_path, "w", encoding="utf-8") as f:
        f.write(env_content)

    # Use global YC keys if not provided
    default_yc = _get_default_yc_keys()
    if default_yc:
        with open(env_path, "r") as f:
            content = f.read()
        content = content.replace("YC_TRANSLATE_API_KEY=", f"YC_TRANSLATE_API_KEY={default_yc['api_key']}")
        content = content.replace("YC_FOLDER_ID=", f"YC_FOLDER_ID={default_yc['folder_id']}")
        with open(env_path, "w") as f:
            f.write(content)

    if start_now == "1":
        _start_screen(name)

    return RedirectResponse(f"/?token={token}&msg=Канал+%27{name}%27+создан+%28%40{target}%29", 302)


@app.post("/api/channel/{name}/start")
async def api_start_channel(name: str, token: str = Query(None)):
    check_auth(token)
    _start_screen(name)
    return RedirectResponse(f"/?token={token}&msg={name}+запущен", 302)


@app.post("/api/channel/{name}/stop")
async def api_stop_channel(name: str, token: str = Query(None)):
    check_auth(token)
    subprocess.run(["screen", "-S", name, "-X", "quit"], capture_output=True, timeout=5)
    return RedirectResponse(f"/?token={token}&msg={name}+остановлен", 302)


@app.post("/api/channel/{name}/delete")
async def api_delete_channel(name: str, token: str = Query(None)):
    check_auth(token)
    ch_dir = os.path.join(CHANNELS_DIR, name)
    if not os.path.exists(ch_dir):
        return RedirectResponse(f"/?token={token}&msg=Ошибка%3A+канал+%27{name}%27+не+найден", 302)

    subprocess.run(["screen", "-S", name, "-X", "quit"], capture_output=True, timeout=5)

    import shutil
    shutil.rmtree(ch_dir)
    return RedirectResponse(f"/?token={token}&msg=Канал+%27{name}%27+удален", 302)


@app.get("/channel/{name}", response_class=HTMLResponse)
async def channel_detail(name: str, token: str = Query(None)):
    check_auth(token)
    analytics = FarmAnalytics()
    s = analytics.channel_stats(name)
    if "error" in s:
        return HTMLResponse(f"Канал '{name}' не найден", 404)
    posts = ""
    for p in s.get("last_posts", []):
        posts += f"<div class='stat'><span class='label'>#{p['id']} {p['date'][:16]}</span><span class='value'>👁 {p['views']} 💬 {p['reactions']}</span></div>"
    running = screen_running(name)
    status_tag = "<span style='color:#3fb950'>● Работает</span>" if running else "<span style='color:#f85149'>● Остановлен</span>"
    body = f"""
    <h1>{s['name']} <span style='font-size:14px;color:#8b949e'>@{s['target']}</span></h1>
    <div class='grid'>
        <div class='card'>
            <h2>Статистика</h2>
            <div class='stat'><span class='label'>Статус</span><span class='value'>{status_tag}</span></div>
            <div class='stat'><span class='label'>Подписчики</span><span class='value'>{s['subscribers']}</span></div>
            <div class='stat'><span class='label'>Доноры</span><span class='value'>{s['donors']}</span></div>
            <div class='stat'><span class='label'>БД всего</span><span class='value'>{s['db']['total']}</span></div>
            <div class='stat'><span class='label'>Опубликовано</span><span class='value'>{s['db']['published']}</span></div>
            <div class='stat'><span class='label'>Пропущено</span><span class='value'>{s['db']['skipped']}</span></div>
            <div class='stat'><span class='label'>Видео</span><span class='value'>{s['db']['video']}</span></div>
        </div>
        <div class='card'>
            <h2>Последние посты</h2>
            {posts if posts else "<div class='stat'><span class='label'>Пока нет постов</span></div>"}
            <p style='margin-top:10px'><a href='/logs/{name}?token={token}'>Логи</a></p>
        </div>
    </div>
    <div class='card'>
        <h2>Действия</h2>
        <p style='margin-top:8px'>
            <a href='/channel/{name}/edit?token={token}' class='btn btn-primary btn-sm'>⚙ Настройки</a>
            <form action='/api/channel/{name}/start?token={token}' method='post' style='display:inline'>
                <button type='submit' class='btn btn-primary btn-sm' {'disabled' if running else ''}>▶ Запустить</button>
            </form>
            <form action='/api/channel/{name}/stop?token={token}' method='post' style='display:inline'>
                <button type='submit' class='btn btn-warning btn-sm' {'disabled' if not running else ''}>⏹ Остановить</button>
            </form>
            <form action='/api/channel/{name}/delete?token={token}' method='post' style='display:inline' onsubmit='return confirm("Удалить {name} и все данные?")'>
                <button type='submit' class='btn btn-danger btn-sm'>🗑 Удалить</button>
            </form>
        </p>
    </div>
    <p><a href='/?token={token}'>← Назад</a></p>"""
    return head(f"{name} — Ferma", token) + body + foot()


@app.get("/channels", response_class=HTMLResponse)
async def channels_list(token: str = Query(None)):
    check_auth(token)
    analytics = FarmAnalytics()
    statuses = analytics.farm_status()
    rows = ""
    for s in statuses:
        if "error" in s:
            rows += f"<tr><td>{s['name']}</td><td colspan='5'>Ошибка: {s['error']}</td></tr>"
            continue
        running = screen_running(s["name"])
        status_tag = "<span style='color:#3fb950'>●</span>" if running else "<span style='color:#f85149'>●</span>"
        rows += f"""<tr>
            <td><a href='/channel/{s['name']}?token={token}'>{s['name']}</a></td>
            <td>@{s['target']}</td>
            <td>{status_tag} {'Работает' if running else 'Остановлен'}</td>
            <td>{s['subscribers']}</td>
            <td>{s['donors']}</td>
            <td>{s['db']['total']}/{s['db']['published']}/{s['db']['skipped']}</td>
            <td>
                <a href='/channel/{s['name']}?token={token}' class='btn btn-primary btn-sm'>Управление</a>
                <a href='/channel/{s['name']}/edit?token={token}' class='btn btn-warning btn-sm'>Настройки</a>
            </td>
        </tr>"""
    body = f"""
    <h1>Все каналы</h1>
    <table>
        <tr><th>Название</th><th>Канал</th><th>Статус</th><th>Подп</th><th>Доноры</th><th>БД (В/О/П)</th><th>Действия</th></tr>
        {rows if rows else "<tr><td colspan='7' style='text-align:center;color:#8b949e'>Нет каналов</td></tr>"}
    </table>
    <p><a href='/?token={token}'>← Назад</a></p>"""
    return head("Каналы — Ferma", token) + body + foot()


@app.get("/channel/{name}/edit", response_class=HTMLResponse)
async def edit_channel_form(name: str, token: str = Query(None)):
    check_auth(token)
    env_path = os.path.join(CHANNELS_DIR, name, ".env")
    if not os.path.exists(env_path):
        return HTMLResponse(f"Канал '{name}' не найден", 404)

    from dotenv import dotenv_values
    cfg = dotenv_values(env_path)

    def v(key, default=""):
        return cfg.get(key, default)

    body = f"""
    <h1>Настройки: {name}</h1>
    <form action='/api/channel/{name}/update?token={token}' method='post'>
        <div class='form-group'><label>BOT_TOKEN</label><input type='text' name='bot_token' value='{v("BOT_TOKEN")}' required></div>
        <div class='form-group'><label>TARGET_CHANNEL</label><input type='text' name='target_channel' value='{v("TARGET_CHANNEL")}' required></div>
        <div class='form-group'><label>Доноры (через запятую)</label><input type='text' name='source_channels' value='{v("SOURCE_CHANNELS")}' required></div>
        <div class='form-row'>
            <div class='form-group'><label>Интервал (часы)</label><input type='number' name='publish_interval_hours' value='{v("PUBLISH_INTERVAL_HOURS", "0.5")}' step='0.1'></div>
            <div class='form-group'><label>Постов за цикл</label><input type='number' name='posts_per_cycle' value='{v("POSTS_PER_CYCLE", "2")}'></div>
        </div>
        <div class='form-row'>
            <div class='form-group'><label>Язык источника</label><input type='text' name='source_lang' value='{v("SOURCE_LANG", "en")}'></div>
            <div class='form-group'><label>Язык перевода</label><input type='text' name='target_lang' value='{v("TARGET_LANG", "ru")}'></div>
        </div>
        <div class='form-group'><label>CPA-ссылки (опционально, через запятую)</label><input type='text' name='cpa_links' value='{v("CPA_LINKS")}' placeholder='https://...'></div>
        <div class='form-row'>
            <div class='form-group'><label>CPA каждые N постов</label><input type='number' name='cpa_insert_every' value='{v("CPA_INSERT_EVERY", "3")}'></div>
            <div class='form-group'><label>YC ключ перевода</label><input type='text' name='yc_api_key' value='{v("YC_TRANSLATE_API_KEY")}'></div>
        </div>
        <div class='form-row'>
            <div class='form-group'><label>YC Folder ID</label><input type='text' name='yc_folder_id' value='{v("YC_FOLDER_ID")}'></div>
            <div class='form-group'><label>Перезапустить после сохранения</label><input type='checkbox' name='restart' value='1' style='width:auto;margin-top:8px' checked></div>
        </div>
        <p style='margin-top:16px'><button type='submit' class='btn btn-primary'>Сохранить</button> <a href='/channel/{name}?token={token}' class='btn btn-warning'>Отмена</a></p>
    </form>"""
    return head(f"Настройки {name} — Ferma", token) + body + foot()


@app.post("/api/channel/{name}/update")
async def api_update_channel(
    name: str, token: str = Query(None),
    bot_token: str = Form(...),
    target_channel: str = Form(...),
    source_channels: str = Form(...),
    publish_interval_hours: float = Form(0.5),
    posts_per_cycle: int = Form(2),
    source_lang: str = Form("en"),
    target_lang: str = Form("ru"),
    cpa_links: str = Form(""),
    cpa_insert_every: int = Form(3),
    yc_api_key: str = Form(""),
    yc_folder_id: str = Form(""),
    restart: str = Form("0"),
):
    check_auth(token)
    env_path = os.path.join(CHANNELS_DIR, name, ".env")
    if not os.path.exists(env_path):
        return RedirectResponse(f"/?token={token}&msg=Ошибка%3A+канал+%27{name}%27+не+найден", 302)

    target = target_channel.strip().lstrip("@")
    sources = ",".join(x.strip() for x in source_channels.split(",") if x.strip())
    cpa_list = ",".join(x.strip() for x in cpa_links.split(",") if x.strip())

    env_content = f"""BOT_TOKEN={bot_token}

YC_TRANSLATE_API_KEY={yc_api_key}
YC_FOLDER_ID={yc_folder_id}

SOURCE_CHANNELS={sources}
TARGET_CHANNEL=@{target}

PUBLISH_INTERVAL_HOURS={publish_interval_hours}
POSTS_PER_CYCLE={posts_per_cycle}

SOURCE_LANG={source_lang}
TARGET_LANG={target_lang}

CPA_LINKS={cpa_list}
CPA_INSERT_EVERY={cpa_insert_every}
"""

    with open(env_path, "w", encoding="utf-8") as f:
        f.write(env_content)

    if restart == "1":
        subprocess.run(["screen", "-S", name, "-X", "quit"], capture_output=True, timeout=5)
        _start_screen(name)

    return RedirectResponse(f"/channel/{name}?token={token}", 302)


@app.get("/logs/{name}", response_class=HTMLResponse)
async def view_logs(name: str, lines: int = 50, token: str = Query(None)):
    check_auth(token)
    log_path = os.path.join(CHANNELS_DIR, name, "bot.log")
    if not os.path.exists(log_path):
        return HTMLResponse(f"Нет логов для '{name}'", 404)
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()
        tail = all_lines[-lines:]
    body = f"<h1>Логи: {name}</h1><p><a href='/channel/{name}?token={token}'>← Назад к каналу</a></p><pre>{''.join(tail)}</pre>"
    return head(f"Логи: {name} — Ferma", token) + body + foot()


@app.get("/filters", response_class=HTMLResponse)
async def filters_page(token: str = Query(None), msg: str = None):
    check_auth(token)
    from core.filter.manage import load_filters
    f = load_filters()
    msg_html = ""
    if msg:
        cls = "msg-success" if "added" in msg or "removed" in msg else "msg-error"
        msg_html = f"<div class='{cls}'>{msg}</div>"
    groups = {
        "footer_patterns": "Футеры (строки с этой фразой удаляются из текста)",
        "ad_keywords": "Рекламные слова (2+ совпадения = пост заблокирован)",
        "external_source_patterns": "Внешние источники (пост блокируется)",
        "teaser_patterns": "Тизеры/списки (пост блокируется)",
    }
    sections = ""
    for key, label in groups.items():
        items = f.get(key, [])
        rows = "".join(
            f"<tr><td>{item}</td><td>"
            f"<form action='/api/filters/remove?token={token}' method='post' style='display:inline'>"
            f"<input type='hidden' name='group' value='{key}'>"
            f"<input type='hidden' name='value' value='{item}'>"
            f"<button type='submit' class='btn btn-danger btn-sm'>X</button></form></td></tr>"
            for item in items
        ) if items else "<tr><td colspan='2' style='color:#8b949e'>(пусто)</td></tr>"
        sections += f"""
        <div class='card'>
            <h2>{label}</h2>
            <table><tr><th>Фраза</th><th style='width:50px'></th></tr>{rows}</table>
            <form action='/api/filters/add?token={token}' method='post' style='margin-top:8px;display:flex;gap:8px'>
                <input type='hidden' name='group' value='{key}'>
                <input type='text' name='value' placeholder='новая фраза...' style='margin-bottom:0;flex:1' required>
                <button type='submit' class='btn btn-primary btn-sm'>Добавить</button>
            </form>
        </div>"""
    body = f"<h1>Управление фильтрами</h1>{msg_html}{sections}<p><a href='/?token={token}'>← Назад</a></p>"
    return head("Фильтры — Ferma", token) + body + foot()


@app.post("/api/filters/add")
async def api_filter_add(token: str = Query(None), group: str = Form(...), value: str = Form(...)):
    check_auth(token)
    from core.filter.manage import load_filters, save_filters
    f = load_filters()
    if group not in f:
        f[group] = []
    v = value.strip().lower()
    if v and v not in f[group]:
        f[group].append(v)
        save_filters(f)
    return RedirectResponse(f"/filters?token={token}&msg=%27{v}%27+added+to+{group}", 302)


@app.post("/api/filters/remove")
async def api_filter_remove(token: str = Query(None), group: str = Form(...), value: str = Form(...)):
    check_auth(token)
    from core.filter.manage import load_filters, save_filters
    f = load_filters()
    if group in f:
        f[group] = [x for x in f[group] if x != value.strip().lower()]
        save_filters(f)
    return RedirectResponse(f"/filters?token={token}&msg=%27{value}%27+removed+from+{group}", 302)


def _get_default_yc_keys() -> dict:
    for entry in os.listdir(CHANNELS_DIR):
        env_path = os.path.join(CHANNELS_DIR, entry, ".env")
        if os.path.isfile(env_path):
            from dotenv import dotenv_values
            cfg = dotenv_values(env_path)
            api_key = cfg.get("YC_TRANSLATE_API_KEY", "")
            folder_id = cfg.get("YC_FOLDER_ID", "")
            if api_key and folder_id:
                return {"api_key": api_key, "folder_id": folder_id}
    return None


def _start_screen(name: str):
    env_path = os.path.join(CHANNELS_DIR, name, ".env")
    if not os.path.exists(env_path):
        return
    log_dir = os.path.join(FARM_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    cmd = (
        f"cd {FARM_DIR} && screen -dmS {name} bash -c "
        f'"mkdir -p logs && PYTHONUNBUFFERED=1 exec {PYTHON} -u '
        f"core/run_channel.py {env_path} 2>&1 | tee -a logs/{name}.log\""
    )
    subprocess.run(cmd, shell=True, capture_output=True, timeout=10)


def main():
    port = int(os.environ.get("ADMIN_PORT", "8080"))
    host = os.environ.get("ADMIN_HOST", "0.0.0.0")
    print(f"Admin panel: http://{host}:{port}/?token={AUTH_TOKEN}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
