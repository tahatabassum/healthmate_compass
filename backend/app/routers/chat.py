"""
Chat & Symptom Triage Router for HealthMate Compass.
Wires the LangGraph chat_graph into the FastAPI API.
Handles sessions, message history, emergency alerts, and specialist suggestions.
"""
import logging
from typing import List, Optional, Dict, Any
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from app.core.security import get_current_user, AuthUser
from app.core.supabase import get_supabase_admin
from app.graph.chat import chat_graph
from app.routers.patients import get_or_create_user_profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


class AutoTitleOutput(BaseModel):
    title: str


class ChatSessionCreate(BaseModel):
    patient_id: Optional[str] = None
    title: Optional[str] = "Symptom Consultation"


class ChatSessionUpdate(BaseModel):
    title: str


class ChatSessionOut(BaseModel):
    id: str
    patient_id: str
    title: str
    risk_level: Optional[str] = None
    created_at: Optional[str] = None


class ChatMessageCreate(BaseModel):
    session_id: str
    content: str
    lang: str = "en"  # "en" or "ur"


class ChatMessageOut(BaseModel):
    id: Optional[str] = None
    session_id: str
    role: str  # "user" or "assistant"
    content: str
    meta: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None


class ChatTurnResponse(BaseModel):
    session_id: str
    role: str = "assistant"
    content_en: str
    content_ur: str
    is_emergency: bool = False
    emergency_action: Optional[Dict[str, Any]] = None
    risk_level: Optional[str] = None
    recommended_specialty: Optional[str] = None
    possible_causes: List[str] = []
    self_care: List[str] = []
    questions_for_doctor: List[str] = []
    session_title: Optional[str] = None
    profile_updates: List[Dict[str, Any]] = []


@router.post("/session", response_model=ChatSessionOut, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    payload: ChatSessionCreate,
    user: AuthUser = Depends(get_current_user),
):
    """Creates a new AI Doctor chat consultation session."""
    profile = await get_or_create_user_profile(user)
    patient_id = profile["id"]
    session_id = str(uuid4())
    supabase = get_supabase_admin()
    if supabase:
        supabase.table("chat_sessions").insert({
            "id": session_id,
            "patient_id": patient_id,
            "title": payload.title or "Symptom Consultation",
        }).execute()

    return ChatSessionOut(
        id=session_id,
        patient_id=patient_id,
        title=payload.title or "Symptom Consultation",
    )


@router.get("/sessions", response_model=List[ChatSessionOut])
async def list_chat_sessions(
    patient_id: Optional[str] = Query(None),
    user: AuthUser = Depends(get_current_user),
):
    """Lists past consultation sessions for authenticated user."""
    profile = await get_or_create_user_profile(user)
    target_patient_id = profile["id"]
    supabase = get_supabase_admin()
    if not supabase:
        return [
            ChatSessionOut(
                id="session-demo-1",
                patient_id=target_patient_id,
                title="Recent Consultation (Demo)",
            )
        ]

    res = (
        supabase.table("chat_sessions")
        .select("*")
        .eq("patient_id", target_patient_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [ChatSessionOut(**r) for r in (res.data or [])]


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageOut])
async def get_session_messages(
    session_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """Fetches chat history for a session."""
    supabase = get_supabase_admin()
    if not supabase:
        return []

    res = (
        supabase.table("chat_messages")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at")
        .execute()
    )
    messages_out = []
    for r in (res.data or []):
        r_copy = dict(r)
        r_copy["id"] = str(r_copy.get("id"))
        messages_out.append(ChatMessageOut(**r_copy))
    return messages_out


@router.patch("/sessions/{session_id}", response_model=ChatSessionOut)
async def rename_chat_session(
    session_id: str,
    payload: ChatSessionUpdate,
    user: AuthUser = Depends(get_current_user),
):
    """Renames consultation session with patient profile ownership validation."""
    profile = await get_or_create_user_profile(user)
    patient_id = profile["id"]
    supabase = get_supabase_admin()
    if not supabase:
        return ChatSessionOut(id=session_id, patient_id=patient_id, title=payload.title.strip())

    existing = supabase.table("chat_sessions").select("*").eq("id", session_id).eq("patient_id", patient_id).execute()
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")

    res = (
        supabase.table("chat_sessions")
        .update({"title": payload.title.strip()})
        .eq("id", session_id)
        .eq("patient_id", patient_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to rename chat session")
    return ChatSessionOut(**res.data[0])


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    session_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """Deletes consultation session and cascades to messages and memories."""
    profile = await get_or_create_user_profile(user)
    patient_id = profile["id"]
    supabase = get_supabase_admin()
    if supabase:
        existing = supabase.table("chat_sessions").select("id").eq("id", session_id).eq("patient_id", patient_id).execute()
        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
        supabase.table("chat_sessions").delete().eq("id", session_id).eq("patient_id", patient_id).execute()
    return None


async def generate_chat_title(text: str) -> str:
    """Generates a concise 3-5 word title with call_llm() and 30-char fallback."""
    cleaned = text.strip()
    fallback = (cleaned[:30] + "...") if len(cleaned) > 30 else cleaned
    try:
        from app.llm.client import call_llm
        res = await call_llm(
            messages=[
                {
                    "role": "system",
                    "content": "You are a concise medical title generator. Generate a 3 to 5 word summary title for this patient's inquiry or symptoms. Output ONLY the short title. No quotes, no markdown, no punctuation.",
                },
                {"role": "user", "content": text},
            ],
            response_model=AutoTitleOutput,
            temperature=0.3,
        )
        if res and res.title and len(res.title.strip()) > 2:
            return res.title.strip().replace('"', '')
    except Exception as e:
        logger.warning(f"Auto-title LLM call failed, using fallback: {e}")
    return fallback


@router.post("/message", response_model=ChatTurnResponse)
async def send_chat_message(
    payload: ChatMessageCreate,
    user: AuthUser = Depends(get_current_user),
):
    """
    Submits a symptom or health inquiry.
    Executes LangGraph workflow:
    - Emergency rule engine (runs first, zero LLM calls)
    - Medical facts & guideline retrieval
    - Gemma 4 triage reasoning
    - Fact extraction & cross-session memory update
    - Auto-titling if initial message
    """
    supabase = get_supabase_admin()
    profile = await get_or_create_user_profile(user)
    patient_id = profile["id"]
    updated_title: Optional[str] = None

    if supabase:
        ses_res = supabase.table("chat_sessions").select("patient_id, title").eq("id", payload.session_id).execute()
        if ses_res.data:
            patient_id = ses_res.data[0]["patient_id"]
            current_title = ses_res.data[0].get("title", "")
            # Auto-title on first message or default placeholder
            if not current_title or current_title in ("Symptom Consultation", "New Chat", "Consultation"):
                try:
                    updated_title = await generate_chat_title(payload.content)
                    supabase.table("chat_sessions").update({"title": updated_title}).eq("id", payload.session_id).execute()
                except Exception as e:
                    logger.warning(f"Failed to auto-title session: {e}")

        # Record user message in DB
        supabase.table("chat_messages").insert({
            "session_id": payload.session_id,
            "role": "user",
            "content": payload.content,
        }).execute()

    # Invoke LangGraph
    initial_state = {
        "session_id": payload.session_id,
        "patient_id": patient_id,
        "user_text": payload.content,
        "lang": payload.lang,
        "profile": {},
        "facts": [],
        "memories": [],
        "guidelines": [],
        "is_emergency": False,
        "emergency_action": None,
        "triage_result": None,
        "response_en": "",
        "response_ur": "",
    }

    final_state = await chat_graph.ainvoke(initial_state)

    is_emergency = final_state.get("is_emergency", False)
    emergency_action = final_state.get("emergency_action")
    triage = final_state.get("triage_result") or {}

    response_en = final_state.get("response_en", "")
    response_ur = final_state.get("response_ur", "")
    risk_level = triage.get("risk") or ("CRITICAL" if is_emergency else "LOW")
    specialty = triage.get("specialty", "General Physician")
    causes = triage.get("possible_causes", [])
    self_care = triage.get("self_care", [])
    questions = triage.get("questions_for_doctor", [])

    applied_chips = final_state.get("applied_chips") or []

    meta_payload = {
        "is_emergency": is_emergency,
        "risk_level": risk_level,
        "specialty": specialty,
        "response_en": response_en,
        "response_ur": response_ur,
        "emergency_action": emergency_action,
        "profile_updates": applied_chips,
    }

    # Record assistant message in DB
    if supabase:
        primary_content = response_ur if payload.lang == "ur" else response_en
        supabase.table("chat_messages").insert({
            "session_id": payload.session_id,
            "role": "assistant",
            "content": primary_content,
            "meta": meta_payload,
        }).execute()

        # Update session risk level
        supabase.table("chat_sessions").update({
            "risk_level": risk_level,
        }).eq("id", payload.session_id).execute()

    return ChatTurnResponse(
        session_id=payload.session_id,
        content_en=response_en,
        content_ur=response_ur,
        is_emergency=is_emergency,
        emergency_action=emergency_action,
        risk_level=risk_level,
        recommended_specialty=specialty,
        possible_causes=causes,
        self_care=self_care,
        questions_for_doctor=questions,
        session_title=updated_title,
        profile_updates=applied_chips,
    )


@router.get("/debug/memory/{session_id}")
async def get_chat_memory_debug(
    session_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """
    Step A Memory Debug Endpoint:
    Inspects exactly what the assistant loads and grounds against for this session:
    - Demographic profile and active/resolved conditions
    - Active persistent medical facts (allergies, medications)
    - Deterministic past session summaries (up to 3 prior sessions)
    - Semantic memory matches with cosine similarity scores
    - Recent conversation turns
    - Full rendered prompt preview and token estimate
    """
    from app.services.memory import (
        get_full_patient_profile,
        get_active_facts_for_patient,
        get_recent_chat_summaries,
        retrieve_memories_with_scores,
    )
    from app.llm.prompts import TRIAGE_CHAT_PROMPT

    profile = await get_or_create_user_profile(user)
    patient_id = profile["id"]
    supabase = get_supabase_admin()

    if supabase:
        ses = supabase.table("chat_sessions").select("patient_id").eq("id", session_id).execute()
        if ses.data:
            patient_id = ses.data[0]["patient_id"]

    full_profile = await get_full_patient_profile(patient_id)
    active_facts = await get_active_facts_for_patient(patient_id)
    past_summaries = await get_recent_chat_summaries(
        patient_id=patient_id,
        exclude_session_id=session_id,
        limit=3,
    )

    # Load recent messages
    recent_msgs = []
    recent_turns_str = "None (Start of conversation)"
    if supabase and session_id:
        try:
            m_res = (
                supabase.table("chat_messages")
                .select("role, content, created_at")
                .eq("session_id", session_id)
                .order("created_at")
                .limit(8)
                .execute()
            )
            if m_res.data:
                recent_msgs = m_res.data
                recent_turns_str = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in recent_msgs])
        except Exception as e:
            logger.debug(f"Debug loader recent msgs notice: {e}")

    # Query last message for semantic memory test
    last_query = recent_msgs[-1]["content"] if recent_msgs else "health checkup"
    semantic_matches = await retrieve_memories_with_scores(
        patient_id=patient_id,
        query_text=last_query,
        k=4,
    )

    # Render prompt
    active_conds = full_profile.get("active_conditions") or []
    resolved_conds = full_profile.get("resolved_conditions") or []
    active_facts_str = "\n".join([
        f"- {f.get('fact_type')}: {f.get('key')} = {f.get('value')}"
        for f in active_facts
        if f.get("status") == "active" and f.get("fact_type") != "chat_summary"
    ]) or "None recorded"

    past_summaries_str = "\n".join([
        f"- Consultation ({s.get('title', 'Previous')}): {s.get('summary')}"
        for s in past_summaries
    ]) or "No previous consultation summaries found"

    semantic_str = "\n".join([f"- {m['content']} (score: {m.get('similarity')})" for m in semantic_matches]) or "None"

    rendered_prompt = TRIAGE_CHAT_PROMPT.format(
        patient_name=full_profile.get("full_name", "Patient"),
        relation=full_profile.get("relation", "self"),
        age=full_profile.get("age", "Adult"),
        gender=full_profile.get("gender", "Not specified"),
        chronic_conditions=", ".join(active_conds) or "None recorded",
        resolved_conditions=", ".join(resolved_conds) or "None",
        allergies=", ".join(full_profile.get("allergies", [])) or "None recorded",
        active_medications=", ".join(full_profile.get("active_medications", [])) or "None recorded",
        active_facts=active_facts_str,
        past_summaries=past_summaries_str,
        recent_conversation=recent_turns_str,
        semantic_memories=semantic_str,
        guidelines="General clinical principles",
        user_message=last_query,
    )

    approx_tokens = int(len(rendered_prompt.split()) * 1.3)

    return {
        "session_id": session_id,
        "patient_id": patient_id,
        "profile_injected": full_profile,
        "memory_facts_injected": active_facts,
        "past_summaries_injected": past_summaries,
        "semantic_memories_retrieved": semantic_matches,
        "recent_turns_count": len(recent_msgs),
        "recent_conversation": recent_turns_str,
        "prompt_sections": {
            "profile": {
                "active_conditions": active_conds,
                "resolved_conditions": resolved_conds,
                "allergies": full_profile.get("allergies", []),
                "active_medications": full_profile.get("active_medications", []),
            },
            "active_facts": active_facts_str,
            "past_summaries": past_summaries_str,
            "semantic_memories": semantic_str,
        },
        "approx_token_count": approx_tokens,
        "raw_prompt_preview": rendered_prompt,
    }
