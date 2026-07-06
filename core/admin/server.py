import os
import sys
import re
import subprocess

from fastapi import FastAPI, Query, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import uvicorn

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ),
)

from core.analytics import FarmAnalytics  # noqa: E402

AUTH_TOKEN = os.environ.get("ADMIN_TOKEN", "ferma2026")
DEMO_TOKEN = "demo"
FARM_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
CHANNELS_DIR = os.path.join(FARM_DIR, "channels")
PYTHON = os.path.join(FARM_DIR, "venv", "bin", "python")

SECRET_FIELDS = {
    "BOT_TOKEN": lambda v: v[:4] + "***" if len(v) > 4 else "***",
    "TELEGRAM_API_ID": lambda v: "***",
    "TELEGRAM_API_HASH": lambda v: "***",
    "TELEGRAM_PHONE": lambda v: v[:2] + "****" if len(v) > 2 else "****",
    "YC_TRANSLATE_API_KEY": lambda v: "***",
    "YC_FOLDER_ID": lambda v: "***",
    "VK_TOKEN": lambda v: "***",
    "CPA_LINKS": lambda v: "***",
}


def is_demo(token: str | None) -> bool:
    return token == DEMO_TOKEN


def mask_value(key: str, value: str, demo: bool) -> str:
    if not demo or not value:
        return value
    fn = SECRET_FIELDS.get(key)
    return fn(value) if fn else value


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
.demo-banner { background:#1c3a5e; border:1px solid #388bfd; border-radius:8px; padding:12px 16px; margin-bottom:20px; color:#79c0ff; font-size:14px; }
.demo-banner b { color:#f0f6fc; }
.demo-disabled { opacity:0.4; pointer-events:none; }
"""


def head(title, token, demo=False):
    demo_html = ""
    if demo:
        demo_html = "<div class='demo-banner'><b>Демо-режим</b> — просмотр интерфейса. Все действия и кнопки недоступны. Секретные данные скрыты.</div>"
    return f"""<!DOCTYPE html><html lang='ru'><head><meta charset='utf-8'><title>{title}</title><style>{CSS}</style>
<script>
function toggleType() {{
    var t = document.getElementById('channel_type');
    var isLightning = t.value === 'lightning';
    document.getElementById('normal_fields').style.display = isLightning ? 'none' : 'block';
    document.getElementById('lightning_fields').style.display = isLightning ? 'block' : 'none';
}}
</script>
</head><body>
<div class='nav'><a href='/?token={token}'>Панель</a><a href='/channels?token={token}'>Каналы</a><a href='/filters?token={token}'>Фильтры</a><a href='/add?token={token}'>+ Добавить канал</a></div>
{demo_html}"""


def foot():
    return "</body></html>"


def check_auth(token: str | None):
    if token != AUTH_TOKEN and token != DEMO_TOKEN:
        raise HTTPException(401, "Invalid token")


CHANNEL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]*$")


def validate_channel_name(name: str):
    if not CHANNEL_NAME_RE.match(name):
        raise HTTPException(400, "Invalid channel name")


def screen_running(name: str) -> bool:
    r = subprocess.run(
        ["screen", "-ls", name], capture_output=True, text=True, timeout=5
    )
    return name in r.stdout


def get_bot_name(token: str) -> str:
    import requests

    try:
        r = requests.get(
            f"https://api.telegram.org/bot{token}/getMe", timeout=10
        )
        data = r.json()
        if data.get("ok"):
            return data["result"]["username"]
    except Exception:
        pass
    return "?"


@app.get("/", response_class=HTMLResponse)
async def dashboard(token: str | None = Query(None), msg: str | None = None):
    check_auth(token)
    demo = is_demo(token)
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
        status_tag = (
            "<span style='color:#3fb950'>● Работает</span>"
            if running
            else "<span style='color:#f85149'>● Остановлен</span>"
        )
        chan_type = s.get("type", "normal")
        type_tag = (
            "⚡️ Lightning"
            if chan_type == "lightning"
            else "🔵 VK"
            if chan_type == "vk"
            else "📰 Normal"
        )
        extra = ""
        if chan_type == "lightning":
            rss = s.get("rss_feeds", [])
            extra = f"<div class='stat'><span class='label'>RSS фидов</span><span class='value'>{len(rss)}</span></div>"
        action_cls = " class='demo-disabled'" if demo else ""
        cards += f"""
        <div class='card'>
            <h2 style='margin-top:0'><a href='/channel/{s["name"]}?token={token}'>{s["name"]}</a> <span style='float:right;font-size:13px;color:#8b949e'>{type_tag}</span></h2>
            <div class='stat'><span class='label'>Статус</span><span class='value'>{status_tag}</span></div>
            <div class='stat'><span class='label'>Подписчики</span><span class='value'>{s["subscribers"]}</span></div>
            <div class='stat'><span class='label'>Доноры</span><span class='value'>{s["donors"]}</span></div>
            {extra}
            <div class='stat'><span class='label'>БД всего</span><span class='value'>{s["db"]["total"]}</span></div>
            <div class='stat'><span class='label'>Опубликовано</span><span class='value'>{s["db"]["published"]}</span></div>
            <div class='stat'><span class='label'>Пропущено</span><span class='value'>{s["db"]["skipped"]}</span></div>
            <div class='stat'><span class='label'>Видео</span><span class='value'>{s["db"]["video"]}</span></div>
            <p style='margin-top:10px'{action_cls}>
                <a href='/logs/{s["name"]}?token={token}'>[логи]</a>
                <a href='/channel/{s["name"]}?token={token}' class='btn btn-primary btn-sm'>Управление</a>
            </p>
        </div>"""
    body = (
        f"<h1>Панель управления</h1>{msg_html}<div class='grid'>{cards}</div>"
    )
    return head("Панель — Ferma", token, demo=demo) + body + foot()


@app.get("/add", response_class=HTMLResponse)
async def add_channel_form(token: str | None = Query(None)):
    check_auth(token)
    demo = is_demo(token)
    disabled = " disabled" if demo else ""
    body = f"""
    <h1>Добавить канал</h1>
    <form action='/api/channel/create?token={token}' method='post'{' class="demo-disabled"' if demo else ""}>
        <div class='form-group'><label>Название (папка)</label><input type='text' name='name' placeholder='например: tech' required{disabled}></div>
        <div class='form-group'><label>Тип канала</label>
            <select name='channel_type' id='channel_type' onchange='toggleType()' required{disabled}>
                <option value='normal'>Normal (Telethon + парсер)</option>
                <option value='lightning'>Lightning / RE:POST (Telethon polling + RSS)</option>
            </select>
        </div>
        <div id='normal_fields'>
            <div class='form-group'><label>BOT_TOKEN</label><input type='text' name='bot_token' placeholder='123456:ABC-DEF1234' required{disabled}></div>
            <div class='form-group'><label>TARGET_CHANNEL</label><input type='text' name='target_channel' placeholder='@moy_kal' required{disabled}></div>
            <div class='form-group'><label>Доноры (через запятую)</label><input type='text' name='source_channels' placeholder='@donor1,@donor2' required{disabled}></div>
            <div class='form-row'>
                <div class='form-group'><label>Интервал (часы)</label><input type='number' name='publish_interval_hours' value='0.5' step='0.1'{disabled}></div>
                <div class='form-group'><label>Постов за цикл</label><input type='number' name='posts_per_cycle' value='2'{disabled}></div>
            </div>
            <div class='form-group'><label><input type='checkbox' name='require_media' value='1' style='width:auto;margin-top:8px'{disabled}> Только посты с медиа (фото/видео)</label></div>
        </div>
        <div id='lightning_fields' style='display:none'>
            <div class='form-group'><label>BOT_TOKEN</label><input type='text' name='bot_token' placeholder='123456:ABC-DEF1234' required{disabled}></div>
            <div class='form-group'><label>TARGET_CHANNEL</label><input type='text' name='target_channel' placeholder='@yourrepost' required{disabled}></div>
            <div class='form-group'><label>Telegram доноры (через запятую)</label><input type='text' name='source_channels' placeholder='@WatcherGuru,@BNONews' required{disabled}></div>
            <div class='form-row'>
                <div class='form-group'><label>TELEGRAM_API_ID</label><input type='text' name='api_id' placeholder='12345' required{disabled}></div>
                <div class='form-group'><label>TELEGRAM_API_HASH</label><input type='text' name='api_hash' placeholder='abc123...' required{disabled}></div>
            </div>
            <div class='form-group'><label>TELEGRAM_PHONE</label><input type='text' name='phone' placeholder='+79001234567' required{disabled}></div>
            <div class='form-group'><label>RSS фиды (через запятую)</label><input type='text' name='rss_feeds' placeholder='https://feeds.bbci.co.uk/news/rss.xml,...'{disabled}></div>
            <div class='form-group'><label>RU доноры (через запятую)</label><input type='text' name='ru_source_channels' placeholder='@tass_agency,@rian_ru,...'{disabled}></div>
            <div class='form-group'><label>Reddit сабреддиты (через запятую)</label><input type='text' name='reddit_subreddits' placeholder='worldnews,news,...'{disabled}></div>
        </div>
        <div class='form-row'>
            <div class='form-group'><label>Язык источника</label><input type='text' name='source_lang' value='en'{disabled}></div>
            <div class='form-group'><label>Язык перевода</label><input type='text' name='target_lang' value='ru'{disabled}></div>
        </div>
        <div class='form-group'><label>CPA-ссылки (опционально, через запятую)</label><input type='text' name='cpa_links' placeholder='https://...'{disabled}></div>
        <div class='form-row'>
            <div class='form-group'><label>CPA каждые N постов</label><input type='number' name='cpa_insert_every' value='3'{disabled}></div>
            <div class='form-group'><label>Запустить после создания</label><input type='checkbox' name='start_now' value='1' style='width:auto;margin-top:8px' checked{disabled}></div>
        </div>
        <p style='margin-top:16px'><button type='submit' class='btn btn-primary'{disabled}>Создать</button> <a href='/?token={token}' class='btn btn-warning'>Отмена</a></p>
    </form>"""
    return head("Добавить канал — Ferma", token, demo=demo) + body + foot()


@app.post("/api/channel/create")
async def api_create_channel(
    token: str | None = Query(None),
    name: str = Form(...),
    channel_type: str = Form("normal"),
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
    require_media: str = Form("0"),
    api_id: str = Form(""),
    api_hash: str = Form(""),
    phone: str = Form(""),
    rss_feeds: str = Form(""),
    ru_source_channels: str = Form(""),
    reddit_subreddits: str = Form(""),
):
    check_auth(token)
    if is_demo(token):
        raise HTTPException(403, "Demo mode: actions disabled")

    name = name.strip().lower().replace(" ", "_")
    if not CHANNEL_NAME_RE.match(name):
        return RedirectResponse(
            f"/?token={token}&msg=Ошибка%3A+недопустимое+имя+канала+%27{name}%27",
            302,
        )
    ch_dir = os.path.join(CHANNELS_DIR, name)
    env_path = os.path.join(ch_dir, ".env")

    if os.path.exists(ch_dir):
        return RedirectResponse(
            f"/?token={token}&msg=Ошибка%3A+канал+%27{name}%27+уже+существует",
            302,
        )

    bot_username = get_bot_name(bot_token)
    if bot_username == "?":
        return RedirectResponse(
            f"/?token={token}&msg=Ошибка%3A+неверный+BOT_TOKEN+для+%27{name}%27",
            302,
        )

    target = target_channel.strip().lstrip("@")
    sources = ",".join(
        x.strip() for x in source_channels.split(",") if x.strip()
    )

    os.makedirs(ch_dir, exist_ok=True)

    cpa_list = ",".join(x.strip() for x in cpa_links.split(",") if x.strip())

    is_lightning = channel_type == "lightning"
    rss_list = ",".join(x.strip() for x in rss_feeds.split(",") if x.strip())
    ru_list = ",".join(
        x.strip() for x in ru_source_channels.split(",") if x.strip()
    )
    reddit_list = ",".join(
        x.strip() for x in reddit_subreddits.split(",") if x.strip()
    )

    if is_lightning:
        env_content = f"""# RE:POST — Lightning News Channel
CHANNEL_TYPE=lightning
TELEGRAM_API_ID={api_id}
TELEGRAM_API_HASH={api_hash}
TELEGRAM_PHONE={phone}

YC_TRANSLATE_API_KEY=
YC_FOLDER_ID=

BOT_TOKEN={bot_token}

SOURCE_CHANNELS={sources}
TARGET_CHANNEL=@{target}

PUBLISH_INTERVAL_HOURS=0
POSTS_PER_CYCLE=0

SOURCE_LANG={source_lang}
TARGET_LANG={target_lang}

CPA_LINKS={cpa_list}
CPA_INSERT_EVERY={cpa_insert_every}
RSS_FEEDS={rss_list}
RU_SOURCE_CHANNELS={ru_list}
REDDIT_SUBREDDITS={reddit_list}
"""
    else:
        env_content = f"""# Normal channel
CHANNEL_TYPE=normal
BOT_TOKEN={bot_token}

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
REQUIRE_MEDIA={"true" if require_media == "1" else "false"}
"""

    with open(env_path, "w", encoding="utf-8") as f:
        f.write(env_content)

    # Use global YC keys if not provided
    default_yc = _get_default_yc_keys()
    if default_yc:
        with open(env_path, "r") as f:
            content = f.read()
        content = content.replace(
            "YC_TRANSLATE_API_KEY=",
            f"YC_TRANSLATE_API_KEY={default_yc['api_key']}",
        )
        content = content.replace(
            "YC_FOLDER_ID=", f"YC_FOLDER_ID={default_yc['folder_id']}"
        )
        with open(env_path, "w") as f:
            f.write(content)

    if start_now == "1":
        _start_screen(name)

    return RedirectResponse(
        f"/?token={token}&msg=Канал+%27{name}%27+создан+%28%40{target}%29", 302
    )


@app.post("/api/channel/{name}/start")
async def api_start_channel(name: str, token: str | None = Query(None)):
    check_auth(token)
    if is_demo(token):
        raise HTTPException(403, "Demo mode: actions disabled")
    validate_channel_name(name)
    _start_screen(name)
    return RedirectResponse(f"/?token={token}&msg={name}+запущен", 302)


@app.post("/api/channel/{name}/stop")
async def api_stop_channel(name: str, token: str | None = Query(None)):
    check_auth(token)
    if is_demo(token):
        raise HTTPException(403, "Demo mode: actions disabled")
    validate_channel_name(name)
    subprocess.run(
        ["screen", "-S", name, "-X", "quit"], capture_output=True, timeout=5
    )
    return RedirectResponse(f"/?token={token}&msg={name}+остановлен", 302)


@app.post("/api/channel/{name}/delete")
async def api_delete_channel(name: str, token: str | None = Query(None)):
    check_auth(token)
    if is_demo(token):
        raise HTTPException(403, "Demo mode: actions disabled")
    validate_channel_name(name)
    ch_dir = os.path.join(CHANNELS_DIR, name)
    if not os.path.exists(ch_dir):
        return RedirectResponse(
            f"/?token={token}&msg=Ошибка%3A+канал+%27{name}%27+не+найден", 302
        )
    subprocess.run(
        ["screen", "-S", name, "-X", "quit"], capture_output=True, timeout=5
    )
    import shutil

    shutil.rmtree(ch_dir)
    return RedirectResponse(
        f"/?token={token}&msg=Канал+%27{name}%27+удален", 302
    )


@app.get("/channel/{name}", response_class=HTMLResponse)
async def channel_detail(name: str, token: str | None = Query(None)):
    check_auth(token)
    demo = is_demo(token)
    validate_channel_name(name)
    analytics = FarmAnalytics()
    s = analytics.channel_stats(name)
    if "error" in s:
        return HTMLResponse(f"Канал '{name}' не найден", 404)
    posts = ""
    for p in s.get("last_posts", []):
        posts += f"<div class='stat'><span class='label'>#{p['id']} {p['date'][:16]}</span><span class='value'>👁 {p['views']} 💬 {p['reactions']}</span></div>"
    if not posts and s.get("vk_posts"):
        for p in s["vk_posts"]:
            icon = "✅" if p["ok"] else "❌"
            tag = f"[{p['type']}]"
            posts += f"<div class='stat'><span class='label'>{icon} {tag} {p['title'][:80]}</span></div>"
    if not posts:
        posts = "<div class='stat'><span class='label'>Пока нет постов</span></div>"
    running = screen_running(name)
    status_tag = (
        "<span style='color:#3fb950'>● Работает</span>"
        if running
        else "<span style='color:#f85149'>● Остановлен</span>"
    )
    chan_type = s.get("type", "normal")
    type_tag = (
        "⚡️ Lightning"
        if chan_type == "lightning"
        else "🔵 VK"
        if chan_type == "vk"
        else "📰 Normal"
    )

    def _render_sources_table(sources: list) -> str:
        if not sources:
            return "<div class='stat'><span class='label'>Нет источников</span></div>"
        rows = "".join(
            f"<tr><td><a href='https://t.me/{s['username']}' target='_blank'>@{s['username']}</a></td>"
            f"<td>{s['title']}</td></tr>"
            for s in sources
        )
        return (
            f"<table><tr><th>Ссылка</th><th>Название</th></tr>{rows}</table>"
        )

    source_channels = s.get("source_channels", [])
    ru_source_channels = s.get("ru_source_channels", [])
    rss = s.get("rss_feeds", [])
    reddit = s.get("reddit_subreddits", [])
    sources_html = ""
    if source_channels:
        sources_html += f"<div class='card'><h2>Telegram доноры ({len(source_channels)})</h2>{_render_sources_table(source_channels)}</div>"
    if ru_source_channels:
        sources_html += f"<div class='card'><h2>RU доноры ({len(ru_source_channels)})</h2>{_render_sources_table(ru_source_channels)}</div>"
    if rss:
        rss_rows = "".join(
            f"<tr><td><a href='{f}' target='_blank' style='font-size:12px'>{f}</a></td></tr>"
            for f in rss
        )
        sources_html += f"<div class='card'><h2>RSS фиды ({len(rss)})</h2><table><tr><th>URL</th></tr>{rss_rows}</table></div>"
    if reddit:
        reddit_rows = "".join(
            f"<tr><td><a href='https://reddit.com/r/{r}' target='_blank'>r/{r}</a></td></tr>"
            for r in reddit
        )
        sources_html += f"<div class='card'><h2>Reddit ({len(reddit)})</h2><table><tr><th>Сабреддит</th></tr>{reddit_rows}</table></div>"
    body = f"""
    <h1>{s["name"]} <span style='font-size:14px;color:#8b949e'>@{s["target"]} {type_tag}</span></h1>
    <div class='grid'>
        <div class='card'>
            <h2>Статистика</h2>
            <div class='stat'><span class='label'>Статус</span><span class='value'>{status_tag}</span></div>
            <div class='stat'><span class='label'>Подписчики</span><span class='value'>{s["subscribers"]}</span></div>
            <div class='stat'><span class='label'>Доноры</span><span class='value'>{s["donors"]}</span></div>
            <div class='stat'><span class='label'>БД всего</span><span class='value'>{s["db"]["total"]}</span></div>
            <div class='stat'><span class='label'>Опубликовано</span><span class='value'>{s["db"]["published"]}</span></div>
            <div class='stat'><span class='label'>Пропущено</span><span class='value'>{s["db"]["skipped"]}</span></div>
            <div class='stat'><span class='label'>Видео</span><span class='value'>{s["db"]["video"]}</span></div>
        </div>
        <div class='card'>
            <h2>Последние посты</h2>
            {posts}
            <p style='margin-top:10px'><a href='/logs/{name}?token={token}'>Логи</a></p>
        </div>
    </div>
    {sources_html}
    <div class='card'>
        <h2>Действия</h2>
        <div style='margin-top:8px;display:flex;flex-wrap:wrap;gap:8px'{' class="demo-disabled"' if demo else ""}>
            <a href='/channel/{name}/edit?token={token}' class='btn btn-primary btn-sm'>⚙ Настройки</a>
            <form action='/api/channel/{name}/start?token={token}' method='post'>
                <button type='submit' class='btn btn-primary btn-sm' {"disabled" if running or demo else ""}>▶ Запустить</button>
            </form>
            <form action='/api/channel/{name}/stop?token={token}' method='post'>
                <button type='submit' class='btn btn-warning btn-sm' {"disabled" if not running or demo else ""}>⏹ Остановить</button>
            </form>
            <form action='/api/channel/{name}/delete?token={token}' method='post' onsubmit='return confirm("Удалить {name} и все данные?")'>
                <button type='submit' class='btn btn-danger btn-sm'{"disabled" if demo else ""}>🗑 Удалить</button>
            </form>
        </div>
    </div>
    <p><a href='/?token={token}'>← Назад</a></p>"""
    return head(f"{name} — Ferma", token, demo=demo) + body + foot()


@app.get("/channels", response_class=HTMLResponse)
async def channels_list(token: str | None = Query(None)):
    check_auth(token)
    demo = is_demo(token)
    analytics = FarmAnalytics()
    statuses = analytics.farm_status()
    rows = ""
    for s in statuses:
        if "error" in s:
            rows += f"<tr><td>{s['name']}</td><td colspan='5'>Ошибка: {s['error']}</td></tr>"
            continue
        running = screen_running(s["name"])
        status_tag = (
            "<span style='color:#3fb950'>●</span>"
            if running
            else "<span style='color:#f85149'>●</span>"
        )
        action_cls = " class='demo-disabled'" if demo else ""
        rows += f"""<tr>
            <td><a href='/channel/{s["name"]}?token={token}'>{s["name"]}</a></td>
            <td>@{s["target"]}</td>
            <td>{status_tag} {"Работает" if running else "Остановлен"}</td>
            <td>{s["subscribers"]}</td>
            <td>{s["donors"]}</td>
            <td>{s["db"]["total"]}/{s["db"]["published"]}/{s["db"]["skipped"]}</td>
            <td{action_cls}>
                <a href='/channel/{s["name"]}?token={token}' class='btn btn-primary btn-sm'>Управление</a>
                <a href='/channel/{s["name"]}/edit?token={token}' class='btn btn-warning btn-sm'>Настройки</a>
            </td>
        </tr>"""
    body = f"""
    <h1>Все каналы</h1>
    <table>
        <tr><th>Название</th><th>Канал</th><th>Статус</th><th>Подп</th><th>Доноры</th><th>БД (В/О/П)</th><th>Действия</th></tr>
        {rows if rows else "<tr><td colspan='7' style='text-align:center;color:#8b949e'>Нет каналов</td></tr>"}
    </table>
    <p><a href='/?token={token}'>← Назад</a></p>"""
    return head("Каналы — Ferma", token, demo=demo) + body + foot()


@app.get("/channel/{name}/edit", response_class=HTMLResponse)
async def edit_channel_form(name: str, token: str | None = Query(None)):
    check_auth(token)
    demo = is_demo(token)
    validate_channel_name(name)
    env_path = os.path.join(CHANNELS_DIR, name, ".env")
    if not os.path.exists(env_path):
        return HTMLResponse(f"Канал '{name}' не найден", 404)
    from dotenv import dotenv_values

    cfg = dotenv_values(env_path)

    def v(key, default=""):
        return mask_value(key, cfg.get(key, default), demo)

    is_lightning = cfg.get("CHANNEL_TYPE", "") == "lightning"
    rm_checked = (
        "checked"
        if cfg.get("REQUIRE_MEDIA", "").lower() in ("1", "true", "yes")
        else ""
    )
    disabled = " disabled" if demo else ""
    body = f"""
    <h1>Настройки: {name} <span style='font-size:14px;color:#8b949e'>{
        "⚡️ Lightning" if is_lightning else "📰 Normal"
    }</span></h1>
    <form action='/api/channel/{name}/update?token={token}' method='post'{
        ' class="demo-disabled"' if demo else ""
    }>
        <input type='hidden' name='channel_type' value='{
        "lightning" if is_lightning else "normal"
    }'>
        <div class='form-group'><label>BOT_TOKEN</label><input type='text' name='bot_token' value='{
        v("BOT_TOKEN")
    }' required{disabled}></div>
        <div class='form-group'><label>TARGET_CHANNEL</label><input type='text' name='target_channel' value='{
        v("TARGET_CHANNEL")
    }' required{disabled}></div>
        <div class='form-group'><label>Доноры (через запятую)</label><input type='text' name='source_channels' value='{
        v("SOURCE_CHANNELS")
    }' required{disabled}></div>
        {
        ""
        if not is_lightning
        else '''
        <div class='form-row'>
            <div class='form-group'><label>TELEGRAM_API_ID</label><input type='text' name='api_id' value='{}'{}></div>
            <div class='form-group'><label>TELEGRAM_API_HASH</label><input type='text' name='api_hash' value='{}'{}></div>
        </div>
        <div class='form-group'><label>TELEGRAM_PHONE</label><input type='text' name='phone' value='{}'{}></div>
        <div class='form-group'><label>RSS фиды (через запятую)</label><input type='text' name='rss_feeds' value='{}'{}></div>
        <div class='form-group'><label>RU доноры (через запятую)</label><input type='text' name='ru_source_channels' value='{}'{}></div>
        <div class='form-group'><label>Reddit сабреддиты (через запятую)</label><input type='text' name='reddit_subreddits' value='{}'{}></div>
        '''.format(
            v("TELEGRAM_API_ID"),
            disabled,
            v("TELEGRAM_API_HASH"),
            disabled,
            v("TELEGRAM_PHONE"),
            disabled,
            v("RSS_FEEDS"),
            disabled,
            v("RU_SOURCE_CHANNELS"),
            disabled,
            v("REDDIT_SUBREDDITS"),
            disabled,
        )
    }
        <div class='form-row'>
            <div class='form-group'><label>Язык источника</label><input type='text' name='source_lang' value='{
        v("SOURCE_LANG", "en")
    }'{disabled}></div>
            <div class='form-group'><label>Язык перевода</label><input type='text' name='target_lang' value='{
        v("TARGET_LANG", "ru")
    }'{disabled}></div>
        </div>
        <div class='form-row'>
            <div class='form-group'><label>Интервал (часы)</label><input type='number' name='publish_interval_hours' value='{
        v("PUBLISH_INTERVAL_HOURS", "0.5")
    }' step='0.1'{disabled}></div>
            <div class='form-group'><label>Постов за цикл</label><input type='number' name='posts_per_cycle' value='{
        v("POSTS_PER_CYCLE", "2")
    }'{disabled}></div>
        </div>
        <div class='form-group'>
            <label><input type='checkbox' name='require_media' value='1' style='width:auto;margin-top:8px' {
        rm_checked
    }{disabled}> Только с медиа</label>
        </div>
        <div class='form-group'><label>CPA-ссылки (через запятую)</label><input type='text' name='cpa_links' value='{
        v("CPA_LINKS")
    }' placeholder='https://...'{disabled}></div>
        <div class='form-row'>
            <div class='form-group'><label>CPA каждые N постов</label><input type='number' name='cpa_insert_every' value='{
        v("CPA_INSERT_EVERY", "3")
    }'{disabled}></div>
            <div class='form-group'><label>YC ключ перевода</label><input type='text' name='yc_api_key' value='{
        v("YC_TRANSLATE_API_KEY")
    }'{disabled}></div>
        </div>
        <div class='form-row'>
            <div class='form-group'><label>YC Folder ID</label><input type='text' name='yc_folder_id' value='{
        v("YC_FOLDER_ID")
    }'{disabled}></div>
        </div>
        <div class='form-group'><label><input type='checkbox' name='restart' value='1' style='width:auto;margin-top:8px' checked{
        disabled
    }> Перезапустить после сохранения</label></div>
        <p style='margin-top:16px'><button type='submit' class='btn btn-primary'{
        disabled
    }>Сохранить</button> <a href='/channel/{name}?token={
        token
    }' class='btn btn-warning'>Отмена</a></p>
    </form>"""
    return head(f"Настройки {name} — Ferma", token, demo=demo) + body + foot()


@app.post("/api/channel/{name}/update")
async def api_update_channel(
    name: str,
    token: str | None = Query(None),
    channel_type: str = Form("normal"),
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
    require_media: str = Form("0"),
    restart: str = Form("0"),
    api_id: str = Form(""),
    api_hash: str = Form(""),
    phone: str = Form(""),
    rss_feeds: str = Form(""),
    ru_source_channels: str = Form(""),
    reddit_subreddits: str = Form(""),
):
    check_auth(token)
    if is_demo(token):
        raise HTTPException(403, "Demo mode: actions disabled")
    validate_channel_name(name)
    env_path = os.path.join(CHANNELS_DIR, name, ".env")
    if not os.path.exists(env_path):
        return RedirectResponse(
            f"/?token={token}&msg=Ошибка%3A+канал+%27{name}%27+не+найден", 302
        )
    target = target_channel.strip().lstrip("@")
    sources = ",".join(
        x.strip() for x in source_channels.split(",") if x.strip()
    )
    cpa_list = ",".join(x.strip() for x in cpa_links.split(",") if x.strip())
    rss_list = ",".join(x.strip() for x in rss_feeds.split(",") if x.strip())
    ru_list = ",".join(
        x.strip() for x in ru_source_channels.split(",") if x.strip()
    )
    reddit_list = ",".join(
        x.strip() for x in reddit_subreddits.split(",") if x.strip()
    )
    is_lightning = channel_type == "lightning"

    if is_lightning:
        env_content = f"""# RE:POST — Lightning News Channel
CHANNEL_TYPE=lightning
TELEGRAM_API_ID={api_id}
TELEGRAM_API_HASH={api_hash}
TELEGRAM_PHONE={phone}

YC_TRANSLATE_API_KEY={yc_api_key}
YC_FOLDER_ID={yc_folder_id}

BOT_TOKEN={bot_token}

SOURCE_CHANNELS={sources}
TARGET_CHANNEL=@{target}

PUBLISH_INTERVAL_HOURS=0
POSTS_PER_CYCLE=0

SOURCE_LANG={source_lang}
TARGET_LANG={target_lang}

CPA_LINKS={cpa_list}
CPA_INSERT_EVERY={cpa_insert_every}
RSS_FEEDS={rss_list}
RU_SOURCE_CHANNELS={ru_list}
REDDIT_SUBREDDITS={reddit_list}
"""
    else:
        env_content = f"""# Normal channel
CHANNEL_TYPE=normal
BOT_TOKEN={bot_token}

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
REQUIRE_MEDIA={"true" if require_media == "1" else "false"}
"""
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(env_content)
    if restart == "1":
        subprocess.run(
            ["screen", "-S", name, "-X", "quit"],
            capture_output=True,
            timeout=5,
        )
        _start_screen(name)
    return RedirectResponse(f"/channel/{name}?token={token}", 302)


@app.get("/logs/{name}", response_class=HTMLResponse)
async def view_logs(
    name: str, lines: int = 50, token: str | None = Query(None)
):
    check_auth(token)
    validate_channel_name(name)
    log_path = os.path.join(CHANNELS_DIR, name, "bot.log")
    if not os.path.exists(log_path):
        log_path = os.path.join(CHANNELS_DIR, name, "logs", f"{name}.log")
    if not os.path.exists(log_path):
        return HTMLResponse(f"Нет логов для '{name}'", 404)
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()
        tail = all_lines[-lines:]
    body = f"<h1>Логи: {name}</h1><p><a href='/channel/{name}?token={token}'>← Назад к каналу</a></p><pre>{''.join(tail)}</pre>"
    return head(f"Логи: {name} — Ferma", token) + body + foot()


@app.get("/filters", response_class=HTMLResponse)
async def filters_page(
    token: str | None = Query(None), msg: str | None = None
):
    check_auth(token)
    demo = is_demo(token)
    from core.filter.manage import load_filters

    f = load_filters()
    msg_html = ""
    if msg:
        cls = (
            "msg-success"
            if "added" in msg or "removed" in msg
            else "msg-error"
        )
        msg_html = f"<div class='{cls}'>{msg}</div>"
    groups = {
        "footer_patterns": "Футеры (строки с этой фразой удаляются из текста)",
        "ad_keywords": "Рекламные слова (1+ совпадение = пост заблокирован)",
        "external_source_patterns": "Внешние источники (пост блокируется)",
        "teaser_patterns": "Тизеры/списки (пост блокируется)",
    }
    sections = ""
    for key, label in groups.items():
        items = f.get(key, [])
        if demo:
            rows = (
                "".join(
                    f"<tr><td>{item}</td><td><button class='btn btn-danger btn-sm' disabled>X</button></td></tr>"
                    for item in items
                )
                if items
                else "<tr><td colspan='2' style='color:#8b949e'>(пусто)</td></tr>"
            )
        else:
            rows = (
                "".join(
                    f"<tr><td>{item}</td><td>"
                    f"<form action='/api/filters/remove?token={token}' method='post' style='display:inline'>"
                    f"<input type='hidden' name='group' value='{key}'>"
                    f"<input type='hidden' name='value' value='{item}'>"
                    f"<button type='submit' class='btn btn-danger btn-sm'>X</button></form></td></tr>"
                    for item in items
                )
                if items
                else "<tr><td colspan='2' style='color:#8b949e'>(пусто)</td></tr>"
            )
        add_form = ""
        if not demo:
            add_form = f"""
            <form action='/api/filters/add?token={token}' method='post' style='margin-top:8px;display:flex;gap:8px'>
                <input type='hidden' name='group' value='{key}'>
                <input type='text' name='value' placeholder='новая фраза...' style='margin-bottom:0;flex:1' required>
                <button type='submit' class='btn btn-primary btn-sm'>Добавить</button>
            </form>"""
        sections += f"""
        <div class='card'>
            <h2>{label}</h2>
            <table><tr><th>Фраза</th><th style='width:50px'></th></tr>{rows}</table>
            {add_form}
        </div>"""
    body = f"<h1>Управление фильтрами</h1>{msg_html}{sections}<p><a href='/?token={token}'>← Назад</a></p>"
    return head("Фильтры — Ferma", token, demo=demo) + body + foot()


@app.post("/api/filters/add")
async def api_filter_add(
    token: str | None = Query(None),
    group: str = Form(...),
    value: str = Form(...),
):
    check_auth(token)
    if is_demo(token):
        raise HTTPException(403, "Demo mode: actions disabled")
    from core.filter.manage import load_filters, save_filters

    f = load_filters()
    if group not in f:
        f[group] = []
    v = value.strip().lower()
    if v and v not in f[group]:
        f[group].append(v)
        save_filters(f)
    return RedirectResponse(
        f"/filters?token={token}&msg=%27{v}%27+added+to+{group}", 302
    )


@app.post("/api/filters/remove")
async def api_filter_remove(
    token: str | None = Query(None),
    group: str = Form(...),
    value: str = Form(...),
):
    check_auth(token)
    if is_demo(token):
        raise HTTPException(403, "Demo mode: actions disabled")
    from core.filter.manage import load_filters, save_filters

    f = load_filters()
    if group in f:
        f[group] = [x for x in f[group] if x != value.strip().lower()]
        save_filters(f)
    return RedirectResponse(
        f"/filters?token={token}&msg=%27{value}%27+removed+from+{group}", 302
    )


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
    if not CHANNEL_NAME_RE.match(name):
        return
    env_path = os.path.join(CHANNELS_DIR, name, ".env")
    if not os.path.exists(env_path):
        return
    from dotenv import dotenv_values

    cfg = dotenv_values(env_path)
    is_lightning = cfg.get("CHANNEL_TYPE", "") == "lightning"
    log_path = os.path.join(CHANNELS_DIR, name, "bot.log")
    if is_lightning:
        entry = f"core/lightning/run_lightning.py {env_path}"
    else:
        entry = f"core/run_channel.py {env_path}"
    cmd = (
        f"cd {FARM_DIR} && screen -dmS {name} bash -c "
        f'"PYTHONUNBUFFERED=1 exec {PYTHON} -u {entry} > {log_path} 2>&1"'
    )
    subprocess.run(cmd, shell=True, capture_output=True, timeout=10)


def main():
    port = int(os.environ.get("ADMIN_PORT", "8080"))
    host = os.environ.get("ADMIN_HOST", "0.0.0.0")
    print(f"Admin panel: http://{host}:{port}/?token={AUTH_TOKEN}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
