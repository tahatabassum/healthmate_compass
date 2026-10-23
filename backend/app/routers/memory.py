"""
Memory facts router for HealthMate Compass.
Allows viewing, creating, editing, and deleting remembered patient health facts.
Enforces strict patient data isolation based on authenticated JWT.
"""
from typing import List, Optional
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from app.core.security import get_current_user, AuthUser
from app.core.supabase import get_supabase_admin
from app.routers.patients import get_or_create_user_profile
from app.services.memory import save_memory_facts
from app.llm.schemas import MemoryFact, FactType

router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemoryFactCreate(BaseModel):
    fact_type: str = Field(default="preference", description="condition | allergy | medication | lifestyle | preference | general")
    key: str = Field(..., description="Key or description of fact e.g. preferred_language, asthma")
    value: str = Field(..., description="Value or detail of fact e.g. Urdu, severe")
    confidence: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)


class MemoryFactOut(BaseModel):
    id: str
    patient_id: str
    fact_type: str
    key: str
    value: str
    status: str
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    confidence: Optional[float] = None
    created_at: Optional[str] = None


class MemoryFactUpdate(BaseModel):
    value: Optional[str] = None
    status: Optional[str] = None  # active | superseded | deleted


@router.post("", response_model=MemoryFactOut, status_code=status.HTTP_201_CREATED)
async def create_memory_fact(
    payload: MemoryFactCreate,
    user: AuthUser = Depends(get_current_user),
):
    """
    Creates a new persistent memory fact for the authenticated patient.
    Enforces patient ownership and deduplication/superseding rules.
    """
    profile = await get_or_create_user_profile(user)
    patient_id = profile["id"]
    supabase = get_supabase_admin()

    clean_key = payload.key.strip()
    clean_val = payload.value.strip()

    # Map to valid FactType enum safely
    f_type_str = payload.fact_type.lower().strip()
    try:
        f_type = FactType(f_type_str)
    except ValueError:
        f_type = FactType.PREFERENCE if "pref" in f_type_str or "lang" in clean_key.lower() else FactType.GENERAL

    new_fact = MemoryFact(
        fact_type=f_type,
        key=clean_key,
        value=clean_val,
        confidence=payload.confidence or 1.0,
        status="active",
    )

    saved = await save_memory_facts(
        patient_id=patient_id,
        facts=[new_fact],
        source_type="manual",
    )

    if saved:
        return MemoryFactOut(**saved[0])

    # Fallback response if mock/local
    return MemoryFactOut(
        id=str(uuid4()),
        patient_id=patient_id,
        fact_type=f_type.value,
        key=clean_key,
        value=clean_val,
        status="active",
        confidence=payload.confidence or 1.0,
    )


@router.get("", response_model=List[MemoryFactOut])
async def list_patient_memory(
    patient_id: Optional[str] = Query(None, description="Optional patient ID"),
    user: AuthUser = Depends(get_current_user),
):
    """Lists all active remembered facts for authenticated user."""
    profile = await get_or_create_user_profile(user)
    target_patient_id = profile["id"]
    supabase = get_supabase_admin()
    if not supabase:
        return []

    res = (
        supabase.table("memory_facts")
        .select("*")
        .eq("patient_id", target_patient_id)
        .eq("status", "active")
        .order("created_at", desc=True)
        .execute()
    )
    return [MemoryFactOut(**r) for r in (res.data or [])]


@router.patch("/{fact_id}", response_model=MemoryFactOut)
async def update_memory_fact(
    fact_id: str,
    payload: MemoryFactUpdate,
    user: AuthUser = Depends(get_current_user),
):
    """Updates a memory fact value or status with ownership validation."""
    profile = await get_or_create_user_profile(user)
    patient_id = profile["id"]
    supabase = get_supabase_admin()
    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}

    if not supabase:
        return MemoryFactOut(
            id=fact_id,
            patient_id=patient_id,
            fact_type="condition",
            key="updated_fact",
            value=update_data.get("value", "updated"),
            status=update_data.get("status", "active"),
        )

    # Validate ownership
    existing = supabase.table("memory_facts").select("id").eq("id", fact_id).eq("patient_id", patient_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Memory fact not found or unauthorized")

    res = supabase.table("memory_facts").update(update_data).eq("id", fact_id).eq("patient_id", patient_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Memory fact not found")
    return MemoryFactOut(**res.data[0])


@router.delete("/{fact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory_fact(
    fact_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """Soft-deletes a remembered fact with ownership verification."""
    profile = await get_or_create_user_profile(user)
    patient_id = profile["id"]
    supabase = get_supabase_admin()
    if supabase:
        supabase.table("memory_facts").update({"status": "deleted"}).eq("id", fact_id).eq("patient_id", patient_id).execute()
    return None
