"""
Configuration settings for HealthMate Compass backend.
Loaded from environment variables or .env file using pydantic-settings.
"""
from typing import Optional, Any
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


def _clean_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip().strip("'\"")


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

    @field_validator("SUPABASE_URL", mode="before")
    @classmethod
    def clean_supabase_url(cls, v: Any) -> str:
        cleaned = _clean_str(v).rstrip("/")
        if cleaned.endswith("/rest/v1"):
            cleaned = cleaned[:-8]
        elif cleaned.endswith("/v1"):
            cleaned = cleaned[:-3]
        return cleaned

    @field_validator("SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "GOOGLE_PLACES_API_KEY", mode="before")
    @classmethod
    def clean_generic_str(cls, v: Any) -> str:
        return _clean_str(v)

    @field_validator("SUPABASE_JWT_SECRET", "FRONTEND_URL", mode="before")
    @classmethod
    def clean_optional_str(cls, v: Any) -> Optional[str]:
        cleaned = _clean_str(v)
        return cleaned if cleaned else None

    def validate_on_startup(self) -> None:
        """Validates critical environment variables and raises RuntimeError if any required auth variable is missing."""
        import logging
        logger = logging.getLogger("healthmate.config")

        missing_auth = []
        if not self.SUPABASE_URL:
            missing_auth.append("SUPABASE_URL")
        if not self.SUPABASE_ANON_KEY:
            missing_auth.append("SUPABASE_ANON_KEY")
        if not self.SUPABASE_SERVICE_ROLE_KEY:
            missing_auth.append("SUPABASE_SERVICE_ROLE_KEY")

        if missing_auth:
            error_msg = (
                f"Startup failed: Missing required Supabase environment variable(s): {', '.join(missing_auth)}. "
                "Ensure these are set in your deployment environment (e.g. Render Dashboard or .env file)."
            )
            logger.critical(error_msg)
            raise RuntimeError(error_msg)

        logger.info("Core database and auth credentials (SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY) are verified.")

        if not self.GEMINI_API_KEY and not self.OPENROUTER_API_KEY:
            logger.warning(
                "CRITICAL: Neither GEMINI_API_KEY nor OPENROUTER_API_KEY is configured. AI features will fail at runtime."
            )
        else:
            logger.info("LLM credentials are configured.")

        if not self.GOOGLE_PLACES_API_KEY:
            logger.info(
                "GOOGLE_PLACES_API_KEY is not set (optional). Fallback to OpenStreetMap and curated doctors will be active."
            )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
