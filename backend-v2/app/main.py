import os
import socket
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Allocator (deployment test)")

# React build lands here: copied by the Dockerfile, or by you when running without Docker.
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


# ---------- API routes (always registered first) ----------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/info")
def info():
    # APP_ENV and DB_PASSWORD come from environment variables:
    # .env locally, Container App env vars / secrets in Azure.
    return {
        "environment": os.getenv("APP_ENV", "local"),
        "version": os.getenv("APP_VERSION", "dev"),
        "secret_configured": bool(os.getenv("DB_PASSWORD")),
        "hostname": socket.gethostname(),
    }


@app.get("/api/projects")
def projects():
    return [
        {"id": 1, "name": "Store remodel tracker", "owner": "Real Estate Systems", "hours": 320},
        {"id": 2, "name": "Lease data migration", "owner": "FinTech", "hours": 180},
        {"id": 3, "name": "Capacity forecast v2", "owner": "Allocator team", "hours": 240},
    ]


# ---------- React frontend (registered last) ----------

if (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


@app.get("/{full_path:path}")
def spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    file = STATIC_DIR / full_path
    if full_path and file.is_file():
        return FileResponse(file)
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "Frontend not built yet. Run npm run build in frontend-v2 or use Docker."}
