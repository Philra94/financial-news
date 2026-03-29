from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agents.paths import FRONTEND_DIST_DIR, ensure_directories
from web.backend.routers import briefings, research, settings, status

ensure_directories()

app = FastAPI(title="Financial News")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(briefings.router)
app.include_router(research.router)
app.include_router(settings.router)
app.include_router(status.router)

assets_dir = FRONTEND_DIST_DIR / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")


@app.get("/healthz")
def healthcheck() -> dict:
    return {"ok": True}


@app.get("/{full_path:path}")
def spa(full_path: str) -> FileResponse:
    index_path = FRONTEND_DIST_DIR / "index.html"
    if not index_path.exists():
        raise FileNotFoundError(f"Frontend build not found at {index_path}")
    return FileResponse(index_path)
