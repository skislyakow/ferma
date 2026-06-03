import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn

from core.analytics import FarmAnalytics

AUTH_TOKEN = os.environ.get("ADMIN_TOKEN", "ferma2026")
CHANNELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "channels")

app = FastAPI(title="Ferma Admin")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


def check_auth(token: str | None = None):
    if token != AUTH_TOKEN:
        raise HTTPException(401, "Invalid token")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, token: str = Query(None)):
    check_auth(token)
    analytics = FarmAnalytics()
    statuses = analytics.farm_status()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "statuses": statuses,
        "token": token,
    })


@app.get("/channel/{name}", response_class=HTMLResponse)
async def channel_detail(name: str, request: Request, token: str = Query(None)):
    check_auth(token)
    analytics = FarmAnalytics()
    stats = analytics.channel_stats(name)
    if "error" in stats:
        return HTMLResponse(f"Channel '{name}' not found", 404)
    return templates.TemplateResponse("channel.html", {
        "request": request,
        "s": stats,
        "token": token,
    })


@app.get("/logs/{name}", response_class=HTMLResponse)
async def view_logs(name: str, request: Request, lines: int = 50, token: str = Query(None)):
    check_auth(token)
    log_path = os.path.join(CHANNELS_DIR, name, "bot.log")
    if not os.path.exists(log_path):
        return HTMLResponse(f"No log for '{name}'", 404)
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()
        tail = all_lines[-lines:]
    return templates.TemplateResponse("logs.html", {
        "request": request,
        "channel": name,
        "lines": tail,
        "token": token,
    })


def main():
    port = int(os.environ.get("ADMIN_PORT", "8080"))
    host = os.environ.get("ADMIN_HOST", "0.0.0.0")
    print(f"Admin panel: http://{host}:{port}/?token={AUTH_TOKEN}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
