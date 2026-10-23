"""
Doctors router for HealthMate Compass.
Provides nearby specialist search via Google Places API (New) with 24h caching.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from app.core.security import get_current_user, AuthUser
from app.services.places import find_nearby_doctors

router = APIRouter(prefix="/api/doctors", tags=["doctors"])


class DoctorItemOut(BaseModel):
    place_id: str
    name: str
    address: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    rating: Optional[float] = None
    rating_count: Optional[int] = None
    phone: Optional[str] = None
    open_now: Optional[bool] = None
    maps_url: str
    distance_m: Optional[int] = None
    specialty: str


class DoctorSearchResponse(BaseModel):
    doctors: List[DoctorItemOut]
    specialty: str
    attribution: str = "Data from Google Maps"
    fallback_used: bool = False
    fallback_message: Optional[str] = None


@router.get("", response_model=DoctorSearchResponse)
async def get_nearby_doctors(
    specialty: str = Query("General Physician", description="Specialty from Specialty enum"),
    lat: Optional[float] = Query(None, description="Latitude from browser geolocation"),
    lng: Optional[float] = Query(None, description="Longitude from browser geolocation"),
    radius: int = Query(5000, ge=1000, le=50000, description="Search radius in meters"),
    city: Optional[str] = Query(None, description="City name if geolocation is unavailable"),
    user: AuthUser = Depends(get_current_user),
):
    """
    Finds real nearby healthcare providers for a given specialty.
    Uses Google Places API with 24h server-side cache.
    """
    doctors, final_specialty, fallback_used, fallback_msg = await find_nearby_doctors(
        specialty=specialty,
        lat=lat,
        lng=lng,
        city=city,
        radius_m=radius,
    )

    doctor_items = [DoctorItemOut(**d) for d in doctors]

    return DoctorSearchResponse(
        doctors=doctor_items,
        specialty=final_specialty,
        attribution="Data from Google Maps",
        fallback_used=fallback_used,
        fallback_message=fallback_msg,
    )
