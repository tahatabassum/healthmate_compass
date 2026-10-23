"""
HealthMate Compass — FastAPI application entry point.
Includes CORS, health probes, and API routers.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routers import patients, reports, doctors, memory, chat

app = FastAPI(
    title="HealthMate Compass API",
    version="0.1.0",
    description="AI health-report translator + doctor chat + specialist finder.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
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
    """Liveness probe. Returns 200 with status=ok."""
    return {"status": "ok", "version": app.version, "environment": settings.ENVIRONMENT}


@app.get("/api/helplines", tags=["meta"])
async def get_verified_helplines() -> list:
    """Returns verified Pakistan national helplines loaded from helplines.json."""
    from app.services.emergency import VERIFIED_HELPLINES
    return VERIFIED_HELPLINES
