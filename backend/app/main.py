import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routers import patients, reports, doctors, memory, chat

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("healthmate.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting HealthMate Compass API (env=%s)...", settings.ENVIRONMENT)
    try:
        settings.validate_on_startup()
    except Exception as e:
        logger.exception("Non-fatal startup validation issue: %s", e)
    yield
    logger.info("Shutting down HealthMate Compass API.")


app = FastAPI(
    title="HealthMate Compass API",
    version="0.1.0",
    description="AI health-report translator + doctor chat + specialist finder.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS configuration
cors_origins = list(settings.CORS_ORIGINS)
if settings.FRONTEND_URL and settings.FRONTEND_URL not in cors_origins:
    cors_origins.append(settings.FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(patients.router)
app.include_router(reports.router)
app.include_router(doctors.router)
app.include_router(memory.router)
app.include_router(chat.router)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    """Liveness probe. Returns 200 immediately without external calls."""
    return {"status": "ok", "version": app.version, "environment": settings.ENVIRONMENT}


@app.get("/health/deep", tags=["meta"])
async def health_deep() -> dict:
    """Readiness probe. Checks database and LLM provider connectivity."""
    checks = {
        "status": "ok",
        "version": app.version,
        "environment": settings.ENVIRONMENT,
        "supabase": "unknown",
        "llm": "unknown",
        "places_api": "osm_fallback" if not settings.GOOGLE_PLACES_API_KEY else "google_places",
    }

    # Supabase connectivity check
    try:
        from app.core.supabase import get_supabase_admin
        supabase = get_supabase_admin()
        if supabase:
            res = supabase.table("patients").select("id").limit(1).execute()
            checks["supabase"] = "connected"
        else:
            checks["supabase"] = "unconfigured (missing keys)"
    except Exception as e:
        checks["supabase"] = f"error: {str(e)[:120]}"
        checks["status"] = "degraded"

    # LLM configuration check
    if settings.GEMINI_API_KEY:
        checks["llm"] = f"gemini ({settings.GEMINI_GEMMA_MODEL})"
    elif settings.OPENROUTER_API_KEY:
        checks["llm"] = f"openrouter ({settings.OPENROUTER_MODEL})"
    else:
        checks["llm"] = "missing_api_keys"
        checks["status"] = "degraded"

    return checks


@app.get("/api/helplines", tags=["meta"])
async def get_verified_helplines() -> list:
    """Returns verified Pakistan national helplines loaded from helplines.json."""
    from app.services.emergency import VERIFIED_HELPLINES
    return VERIFIED_HELPLINES
