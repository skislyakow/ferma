import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse
import uvicorn

from core.analytics import FarmAnalytics

AUTH_TOKEN = os.environ.get("ADMIN_TOKEN", "ferma2026")
CHANNELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "channels")

app = FastAPI(title="Ferma Admin")

CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,system-ui,sans-serif; background:#0d1117; color:#c9d1d9; padding:20px; }
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
.nav { margin-bottom:20px; padding:10px 0; border-bottom:1px solid #30363d; }
.nav a { margin-right:16px; font-size:14px; }
"""

def head(title, token):
    return f"<!DOCTYPE html><html lang='ru'><head><meta charset='utf-8'><title>{title}</title><style>{CSS}</style></head><body><div class='nav'><a href='/?token={token}'>Dashboard</a></div>"

def foot():
    return "</body></html>"

def check_auth(token):
    if token != AUTH_TOKEN:
        raise HTTPException(401, "Invalid token")


@app.get("/", response_class=HTMLResponse)
async def dashboard(token: str = Query(None)):
    check_auth(token)
    analytics = FarmAnalytics()
    statuses = analytics.farm_status()
    cards = ""
    for s in statuses:
        if "error" in s:
            cards += f"<div class='card'><h2>{s['name']}</h2><p>Error: {s['error']}</p></div>"
            continue
        cards += f"""
        <div class='card'>
            <h2 style='margin-top:0'><a href='/channel/{s['name']}?token={token}'>{s['name']}</a> <span style='float:right;font-size:13px;color:#8b949e'>@{s['target']}</span></h2>
            <div class='stat'><span class='label'>Subscribers</span><span class='value'>{s['subscribers']}</span></div>
            <div class='stat'><span class='label'>Donors</span><span class='value'>{s['donors']}</span></div>
            <div class='stat'><span class='label'>DB total</span><span class='value'>{s['db']['total']}</span></div>
            <div class='stat'><span class='label'>Published</span><span class='value'>{s['db']['published']}</span></div>
            <div class='stat'><span class='label'>Skipped</span><span class='value'>{s['db']['skipped']}</span></div>
            <div class='stat'><span class='label'>Videos</span><span class='value'>{s['db']['video']}</span></div>
            <p style='margin-top:10px'><a href='/logs/{s['name']}?token={token}'>[logs]</a></p>
        </div>"""
    body = f"<h1>Farm Dashboard</h1><div class='grid'>{cards}</div>"
    return head("Dashboard — Ferma", token) + body + foot()


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
    body = f"""
    <h1>{s['name']} <span style='font-size:14px;color:#8b949e'>@{s['target']}</span></h1>
    <div class='grid'>
        <div class='card'>
            <h2>Stats</h2>
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
        </div>
    </div>
    <p><a href='/logs/{name}?token={token}'>View logs</a></p>
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


def main():
    port = int(os.environ.get("ADMIN_PORT", "8080"))
    host = os.environ.get("ADMIN_HOST", "0.0.0.0")
    print(f"Admin panel: http://{host}:{port}/?token={AUTH_TOKEN}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
