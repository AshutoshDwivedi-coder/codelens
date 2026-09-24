"""
main.py – FastAPI application entry point for CodeLens.

Registers all routers, CORS, middleware, and startup/shutdown events.
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

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


# ──────────────────────────── Root ────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "name": "CodeLens",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
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
