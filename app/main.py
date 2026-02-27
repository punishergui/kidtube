from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="KidTube")


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def root() -> str:
    return "<html><body><h1>KidTube running</h1></body></html>"
