"""
Supabase client provider for HealthMate Compass backend.
Uses the service role key for admin/backend queries, respecting RLS logic in application queries.
"""
from functools import lru_cache
from typing import Optional
from supabase import create_client, Client
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


@lru_cache()
def get_supabase_admin() -> Optional[Client]:
    """
    Returns a cached Supabase client with the service role key.
    Returns None if SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY are unset.
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        logger.warning(
            "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is not set. Supabase client unavailable."
        )
        return None
    url = settings.SUPABASE_URL.strip().rstrip('/')
    if url.endswith('/rest/v1'):
        url = url[:-8]
    elif url.endswith('/v1'):
        url = url[:-3]

    try:
        return create_client(url, settings.SUPABASE_SERVICE_ROLE_KEY)
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        return None
