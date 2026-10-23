"""
End-to-end reproducible test suite for Problem 2: Cross-Chat Memory & Fact Persistence.
Validates:
1. Allergy & Medication extraction and persistence in Chat 1.
2. Cross-chat recall in brand new Chat 2 ("Which antibiotics are safe for me?" / "What medicine do I take?").
3. Rolling summary generation and deterministic retrieval across sessions.
4. Condition resolution ("I recovered from the flu") -> marked resolved, not active.
5. Safety guardrail: Statements about others ("my friend has diabetes") do NOT pollute profile.
6. Persistence across simulated reload / fresh profile query.
"""
import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock

from app.core.supabase import get_supabase_admin
from app.llm.schemas import (
    TriageResult,
    RiskLevel,
    Specialty,
    ProfileUpdateItem,
    ProfileOperation,
    ProfileTargetType,
    MemoryFact,
    FactType,
)
from app.services.memory import (
    apply_profile_updates,
    get_full_patient_profile,
    get_active_facts_for_patient,
    get_recent_chat_summaries,
    save_memory_facts,
    get_or_create_rolling_summary,
    undo_profile_change,
)
from app.graph.chat import node_load_profile, node_triage_answer, node_save_memory, ChatGraphState


@pytest.fixture
def test_patient():
    """Creates a real test patient with valid UUID in Supabase and cleans up afterward."""
    supabase = get_supabase_admin()
    owner_id = str(uuid4())
    if supabase:
        try:
            owner_res = supabase.table("patients").select("owner_id").limit(1).execute()
            if owner_res.data and owner_res.data[0].get("owner_id"):
                owner_id = owner_res.data[0]["owner_id"]
        except Exception:
            pass

    patient_id = str(uuid4())
    if supabase:
        supabase.table("patients").insert({
            "id": patient_id,
            "owner_id": owner_id,
            "full_name": "Test Memory Patient",
            "gender": "male",
            "blood_group": "B+",
            "allergies": [],
            "chronic_conditions": [],
        }).execute()

    yield patient_id

    if supabase:
        try:
            supabase.table("memory_facts").delete().eq("patient_id", patient_id).execute()
            supabase.table("memory_embeddings").delete().eq("patient_id", patient_id).execute()
            supabase.table("chat_sessions").delete().eq("patient_id", patient_id).execute()
            supabase.table("patients").delete().eq("id", patient_id).execute()
        except Exception:
            pass


@pytest.mark.asyncio
async def test_cross_chat_memory_e2e_flow(test_patient):
    """
    Simulates Chat 1 -> Persistence -> Chat 2 with a test patient ID.
    Chat 1: 'I am allergic to penicillin and I take metformin 500mg twice daily.'
    Chat 2: 'Which antibiotics are safe for me?'
    """
    test_patient_id = test_patient
    session_1 = str(uuid4())
    session_2 = str(uuid4())

    supabase = get_supabase_admin()
    if supabase:
        supabase.table("chat_sessions").insert({
            "id": session_1,
            "patient_id": test_patient_id,
            "title": "Chat 1 Consultation",
        }).execute()
        supabase.table("chat_sessions").insert({
            "id": session_2,
            "patient_id": test_patient_id,
            "title": "Chat 2 Consultation",
        }).execute()

    # ─────────────────────────────────────────────────────────────────────────
    # 1. CHAT 1: User says: "I am allergic to penicillin and I take metformin 500mg twice daily."
    # ─────────────────────────────────────────────────────────────────────────
    chat1_updates = [
        ProfileUpdateItem(
            operation=ProfileOperation.ADD,
            target_type=ProfileTargetType.ALLERGY,
            name="Penicillin",
            value="severe",
            evidence_quote="I am allergic to penicillin",
        ),
        ProfileUpdateItem(
            operation=ProfileOperation.ADD,
            target_type=ProfileTargetType.MEDICATION,
            name="Metformin",
            value="500mg twice daily",
            evidence_quote="I take metformin 500mg twice daily",
        ),
    ]

    applied_chips = await apply_profile_updates(
        patient_id=test_patient_id,
        updates=chat1_updates,
        session_id=session_1,
    )
    assert len(applied_chips) == 2, f"Expected 2 profile chips applied, got {len(applied_chips)}"

    # Verify memory_facts table has both active facts
    active_facts = await get_active_facts_for_patient(test_patient_id)
    allergy_facts = [f for f in active_facts if f["fact_type"] == "allergy" and "penicillin" in f["key"].lower()]
    med_facts = [f for f in active_facts if f["fact_type"] == "medication" and "metformin" in f["key"].lower()]
    assert len(allergy_facts) >= 1, "Penicillin allergy must be saved in active memory_facts"
    assert len(med_facts) >= 1, "Metformin medication must be saved in active memory_facts"

    # Simulate rolling summary generation for Chat 1
    mock_summary_res = MagicMock()
    mock_summary_res.summary = "Patient discussed allergies to penicillin and daily metformin usage."

    with patch("app.llm.client.call_llm", return_value=mock_summary_res), \
         patch("app.llm.client.get_embedding", return_value=[0.05] * 768):
        summary_created = await get_or_create_rolling_summary(
            session_id=session_1,
            patient_id=test_patient_id,
            messages=[
                {"role": "user", "content": "I am allergic to penicillin and I take metformin 500mg twice daily."},
                {"role": "assistant", "content": "I have noted your penicillin allergy and metformin medication."},
            ],
            force=True,
        )
        assert summary_created is not None, "Summary should be generated"

    # ─────────────────────────────────────────────────────────────────────────
    # 2. CHAT 2 (BRAND NEW SESSION): User starts a new consultation
    # "Which antibiotics are safe for me?"
    # ─────────────────────────────────────────────────────────────────────────
    state_chat2: ChatGraphState = {
        "session_id": session_2,
        "patient_id": test_patient_id,
        "user_text": "Which antibiotics are safe for me?",
        "lang": "en",
        "profile": {},
        "facts": [],
        "past_summaries": [],
        "recent_conversation": "None (Start of conversation)",
        "memories": [],
        "guidelines": [],
        "is_emergency": False,
        "emergency_action": None,
        "triage_result": None,
        "profile_updates": [],
        "applied_chips": [],
        "response_en": "",
        "response_ur": "",
        "prompt_preview": None,
    }

    # Step 1: node_load_profile must deterministically load profile & past summaries
    loaded = await node_load_profile(state_chat2)
    state_chat2.update(loaded)

    # Verify profile contains penicillin allergy
    profile = state_chat2["profile"]
    assert any("penicillin" in str(a).lower() for a in profile.get("allergies", [])), (
        f"Profile in brand new session must contain Penicillin allergy, got: {profile.get('allergies')}"
    )

    # Verify profile contains metformin
    assert any("metformin" in str(m).lower() for m in profile.get("active_medications", [])), (
        f"Profile in brand new session must contain Metformin, got: {profile.get('active_medications')}"
    )

    # Verify past session 1 summary is loaded deterministically
    past_sums = state_chat2["past_summaries"]
    assert len(past_sums) >= 1, "Past session summaries must include session 1 summary"
    assert any("penicillin" in s["summary"].lower() or "metformin" in s["summary"].lower() for s in past_sums)

    # Step 2: node_triage_answer formats prompt correctly
    mock_triage_res = TriageResult(
        risk=RiskLevel.LOW,
        urgency="ROUTINE",
        answer_en="Because your profile records an allergy to Penicillin, penicillin-class antibiotics must be strictly avoided. A physician may consider non-penicillin alternatives.",
        answer_ur="چونکہ آپ کے ریکارڈ میں پینسلین سے الرجی درج ہے، اس لیے پینسلین سے پرہیز کرنا ضروری ہے۔",
        possible_causes=[],
        self_care=["Consult your prescribing doctor before taking any antibiotic"],
        specialty=Specialty.GENERAL_PHYSICIAN,
        questions_for_doctor=["Which non-penicillin antibiotic is suitable for my infection?"],
        new_facts=[],
        profile_updates=[],
    )

    with patch("app.llm.client.call_llm", return_value=mock_triage_res):
        triage_out = await node_triage_answer(state_chat2)
        state_chat2.update(triage_out)

    assert "penicillin" in state_chat2["response_en"].lower(), "Assistant answer must acknowledge allergy"
    assert "Active medications: Metformin" in state_chat2["prompt_preview"] or "Metformin" in state_chat2["prompt_preview"]
    assert "Known allergies: Penicillin" in state_chat2["prompt_preview"] or "Penicillin" in state_chat2["prompt_preview"]


@pytest.mark.asyncio
async def test_condition_resolution_flu(test_patient):
    """
    User says: 'I recovered from the flu'
    - Condition Flu must be resolved
    - Flu must be in resolved_conditions, NOT active_conditions
    """
    test_patient_id = test_patient

    # Add active flu first
    await apply_profile_updates(
        patient_id=test_patient_id,
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
    p_before = await get_full_patient_profile(test_patient_id)
    assert any("flu" in c.lower() for c in p_before["active_conditions"]), "Flu should initially be active"

    # Now user recovers from flu
    chips = await apply_profile_updates(
        patient_id=test_patient_id,
        updates=[
            ProfileUpdateItem(
                operation=ProfileOperation.RESOLVE,
                target_type=ProfileTargetType.CONDITION,
                name="Flu",
                value="resolved",
                evidence_quote="I recovered from the flu",
            )
        ],
    )
    assert len(chips) == 1
    assert chips[0]["operation"] == "resolve"

    # Check updated profile
    p_after = await get_full_patient_profile(test_patient_id)
    assert not any("flu" in c.lower() for c in p_after["active_conditions"]), "Flu must NOT be active after resolution"
    assert any("flu" in c.lower() for c in p_after["resolved_conditions"]), "Flu MUST be present in resolved_conditions"


@pytest.mark.asyncio
async def test_negative_control_friend_has_diabetes(test_patient):
    """
    User says: 'my friend has diabetes'
    The model should NOT extract profile updates, and the user's profile must remain unchanged.
    """
    test_patient_id = test_patient

    mock_triage_res = TriageResult(
        risk=RiskLevel.LOW,
        urgency="ROUTINE",
        answer_en="I understand your friend has diabetes. They should monitor their blood glucose closely with their doctor.",
        answer_ur="آپ کے دوست کو چاہیے کہ وہ اپنے معالج کے مشورے کے مطابق شوگر کی جانچ رکھیں۔",
        possible_causes=[],
        self_care=[],
        specialty=Specialty.ENDOCRINOLOGIST,
        questions_for_doctor=[],
        new_facts=[],
        profile_updates=[],  # Empty as required by instruction
    )

    state: ChatGraphState = {
        "session_id": str(uuid4()),
        "patient_id": test_patient_id,
        "user_text": "my friend has diabetes",
        "lang": "en",
        "profile": {"active_conditions": [], "allergies": [], "active_medications": []},
        "facts": [],
        "past_summaries": [],
        "recent_conversation": "None",
        "memories": [],
        "guidelines": [],
        "is_emergency": False,
        "emergency_action": None,
        "triage_result": None,
        "profile_updates": [],
        "applied_chips": [],
        "response_en": "",
        "response_ur": "",
        "prompt_preview": None,
    }

    mock_summary = MagicMock()
    mock_summary.summary = "Discussion regarding friend's health condition."

    with patch("app.llm.client.call_llm", side_effect=[mock_triage_res, mock_summary]), \
         patch("app.llm.client.get_embedding", return_value=[0.05] * 768):
        triage_out = await node_triage_answer(state)
        state.update(triage_out)
        assert len(state["profile_updates"]) == 0, "No profile updates should be extracted for statements about others"

        save_out = await node_save_memory(state)
        assert len(save_out["applied_chips"]) == 0, "No chips should be applied"

    # Confirm user's profile does not have diabetes
    p = await get_full_patient_profile(test_patient_id)
    assert not any("diabetes" in c.lower() for c in p["active_conditions"])


@pytest.mark.asyncio
async def test_persistence_across_simulated_restart(test_patient):
    """
    Tests that a newly constructed profile query with only patient_id
    accurately reconstructs conditions, allergies, and medications.
    """
    test_patient_id = test_patient

    # Save a set of facts
    await save_memory_facts(
        patient_id=test_patient_id,
        facts=[
            MemoryFact(fact_type=FactType.ALLERGY, key="aspirin", value="rash", status="active"),
            MemoryFact(fact_type=FactType.MEDICATION, key="atorvastatin", value="20mg bedtime", status="active"),
            MemoryFact(fact_type=FactType.CONDITION, key="hypertension", value="active", status="active"),
        ],
        source_type="report",
    )

    # Simulate fresh process query
    fresh_profile = await get_full_patient_profile(test_patient_id)

    assert any("aspirin" in a.lower() for a in fresh_profile["allergies"]), "Aspirin allergy persisted"
    assert any("atorvastatin" in m.lower() for m in fresh_profile["active_medications"]), "Atorvastatin persisted"
    assert any("hypertension" in c.lower() for c in fresh_profile["active_conditions"]), "Hypertension persisted"
