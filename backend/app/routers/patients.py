"""
Profile router for HealthMate Compass.
Enforces 1 User = 1 Profile architecture.
Automatically provisions a single profile for authenticated users upon request.
Derives patient profile strictly from authenticated Supabase user (owner_id = user.id).
"""
from typing import List, Optional
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.core.security import get_current_user, AuthUser
from app.core.supabase import get_supabase_admin

router = APIRouter(tags=["profile"])


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    allergies: Optional[List[str]] = None
    chronic_conditions: Optional[List[str]] = None
    preferred_language: Optional[str] = None


class ProfileOut(BaseModel):
    id: str
    owner_id: str
    full_name: str
    relation: str = "self"
    dob: Optional[str] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    allergies: List[str] = []
    chronic_conditions: List[str] = []
    preferred_language: str = "en"
    created_at: Optional[str] = None


async def get_or_create_user_profile(user: AuthUser) -> dict:
    """
    Idempotently returns the single personal health profile for this authenticated user.
    If no profile exists yet, provisions one automatically with default settings.
    """
    supabase = get_supabase_admin()
    if not supabase:
        return {
            "id": "de1ba63b-28f8-4a54-a68f-ab9b799cdd7d",
            "owner_id": user.id,
            "full_name": "Taha Tabassum",
            "relation": "self",
            "gender": "male",
            "blood_group": "B+",
            "allergies": [],
            "chronic_conditions": [],
            "preferred_language": "en",
        }

    # 1. Query by unique owner_id
    res = (
        supabase.table("patients")
        .select("*")
        .eq("owner_id", user.id)
        .limit(1)
        .execute()
    )
    if res.data and len(res.data) > 0:
        return res.data[0]

    # 2. Idempotent creation on first signup/login
    default_name = user.email.split("@")[0].replace(".", " ").title() if user.email else "Personal Profile"
    new_profile = {
        "owner_id": user.id,
        "full_name": default_name,
        "relation": "self",
        "gender": None,
        "blood_group": None,
        "allergies": [],
        "chronic_conditions": [],
        "preferred_language": "en",
    }
    try:
        ins = supabase.table("patients").insert(new_profile).execute()
        if ins.data and len(ins.data) > 0:
            return ins.data[0]
    except Exception as e:
        # Race condition safeguard: re-query in case another concurrent request created it
        recheck = (
            supabase.table("patients")
            .select("*")
            .eq("owner_id", user.id)
            .limit(1)
            .execute()
        )
        if recheck.data and len(recheck.data) > 0:
            return recheck.data[0]
        raise HTTPException(status_code=500, detail=f"Failed to provision user profile: {e}")

    return new_profile


@router.get("/api/profile", response_model=ProfileOut)
async def get_current_profile(user: AuthUser = Depends(get_current_user)):
    """Returns the authenticated user's personal health profile."""
    profile = await get_or_create_user_profile(user)
    return profile


@router.patch("/api/profile", response_model=ProfileOut)
async def update_current_profile(
    payload: ProfileUpdate,
    user: AuthUser = Depends(get_current_user),
):
    """Updates the authenticated user's personal health profile."""
    supabase = get_supabase_admin()
    profile = await get_or_create_user_profile(user)
    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}

    if not supabase:
        profile.update(update_data)
        return profile

    if not update_data:
        return profile

    res = (
        supabase.table("patients")
        .update(update_data)
        .eq("id", profile["id"])
        .eq("owner_id", user.id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=400, detail="Profile update failed")
    return res.data[0]


# ── Backward compatibility aliases for existing components & tests ────────────
@router.get("/api/patients", response_model=List[ProfileOut])
async def list_patients(user: AuthUser = Depends(get_current_user)):
    """Returns the user's single profile wrapped in a list."""
    profile = await get_or_create_user_profile(user)
    return [profile]


@router.post("/api/patients", response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
async def create_or_update_patient(
    payload: ProfileUpdate,
    user: AuthUser = Depends(get_current_user),
):
    """Idempotently updates the user's personal health profile."""
    return await update_current_profile(payload, user)


@router.get("/api/patients/{patient_id}", response_model=ProfileOut)
async def get_patient_by_id(
    patient_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """Returns the user's profile, verifying owner isolation."""
    profile = await get_or_create_user_profile(user)
    if profile["id"] != patient_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to requested profile")
    return profile


# ── Profile Lifecycle: Undo, Conditions & Change Log (Phase C) ─────────────────

@router.post("/api/profile/undo/{log_id}")
async def undo_profile_update(
    log_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """Reverts an auto-profile update made during chat."""
    profile = await get_or_create_user_profile(user)
    from app.services.memory import undo_profile_change
    res = await undo_profile_change(log_id=log_id, patient_id=profile["id"])
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message", "Failed to undo change"))
    return res


@router.get("/api/profile/conditions")
async def get_patient_conditions(
    user: AuthUser = Depends(get_current_user),
):
    """Returns active and resolved health conditions for the user's profile."""
    profile = await get_or_create_user_profile(user)
    supabase = get_supabase_admin()
    if not supabase:
        return {
            "active": profile.get("chronic_conditions", []),
            "resolved": [],
        }

    active_list = []
    resolved_list = []
    try:
        c_res = (
            supabase.table("patient_conditions")
            .select("*")
            .eq("patient_id", profile["id"])
            .order("created_at", desc=True)
            .execute()
        )
        if c_res.data:
            for row in c_res.data:
                if row.get("status") == "active":
                    active_list.append(row)
                elif row.get("status") == "resolved":
                    resolved_list.append(row)
    except Exception:
        # Fallback to chronic_conditions array
        active_list = [{"name": c, "status": "active"} for c in (profile.get("chronic_conditions") or [])]

    return {
        "active": active_list,
        "resolved": resolved_list,
    }


@router.get("/api/profile/change-log")
async def get_profile_change_log(
    user: AuthUser = Depends(get_current_user),
):
    """Returns audit log of all automatic and manual changes to the profile."""
    profile = await get_or_create_user_profile(user)
    supabase = get_supabase_admin()
    if not supabase:
        return []

    try:
        log_res = (
            supabase.table("profile_change_log")
            .select("*")
            .eq("patient_id", profile["id"])
            .order("created_at", desc=True)
            .limit(30)
            .execute()
        )
        return log_res.data or []
    except Exception:
        return []
