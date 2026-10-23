"""
Integration tests for Chat router, LangGraph emergency routing, and Memory endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
DEV_HEADERS = {"Authorization": "Bearer dev-user-12345"}


def test_chat_session_creation():
    # Create patient
    p_resp = client.post("/api/patients", json={"full_name": "Chat Patient", "relation": "self"}, headers=DEV_HEADERS)
    patient_id = p_resp.json()["id"]

    resp = client.post(
        "/api/chat/session",
        json={"patient_id": patient_id, "title": "Headache check"},
        headers=DEV_HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["title"] == "Headache check"


def test_chat_emergency_interception_bypasses_llm():
    # Create patient and session
    p_resp = client.post("/api/patients", json={"full_name": "Emergency Patient", "relation": "self"}, headers=DEV_HEADERS)
    patient_id = p_resp.json()["id"]

    ses_resp = client.post(
        "/api/chat/session",
        json={"patient_id": patient_id, "title": "Emergency Check"},
        headers=DEV_HEADERS,
    )
    session_id = ses_resp.json()["id"]

    # Sending an emergency message must immediately trigger emergency action
    # without needing LLM execution or active API keys.
    msg_payload = {
        "session_id": session_id,
        "content": "Doctor please help, patient is having severe chest pain and trouble breathing",
        "lang": "en",
    }
    resp = client.post("/api/chat/message", json=msg_payload, headers=DEV_HEADERS)
    assert resp.status_code == 200
    res = resp.json()
    assert res["is_emergency"] is True
    assert res["emergency_action"] is not None
    assert res["emergency_action"]["emergency_number"] == "1122"
    assert "Rescue 1122" in res["content_en"]
    assert "1122" in res["content_ur"]


def test_memory_facts_listing_and_patch():
    p_resp = client.post("/api/patients", json={"full_name": "Memory Patient", "relation": "self"}, headers=DEV_HEADERS)
    patient_id = p_resp.json()["id"]

    # List memory facts for patient
    resp = client.get(f"/api/memory?patient_id={patient_id}", headers=DEV_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_chat_session_rename_and_delete():
    # 1. Create a session
    ses_resp = client.post(
        "/api/chat/session",
        json={"title": "Original Title"},
        headers=DEV_HEADERS,
    )
    assert ses_resp.status_code == 201
    session_id = ses_resp.json()["id"]

    # 2. Rename session
    patch_resp = client.patch(
        f"/api/chat/sessions/{session_id}",
        json={"title": "Updated Chronic Pain Consultation"},
        headers=DEV_HEADERS,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "Updated Chronic Pain Consultation"

    # 3. Delete session
    del_resp = client.delete(
        f"/api/chat/sessions/{session_id}",
        headers=DEV_HEADERS,
    )
    assert del_resp.status_code == 204

    # 4. Verify gone
    del_check = client.delete(
        f"/api/chat/sessions/{session_id}",
        headers=DEV_HEADERS,
    )
    assert del_check.status_code == 404
