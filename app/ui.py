from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
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
        "default-src 'self'; "
        "img-src 'self' data: https://i.ytimg.com https:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' https://www.youtube.com; "
        "frame-src https://www.youtube-nocookie.com https://www.youtube.com; "
        "connect-src 'self'"
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@router.get("/", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
def ui_dashboard(request: Request) -> HTMLResponse:
    return render_page(request, "dashboard.html", page="dashboard", nav_mode="kid")


@router.get('/admin', response_class=HTMLResponse)
def ui_admin_home(request: Request) -> HTMLResponse:
    return render_page(request, 'admin.html', page='admin', nav_mode='admin')


@router.get('/admin/channels', response_class=HTMLResponse)
def ui_admin_channels(request: Request) -> HTMLResponse:
    return render_page(request, 'channels.html', page='channels', nav_mode='admin')


@router.get('/admin/kids', response_class=HTMLResponse)
def ui_admin_kids(request: Request) -> HTMLResponse:
    return render_page(request, 'kids.html', page='kids', nav_mode='admin')


@router.get('/admin/sync', response_class=HTMLResponse)
def ui_admin_sync(request: Request) -> HTMLResponse:
    return render_page(request, 'sync.html', page='sync', nav_mode='admin')


@router.get('/channels')
def ui_channels_redirect() -> RedirectResponse:
    return RedirectResponse(url='/admin/channels', status_code=307)


@router.get('/kids')
def ui_kids_redirect() -> RedirectResponse:
    return RedirectResponse(url='/admin/kids', status_code=307)


@router.get('/sync')
def ui_sync_redirect() -> RedirectResponse:
    return RedirectResponse(url='/admin/sync', status_code=307)


@router.get("/watch/{youtube_id}", response_class=HTMLResponse)
def ui_watch(request: Request, youtube_id: str) -> HTMLResponse:
    embed_origin = str(request.base_url).rstrip("/")
    return render_page(
        request,
        "watch.html",
        page="watch",
        youtube_id=youtube_id,
        embed_origin=embed_origin,
        nav_mode='kid',
    )
