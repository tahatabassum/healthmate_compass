"""
LLM Client layer for HealthMate Compass.
- Primary provider: Gemini API (OpenAI-compatible endpoint with Gemma 4 model)
- Fallback provider: OpenRouter (Gemma 4 model)
- Structured output via Instructor with Pydantic
- Automatic logging to llm_logs table in Supabase
"""
import time
import logging
from typing import Type, TypeVar, Optional, Any, List
import httpx
from openai import AsyncOpenAI
import instructor
from pydantic import BaseModel

from app.core.config import settings
from app.core.supabase import get_supabase_admin

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Initialize raw OpenAI clients
_gemini_client: Optional[AsyncOpenAI] = None
_openrouter_client: Optional[AsyncOpenAI] = None


def get_gemini_client() -> AsyncOpenAI:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = AsyncOpenAI(
            api_key=settings.GEMINI_API_KEY or "dummy-key",
            base_url=settings.GEMINI_BASE_URL,
            timeout=30.0,
        )
    return _gemini_client


def get_openrouter_client() -> AsyncOpenAI:
    global _openrouter_client
    if _openrouter_client is None:
        _openrouter_client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY or "dummy-key",
            base_url=settings.OPENROUTER_BASE_URL,
            timeout=30.0,
        )
    return _openrouter_client


async def log_llm_call(
    provider: str,
    model: str,
    latency_ms: int,
    status: str,
) -> None:
    """Logs LLM invocation metadata to Supabase llm_logs table asynchronously."""
    try:
        supabase = get_supabase_admin()
        if supabase is not None:
            supabase.table("llm_logs").insert({
                "provider": provider,
                "model": model,
                "latency_ms": latency_ms,
                "status": status,
            }).execute()
    except Exception as e:
        logger.warning(f"Could not log LLM call to Supabase: {e}")


async def call_llm(
    messages: List[dict[str, Any]],
    response_model: Type[T],
    temperature: float = 0.2,
    max_retries: int = 1,
) -> T:
    """
    Executes a structured LLM call with Gemma 4 using Instructor.
    Attempts primary (Gemini API) first; falls back to OpenRouter on failure.
    """
    start_time = time.perf_counter()
    last_error: Optional[Exception] = None

    # 1. Primary Attempt: OpenRouter (Reliable Gemma 4 provider)
    if settings.OPENROUTER_API_KEY:
        openrouter_client = instructor.from_openai(
            get_openrouter_client(),
            mode=instructor.Mode.JSON,
        )
        for model_id in [settings.OPENROUTER_MODEL, settings.OPENROUTER_MODEL_FREE]:
            if not model_id:
                continue
            fb_start = time.perf_counter()
            try:
                res: T = await openrouter_client.chat.completions.create(
                    model=model_id,
                    messages=messages,
                    response_model=response_model,
                    temperature=temperature,
                    max_retries=max_retries,
                )
                latency = int((time.perf_counter() - fb_start) * 1000)
                await log_llm_call("openrouter", model_id, latency, "success")
                return res
            except Exception as e:
                last_error = e
                latency = int((time.perf_counter() - fb_start) * 1000)
                logger.warning(f"OpenRouter model {model_id} failed: {e}. Trying fallback...")
                await log_llm_call("openrouter", model_id, latency, f"failed: {str(e)[:50]}")

    # 2. Secondary Attempt: Gemini API
    if settings.GEMINI_API_KEY:
        primary_client = instructor.from_openai(
            get_gemini_client(),
            mode=instructor.Mode.JSON,
        )
        try:
            res: T = await primary_client.chat.completions.create(
                model=settings.GEMINI_GEMMA_MODEL,
                messages=messages,
                response_model=response_model,
                temperature=temperature,
                max_retries=max_retries,
            )
            latency = int((time.perf_counter() - start_time) * 1000)
            await log_llm_call("gemini", settings.GEMINI_GEMMA_MODEL, latency, "success")
            return res
        except Exception as e:
            last_error = e
            latency = int((time.perf_counter() - start_time) * 1000)
            logger.warning(f"Gemini API call failed ({settings.GEMINI_GEMMA_MODEL}): {e}")
            await log_llm_call("gemini", settings.GEMINI_GEMMA_MODEL, latency, f"failed: {str(e)[:50]}")

    # If all providers fail
    total_latency = int((time.perf_counter() - start_time) * 1000)
    await log_llm_call("all", "none", total_latency, "all_providers_failed")
    raise RuntimeError(
        f"All LLM providers (Gemini + OpenRouter) failed or keys are missing. Last error: {last_error}"
    )


async def get_embedding(text: str) -> List[float]:
    """
    Generates a 768-dimensional embedding using Gemini GEMINI_EMBED_MODEL.
    Strictly asserts output dimension == 768 to prevent database schema mismatch.
    """
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not configured for embeddings. Returning mock 768-dim vector.")
        return [0.0] * 768

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_EMBED_MODEL}:embedContent?key={settings.GEMINI_API_KEY}"
    payload = {
        "model": f"models/{settings.GEMINI_EMBED_MODEL}",
        "content": {"parts": [{"text": text[:2000]}]},
        "outputDimensionality": 768,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        embedding = data.get("embedding", {}).get("values", [])
        if len(embedding) != 768:
            raise ValueError(f"Expected 768-dim embedding, got {len(embedding)}")
        return embedding
