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

    # App Environment
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
