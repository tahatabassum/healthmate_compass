"""
Unit tests for Doctor Finder service & API router (backend/app/services/places.py).
Tests distance math, cache keys, and API search endpoint.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.places import (
    haversine_distance,
    get_cache_key,
)

client = TestClient(app)
DEV_HEADERS = {"Authorization": "Bearer dev-user-12345"}


def test_haversine_distance():
    # Known distance: Islamabad (33.6844, 73.0479) to Rawalpindi (33.5651, 73.0169) ~ 13-14 km
    dist = haversine_distance(33.6844, 73.0479, 33.5651, 73.0169)
    assert 12000 < dist < 16000


def test_cache_key_generation():
    key1 = get_cache_key("Cardiologist", 31.450412, 73.135041, None)
    assert key1 == "Cardiologist:31.45:73.14"

    key2 = get_cache_key("Nephrologist", None, None, "Faisalabad")
    assert key2 == "Nephrologist:city_faisalabad"


def test_doctors_api_endpoint():
    resp = client.get(
        "/api/doctors?specialty=Cardiologist&lat=31.4504&lng=73.1350&radius=5000",
        headers=DEV_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "doctors" in data
    assert data["attribution"] == "Data from Google Maps"
    assert data["specialty"] == "Cardiologist"
    assert len(data["doctors"]) > 0

    first_doc = data["doctors"][0]
    assert "name" in first_doc
    assert "maps_url" in first_doc
    assert "distance_m" in first_doc
    assert first_doc["specialty"] == "Cardiologist"


def test_doctors_api_auth_required():
    resp = client.get("/api/doctors?specialty=Cardiologist")
    assert resp.status_code == 401
