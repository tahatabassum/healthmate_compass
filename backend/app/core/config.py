"""
Configuration settings for HealthMate Compass backend.
Loaded from environment variables or .env file using pydantic-settings.
"""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8-sig",
        extra="ignore",
    )

    # Gemini API (Primary LLM Provider)
    GEMINI_API_KEY: str = ""
    GEMINI_GEMMA_MODEL: str = "gemma-4-26b-a4b-it"
    GEMINI_EMBED_MODEL: str = "gemini-embedding-001"
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    # OpenRouter (Fallback LLM Provider)
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "google/gemma-4-26b-a4b-it"
    OPENROUTER_MODEL_FREE: str = "google/gemma-4-26b-a4b-it:free"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Supabase (Database, Auth & Storage)
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_JWT_SECRET: Optional[str] = None

    # Google Places API (New)
    GOOGLE_PLACES_API_KEY: str = ""

    # Frontend URL (for Vercel deployment)
    FRONTEND_URL: Optional[str] = None

    # App Environment
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    def validate_on_startup(self) -> None:
        """Logs warnings for missing configuration without leaking values or crashing startup."""
        import logging
        logger = logging.getLogger("healthmate.config")
        missing_required = []
        if not self.SUPABASE_URL:
            missing_required.append("SUPABASE_URL")
        if not self.SUPABASE_SERVICE_ROLE_KEY and not self.SUPABASE_ANON_KEY:
            missing_required.append("SUPABASE_SERVICE_ROLE_KEY / SUPABASE_ANON_KEY")
        if not self.GEMINI_API_KEY and not self.OPENROUTER_API_KEY:
            missing_required.append("GEMINI_API_KEY or OPENROUTER_API_KEY")

        if missing_required:
            logger.warning(
                "CRITICAL ENV VARS MISSING: %s. Some features may fail at runtime.",
                ", ".join(missing_required),
            )
        else:
            logger.info("Core database and LLM credentials are configured.")

        if not self.GOOGLE_PLACES_API_KEY:
            logger.info(
                "GOOGLE_PLACES_API_KEY is not set (optional). Fallback to OpenStreetMap and curated doctors will be active."
            )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
