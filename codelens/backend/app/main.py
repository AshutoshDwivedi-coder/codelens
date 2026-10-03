"""
main.py – FastAPI application entry point for CodeLens.

Registers all routers, CORS, middleware, and startup/shutdown events.
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

import os
from pathlib import Path

# Prevent HuggingFace tokenizer parallelism warnings and deadlocks.
# OMP threads = 1 avoids CPU thrashing on Render's single-core free tier.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
try:
    import torch
    torch.set_num_threads(1)
    if hasattr(torch, "set_num_interop_threads"):
        torch.set_num_interop_threads(1)
    torch.set_grad_enabled(False)
except Exception:
    pass

# Store HuggingFace model cache in project directory so build-time cache persists to runtime
_hf_dir = Path(__file__).resolve().parent.parent / ".hf_cache"
_hf_dir.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(_hf_dir))

# On Render free tier the source directory is ephemeral / read-only at runtime.
# Default INDEXES_DIR and CLONED_REPOS_DIR to /tmp (always writable) unless
# the operator explicitly sets a persistent-disk path.
if not os.environ.get("INDEXES_DIR"):
    _idx = Path("/tmp/codelens_indexes")
    _idx.mkdir(parents=True, exist_ok=True)
    os.environ["INDEXES_DIR"] = str(_idx)
if not os.environ.get("CLONED_REPOS_DIR"):
    _repos = Path("/tmp/codelens_repos")
    _repos.mkdir(parents=True, exist_ok=True)
    os.environ["CLONED_REPOS_DIR"] = str(_repos)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

# ──────────────────────────── Logging ──────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger("codelens.main")

# ──────────────────────────── App factory ─────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("CodeLens API starting up…")
    # Pre-initialise cache
    from app.config import settings
    from app.cache import get_cache
    cache = get_cache(
        redis_url=settings.redis_url,
        ttl=settings.cache_ttl_seconds,
        max_size=settings.query_cache_max_size,
    )
    logger.info("Cache backend: %s", cache.backend_name)
    yield
    logger.info("CodeLens API shutting down…")


app = FastAPI(
    title="CodeLens API",
    version="1.0.0",
    description="CPU-only, version-aware code retrieval system",
    lifespan=lifespan,
)

# ──────────────────────────── Middleware ───────────────────────────────────

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    response.headers["X-Response-Time-Ms"] = str(elapsed_ms)
    return response


# ──────────────────────────── Routers ─────────────────────────────────────

from app.api.search import router as search_router
from app.api.index_api import router as index_router
from app.api.readme_api import router as readme_router

app.include_router(search_router, prefix="/api")
app.include_router(index_router, prefix="/api")
app.include_router(readme_router, prefix="/api")


# ──────────────────────────── Frontend Serving ────────────────────────────
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Path to the built frontend (relative to the backend directory where uvicorn is run)
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "../../frontend/dist")

if os.path.isdir(FRONTEND_DIST):
    # Mount the 'assets' directory or other static files
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    # Serve files like vite.svg, etc., if needed, though they might be in root
    # A cleaner approach for SPA is to catch all non-API routes:
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Allow requests to /api/health to pass through (or let FastAPI handle prior routes)
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"error": "Not found"})
        
        # Check if the exact file exists in dist (e.g. /vite.svg, /favicon.ico)
        file_path = os.path.join(FRONTEND_DIST, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
            
        # Fallback to index.html for SPA routing
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
else:
    @app.get("/")
    async def root():
        return {
            "name": "CodeLens",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/api/health",
            "note": "Frontend dist directory not found. Please build the frontend."
        }


# ──────────────────────────── Exception handler ────────────────────────────

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


# ──────────────────────────── Dev entrypoint ──────────────────────────────

if __name__ == "__main__":
    import uvicorn
    from app.config import settings
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="info",
    )
