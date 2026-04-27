import logging
import asyncio
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from backend.core.config import settings
from backend.api.routes import jobs, resume, pipeline, cover_letter
from backend.api.websocket import router as ws_router, manager as ws_manager
from backend.utils.cache import job_cache
from backend.utils.ollama_client import OllamaClient, OllamaConnectionError, OllamaModelNotFoundError

# ── Logging Setup ──────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Silence noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("multipart").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown lifecycle.

    Startup:
    - Load job cache from disk
    - Verify Ollama is reachable
    - Verify model is pulled and ready
    - Log system readiness

    Shutdown:
    - Persist cache to disk
    - Log clean shutdown
    """
    # ── STARTUP ────────────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("  AI Recruiter Pipeline — Starting Up")
    logger.info("=" * 60)

    startup_start = time.time()

    # ── 1. Load disk cache ─────────────────────────────────────────────────────
    logger.info("Loading job cache from disk...")
    try:
        await job_cache.load_from_disk()
        stats = await job_cache.stats()
        logger.info(
            f"Cache loaded — {stats['active']} active jobs, "
            f"{stats['expired']} expired"
        )
    except Exception as e:
        logger.warning(f"Cache load failed (non-fatal): {e}")

    # ── 2. Verify Ollama ───────────────────────────────────────────────────────
    logger.info(
        f"Checking Ollama at {settings.ollama_base_url} "
        f"with model '{settings.ollama_model}'..."
    )
    ollama = OllamaClient()
    try:
        await ollama.assert_ready()
        logger.info(
            f"Ollama ready — model '{settings.ollama_model}' available"
        )
    except OllamaConnectionError:
        logger.warning(
            f"Ollama unreachable at {settings.ollama_base_url}. "
            f"Pipeline will fail until Ollama is running. "
            f"Start it with: ollama serve"
        )
    except OllamaModelNotFoundError:
        logger.warning(
            f"Model '{settings.ollama_model}' not found. "
            f"Pull it with: ollama pull {settings.ollama_model}"
        )
    except Exception as e:
        logger.warning(f"Ollama check failed (non-fatal): {e}")

    # ── 3. Ready ───────────────────────────────────────────────────────────────
    elapsed = round(time.time() - startup_start, 2)
    logger.info("=" * 60)
    logger.info(f"  Server ready in {elapsed}s")
    logger.info(f"  API:  http://{settings.app_host}:{settings.app_port}")
    logger.info(f"  Docs: http://{settings.app_host}:{settings.app_port}/docs")
    logger.info(f"  WS:   ws://{settings.app_host}:{settings.app_port}/ws/pipeline")
    logger.info("=" * 60)

    yield

    # ── SHUTDOWN ───────────────────────────────────────────────────────────────
    logger.info("Shutting down...")

    # Persist cache
    try:
        await job_cache.save_to_disk()
        stats = await job_cache.stats()
        logger.info(f"Cache persisted — {stats['active']} jobs saved to disk")
    except Exception as e:
        logger.warning(f"Cache persist failed: {e}")

    logger.info(
        f"WebSocket connections closed: {ws_manager.client_count} active at shutdown"
    )
    logger.info("AI Recruiter Pipeline — Shutdown complete")


# ── App Factory ────────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Recruiter Pipeline",
        description=(
            "Multi-agent AI pipeline that scrapes job listings, "
            "matches them against your resume, scores opportunities by fit, "
            "and auto-drafts tailored cover letters. Powered by local Ollama LLMs."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── Middleware ─────────────────────────────────────────────────────────────

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url, "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # GZip compression for large job payloads
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # ── Request Timing Middleware ──────────────────────────────────────────────

    @app.middleware("http")
    async def add_timing_header(request: Request, call_next):
        """Add X-Response-Time header to every response."""
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Response-Time"] = f"{elapsed_ms}ms"
        return response

    # ── Global Exception Handler ───────────────────────────────────────────────

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(
            f"Unhandled exception on {request.method} {request.url.path}: {exc}"
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(exc) if settings.debug else "An unexpected error occurred.",
                "path": str(request.url.path),
            },
        )

    # ── Routers ────────────────────────────────────────────────────────────────

    API_PREFIX = "/api/v1"

    app.include_router(jobs.router,         prefix=API_PREFIX)
    app.include_router(resume.router,       prefix=API_PREFIX)
    app.include_router(pipeline.router,     prefix=API_PREFIX)
    app.include_router(cover_letter.router, prefix=API_PREFIX)
    app.include_router(ws_router)           # WebSocket — no prefix, /ws/pipeline

    # ── Health & Meta Endpoints ────────────────────────────────────────────────

    @app.get("/", tags=["Health"], summary="Root")
    async def root():
        return {
            "name": "AI Recruiter Pipeline",
            "version": "1.0.0",
            "status": "running",
            "docs": "/docs",
            "websocket": "/ws/pipeline",
        }

    @app.get("/health", tags=["Health"], summary="Health check")
    async def health():
        """
        Comprehensive health check.
        Returns status of all subsystems.
        """
        ollama = OllamaClient()
        ollama_ok = await ollama.health_check()
        model_ok = await ollama.is_model_available() if ollama_ok else False
        cache_stats = await job_cache.stats()

        all_healthy = ollama_ok and model_ok

        return JSONResponse(
            status_code=200 if all_healthy else 207,   # 207 = partial
            content={
                "status": "healthy" if all_healthy else "degraded",
                "subsystems": {
                    "ollama": {
                        "status": "ok" if ollama_ok else "unreachable",
                        "url": settings.ollama_base_url,
                    },
                    "model": {
                        "status": "ok" if model_ok else "not_found",
                        "model": settings.ollama_model,
                    },
                    "cache": {
                        "status": "ok",
                        "active_jobs": cache_stats["active"],
                        "total_jobs": cache_stats["total"],
                    },
                    "websocket": {
                        "status": "ok",
                        "active_connections": ws_manager.client_count,
                    },
                },
            },
        )

    @app.get("/health/ollama", tags=["Health"], summary="Ollama health check")
    async def health_ollama():
        """Quick Ollama connectivity check."""
        ollama = OllamaClient()
        reachable = await ollama.health_check()
        model_ready = await ollama.is_model_available() if reachable else False

        if not reachable:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unreachable",
                    "message": (
                        f"Cannot reach Ollama at {settings.ollama_base_url}. "
                        f"Run: ollama serve"
                    ),
                },
            )
        if not model_ready:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "model_missing",
                    "message": (
                        f"Model '{settings.ollama_model}' not found. "
                        f"Run: ollama pull {settings.ollama_model}"
                    ),
                },
            )
        return {
            "status": "ok",
            "model": settings.ollama_model,
            "url": settings.ollama_base_url,
        }

    return app


# ── App Instance ───────────────────────────────────────────────────────────────

app = create_app()


# ── Dev Entry Point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
        ws_ping_interval=20,
        ws_ping_timeout=30,
    )