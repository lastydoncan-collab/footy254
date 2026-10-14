"""
FOOTY254 - application entry point.

One process serves both the JSON API (under /api) and the built React app
(everything else), on the SAME origin. That single decision is what lets the
product run on any device and network: there is no hard-coded API address in
the browser, cookies are first-party, and no CORS configuration is needed.
"""

import logging
import os
from importlib import import_module
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from time import time

from dotenv import load_dotenv

# Load .env BEFORE any project module is imported: configuration modules read
# os.getenv() at import time.
load_dotenv()

from fastapi import APIRouter, FastAPI, Request  # noqa: E402
from fastapi.concurrency import run_in_threadpool  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.middleware.gzip import GZipMiddleware  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
RateLimitExceeded = import_module("slowapi.errors").RateLimitExceeded  # noqa: E402
from starlette.staticfiles import StaticFiles  # noqa: E402

from config import settings  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)

# Fail fast on an unusable signing secret, before anything else is imported
# that could depend on it.
settings.validate_jwt_secret()

from api.account import router as account_router  # noqa: E402
from api.admin import router as admin_router  # noqa: E402
from api.card_payments import router as card_router  # noqa: E402
from api.fixtures import router as fixtures_router  # noqa: E402
from api.mpesa import router as mpesa_router  # noqa: E402
from api.predictions import router as predictions_router  # noqa: E402
from api.subscriptions import router as subscriptions_router  # noqa: E402
from api.synchronization import router as synchronization_router  # noqa: E402
from database.db_config import check_database, close_pool  # noqa: E402
from database.team_repository import get_all_teams  # noqa: E402
from ml_pipeline.api.auth import router as auth_router  # noqa: E402
from ml_pipeline.core.model_loader import load_all_cached, model_status  # noqa: E402
from security.http_guards import (  # noqa: E402
    OriginGuardMiddleware,
    SecurityHeadersMiddleware,
)
from security.rate_limiter import limiter  # noqa: E402
from services.cache import ttl_cache  # noqa: E402

APP_START_TIME = time()


# ==========================================================
# LIFESPAN (startup / shutdown)
# ==========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.RUN_MIGRATIONS_ON_STARTUP:
        from database.migrate import apply_migrations

        try:
            applied = await run_in_threadpool(apply_migrations)

            if applied:
                logger.info("Database migrations applied: %s", ", ".join(applied))
        except Exception:
            logger.exception("Database migration failed.")

            if settings.IS_PRODUCTION:
                # Refuse to serve against a schema we could not verify; the
                # container orchestrator will retry once the database is ready.
                raise

    try:
        await run_in_threadpool(load_all_cached)
        logger.info("Machine learning models loaded successfully.")
    except Exception:
        logger.exception("Failed loading ML artifacts during startup.")

    scheduler_started = False

    if settings.ENABLE_SCHEDULER:
        from services.scheduler import start_scheduler

        start_scheduler()
        scheduler_started = True
        logger.info("Background scheduler started.")

    try:
        yield
    finally:
        if scheduler_started:
            from services.scheduler import stop_scheduler

            stop_scheduler()

        close_pool()
        logger.info("FOOTY254 backend stopped.")


app = FastAPI(
    title="FOOTY254 AI Prediction API",
    version="2.1.0",
    description="Real-Time AI Football Prediction Backend",
    lifespan=lifespan,
    docs_url=f"{settings.API_PREFIX}/docs" if settings.ENABLE_DOCS else None,
    redoc_url=None,
    openapi_url=f"{settings.API_PREFIX}/openapi.json" if settings.ENABLE_DOCS else None,
)

# ==========================================================
# ERROR HANDLING
# ==========================================================

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: Exception):
    # slowapi's default body uses an "error" key; every client of this API
    # reads "detail".
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please wait a moment and try again."},
        headers={"Retry-After": "60"},
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    """Turn pydantic's error list into one readable string under "detail"."""

    errors = exc.errors()
    first = errors[0] if errors else {}

    message = str(first.get("msg", "Invalid request."))

    if message.startswith("Value error, "):
        message = message[len("Value error, "):]
    else:
        field = [
            str(part)
            for part in first.get("loc", ())
            if part not in ("body", "query", "path")
        ]

        if field:
            label = field[-1].replace("_", " ").capitalize()
            message = f"{label}: {message}"

    return JSONResponse(status_code=422, content={"detail": message})


# ==========================================================
# MIDDLEWARE  (last added = outermost)
# ==========================================================

app.add_middleware(GZipMiddleware, minimum_size=1024)

app.add_middleware(
    SecurityHeadersMiddleware,
    csp_connect_src=" ".join(settings.EXTRA_ORIGINS),
)

app.add_middleware(OriginGuardMiddleware)

# Same-origin deployments need no CORS. It is only enabled for explicitly
# listed origins (a separately hosted frontend, or the Vite dev server).
if settings.ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

# ==========================================================
# API ROUTES (all under /api)
# ==========================================================

api_router = APIRouter(prefix=settings.API_PREFIX)

for router in (
    auth_router,
    account_router,
    admin_router,
    fixtures_router,
    predictions_router,
    synchronization_router,
    subscriptions_router,
    card_router,
    mpesa_router,
):
    api_router.include_router(router)


@ttl_cache(60)
def _cached_teams():
    return get_all_teams()


@api_router.get("/health", tags=["System"])
def health():
    database_ok = True
    database_error = None
    model_loaded = True
    model_error = None
    teams = 0

    try:
        check_database()
        teams = len(_cached_teams())
    except Exception as exc:
        database_ok = False
        database_error = str(exc)

    try:
        load_all_cached()
    except Exception as exc:
        model_loaded = False
        model_error = str(exc)

    expose = settings.EXPOSE_ERROR_DETAILS

    return {
        "status": "healthy" if database_ok and model_loaded else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": round(time() - APP_START_TIME, 2),
        "database": {
            "connected": database_ok,
            "error": database_error if expose else None,
            "historical_teams": teams,
        },
        "machine_learning": {
            "loaded": model_loaded,
            "error": model_error if expose else None,
            "artifacts": model_status(),
        },
    }


@api_router.get("/model/status", tags=["System"])
def model_information():
    loaded = True
    error = None

    try:
        load_all_cached()
    except Exception as exc:
        loaded = False
        error = str(exc)

    return {
        "loaded": loaded,
        "error": error if settings.EXPOSE_ERROR_DETAILS else None,
        "artifacts": model_status(),
    }


@api_router.get("/teams", tags=["System"])
def teams():
    items = _cached_teams()

    return {"count": len(items), "teams": items}


app.include_router(api_router)

# Daraja callbacks registered before the /api prefix existed keep working.
app.include_router(mpesa_router, include_in_schema=False)


@app.get("/healthz", include_in_schema=False)
def liveness():
    """Process liveness for load balancers / Docker (touches nothing external)."""

    return {"status": "ok"}


@app.get("/health", include_in_schema=False)
def legacy_health():
    return health()


# ==========================================================
# SINGLE-PAGE APP (built React dashboard)
# ==========================================================

DIST = settings.FRONTEND_DIST.resolve()
INDEX_FILE = DIST / "index.html"


class ImmutableStaticFiles(StaticFiles):
    """Vite fingerprints everything in /assets, so it can be cached forever."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)

        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"

        return response


if INDEX_FILE.is_file():
    if (DIST / "assets").is_dir():
        app.mount("/assets", ImmutableStaticFiles(directory=DIST / "assets"), name="assets")

    def _static_response(path):
        # index.html and the service worker must always be revalidated or users
        # get stuck on an old build; other root files (icons) can be cached.
        if path.name in {"index.html", "sw.js", "manifest.webmanifest"}:
            cache = "no-cache"
        else:
            cache = "public, max-age=3600"

        return FileResponse(path, headers={"Cache-Control": cache})

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def spa(full_path: str):
        # Unknown API paths must be a real 404, never the HTML shell.
        if full_path == settings.API_PREFIX.strip("/") or full_path.startswith(
            settings.API_PREFIX.strip("/") + "/"
        ):
            return JSONResponse(status_code=404, content={"detail": "Not found."})

        if full_path:
            candidate = (DIST / full_path).resolve()

            if candidate.is_file() and candidate.is_relative_to(DIST):
                return _static_response(candidate)

        # Client-side route (/predictions, /login, ...): hand over the app shell.
        return _static_response(INDEX_FILE)

else:

    @app.get("/", include_in_schema=False)
    def root():
        return {
            "application": "FOOTY254",
            "version": app.version,
            "status": "Running",
            "frontend": "not built - run 'npm run build' in footy254-dashboard/, "
            "or use the Vite dev server",
            "docs": f"{settings.API_PREFIX}/docs" if settings.ENABLE_DOCS else None,
            "health": f"{settings.API_PREFIX}/health",
        }


# ==========================================================
# `python main.py` convenience launcher (any OS)
# ==========================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        proxy_headers=True,
        forwarded_allow_ips=os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1"),
    )
