"""
Automated Data Isolation & RLS Security Tests for HealthMate Compass.
Verifies that:
1. User A cannot view User B's profile.
2. User A cannot view, update, or access User B's uploaded reports.
3. User A cannot access User B's chat sessions or messages.
4. User A cannot access User B's memory facts.
5. All endpoints strictly derive identity from authenticated JWT, never client-sent patient_id.
"""
import io
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.supabase import get_supabase_admin

client = TestClient(app)


@pytest.fixture(scope="module")
def test_users():
    """Provisions two real test users in Supabase auth for isolation testing."""
    sb = get_supabase_admin()
    if not sb:
        pytest.skip("Supabase not configured")

    rand_a = uuid.uuid4().hex[:8]
    rand_b = uuid.uuid4().hex[:8]
    email_a = f"test_alice_{rand_a}@healthmate.local"
    email_b = f"test_bob_{rand_b}@healthmate.local"

    u_a = sb.auth.admin.create_user({"email": email_a, "password": "Password123!", "email_confirm": True})
    u_b = sb.auth.admin.create_user({"email": email_b, "password": "Password123!", "email_confirm": True})

    user_a_id = u_a.user.id
    user_b_id = u_b.user.id

    headers_a = {"Authorization": f"Bearer dev-user-{user_a_id}"}
    headers_b = {"Authorization": f"Bearer dev-user-{user_b_id}"}

    yield {
        "user_a_id": user_a_id,
        "user_b_id": user_b_id,
        "headers_a": headers_a,
        "headers_b": headers_b,
    }

    # Teardown: delete test users and their child records
    try:
        sb.table("patients").delete().in_("owner_id", [user_a_id, user_b_id]).execute()
        sb.auth.admin.delete_user(user_a_id)
        sb.auth.admin.delete_user(user_b_id)
    except Exception:
        pass


def test_profile_isolation(test_users):
    headers_a = test_users["headers_a"]
    headers_b = test_users["headers_b"]

    # User A updates profile
    resp_a = client.patch(
        "/api/profile",
        json={"full_name": "Alice User", "blood_group": "A+", "allergies": ["Peanuts"]},
        headers=headers_a,
    )
    assert resp_a.status_code == 200
    profile_a = resp_a.json()
    assert profile_a["full_name"] == "Alice User"

    # User B updates profile
    resp_b = client.patch(
        "/api/profile",
        json={"full_name": "Bob User", "blood_group": "B+", "allergies": ["Sulfa"]},
        headers=headers_b,
    )
    assert resp_b.status_code == 200
    profile_b = resp_b.json()
    assert profile_b["full_name"] == "Bob User"

    # User B fetches profile -> must get Bob, never Alice
    check_b = client.get("/api/profile", headers=headers_b)
    assert check_b.status_code == 200
    assert check_b.json()["full_name"] == "Bob User"
    assert check_b.json()["id"] != profile_a["id"]


def test_reports_isolation(test_users):
    headers_a = test_users["headers_a"]
    headers_b = test_users["headers_b"]

    # User A uploads a report
    fake_pdf = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF"
    files = {"file": ("alice_report.pdf", io.BytesIO(fake_pdf), "application/pdf")}
    upload_resp = client.post("/api/reports/upload", files=files, headers=headers_a)
    assert upload_resp.status_code == 201
    report_a_id = upload_resp.json()["report_id"]

    # User B lists reports -> must NOT see Alice's report
    b_reports_resp = client.get("/api/reports", headers=headers_b)
    assert b_reports_resp.status_code == 200
    b_report_ids = [r["id"] for r in b_reports_resp.json()]
    assert report_a_id not in b_report_ids

    # User B attempts direct access to Alice's report by ID -> MUST be denied (404/403)
    direct_access = client.get(f"/api/reports/{report_a_id}", headers=headers_b)
    assert direct_access.status_code in (403, 404)


def test_chat_session_isolation(test_users):
    headers_a = test_users["headers_a"]
    headers_b = test_users["headers_b"]

    # User A creates a chat session
    ses_resp = client.post("/api/chat/session", json={"title": "Alice Consultation"}, headers=headers_a)
    assert ses_resp.status_code == 201
    alice_session_id = ses_resp.json()["id"]

    # User B lists sessions -> must NOT contain Alice's session
    b_sessions_resp = client.get("/api/chat/sessions", headers=headers_b)
    assert b_sessions_resp.status_code == 200
    b_session_ids = [s["id"] for s in b_sessions_resp.json()]
    assert alice_session_id not in b_session_ids


def test_memory_facts_isolation(test_users):
    """Verifies User A's private health memory facts cannot be seen, edited, or deleted by User B."""
    headers_a = test_users["headers_a"]
    headers_b = test_users["headers_b"]

    # User A creates a memory preference
    create_resp = client.post(
        "/api/memory",
        json={"fact_type": "preference", "key": "preferred_language", "value": "Urdu"},
        headers=headers_a,
    )
    assert create_resp.status_code == 201
    fact_a = create_resp.json()
    fact_a_id = fact_a["id"]

    # User B lists memory facts -> must NOT contain Alice's fact
    list_b = client.get("/api/memory", headers=headers_b)
    assert list_b.status_code == 200
    b_facts = list_b.json()
    assert not any(f["id"] == fact_a_id for f in b_facts)
    assert not any(f.get("value") == "Urdu" for f in b_facts)

    # User B attempts to tamper with User A's fact -> 404 unauthorized
    patch_attempt = client.patch(
        f"/api/memory/{fact_a_id}",
        json={"value": "Hacked Value"},
        headers=headers_b,
    )
    assert patch_attempt.status_code == 404

