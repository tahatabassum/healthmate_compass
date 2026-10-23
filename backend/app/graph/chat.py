"""
LangGraph AI Doctor Symptom Chat & Triage Flow for HealthMate Compass.
Follows PRD Section 12 strictly:
load_profile -> emergency_check --(yes)--> emergency_response -> END
                    |
                   (no)
                    v
        retrieve_memory -> retrieve_guidelines -> triage_answer -> save_memory -> END
"""
import logging
from typing import TypedDict, Optional, List, Dict, Any
from langgraph.graph import StateGraph, END, START

from app.core.supabase import get_supabase_admin
from app.services.emergency import check_emergency, EmergencyCheckResult
from app.services.memory import (
    get_active_facts_for_patient,
    get_full_patient_profile,
    retrieve_memories,
    retrieve_cross_chat_memories,
    retrieve_guidelines,
    save_memory_facts,
    save_summary_embedding,
    apply_profile_updates,
    get_or_create_rolling_summary,
    get_recent_chat_summaries,
)
from app.llm import client as llm_client
from app.llm.schemas import TriageResult
from app.llm.prompts import TRIAGE_CHAT_PROMPT

logger = logging.getLogger(__name__)


class ChatGraphState(TypedDict):
    session_id: str
    patient_id: str
    user_text: str
    lang: str
    profile: Dict[str, Any]
    facts: List[Dict[str, Any]]
    past_summaries: List[Dict[str, Any]]
    recent_conversation: str
    memories: List[str]
    guidelines: List[str]
    is_emergency: bool
    emergency_action: Optional[Dict[str, Any]]
    triage_result: Optional[Dict[str, Any]]
    profile_updates: List[Dict[str, Any]]
    applied_chips: List[Dict[str, Any]]
    response_en: str
    response_ur: str
    prompt_preview: Optional[str]


# ── Graph Node 1: Load Profile & Recent Turns ───────────────────────────────
async def node_load_profile(state: ChatGraphState) -> Dict[str, Any]:
    patient_id = state["patient_id"]
    session_id = state.get("session_id", "")

    # 1. Full structured profile & active persistent facts
    profile_data = await get_full_patient_profile(patient_id)
    facts = await get_active_facts_for_patient(patient_id)

    # 2. Deterministic recent session summaries (up to 3 prior consultations)
    past_summaries = await get_recent_chat_summaries(
        patient_id=patient_id,
        exclude_session_id=session_id,
        limit=3,
    )

    # 3. Recent turns from current session (last 8 messages)
    recent_turns = "None (Start of conversation)"
    supabase = get_supabase_admin()
    if supabase and session_id:
        try:
            m_res = (
                supabase.table("chat_messages")
                .select("role, content")
                .eq("session_id", session_id)
                .order("created_at")
                .limit(8)
                .execute()
            )
            if m_res.data:
                recent_turns = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in m_res.data])
        except Exception as e:
            logger.debug(f"Error loading recent turns: {e}")

    return {
        "profile": profile_data,
        "facts": facts,
        "past_summaries": past_summaries,
        "recent_conversation": recent_turns,
    }


# ── Graph Node 2: Emergency Check (Zero LLM) ────────────────────────────────
async def node_emergency_check(state: ChatGraphState) -> Dict[str, Any]:
    check: EmergencyCheckResult = check_emergency(state["user_text"])
    if check.is_emergency:
        return {
            "is_emergency": True,
            "emergency_action": {
                "matched_term": check.matched_term,
                "emergency_number": check.emergency_number,
                "emergency_service": check.emergency_service,
                "instruction_en": check.instruction_en,
                "instruction_ur": check.instruction_ur,
                "helplines": check.helplines,
            },
            "response_en": check.instruction_en,
            "response_ur": check.instruction_ur,
        }
    return {"is_emergency": False, "emergency_action": None}


def route_after_emergency(state: ChatGraphState) -> str:
    if state.get("is_emergency"):
        return "emergency_response"
    return "retrieve_memory"


# ── Graph Node 3: Emergency Response Exit ───────────────────────────────────
async def node_emergency_response(state: ChatGraphState) -> Dict[str, Any]:
    return {}


# ── Graph Node 4: Retrieve Cross-Chat Memory (pgvector top-k=4) ─────────────
async def node_retrieve_memory(state: ChatGraphState) -> Dict[str, Any]:
    memories = await retrieve_cross_chat_memories(
        patient_id=state["patient_id"],
        current_session_id=state["session_id"],
        query_text=state["user_text"],
        k=4,
    )
    return {"memories": memories}


# ── Graph Node 5: Retrieve Guidelines (WHO/CDC top-k=3) ─────────────────────
async def node_retrieve_guidelines(state: ChatGraphState) -> Dict[str, Any]:
    guidelines = await retrieve_guidelines(state["user_text"], k=3)
    return {"guidelines": guidelines}


# ── Graph Node 6: Triage Answer with Gemma 4 ─────────────────────────────────
async def node_triage_answer(state: ChatGraphState) -> Dict[str, Any]:
    prof = state["profile"]
    active_conds = prof.get("active_conditions") or prof.get("chronic_conditions") or []
    resolved_conds = prof.get("resolved_conditions") or []

    # Filter out internal chat_summary facts from active_facts list
    active_facts_str = "\n".join([
        f"- {f.get('fact_type')}: {f.get('key')} = {f.get('value')}"
        for f in state.get("facts", [])
        if f.get("status") == "active" and f.get("fact_type") != "chat_summary"
    ]) or "None recorded"

    # Deterministic past session summaries
    past_summaries_list = state.get("past_summaries", [])
    past_summaries_str = "\n".join([
        f"- Consultation ({s.get('title', 'Previous')}): {s.get('summary')}"
        for s in past_summaries_list
    ]) or "No previous consultation summaries found"

    semantic_memories_str = "\n".join([f"- {m}" for m in state.get("memories", [])]) or "None"
    guidelines_str = "\n".join([f"- {g}" for g in state.get("guidelines", [])]) or "General clinical principles"

    prompt = TRIAGE_CHAT_PROMPT.format(
        patient_name=prof.get("full_name", "Patient"),
        relation=prof.get("relation", "self"),
        age=prof.get("age", "Adult"),
        gender=prof.get("gender", "Not specified"),
        chronic_conditions=", ".join(active_conds) or "None recorded",
        resolved_conditions=", ".join(resolved_conds) or "None",
        allergies=", ".join(prof.get("allergies", [])) or "None recorded",
        active_medications=", ".join(prof.get("active_medications", [])) or "None recorded",
        active_facts=active_facts_str,
        past_summaries=past_summaries_str,
        recent_conversation=state.get("recent_conversation", "None"),
        semantic_memories=semantic_memories_str,
        guidelines=guidelines_str,
        user_message=state["user_text"],
    )

    triage: TriageResult = await llm_client.call_llm(
        messages=[
            {"role": "system", "content": "You are HealthMate Compass, a helpful, cautious health triage assistant. You do not diagnose."},
            {"role": "user", "content": prompt},
        ],
        response_model=TriageResult,
        temperature=0.2,
    )

    triage_dict = triage.model_dump()
    return {
        "triage_result": triage_dict,
        "response_en": triage.answer_en,
        "response_ur": triage.answer_ur,
        "profile_updates": triage_dict.get("profile_updates", []),
        "prompt_preview": prompt,
    }


def extract_memory_directives(text: str) -> List[Any]:
    from app.llm.schemas import MemoryFact, FactType
    import re
    facts = []
    if not text:
        return facts

    # 1. Preferred language check
    lang_match = re.search(r"(?:preferred\s+language|remember\s+that.*language)\s+(?:is|to\s+be)?\s*([A-Za-z]+)", text, re.I)
    if lang_match:
        val = lang_match.group(1).strip().capitalize()
        if val.lower() in ("urdu", "english", "arabic", "spanish", "french", "punjabi", "hindi"):
            facts.append(MemoryFact(
                fact_type=FactType.PREFERENCE,
                key="preferred_language",
                value=val,
                status="active",
            ))

    # 2. General "remember that X" directives
    rem_match = re.search(r"\b(?:remember\s+that|please\s+remember\s+that|keep\s+in\s+mind\s+that)\s+([^.!?]+)", text, re.I)
    if rem_match:
        phrase = rem_match.group(1).strip()
        prop_match = re.match(r"^(?:my\s+)?([a-zA-Z\s]+?)\s+is\s+([^.!?]+)$", phrase, re.I)
        if prop_match:
            k = prop_match.group(1).strip().lower().replace(" ", "_")
            v = prop_match.group(2).strip()
            if not any(f.key == k for f in facts):
                facts.append(MemoryFact(
                    fact_type=FactType.PREFERENCE,
                    key=k,
                    value=v,
                    status="active",
                ))
        else:
            if not facts:
                facts.append(MemoryFact(
                    fact_type=FactType.GENERAL,
                    key="user_note",
                    value=phrase,
                    status="active",
                ))
    return facts


# ── Graph Node 7: Save Memory, Profile Updates & Rolling Summary ─────────────
async def node_save_memory(state: ChatGraphState) -> Dict[str, Any]:
    triage_data = state.get("triage_result") or {}
    patient_id = state["patient_id"]
    session_id = state["session_id"]
    user_text = state.get("user_text", "")
    applied_chips = []

    # 1. Apply explicit profile updates (add / resolve condition, allergy, medication)
    raw_updates = triage_data.get("profile_updates") or []
    if raw_updates:
        try:
            applied_chips = await apply_profile_updates(
                patient_id=patient_id,
                updates=raw_updates,
                session_id=session_id,
            )
        except Exception as e:
            logger.error(f"Error applying profile updates: {e}")

    # 2. Save any new facts from LLM
    from app.llm.schemas import MemoryFact
    facts_to_save: List[MemoryFact] = []
    if "new_facts" in triage_data and triage_data["new_facts"]:
        new_facts = triage_data["new_facts"]
        parsed_facts = [MemoryFact(**f) if isinstance(f, dict) else f for f in new_facts]
        facts_to_save.extend(parsed_facts)

    # 3. Deterministic user directives to remember (e.g. "remember that my preferred language is Urdu")
    directive_facts = extract_memory_directives(user_text)
    for df in directive_facts:
        if not any(f.key == df.key for f in facts_to_save):
            facts_to_save.append(df)

    if facts_to_save:
        try:
            await save_memory_facts(
                patient_id=patient_id,
                facts=facts_to_save,
                source_type="chat",
                source_id=session_id,
            )
        except Exception as e:
            logger.error(f"Error persisting memory facts: {e}")

    # 4. Rolling summary & 768d embedding (forced with current turn included)
    try:
        await get_or_create_rolling_summary(
            session_id=session_id,
            patient_id=patient_id,
            current_user_text=state.get("user_text"),
            current_assistant_text=state.get("response_en"),
            force=True,
        )
    except Exception as e:
        logger.debug(f"Rolling summary notice: {e}")

    return {"applied_chips": applied_chips}


# ── Build & Compile Graph ────────────────────────────────────────────────────
builder = StateGraph(ChatGraphState)

builder.add_node("load_profile", node_load_profile)
builder.add_node("emergency_check", node_emergency_check)
builder.add_node("emergency_response", node_emergency_response)
builder.add_node("retrieve_memory", node_retrieve_memory)
builder.add_node("retrieve_guidelines", node_retrieve_guidelines)
builder.add_node("triage_answer", node_triage_answer)
builder.add_node("save_memory", node_save_memory)

builder.add_edge(START, "load_profile")
builder.add_edge("load_profile", "emergency_check")
builder.add_conditional_edges(
    "emergency_check",
    route_after_emergency,
    {
        "emergency_response": "emergency_response",
        "retrieve_memory": "retrieve_memory",
    },
)
builder.add_edge("emergency_response", END)
builder.add_edge("retrieve_memory", "retrieve_guidelines")
builder.add_edge("retrieve_guidelines", "triage_answer")
builder.add_edge("triage_answer", "save_memory")
builder.add_edge("save_memory", END)

chat_graph = builder.compile()
