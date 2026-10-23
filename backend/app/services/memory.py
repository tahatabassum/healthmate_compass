"""
Memory Service for HealthMate Compass.
Handles:
1. Persistent extracted facts (`memory_facts` table) with deduplication & superseding merge rules.
2. Vector embeddings (`memory_embeddings` table) with strict 768-dim embeddings and `match_memories()` RPC.
3. Medical guideline retrieval (`guideline_chunks` table) via `match_guidelines()` RPC.
"""
import logging
from typing import List, Optional, Dict, Any
from uuid import uuid4
from app.core.supabase import get_supabase_admin
from app.llm import client as llm_client
from app.llm.schemas import MemoryFact, FactType

logger = logging.getLogger(__name__)


async def get_embedding(text: str) -> List[float]:
    return await llm_client.get_embedding(text)


async def save_memory_facts(
    patient_id: str,
    facts: List[MemoryFact],
    source_type: str = "report",
    source_id: Optional[str] = None,
) -> List[dict]:
    """
    Saves extracted memory facts with merge rules:
    - If active fact with same (patient_id, fact_type, key) exists:
      Marks old fact as status='superseded' and sets superseded_by = new_fact_id.
    - If fact is resolved or superseded, stores it with that explicit status.
    """
    supabase = get_supabase_admin()
    if not supabase or not facts:
        return []

    saved_facts = []

    for fact in facts:
        new_fact_id = str(uuid4())
        norm_key = fact.key.lower().strip()
        norm_val = fact.value.strip()

        # Determine target status
        target_status = getattr(fact, "status", None) or "active"
        if "resolved" in norm_val.lower():
            target_status = "resolved"
        elif "stopped" in norm_val.lower() or "no longer" in norm_val.lower():
            target_status = "superseded"

        try:
            # Check for existing active fact
            existing = (
                supabase.table("memory_facts")
                .select("id")
                .eq("patient_id", patient_id)
                .eq("fact_type", fact.fact_type.value if hasattr(fact.fact_type, "value") else str(fact.fact_type))
                .eq("key", norm_key)
                .eq("status", "active")
                .execute()
            )

            # Supersede existing facts of same key
            if existing.data:
                for old_row in existing.data:
                    supabase.table("memory_facts").update({
                        "status": "superseded",
                        "superseded_by": new_fact_id,
                    }).eq("id", old_row["id"]).execute()

            # Insert fact with computed status
            row = {
                "id": new_fact_id,
                "patient_id": patient_id,
                "fact_type": fact.fact_type.value if hasattr(fact.fact_type, "value") else str(fact.fact_type),
                "key": norm_key,
                "value": norm_val,
                "status": target_status,
                "source_type": source_type,
                "source_id": source_id,
                "confidence": fact.confidence,
            }
            res = supabase.table("memory_facts").insert(row).execute()
            if res.data:
                saved_facts.append(res.data[0])

        except Exception as e:
            logger.error(f"Error persisting memory fact '{fact.key}': {e}")

    return saved_facts


async def get_active_facts_for_patient(patient_id: str) -> List[dict]:
    """Fetches all active facts for prompt grounding."""
    supabase = get_supabase_admin()
    if not supabase:
        return []

    try:
        res = (
            supabase.table("memory_facts")
            .select("*")
            .eq("patient_id", patient_id)
            .eq("status", "active")
            .order("created_at")
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.warning(f"Could not load active facts: {e}")
        return []


async def save_summary_embedding(
    patient_id: str,
    content: str,
    source_type: str = "report",
    source_id: Optional[str] = None,
) -> Optional[str]:
    """
    Computes 768-dim embedding and stores it in memory_embeddings table.
    """
    supabase = get_supabase_admin()
    if not supabase or not content.strip():
        return None

    try:
        embedding_vector = await get_embedding(content)
        row = {
            "patient_id": patient_id,
            "content": content,
            "source_type": source_type,
            "source_id": source_id,
            "embedding": embedding_vector,
        }
        res = supabase.table("memory_embeddings").insert(row).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]["id"]
    except Exception as e:
        logger.warning(f"Failed to save memory embedding: {e}")

    return None


async def retrieve_memories_with_scores(
    patient_id: str,
    query_text: str,
    k: int = 4,
) -> List[Dict[str, Any]]:
    """
    Searches semantic memory using match_memories() RPC.
    Returns list of dicts with 'content' and 'similarity'.
    Filters out NaN or low similarity (< 0.25) results.
    """
    supabase = get_supabase_admin()
    if not supabase or not query_text.strip():
        return []

    try:
        query_vector = await get_embedding(query_text)
        res = supabase.rpc("match_memories", {
            "p_patient": patient_id,
            "q": query_vector,
            "k": k,
        }).execute()
        if res.data:
            valid_results = []
            for row in res.data:
                content = row.get("content")
                sim = row.get("similarity")
                if not content:
                    continue
                sim_float = 0.0
                try:
                    if sim is not None and str(sim).lower() != "nan":
                        sim_float = float(sim)
                except Exception:
                    sim_float = 0.0
                if sim_float > 0.25 or sim is None:
                    valid_results.append({
                        "content": content,
                        "similarity": round(sim_float, 4),
                        "source_type": row.get("source_type"),
                    })
            return valid_results
    except Exception as e:
        logger.warning(f"match_memories RPC error: {e}")

    return []


async def retrieve_memories(
    patient_id: str,
    query_text: str,
    k: int = 4,
) -> List[str]:
    """
    Searches semantic memory using the match_memories() RPC.
    Returns top-k matching memory snippets.
    """
    results = await retrieve_memories_with_scores(patient_id=patient_id, query_text=query_text, k=k)
    return [r["content"] for r in results]


async def retrieve_guidelines(
    query_text: str,
    k: int = 3,
) -> List[str]:
    """
    Searches medical knowledge base using match_guidelines() RPC.
    """
    supabase = get_supabase_admin()
    if not supabase or not query_text.strip():
        return []

    try:
        query_vector = await get_embedding(query_text)
        res = supabase.rpc("match_guidelines", {
            "q": query_vector,
            "k": k,
        }).execute()
        if res.data:
            return [f"[{r.get('title', 'Guideline')}]: {r.get('content')}" for r in res.data if "content" in r]
    except Exception as e:
        logger.warning(f"match_guidelines RPC error: {e}")

    return []


# ── Structured Profile Retrieval (4b) ─────────────────────────────────────────

async def get_full_patient_profile(patient_id: str) -> Dict[str, Any]:
    """
    Loads complete profile for prompt grounding:
    - Demographic info from patients table
    - Active & resolved conditions from patient_conditions or fallback chronic_conditions
    - Active medications
    - Known allergies
    """
    profile = {
        "id": patient_id,
        "full_name": "Patient",
        "relation": "self",
        "age": "Adult",
        "gender": "Not specified",
        "blood_group": "Unknown",
        "chronic_conditions": [],
        "active_conditions": [],
        "resolved_conditions": [],
        "allergies": [],
        "active_medications": [],
    }

    supabase = get_supabase_admin()
    if not supabase:
        return profile

    # 1. Base patient row
    try:
        p_res = supabase.table("patients").select("*").eq("id", patient_id).execute()
        if p_res.data:
            p = p_res.data[0]
            profile.update({
                "full_name": p.get("full_name", "Patient"),
                "relation": p.get("relation", "self"),
                "gender": p.get("gender", "Not specified"),
                "blood_group": p.get("blood_group", "Unknown"),
                "allergies": p.get("allergies") or [],
            })
            if p.get("dob"):
                try:
                    from datetime import date
                    dob_year = int(str(p["dob"]).split("-")[0])
                    profile["age"] = f"{date.today().year - dob_year} years"
                except Exception:
                    profile["age"] = str(p.get("dob"))
            if p.get("chronic_conditions"):
                profile["chronic_conditions"] = list(p.get("chronic_conditions"))
    except Exception as e:
        logger.warning(f"Error fetching patient row: {e}")

    # 2. Structured conditions table (patient_conditions)
    has_conditions_table = False
    try:
        c_res = (
            supabase.table("patient_conditions")
            .select("*")
            .eq("patient_id", patient_id)
            .order("created_at")
            .execute()
        )
        if c_res.data is not None:
            has_conditions_table = True
            for c in c_res.data:
                c_name = c.get("name", "").strip()
                c_status = c.get("status", "active")
                if c_status == "active":
                    profile["active_conditions"].append(c_name)
                    if c_name not in profile["chronic_conditions"]:
                        profile["chronic_conditions"].append(c_name)
                elif c_status == "resolved":
                    res_date = c.get("resolved_at") or ""
                    date_str = f" (resolved {res_date})" if res_date else " (resolved)"
                    profile["resolved_conditions"].append(f"{c_name}{date_str}")
    except Exception:
        # Table might not exist yet; gracefully fallback
        pass

    if not has_conditions_table and profile["chronic_conditions"]:
        profile["active_conditions"] = list(profile["chronic_conditions"])

    # 3. Active medications
    try:
        m_res = (
            supabase.table("medications")
            .select("name, dosage, frequency")
            .eq("patient_id", patient_id)
            .eq("is_active", True)
            .execute()
        )
        if m_res.data:
            meds = []
            for m in m_res.data:
                desc = m["name"]
                if m.get("dosage"):
                    desc += f" {m['dosage']}"
                if m.get("frequency"):
                    desc += f" ({m['frequency']})"
                meds.append(desc)
            profile["active_medications"] = meds
    except Exception as e:
        logger.warning(f"Error loading medications: {e}")

    # 4. Durable fallback from memory_facts (medications, conditions, allergies)
    try:
        mf_res = (
            supabase.table("memory_facts")
            .select("fact_type, key, value, status")
            .eq("patient_id", patient_id)
            .execute()
        )
        if mf_res.data:
            for row in mf_res.data:
                ft = row.get("fact_type")
                k = (row.get("key") or "").title()
                val = row.get("value") or ""
                st = row.get("status") or "active"

                if ft == "medication":
                    if st == "active":
                        med_label = f"{k} ({val})" if val and val.lower() != "active" and val.lower() != k.lower() else k
                        if not any(k.lower() in existing.lower() for existing in profile["active_medications"]):
                            profile["active_medications"].append(med_label)
                    elif st in ("superseded", "resolved", "inactive"):
                        # Remove from active medications
                        profile["active_medications"] = [
                            m for m in profile["active_medications"] if k.lower() not in m.lower()
                        ]

                elif ft == "condition":
                    if st == "active":
                        if not any(c.lower() == k.lower() for c in profile["active_conditions"]):
                            profile["active_conditions"].append(k)
                        if not any(c.lower() == k.lower() for c in profile["chronic_conditions"]):
                            profile["chronic_conditions"].append(k)
                    elif st in ("superseded", "resolved", "inactive") or "resolved" in val.lower():
                        res_str = f"{k} ({val})" if val and "resolved" in val.lower() else f"{k} (resolved)"
                        if not any(k.lower() in r.lower() for r in profile["resolved_conditions"]):
                            profile["resolved_conditions"].append(res_str)
                        profile["active_conditions"] = [c for c in profile["active_conditions"] if c.lower() != k.lower()]
                        profile["chronic_conditions"] = [c for c in profile["chronic_conditions"] if c.lower() != k.lower()]

                elif ft == "allergy":
                    if st == "active":
                        if not any(a.lower() == k.lower() for a in profile["allergies"]):
                            profile["allergies"].append(k)
                    elif st in ("superseded", "resolved", "inactive"):
                        profile["allergies"] = [a for a in profile["allergies"] if a.lower() != k.lower()]
    except Exception as e:
        logger.debug(f"memory_facts profile sync notice: {e}")

    return profile


# ── Auto-Updating Profile with Change Log & Undo (4c) ─────────────────────────

async def apply_profile_updates(
    patient_id: str,
    updates: List[Any],
    session_id: Optional[str] = None,
    message_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Applies explicit first-person profile changes:
    - Resolves or adds condition in `patient_conditions` + `patients.chronic_conditions`
    - Adds or removes allergies in `patients.allergies`
    - Updates `medications`
    - Records audit row in `profile_change_log`
    - Returns UI chips for the chat interface with Undo IDs.
    """
    supabase = get_supabase_admin()
    if not supabase or not updates:
        return []

    from datetime import date
    today_str = date.today().isoformat()
    applied_chips = []

    # Get current patient state
    patient_row = {}
    try:
        p_res = supabase.table("patients").select("*").eq("id", patient_id).execute()
        if p_res.data:
            patient_row = p_res.data[0]
    except Exception as e:
        logger.error(f"Failed to fetch patient for update: {e}")
        return []

    curr_conditions = list(patient_row.get("chronic_conditions") or [])
    curr_allergies = list(patient_row.get("allergies") or [])

    for item in updates:
        # item can be ProfileUpdateItem or dict
        if isinstance(item, dict):
            op = item.get("operation", "add")
            target_type = item.get("target_type", "condition")
            target_name = item.get("name", "").strip()
            value = item.get("value")
            quote = item.get("evidence_quote", "")
        else:
            op = getattr(item.operation, "value", str(item.operation))
            target_type = getattr(item.target_type, "value", str(item.target_type))
            target_name = str(item.name).strip()
            value = item.value
            quote = item.evidence_quote

        if not target_name:
            continue

        log_id = str(uuid4())
        old_val = None
        new_val = None
        chip_text = ""

        # ── 1. Condition Update ───────────────────────────────────────────────
        if target_type == "condition":
            norm_name = target_name.title()
            if op == "resolve":
                old_val = {"status": "active", "name": norm_name}
                new_val = {"status": "resolved", "resolved_at": today_str, "name": norm_name}
                chip_text = f"Profile updated: {norm_name} marked as recovered"

                # Update patient_conditions table if present
                try:
                    existing = (
                        supabase.table("patient_conditions")
                        .select("id")
                        .eq("patient_id", patient_id)
                        .ilike("name", norm_name)
                        .eq("status", "active")
                        .execute()
                    )
                    if existing.data:
                        for row in existing.data:
                            supabase.table("patient_conditions").update({
                                "status": "resolved",
                                "resolved_at": today_str,
                            }).eq("id", row["id"]).execute()
                    else:
                        supabase.table("patient_conditions").insert({
                            "patient_id": patient_id,
                            "name": norm_name,
                            "status": "resolved",
                            "resolved_at": today_str,
                            "source": "chat",
                        }).execute()
                except Exception as e:
                    logger.debug(f"patient_conditions update note: {e}")

                # Sync patients.chronic_conditions
                curr_conditions = [c for c in curr_conditions if c.lower() != norm_name.lower()]
                supabase.table("patients").update({"chronic_conditions": curr_conditions}).eq("id", patient_id).execute()

                # Sync memory_facts
                await save_memory_facts(
                    patient_id=patient_id,
                    facts=[MemoryFact(fact_type=FactType.CONDITION, key=norm_name.lower(), value=f"resolved on {today_str}")],
                    source_type="chat",
                    source_id=session_id,
                )

            elif op == "add":
                old_val = None
                new_val = {"status": "active", "name": norm_name, "started_at": today_str}
                chip_text = f"Profile updated: Added condition {norm_name}"

                # Update patient_conditions table
                try:
                    supabase.table("patient_conditions").insert({
                        "patient_id": patient_id,
                        "name": norm_name,
                        "status": "active",
                        "started_at": today_str,
                        "source": "chat",
                    }).execute()
                except Exception as e:
                    logger.debug(f"patient_conditions insert note: {e}")

                if not any(c.lower() == norm_name.lower() for c in curr_conditions):
                    curr_conditions.append(norm_name)
                    supabase.table("patients").update({"chronic_conditions": curr_conditions}).eq("id", patient_id).execute()

                await save_memory_facts(
                    patient_id=patient_id,
                    facts=[MemoryFact(fact_type=FactType.CONDITION, key=norm_name.lower(), value="active")],
                    source_type="chat",
                    source_id=session_id,
                )

        # ── 2. Allergy Update ─────────────────────────────────────────────────
        elif target_type == "allergy":
            norm_name = target_name.title()
            if op == "add":
                old_val = None
                new_val = {"allergen": norm_name, "status": "active"}
                chip_text = f"Profile updated: Added allergy to {norm_name}"
                if not any(a.lower() == norm_name.lower() for a in curr_allergies):
                    curr_allergies.append(norm_name)
                    supabase.table("patients").update({"allergies": curr_allergies}).eq("id", patient_id).execute()
                await save_memory_facts(
                    patient_id=patient_id,
                    facts=[MemoryFact(fact_type=FactType.ALLERGY, key=norm_name.lower(), value="active")],
                    source_type="chat",
                    source_id=session_id,
                )
            elif op in ("resolve", "remove"):
                old_val = {"allergen": norm_name}
                new_val = None
                chip_text = f"Profile updated: Removed allergy {norm_name}"
                curr_allergies = [a for a in curr_allergies if a.lower() != norm_name.lower()]
                supabase.table("patients").update({"allergies": curr_allergies}).eq("id", patient_id).execute()

        # ── 3. Medication Update ──────────────────────────────────────────────
        elif target_type == "medication":
            norm_name = target_name.title()
            if op in ("resolve", "remove"):
                old_val = {"name": norm_name, "is_active": True}
                new_val = {"name": norm_name, "is_active": False}
                chip_text = f"Profile updated: Stopped medication {norm_name}"
                # Mark as superseded in memory_facts
                await save_memory_facts(
                    patient_id=patient_id,
                    facts=[
                        MemoryFact(
                            fact_type=FactType.MEDICATION,
                            key=norm_name.lower(),
                            value=f"stopped on {today_str}",
                            status="superseded",
                        )
                    ],
                    source_type="chat",
                    source_id=session_id,
                )
                try:
                    supabase.table("medications").update({"is_active": False}).eq("patient_id", patient_id).ilike("name", norm_name).execute()
                except Exception as e:
                    logger.debug(f"medication stop error: {e}")
            elif op == "add":
                old_val = None
                new_val = {"name": norm_name, "is_active": True, "detail": quote}
                chip_text = f"Profile updated: Added medication {norm_name}"
                # Save to memory_facts
                await save_memory_facts(
                    patient_id=patient_id,
                    facts=[
                        MemoryFact(
                            fact_type=FactType.MEDICATION,
                            key=norm_name.lower(),
                            value=quote or "active",
                            status="active",
                        )
                    ],
                    source_type="chat",
                    source_id=session_id,
                )
                try:
                    supabase.table("medications").insert({
                        "patient_id": patient_id,
                        "name": norm_name,
                        "is_active": True,
                    }).execute()
                except Exception as e:
                    logger.debug(f"medication add error: {e}")

        # ── 4. Log change in profile_change_log ────────────────────────────────
        log_entry = {
            "id": log_id,
            "patient_id": patient_id,
            "change_type": target_type,
            "target_name": target_name,
            "operation": op,
            "old_value": old_val,
            "new_value": new_val,
            "evidence_quote": quote,
            "source_session_id": session_id,
            "source_message_id": message_id,
            "undone": False,
        }

        import json
        try:
            supabase.table("profile_change_log").insert(log_entry).execute()
        except Exception:
            # Fallback storage in memory_facts table if profile_change_log not yet migrated
            try:
                supabase.table("memory_facts").insert({
                    "id": log_id,
                    "patient_id": patient_id,
                    "fact_type": "change_log",
                    "key": log_id,
                    "value": json.dumps(log_entry),
                    "status": "active",
                    "source_type": "chat",
                }).execute()
            except Exception as e:
                logger.debug(f"memory_facts log fallback note: {e}")

        applied_chips.append({
            "id": log_id,
            "text": chip_text,
            "operation": op,
            "target_name": target_name,
            "target_type": target_type,
            "evidence_quote": quote,
        })

    return applied_chips


# ── Undo Profile Change (4c & 4d) ─────────────────────────────────────────────

async def undo_profile_change(log_id: str, patient_id: str) -> Dict[str, Any]:
    """
    Reverts a profile change from profile_change_log:
    - If was 'resolve' condition -> restores to active
    - If was 'add' condition/allergy -> removes it
    - Sets undone = True
    """
    supabase = get_supabase_admin()
    if not supabase:
        return {"success": False, "message": "Database unavailable"}

    import json
    entry = None

    # Try profile_change_log table
    try:
        log_res = (
            supabase.table("profile_change_log")
            .select("*")
            .eq("id", log_id)
            .execute()
        )
        if log_res.data:
            entry = log_res.data[0]
    except Exception:
        pass

    # Fallback to memory_facts if table not yet migrated
    if not entry:
        try:
            mf_res = supabase.table("memory_facts").select("*").eq("key", log_id).execute()
            if mf_res.data:
                entry = json.loads(mf_res.data[0]["value"])
                if mf_res.data[0].get("status") == "undone":
                    entry["undone"] = True
        except Exception as e:
            logger.debug(f"Error reading memory_facts log fallback: {e}")

    if not entry:
        return {"success": False, "message": "Change log entry not found"}

    if entry.get("undone"):
        return {"success": True, "message": "Change was already undone"}

    p_id = entry["patient_id"]
    change_type = entry.get("change_type")
    operation = entry.get("operation")
    target_name = entry.get("target_name")
    norm_name = target_name.title() if target_name else ""

    # Revert patient record
    p_data = supabase.table("patients").select("*").eq("id", p_id).execute()
    patient_row = p_data.data[0] if p_data.data else {}
    curr_conditions = list(patient_row.get("chronic_conditions") or [])
    curr_allergies = list(patient_row.get("allergies") or [])

    if change_type == "condition":
        if operation == "resolve":
            # Restore to active
            try:
                supabase.table("patient_conditions").update({
                    "status": "active",
                    "resolved_at": None,
                }).eq("patient_id", p_id).ilike("name", norm_name).execute()
            except Exception:
                pass
            if not any(c.lower() == norm_name.lower() for c in curr_conditions):
                curr_conditions.append(norm_name)
                supabase.table("patients").update({"chronic_conditions": curr_conditions}).eq("id", p_id).execute()
            try:
                supabase.table("memory_facts").update({"status": "active"}).eq("patient_id", p_id).eq("fact_type", "condition").eq("key", norm_name.lower()).execute()
            except Exception:
                pass

        elif operation == "add":
            # Remove condition
            try:
                supabase.table("patient_conditions").update({
                    "status": "superseded",
                }).eq("patient_id", p_id).ilike("name", norm_name).execute()
            except Exception:
                pass
            curr_conditions = [c for c in curr_conditions if c.lower() != norm_name.lower()]
            supabase.table("patients").update({"chronic_conditions": curr_conditions}).eq("id", p_id).execute()
            try:
                supabase.table("memory_facts").update({"status": "superseded"}).eq("patient_id", p_id).eq("fact_type", "condition").eq("key", norm_name.lower()).execute()
            except Exception:
                pass

    elif change_type == "allergy":
        if operation == "add":
            curr_allergies = [a for a in curr_allergies if a.lower() != norm_name.lower()]
            supabase.table("patients").update({"allergies": curr_allergies}).eq("id", p_id).execute()
            try:
                supabase.table("memory_facts").update({"status": "superseded"}).eq("patient_id", p_id).eq("fact_type", "allergy").eq("key", norm_name.lower()).execute()
            except Exception:
                pass
        elif operation in ("resolve", "remove"):
            if not any(a.lower() == norm_name.lower() for a in curr_allergies):
                curr_allergies.append(norm_name)
                supabase.table("patients").update({"allergies": curr_allergies}).eq("id", p_id).execute()
            try:
                supabase.table("memory_facts").update({"status": "active"}).eq("patient_id", p_id).eq("fact_type", "allergy").eq("key", norm_name.lower()).execute()
            except Exception:
                pass

    elif change_type == "medication":
        if operation == "add":
            # Revert add -> deactivate medication
            try:
                supabase.table("medications").update({"is_active": False}).eq("patient_id", p_id).ilike("name", norm_name).execute()
            except Exception:
                pass
            try:
                supabase.table("memory_facts").update({"status": "superseded"}).eq("patient_id", p_id).eq("fact_type", "medication").eq("key", norm_name.lower()).execute()
            except Exception:
                pass
        elif operation in ("resolve", "remove"):
            # Revert stop -> reactivate medication
            try:
                supabase.table("medications").update({"is_active": True}).eq("patient_id", p_id).ilike("name", norm_name).execute()
            except Exception:
                pass
            try:
                supabase.table("memory_facts").update({"status": "active"}).eq("patient_id", p_id).eq("fact_type", "medication").eq("key", norm_name.lower()).execute()
            except Exception:
                pass

    # Mark log entry as undone
    try:
        supabase.table("profile_change_log").update({"undone": True}).eq("id", log_id).execute()
    except Exception:
        pass
    try:
        supabase.table("memory_facts").update({"status": "undone"}).eq("key", log_id).execute()
    except Exception:
        pass

    return {
        "success": True,
        "message": f"Successfully reverted change for {norm_name}",
        "target_name": norm_name,
        "undone": True,
    }


# ── Rolling Summary & Cross-Chat Embedding (4a & 4d) ─────────────────────────

async def get_or_create_rolling_summary(
    session_id: str,
    patient_id: str,
    messages: Optional[List[Dict[str, str]]] = None,
    current_user_text: Optional[str] = None,
    current_assistant_text: Optional[str] = None,
    force: bool = False,
) -> Optional[str]:
    """
    Summarizes conversation messages into a clinical summary, embeds it at 768d,
    and saves to multiple durable locations (chat_sessions, memory_embeddings, memory_facts).
    """
    supabase = get_supabase_admin()
    if not supabase:
        return None

    try:
        if messages is None:
            msgs_res = (
                supabase.table("chat_messages")
                .select("role, content")
                .eq("session_id", session_id)
                .order("created_at")
                .execute()
            )
            messages = msgs_res.data or []

        # If current turn is supplied, ensure it is included
        transcript_msgs = list(messages)
        if current_user_text and not any(m.get("content") == current_user_text for m in transcript_msgs):
            transcript_msgs.append({"role": "user", "content": current_user_text})
        if current_assistant_text and not any(m.get("content") == current_assistant_text for m in transcript_msgs):
            transcript_msgs.append({"role": "assistant", "content": current_assistant_text})

        if len(transcript_msgs) < 2 and not force:
            return None

        # Build transcript text for summarization
        conv_text = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in transcript_msgs[-8:]])
        if not conv_text.strip():
            return None

        # Generate rolling summary
        from pydantic import BaseModel, Field

        class SessionSummaryOutput(BaseModel):
            summary: str = Field(description="2-3 sentence clinical summary of discussed symptoms, questions, advice, and any medicines or allergies mentioned")

        res = await llm_client.call_llm(
            messages=[
                {
                    "role": "system",
                    "content": "You are a clinical summarizer for HealthMate Compass. Generate a concise 2 to 3 sentence factual summary of the key symptoms, mentioned conditions/medicines/allergies, questions, and advice discussed in this consultation. Keep it neutral and strictly factual.",
                },
                {"role": "user", "content": conv_text},
            ],
            response_model=SessionSummaryOutput,
            temperature=0.2,
        )

        summary_text = res.summary.strip() if res and res.summary else ""
        if not summary_text:
            return None

        # 1. Save summary on chat_sessions table
        try:
            supabase.table("chat_sessions").update({"summary": summary_text}).eq("id", session_id).execute()
        except Exception as e:
            logger.debug(f"chat_sessions.summary column update notice: {e}")

        # 2. Embed summary at 768d in memory_embeddings
        await save_summary_embedding(
            patient_id=patient_id,
            content=f"Past Consultation Summary: {summary_text}",
            source_type="chat_summary",
            source_id=session_id,
        )

        # 3. Save deterministically to memory_facts as chat_summary fact
        await save_memory_facts(
            patient_id=patient_id,
            facts=[
                MemoryFact(
                    fact_type=FactType.CHAT_SUMMARY,
                    key=session_id,
                    value=summary_text,
                    status="active",
                )
            ],
            source_type="chat",
            source_id=session_id,
        )

        return summary_text
    except Exception as e:
        logger.warning(f"Error creating rolling summary: {e}")
        return None


async def get_recent_chat_summaries(
    patient_id: str,
    exclude_session_id: Optional[str] = None,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """
    Deterministically retrieves the most recent consultation summaries for a patient:
    Queries multiple durable sources:
    1. memory_facts (fact_type='chat_summary')
    2. memory_embeddings (source_type='chat_summary')
    3. chat_sessions (summary column)
    Deduplicates and returns the top `limit` summaries sorted newest to oldest.
    """
    supabase = get_supabase_admin()
    if not supabase or not patient_id:
        return []

    summaries: Dict[str, Dict[str, Any]] = {}

    # Source 1: memory_facts where fact_type = 'chat_summary'
    try:
        mf_res = (
            supabase.table("memory_facts")
            .select("id, key, value, created_at")
            .eq("patient_id", patient_id)
            .eq("fact_type", "chat_summary")
            .order("created_at", desc=True)
            .limit(limit * 2)
            .execute()
        )
        if mf_res.data:
            for row in mf_res.data:
                s_id = row.get("key") or row.get("id")
                if exclude_session_id and s_id == exclude_session_id:
                    continue
                if s_id not in summaries and row.get("value"):
                    summaries[s_id] = {
                        "session_id": s_id,
                        "title": "Previous Consultation",
                        "summary": row["value"].strip(),
                        "created_at": row.get("created_at"),
                    }
    except Exception as e:
        logger.debug(f"memory_facts chat_summary lookup notice: {e}")

    # Source 2: memory_embeddings where source_type = 'chat_summary'
    try:
        me_res = (
            supabase.table("memory_embeddings")
            .select("id, source_id, content, created_at")
            .eq("patient_id", patient_id)
            .eq("source_type", "chat_summary")
            .order("created_at", desc=True)
            .limit(limit * 2)
            .execute()
        )
        if me_res.data:
            for row in me_res.data:
                s_id = row.get("source_id") or row.get("id")
                if exclude_session_id and s_id == exclude_session_id:
                    continue
                content = (row.get("content") or "").replace("Past Consultation Summary: ", "").strip()
                if s_id not in summaries and content:
                    summaries[s_id] = {
                        "session_id": s_id,
                        "title": "Previous Consultation",
                        "summary": content,
                        "created_at": row.get("created_at"),
                    }
    except Exception as e:
        logger.debug(f"memory_embeddings chat_summary lookup notice: {e}")

    # Source 3: chat_sessions table if summary column is present
    try:
        cs_res = (
            supabase.table("chat_sessions")
            .select("id, title, summary, created_at")
            .eq("patient_id", patient_id)
            .not_.is_("summary", "null")
            .order("created_at", desc=True)
            .limit(limit * 2)
            .execute()
        )
        if cs_res.data:
            for row in cs_res.data:
                s_id = row.get("id")
                if exclude_session_id and s_id == exclude_session_id:
                    continue
                if s_id not in summaries and row.get("summary"):
                    summaries[s_id] = {
                        "session_id": s_id,
                        "title": row.get("title") or "Previous Consultation",
                        "summary": row["summary"].strip(),
                        "created_at": row.get("created_at"),
                    }
                elif s_id in summaries and row.get("title") and summaries[s_id].get("title") == "Previous Consultation":
                    summaries[s_id]["title"] = row.get("title")
    except Exception as e:
        logger.debug(f"chat_sessions summary lookup notice: {e}")

    sorted_list = sorted(
        summaries.values(),
        key=lambda x: str(x.get("created_at") or ""),
        reverse=True,
    )
    return sorted_list[:limit]


async def retrieve_cross_chat_memories(
    patient_id: str,
    current_session_id: str,
    query_text: str,
    k: int = 4,
) -> List[str]:
    """
    Retrieves top-k relevant cross-chat memories & summaries for prompt grounding:
    Excludes current immediate session ID to ensure past history is retrieved cleanly.
    """
    raw_memories = await retrieve_memories(patient_id=patient_id, query_text=query_text, k=k * 2)
    cleaned = []
    for m in raw_memories:
        m_str = m.strip()
        if m_str and m_str not in cleaned:
            cleaned.append(m_str)
        if len(cleaned) >= k:
            break

    return cleaned
