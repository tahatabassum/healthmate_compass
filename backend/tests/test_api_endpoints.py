"""
Integration tests for FastAPI endpoints:
- Auth enforcement (401 on missing token)
- /api/patients listing and creation with dev token
- /api/reports/upload with multipart file
"""
import pytest
import io
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

DEV_HEADERS = {"Authorization": "Bearer dev-user-12345"}


def test_auth_enforced_on_protected_endpoints():
    # Requests without Authorization header must return 401
    resp_patients = client.get("/api/patients")
    assert resp_patients.status_code == 401

    resp_reports = client.get("/api/reports?patient_id=123")
    assert resp_reports.status_code == 401


def test_list_and_create_patients():
    # List patients
    resp = client.get("/api/patients", headers=DEV_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    # Create a patient profile
    new_patient = {
        "full_name": "Fatima Bibi",
        "relation": "mother",
        "dob": "1965-04-12",
        "gender": "female",
        "blood_group": "O+",
        "allergies": ["Sulfa"],
        "chronic_conditions": ["Hypertension"],
        "preferred_language": "ur",
    }
    resp_create = client.post("/api/patients", json=new_patient, headers=DEV_HEADERS)
    assert resp_create.status_code == 201
    created = resp_create.json()
    assert created["full_name"] == "Fatima Bibi"
    assert created["gender"] == "female"


def test_upload_report_endpoint():
    # 1. Create a patient first
    p_resp = client.post("/api/patients", json={"full_name": "Test Patient", "relation": "self"}, headers=DEV_HEADERS)
    patient_id = p_resp.json()["id"]

    # 2. Create fake lab report PDF content in-memory
    fake_pdf = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF"
    files = {
        "file": ("lab_report.pdf", io.BytesIO(fake_pdf), "application/pdf")
    }
    data = {"patient_id": patient_id}

    resp = client.post("/api/reports/upload", data=data, files=files, headers=DEV_HEADERS)
    assert resp.status_code == 201
    res_data = resp.json()
    assert "report_id" in res_data
    assert res_data["status"] == "uploaded"
    assert res_data["patient_id"] == patient_id
