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
<div class='nav'><a href='/?token={token}'>Dashboard</a><a href='/add?token={token}'>+ Add Channel</a></div>"""

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
        cls = "msg-success" if not msg.startswith("Error") else "msg-error"
        msg_html = f"<div class='{cls}'>{msg}</div>"
    cards = ""
    for s in statuses:
        if "error" in s:
            cards += f"<div class='card'><h2>{s['name']}</h2><p>Error: {s['error']}</p></div>"
            continue
        running = screen_running(s["name"])
        status_tag = "<span style='color:#3fb950'>● Running</span>" if running else "<span style='color:#f85149'>● Stopped</span>"
        cards += f"""
        <div class='card'>
            <h2 style='margin-top:0'><a href='/channel/{s['name']}?token={token}'>{s['name']}</a> <span style='float:right;font-size:13px;color:#8b949e'>@{s['target']}</span></h2>
            <div class='stat'><span class='label'>Status</span><span class='value'>{status_tag}</span></div>
            <div class='stat'><span class='label'>Subscribers</span><span class='value'>{s['subscribers']}</span></div>
            <div class='stat'><span class='label'>Donors</span><span class='value'>{s['donors']}</span></div>
            <div class='stat'><span class='label'>DB total</span><span class='value'>{s['db']['total']}</span></div>
            <div class='stat'><span class='label'>Published</span><span class='value'>{s['db']['published']}</span></div>
            <div class='stat'><span class='label'>Skipped</span><span class='value'>{s['db']['skipped']}</span></div>
            <div class='stat'><span class='label'>Videos</span><span class='value'>{s['db']['video']}</span></div>
            <p style='margin-top:10px'>
                <a href='/logs/{s['name']}?token={token}'>[logs]</a>
                {'<a href="/channel/' + s['name'] + '?token=' + token + '" class="btn btn-primary btn-sm">Manage</a>' if not running else ''}
            </p>
        </div>"""
    body = f"<h1>Farm Dashboard</h1>{msg_html}<div class='grid'>{cards}</div>"
    return head("Dashboard — Ferma", token) + body + foot()


@app.get("/add", response_class=HTMLResponse)
async def add_channel_form(token: str = Query(None)):
    check_auth(token)
    body = f"""
    <h1>Add Channel</h1>
    <form action='/api/channel/create?token={token}' method='post'>
        <div class='form-group'><label>Channel name (directory)</label><input type='text' name='name' placeholder='e.g. tech' required></div>
        <div class='form-group'><label>BOT_TOKEN</label><input type='text' name='bot_token' placeholder='123456:ABC-DEF1234' required></div>
        <div class='form-group'><label>TARGET_CHANNEL</label><input type='text' name='target_channel' placeholder='@my_channel' required></div>
        <div class='form-group'><label>SOURCE_CHANNELS (comma-separated)</label><input type='text' name='source_channels' placeholder='@donor1,@donor2' required></div>
        <div class='form-row'>
            <div class='form-group'><label>PUBLISH_INTERVAL_HOURS</label><input type='number' name='publish_interval_hours' value='0.5' step='0.1'></div>
            <div class='form-group'><label>POSTS_PER_CYCLE</label><input type='number' name='posts_per_cycle' value='2'></div>
        </div>
        <div class='form-row'>
            <div class='form-group'><label>SOURCE_LANG</label><input type='text' name='source_lang' value='en'></div>
            <div class='form-group'><label>TARGET_LANG</label><input type='text' name='target_lang' value='ru'></div>
        </div>
        <div class='form-group'><label>CPA_LINKS (optional, comma-separated)</label><input type='text' name='cpa_links' placeholder='https://...'></div>
        <div class='form-row'>
            <div class='form-group'><label>CPA_INSERT_EVERY</label><input type='number' name='cpa_insert_every' value='3'></div>
            <div class='form-group'><label>Start after creation</label><input type='checkbox' name='start_now' value='1' style='width:auto;margin-top:8px' checked></div>
        </div>
        <p style='margin-top:16px'><button type='submit' class='btn btn-primary'>Create Channel</button> <a href='/?token={token}' class='btn btn-warning'>Cancel</a></p>
    </form>"""
    return head("Add Channel — Ferma", token) + body + foot()


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
        return RedirectResponse(f"/?token={token}&msg=Error%3A+channel+%27{name}%27+already+exists", 302)

    # Validate bot token
    bot_username = get_bot_name(bot_token)
    if bot_username == "?":
        return RedirectResponse(f"/?token={token}&msg=Error%3A+invalid+BOT_TOKEN+for+%27{name}%27", 302)

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

    return RedirectResponse(f"/?token={token}&msg=Channel+%27{name}%27+created+%28%40{target}%29", 302)


@app.post("/api/channel/{name}/start")
async def api_start_channel(name: str, token: str = Query(None)):
    check_auth(token)
    _start_screen(name)
    return RedirectResponse(f"/?token={token}&msg={name}+started", 302)


@app.post("/api/channel/{name}/stop")
async def api_stop_channel(name: str, token: str = Query(None)):
    check_auth(token)
    subprocess.run(["screen", "-S", name, "-X", "quit"], capture_output=True, timeout=5)
    return RedirectResponse(f"/?token={token}&msg={name}+stopped", 302)


@app.post("/api/channel/{name}/delete")
async def api_delete_channel(name: str, token: str = Query(None)):
    check_auth(token)
    ch_dir = os.path.join(CHANNELS_DIR, name)
    if not os.path.exists(ch_dir):
        return RedirectResponse(f"/?token={token}&msg=Error%3A+channel+%27{name}%27+not+found", 302)

    # Stop screen first
    subprocess.run(["screen", "-S", name, "-X", "quit"], capture_output=True, timeout=5)

    import shutil
    shutil.rmtree(ch_dir)
    return RedirectResponse(f"/?token={token}&msg=Channel+%27{name}%27+deleted", 302)


@app.get("/channel/{name}", response_class=HTMLResponse)
async def channel_detail(name: str, token: str = Query(None)):
    check_auth(token)
    analytics = FarmAnalytics()
    s = analytics.channel_stats(name)
    if "error" in s:
        return HTMLResponse(f"Channel '{name}' not found", 404)
    posts = ""
    for p in s.get("last_posts", []):
        posts += f"<div class='stat'><span class='label'>#{p['id']} {p['date'][:16]}</span><span class='value'>👁 {p['views']} 💬 {p['reactions']}</span></div>"
    running = screen_running(name)
    status_tag = "<span style='color:#3fb950'>● Running</span>" if running else "<span style='color:#f85149'>● Stopped</span>"
    body = f"""
    <h1>{s['name']} <span style='font-size:14px;color:#8b949e'>@{s['target']}</span></h1>
    <div class='grid'>
        <div class='card'>
            <h2>Stats</h2>
            <div class='stat'><span class='label'>Status</span><span class='value'>{status_tag}</span></div>
            <div class='stat'><span class='label'>Subscribers</span><span class='value'>{s['subscribers']}</span></div>
            <div class='stat'><span class='label'>Donors</span><span class='value'>{s['donors']}</span></div>
            <div class='stat'><span class='label'>DB total</span><span class='value'>{s['db']['total']}</span></div>
            <div class='stat'><span class='label'>Published</span><span class='value'>{s['db']['published']}</span></div>
            <div class='stat'><span class='label'>Skipped</span><span class='value'>{s['db']['skipped']}</span></div>
            <div class='stat'><span class='label'>Videos</span><span class='value'>{s['db']['video']}</span></div>
        </div>
        <div class='card'>
            <h2>Last Posts</h2>
            {posts if posts else "<div class='stat'><span class='label'>No posts yet</span></div>"}
            <p style='margin-top:10px'><a href='/logs/{name}?token={token}'>View logs</a></p>
        </div>
    </div>
    <div class='card'>
        <h2>Actions</h2>
        <p style='margin-top:8px'>
            <form action='/api/channel/{name}/start?token={token}' method='post' style='display:inline'>
                <button type='submit' class='btn btn-primary btn-sm' {'disabled' if running else ''}>▶ Start</button>
            </form>
            <form action='/api/channel/{name}/stop?token={token}' method='post' style='display:inline'>
                <button type='submit' class='btn btn-warning btn-sm' {'disabled' if not running else ''}>⏹ Stop</button>
            </form>
            <form action='/api/channel/{name}/delete?token={token}' method='post' style='display:inline' onsubmit='return confirm("Delete {name} and all data?")'>
                <button type='submit' class='btn btn-danger btn-sm'>🗑 Delete</button>
            </form>
        </p>
    </div>
    <p><a href='/?token={token}'>← Back</a></p>"""
    return head(f"{name} — Ferma", token) + body + foot()


@app.get("/logs/{name}", response_class=HTMLResponse)
async def view_logs(name: str, lines: int = 50, token: str = Query(None)):
    check_auth(token)
    log_path = os.path.join(CHANNELS_DIR, name, "bot.log")
    if not os.path.exists(log_path):
        return HTMLResponse(f"No log for '{name}'", 404)
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()
        tail = all_lines[-lines:]
    body = f"<h1>Logs: {name}</h1><p><a href='/channel/{name}?token={token}'>← Back to channel</a></p><pre>{''.join(tail)}</pre>"
    return head(f"Logs: {name} — Ferma", token) + body + foot()


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
