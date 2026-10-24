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
raw_origins = list(settings.CORS_ORIGINS)
if settings.FRONTEND_URL:
    raw_origins.append(settings.FRONTEND_URL.strip().rstrip("/"))
raw_origins.append("https://healthmate-compass.vercel.app")
cors_origins = list(dict.fromkeys([o.rstrip("/") for o in raw_origins if o]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"^https://[a-zA-Z0-9\-]+(\.vercel\.app|\.onrender\.com)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
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


@app.get("/health/auth", tags=["meta"])
async def health_auth() -> dict:
    """
    Diagnostic probe for authentication configuration.
    Reports which required/optional auth variables are present (NAMES ONLY, NEVER VALUES)
    and whether Supabase client and JWKS can be contacted.
    """
    from app.core.supabase import get_supabase_admin
    from app.core.security import get_jwks_client

    env_vars = {
        "SUPABASE_URL": bool(settings.SUPABASE_URL),
        "SUPABASE_ANON_KEY": bool(settings.SUPABASE_ANON_KEY),
        "SUPABASE_SERVICE_ROLE_KEY": bool(settings.SUPABASE_SERVICE_ROLE_KEY),
        "SUPABASE_JWT_SECRET": bool(settings.SUPABASE_JWT_SECRET),
        "FRONTEND_URL": bool(settings.FRONTEND_URL),
    }

    all_required_present = bool(
        settings.SUPABASE_URL and settings.SUPABASE_ANON_KEY and settings.SUPABASE_SERVICE_ROLE_KEY
    )

    admin_client_ok = False
    supabase_reachable = False
    try:
        supabase = get_supabase_admin()
        if supabase is not None:
            admin_client_ok = True
            res = supabase.table("patients").select("id").limit(1).execute()
            supabase_reachable = True
    except Exception as e:
        logger.debug("Health auth check supabase ping: %s", e)

    jwks_client_ok = False
    jwks_keys_count = 0
    try:
        jwks = get_jwks_client()
        if jwks is not None:
            keys = jwks.get_signing_keys()
            jwks_client_ok = True
            jwks_keys_count = len(keys)
    except Exception as e:
        logger.debug("Health auth check jwks ping: %s", e)

    methods = []
    if jwks_client_ok:
        methods.append("jwks_asymmetric (ES256/RS256)")
    if settings.SUPABASE_JWT_SECRET:
        methods.append("legacy_hs256_secret")
    if admin_client_ok:
        methods.append("supabase_auth_api_fallback")

    return {
        "status": "ok" if (all_required_present and admin_client_ok) else "degraded",
        "environment": settings.ENVIRONMENT,
        "auth_configured": all_required_present,
        "variables_present": env_vars,
        "supabase_admin_client_initialized": admin_client_ok,
        "supabase_reachable": supabase_reachable,
        "jwks_client_initialized": jwks_client_ok,
        "jwks_cached_keys": jwks_keys_count,
        "verification_methods": methods,
    }


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
