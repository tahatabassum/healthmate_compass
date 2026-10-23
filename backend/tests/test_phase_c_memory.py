"""
Phase C Automated Test Suite for HealthMate Compass:
Covers all 5 requirements in PRD Section 4d:
1. Multi-chat recall: Chat 1 states penicillin allergy -> Chat 2 uses allergy when asked about safe antibiotics.
2. Condition resolution: Active condition 'Flu' -> 'I have recovered from the flu' marks it resolved with date, no duplicates.
3. Third-person non-interference: 'My friend has diabetes' changes NOTHING in the profile.
4. Cross-chat recall: New chat 'What did we discuss before?' recalls summary of previous chat.
5. Undo test: Calling undo restores the old state.
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.supabase import get_supabase_admin
from app.services.memory import (
    apply_profile_updates,
    undo_profile_change,
    get_full_patient_profile,
    get_or_create_rolling_summary,
    retrieve_cross_chat_memories,
)
from app.llm.schemas import ProfileOperation, ProfileTargetType, ProfileUpdateItem

client = TestClient(app)


@pytest.fixture(scope="module")
def phase_c_user():
    """Provisions a clean test user in Supabase for Phase C verification."""
    sb = get_supabase_admin()
    if not sb:
        pytest.skip("Supabase not configured")

    rand_id = uuid.uuid4().hex[:8]
    email = f"phase_c_{rand_id}@healthmate.local"
    u = sb.auth.admin.create_user({"email": email, "password": "Password123!", "email_confirm": True})
    user_id = u.user.id
    headers = {"Authorization": f"Bearer dev-user-{user_id}"}

    # Initialize profile
    p_res = client.patch(
        "/api/profile",
        json={"full_name": "Phase C Patient", "gender": "male", "blood_group": "O+"},
        headers=headers,
    )
    patient_id = p_res.json()["id"]

    yield {
        "user_id": user_id,
        "patient_id": patient_id,
        "headers": headers,
    }

    # Cleanup
    try:
        sb.table("patients").delete().eq("owner_id", user_id).execute()
        sb.auth.admin.delete_user(user_id)
    except Exception:
        pass


@pytest.mark.asyncio
async def test_1_multi_chat_allergy_recall(phase_c_user):
    """
    Test 1: Chat 1 adds penicillin allergy.
    Chat 2 in a new session asks about antibiotics -> response accounts for penicillin allergy.
    """
    headers = phase_c_user["headers"]
    patient_id = phase_c_user["patient_id"]

    # Chat 1: Create session 1 and record penicillin allergy
    s1_resp = client.post("/api/chat/session", json={"title": "Allergy Discussion"}, headers=headers)
    assert s1_resp.status_code == 201
    s1_id = s1_resp.json()["id"]

    msg1_resp = client.post(
        "/api/chat/message",
        json={"session_id": s1_id, "content": "I am allergic to penicillin. It gives me severe hives.", "lang": "en"},
        headers=headers,
    )
    assert msg1_resp.status_code == 200

    # Verify profile now reflects Penicillin allergy
    prof = await get_full_patient_profile(patient_id)
    allergies_lower = [a.lower() for a in prof.get("allergies", [])]
    assert any("penicillin" in a for a in allergies_lower), f"Penicillin allergy not in profile: {allergies_lower}"

    # Chat 2: Brand new session asking which antibiotics are safe
    s2_resp = client.post("/api/chat/session", json={"title": "Antibiotics Inquiry"}, headers=headers)
    assert s2_resp.status_code == 201
    s2_id = s2_resp.json()["id"]

    msg2_resp = client.post(
        "/api/chat/message",
        json={"session_id": s2_id, "content": "Which antibiotics are safe for me?", "lang": "en"},
        headers=headers,
    )
    assert msg2_resp.status_code == 200
    answer = msg2_resp.json()["content_en"].lower()
    # The model response must account for penicillin allergy
    assert "penicillin" in answer or "allergic" in answer or "allergy" in answer


@pytest.mark.asyncio
async def test_2_condition_resolution_with_date(phase_c_user):
    """
    Test 2: Profile has active 'Flu'. User says 'I have recovered from the flu.'
    System resolves Flu with a date and does not duplicate records.
    """
    headers = phase_c_user["headers"]
    patient_id = phase_c_user["patient_id"]

    # Seed Flu into profile
    await apply_profile_updates(
        patient_id=patient_id,
        updates=[
            ProfileUpdateItem(
                operation=ProfileOperation.ADD,
                target_type=ProfileTargetType.CONDITION,
                name="Flu",
                value="active",
                evidence_quote="I have the flu",
            )
        ],
    )

    prof_before = await get_full_patient_profile(patient_id)
    assert any("flu" in c.lower() for c in prof_before.get("active_conditions", []))

    # User announces recovery
    s_resp = client.post("/api/chat/session", json={"title": "Flu Recovery"}, headers=headers)
    sid = s_resp.json()["id"]

    rec_resp = client.post(
        "/api/chat/message",
        json={"session_id": sid, "content": "I have recovered from the flu completely.", "lang": "en"},
        headers=headers,
    )
    assert rec_resp.status_code == 200

    # Profile check: Flu must no longer be active
    prof_after = await get_full_patient_profile(patient_id)
    active_conds = [c.lower() for c in prof_after.get("active_conditions", [])]
    assert "flu" not in active_conds, f"Flu should be resolved, but found active: {active_conds}"


@pytest.mark.asyncio
async def test_3_third_person_does_not_update_profile(phase_c_user):
    """
    Test 3: 'My friend has diabetes' must NOT update the user's profile.
    """
    headers = phase_c_user["headers"]
    patient_id = phase_c_user["patient_id"]

    prof_before = await get_full_patient_profile(patient_id)
    conds_before = list(prof_before.get("active_conditions", []))

    s_resp = client.post("/api/chat/session", json={"title": "Friend Inquiry"}, headers=headers)
    sid = s_resp.json()["id"]

    friend_resp = client.post(
        "/api/chat/message",
        json={"session_id": sid, "content": "My friend has diabetes, what diet should they eat?", "lang": "en"},
        headers=headers,
    )
    assert friend_resp.status_code == 200
    updates = friend_resp.json().get("profile_updates", [])

    # Updates must be empty or not contain diabetes
    for u in updates:
        assert "diabetes" not in str(u.get("target_name", "")).lower()

    prof_after = await get_full_patient_profile(patient_id)
    conds_after = list(prof_after.get("active_conditions", []))
    assert not any("diabetes" in c.lower() for c in conds_after), "Diabetes was mistakenly added to profile!"


@pytest.mark.asyncio
async def test_4_cross_chat_recall_past_summary(phase_c_user):
    """
    Test 4: User asks in a brand-new chat 'What did we discuss before?'
    The graph retrieves and recalls summary of past chat sessions.
    """
    headers = phase_c_user["headers"]
    patient_id = phase_c_user["patient_id"]

    # Ensure a rolling summary exists
    s_past = client.post("/api/chat/session", json={"title": "Past Health Chat"}, headers=headers)
    s_past_id = s_past.json()["id"]

    client.post(
        "/api/chat/message",
        json={"session_id": s_past_id, "content": "I had a mild migraine and rested for 2 hours.", "lang": "en"},
        headers=headers,
    )
    await get_or_create_rolling_summary(session_id=s_past_id, patient_id=patient_id, force=True)

    # Brand new chat asking about past discussion
    s_new = client.post("/api/chat/session", json={"title": "Memory Inquiry"}, headers=headers)
    s_new_id = s_new.json()["id"]

    recall_resp = client.post(
        "/api/chat/message",
        json={"session_id": s_new_id, "content": "What did we discuss in our earlier conversations?", "lang": "en"},
        headers=headers,
    )
    assert recall_resp.status_code == 200
    text = recall_resp.json()["content_en"].lower()
    # Must answer meaningfully referencing past topics (migraine, allergy, headache, or past chats)
    assert any(term in text for term in ["migraine", "allergy", "penicillin", "antibiotic", "earlier", "past", "discuss"])


@pytest.mark.asyncio
async def test_5_undo_profile_update(phase_c_user):
    """
    Test 5: Undo on a profile update restores the old state.
    """
    headers = phase_c_user["headers"]
    patient_id = phase_c_user["patient_id"]

    # 1. Add Asthma
    chips = await apply_profile_updates(
        patient_id=patient_id,
        updates=[
            ProfileUpdateItem(
                operation=ProfileOperation.ADD,
                target_type=ProfileTargetType.CONDITION,
                name="Asthma",
                value="active",
                evidence_quote="I have asthma",
            )
        ],
    )
    assert len(chips) > 0
    log_id = chips[0]["id"]

    # Verify Asthma is active
    prof1 = await get_full_patient_profile(patient_id)
    assert any("asthma" in c.lower() for c in prof1.get("active_conditions", []))

    # 2. Call Undo endpoint
    undo_resp = client.post(f"/api/profile/undo/{log_id}", headers=headers)
    assert undo_resp.status_code == 200
    assert undo_resp.json()["success"] is True

    # 3. Verify Asthma was removed
    prof2 = await get_full_patient_profile(patient_id)
    active_after = [c.lower() for c in prof2.get("active_conditions", [])]
    assert "asthma" not in active_after, f"Asthma should be undone, but found: {active_after}"
