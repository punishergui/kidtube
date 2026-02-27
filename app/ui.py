from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def render_page(request: Request, template_name: str, **context: str) -> HTMLResponse:
    response = templates.TemplateResponse(
        request=request,
        name=template_name,
        context=context,
    )
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self'; "
        "frame-src https://www.youtube-nocookie.com https://www.youtube.com"
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@router.get("/", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
def ui_dashboard(request: Request) -> HTMLResponse:
    return render_page(request, "dashboard.html", page="dashboard")


@router.get("/channels", response_class=HTMLResponse)
def ui_channels(request: Request) -> HTMLResponse:
    return render_page(request, "channels.html", page="channels")


@router.get("/kids", response_class=HTMLResponse)
def ui_kids(request: Request) -> HTMLResponse:
    return render_page(request, "kids.html", page="kids")


@router.get("/sync", response_class=HTMLResponse)
def ui_sync(request: Request) -> HTMLResponse:
    return render_page(request, "sync.html", page="sync")


@router.get("/watch/{youtube_id}", response_class=HTMLResponse)
def ui_watch(request: Request, youtube_id: str) -> HTMLResponse:
    return render_page(request, "watch.html", page="watch", youtube_id=youtube_id)
