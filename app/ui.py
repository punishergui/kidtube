from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
@router.get("/channels", response_class=HTMLResponse)
@router.get("/kids", response_class=HTMLResponse)
@router.get("/sync", response_class=HTMLResponse)
def ui_index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html")
