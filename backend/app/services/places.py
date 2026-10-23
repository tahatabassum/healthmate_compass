"""
Google Places API (New) service for HealthMate Compass Doctor Finder.
- Queries Places API (New) with locationBias and strict field masks.
- Caches results for 24h in doctor_cache table to minimize API quota usage.
- Computes distances using the haversine formula.
- Includes automatic fallback (expand radius -> General Physician).
- Never returns AI-generated doctor data (strict attribution).
"""
import math
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple, Dict, Any
import httpx
from app.core.config import settings
from app.core.supabase import get_supabase_admin
from app.services.flags import SPECIALTY_DATA, DEFAULT_SPECIALTY
from app.llm.schemas import Specialty

logger = logging.getLogger(__name__)

PLACES_SEARCH_QUERIES: Dict[str, str] = SPECIALTY_DATA.get("places_search_queries", {})
PLACES_API_URL = "https://places.googleapis.com/v1/places:searchText"
PLACES_FIELD_MASK = (
    "places.id,"
    "places.displayName,"
    "places.formattedAddress,"
    "places.location,"
    "places.rating,"
    "places.userRatingCount,"
    "places.nationalPhoneNumber,"
    "places.regularOpeningHours,"
    "places.googleMapsUri"
)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """Calculates distance between two points on Earth in meters."""
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return int(R * c)


def get_cache_key(specialty: str, lat: Optional[float], lng: Optional[float], city: Optional[str]) -> str:
    """Generates a normalized cache key rounded to ~1.1km grid."""
    if lat is not None and lng is not None:
        return f"{specialty}:{round(lat, 2)}:{round(lng, 2)}"
    norm_city = (city or "default").strip().lower()
    return f"{specialty}:city_{norm_city}"


def get_cached_doctors(cache_key: str) -> Optional[List[dict]]:
    """Checks the doctor_cache table for non-expired results."""
    supabase = get_supabase_admin()
    if not supabase:
        return None

    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        res = (
            supabase.table("doctor_cache")
            .select("results")
            .eq("cache_key", cache_key)
            .gt("expires_at", now_iso)
            .limit(1)
            .execute()
        )
        if res.data and len(res.data) > 0:
            return res.data[0].get("results")
    except Exception as e:
        logger.warning(f"doctor_cache lookup failed: {e}")

    return None


def store_cached_doctors(cache_key: str, results: List[dict]) -> None:
    """Stores doctors in doctor_cache table with a 24-hour expiration."""
    supabase = get_supabase_admin()
    if not supabase:
        return

    try:
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(hours=24)).isoformat()
        supabase.table("doctor_cache").upsert(
            {
                "cache_key": cache_key,
                "results": results,
                "created_at": now.isoformat(),
                "expires_at": expires_at,
            },
            on_conflict="cache_key",
        ).execute()
    except Exception as e:
        logger.warning(f"Failed to store results in doctor_cache: {e}")


def get_sample_doctors(specialty: str, lat: float, lng: float) -> List[dict]:
    """
    Fallback realistic hospital/doctor clinics for demo resilience
    when Google Places API key is unconfigured or rate-limited.
    """
    base_places = [
        {
            "place_id": f"sample_doc_{specialty.lower()}_1",
            "name": f"City Care Clinic & {specialty} Center",
            "address": "Jail Road, Civil Lines, Faisalabad",
            "lat": lat + 0.008,
            "lng": lng + 0.006,
            "rating": 4.8,
            "rating_count": 142,
            "phone": "+92 41 9200100",
            "open_now": True,
            "maps_url": f"https://www.google.com/maps/search/?api=1&query={lat + 0.008},{lng + 0.006}",
            "distance_m": haversine_distance(lat, lng, lat + 0.008, lng + 0.006),
            "specialty": specialty,
        },
        {
            "place_id": f"sample_doc_{specialty.lower()}_2",
            "name": f"National Healthcare & {specialty} Consultants",
            "address": "East Canal Road, Faisalabad",
            "lat": lat - 0.012,
            "lng": lng + 0.010,
            "rating": 4.6,
            "rating_count": 89,
            "phone": "+92 41 8712345",
            "open_now": True,
            "maps_url": f"https://www.google.com/maps/search/?api=1&query={lat - 0.012},{lng + 0.010}",
            "distance_m": haversine_distance(lat, lng, lat - 0.012, lng + 0.010),
            "specialty": specialty,
        },
        {
            "place_id": f"sample_doc_{specialty.lower()}_3",
            "name": f"Allied Medicare Institute ({specialty} Dept)",
            "address": "Sargodha Road, Faisalabad",
            "lat": lat + 0.015,
            "lng": lng - 0.011,
            "rating": 4.5,
            "rating_count": 210,
            "phone": "+92 41 5006000",
            "open_now": False,
            "maps_url": f"https://www.google.com/maps/search/?api=1&query={lat + 0.015},{lng - 0.011}",
            "distance_m": haversine_distance(lat, lng, lat + 0.015, lng - 0.011),
            "specialty": specialty,
        },
    ]
    return base_places


async def query_places_api(
    query_text: str,
    lat: Optional[float],
    lng: Optional[float],
    radius_m: int = 5000,
) -> List[dict]:
    """Queries Google Places Text Search (New)."""
    if not settings.GOOGLE_PLACES_API_KEY:
        return []

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": PLACES_FIELD_MASK,
    }

    body: Dict[str, Any] = {
        "textQuery": query_text,
        "maxResultCount": 10,
    }

    if lat is not None and lng is not None:
        body["locationBias"] = {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": float(radius_m),
            }
        }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(PLACES_API_URL, json=body, headers=headers)
        if resp.status_code != 200:
            logger.warning(f"Places API error: status {resp.status_code}, {resp.text[:200]}")
            return []

        data = resp.json()
        places = data.get("places", [])
        results = []
        for p in places:
            loc = p.get("location", {})
            p_lat = loc.get("latitude")
            p_lng = loc.get("longitude")
            dist = None
            if lat is not None and lng is not None and p_lat is not None and p_lng is not None:
                dist = haversine_distance(lat, lng, p_lat, p_lng)

            opening_hours = p.get("regularOpeningHours", {})
            open_now = opening_hours.get("openNow")

            results.append({
                "place_id": p.get("id"),
                "name": p.get("displayName", {}).get("text", "Medical Clinic"),
                "address": p.get("formattedAddress", ""),
                "lat": p_lat,
                "lng": p_lng,
                "rating": p.get("rating"),
                "rating_count": p.get("userRatingCount"),
                "phone": p.get("nationalPhoneNumber"),
                "open_now": open_now,
                "maps_url": p.get("googleMapsUri") or f"https://www.google.com/maps/search/?api=1&query={p_lat},{p_lng}",
                "distance_m": dist,
            })
        return results


async def query_osm_healthcare(
    specialty: str,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    city: Optional[str] = None,
    radius_m: int = 10000,
) -> Tuple[List[dict], bool, Optional[str]]:
    """
    Real-time OpenStreetMap / Nominatim live search for hospitals, clinics, and specialists.
    100% free, no credit card, no API key required.
    Strictly confines searches to the requested city or GPS coordinates.
    Never hallucinates or substitutes clinics from other cities.
    """
    headers = {"User-Agent": "HealthMateCompass/1.0 (hackathon@healthmate.pk)"}
    specialty_keywords = {
        "Cardiology": ["cardiology hospital", "cardiac center", "heart hospital"],
        "Dermatology": ["skin clinic", "dermatologist", "skin hospital"],
        "Endocrinology": ["diabetes clinic", "diabetic center", "endocrinology"],
        "Gastroenterology": ["gastro clinic", "liver center", "digestive clinic"],
        "Hematology": ["blood bank", "hematology clinic", "hospital"],
        "Nephrology": ["kidney hospital", "dialysis center", "nephrology"],
        "Neurology": ["neuro hospital", "brain spine clinic", "hospital"],
        "Oncology": ["cancer hospital", "oncology center"],
        "Pulmonology": ["chest clinic", "respiratory hospital", "tb clinic"],
        "Rheumatology": ["arthritis clinic", "rheumatology", "hospital"],
        "Infectious Disease": ["general hospital", "isolation hospital"],
        "General Medicine": ["hospital", "clinic", "general physician"],
        "Dentist": ["dentist", "dental clinic", "dental hospital"],
        "Dentistry": ["dentist", "dental clinic", "dental hospital"],
        "Pediatrics": ["children hospital", "pediatric clinic", "child care"],
        "Gynecology": ["maternity hospital", "women clinic", "gynecology"],
        "Orthopedics": ["orthopedic hospital", "bone joint clinic"],
        "Ophthalmology": ["eye hospital", "eye clinic", "optical clinic"],
        "ENT": ["ent clinic", "ear nose throat hospital"],
    }

    kw_list = specialty_keywords.get(specialty, [f"{specialty.lower()} clinic", f"{specialty.lower()} hospital", "hospital"])

    queries_to_try = []
    fallback_used = False
    fallback_msg = None

    if city and city.strip():
        clean_city = city.strip()
        # 1. Primary targeted queries in that city
        for kw in kw_list[:2]:
            queries_to_try.append({"q": f"{kw} {clean_city}", "format": "json", "limit": 6})
        # 2. Broader queries in that exact same city
        queries_to_try.append({"q": f"{specialty} {clean_city}", "format": "json", "limit": 6})
        queries_to_try.append({"q": f"hospital {clean_city}", "format": "json", "limit": 6})
    elif lat is not None and lng is not None:
        delta = min(0.2, (radius_m / 111000.0) * 1.5)
        viewbox = f"{lng-delta},{lat+delta},{lng+delta},{lat-delta}"
        for kw in kw_list[:2]:
            queries_to_try.append({
                "q": kw,
                "viewbox": viewbox,
                "bounded": 1,
                "format": "json",
                "limit": 6,
            })
        queries_to_try.append({
            "q": "hospital",
            "viewbox": viewbox,
            "bounded": 1,
            "format": "json",
            "limit": 6,
        })
    else:
        # Default fallback only if neither city nor coordinates provided
        queries_to_try.append({"q": f"hospital Pakistan", "format": "json", "limit": 6})

    results = []
    seen_ids = set()

    async with httpx.AsyncClient(timeout=8.0) as client:
        for idx, p in enumerate(queries_to_try):
            try:
                resp = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params=p,
                    headers=headers,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data:
                        pid = str(item.get("place_id") or item.get("osm_id"))
                        if pid in seen_ids:
                            continue
                        seen_ids.add(pid)
                        p_lat = float(item["lat"])
                        p_lng = float(item["lon"])
                        dist = None
                        if lat is not None and lng is not None:
                            dist = haversine_distance(lat, lng, p_lat, p_lng)

                        name = item.get("name") or item.get("display_name", "").split(",")[0]
                        address = item.get("display_name", "")

                        # Filter out veterinary / animal hospitals
                        lower_info = (name + " " + address).lower()
                        if any(v in lower_info for v in ["veterinary", " vet", "animal"]):
                            continue

                        results.append({
                            "place_id": f"osm_{pid}",
                            "name": name,
                            "address": address,
                            "lat": p_lat,
                            "lng": p_lng,
                            "rating": None,
                            "rating_count": None,
                            "phone": None,
                            "open_now": None,
                            "maps_url": f"https://www.google.com/maps/search/?api=1&query={p_lat},{p_lng}",
                            "distance_m": dist,
                        })
                    if len(results) >= 2:
                        if idx >= 2 and city:
                            fallback_used = True
                            fallback_msg = f"Showing general hospitals & clinics in {city.strip()}."
                        break
            except Exception as e:
                logger.warning(f"OSM healthcare search warning: {e}")
                continue

    return results, fallback_used, fallback_msg


async def find_nearby_doctors(
    specialty: str,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    city: Optional[str] = None,
    radius_m: int = 5000,
) -> Tuple[List[dict], str, bool, Optional[str]]:
    """
    Main Doctor Finder routine:
    1. Check 24h cache.
    2. Try Google Places API (if key configured).
    3. If empty/unconfigured, query real-time OpenStreetMap live results.
    4. Never inject fake doctors from other cities.
    5. Cache & return with live Google Maps navigation links.
    """
    target_specialty = specialty if specialty in PLACES_SEARCH_QUERIES else DEFAULT_SPECIALTY
    cache_key = get_cache_key(target_specialty, lat, lng, city)

    # 1. Check cache
    cached = get_cached_doctors(cache_key)
    if cached:
        return cached, target_specialty, False, None

    results = []
    fallback_used = False
    fallback_message = None

    # 2. Try Google Places API if key exists
    if settings.GOOGLE_PLACES_API_KEY:
        query_base = PLACES_SEARCH_QUERIES.get(target_specialty, "doctor clinic")
        search_query = f"{query_base} in {city}" if city and (lat is None or lng is None) else f"{query_base} near me"
        results = await query_places_api(search_query, lat, lng, radius_m=radius_m)

        if not results and radius_m < 15000 and lat is not None and lng is not None:
            results = await query_places_api(search_query, lat, lng, radius_m=15000)

        if not results and target_specialty != DEFAULT_SPECIALTY:
            gp_query = f"{PLACES_SEARCH_QUERIES[DEFAULT_SPECIALTY]} near me"
            results = await query_places_api(gp_query, lat, lng, radius_m=15000)
            if results:
                fallback_used = True
                fallback_message = f"No {target_specialty} specialists found within 15 km. Showing nearby General Physicians."
                target_specialty = DEFAULT_SPECIALTY

    # 3. Real-time OpenStreetMap live hospital & specialist search (No card or API key needed!)
    if not results:
        osm_res, osm_fallback, osm_msg = await query_osm_healthcare(target_specialty, lat, lng, city, radius_m=radius_m)
        if osm_res:
            results = osm_res
            if osm_fallback:
                fallback_used = True
                fallback_message = osm_msg

    # Tag results with specialty
    for r in results:
        r["specialty"] = target_specialty

    # Sort by distance if distance available, else rating
    results.sort(key=lambda x: (x.get("distance_m") or 999999, -(x.get("rating") or 0)))

    # Store in cache
    if results:
        store_cached_doctors(cache_key, results)

    return results, target_specialty, fallback_used, fallback_message

