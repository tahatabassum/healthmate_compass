"""
Reports router for HealthMate Compass.
Handles report upload, dual-pass analysis, storage, and retrieval.
"""
import os
import uuid
import json
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel
from app.core.security import get_current_user, AuthUser
from app.core.supabase import get_supabase_admin
from app.services.extractor import run_report_pipeline, generate_report_explanation, run_prescription_pipeline
from app.services.flags import process_extracted_values, compute_overall_risk
from app.llm.schemas import (
    ExtractedValue,
    ReportExplanation,
    PrescribedMedicine,
    PrescriptionExtraction,
    MemoryFact,
    FactType,
)
from app.services.memory import save_memory_facts
from app.routers.patients import get_or_create_user_profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports", tags=["reports"])

UPLOAD_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
os.makedirs(UPLOAD_CACHE_DIR, exist_ok=True)


class ReportUploadResponse(BaseModel):
    report_id: str
    patient_id: str
    file_path: str
    status: str


class ReportValueOut(BaseModel):
    id: Optional[str] = None
    report_id: str
    test_name: str
    canonical_name: Optional[str] = None
    value: Optional[float] = None
    raw_value: Optional[str] = None
    unit: Optional[str] = None
    ref_low: Optional[float] = None
    ref_high: Optional[float] = None
    flag: Optional[str] = None
    specialty_hint: Optional[str] = None
    is_user_edited: bool = False
    sanity_error: Optional[str] = None


class ReportDetailOut(BaseModel):
    id: str
    patient_id: str
    file_path: str
    file_type: Optional[str] = None
    report_date: Optional[str] = None
    patient_name_found: Optional[str] = None
    lab_name: Optional[str] = None
    doctor_name: Optional[str] = None
    patient_name_mismatch: bool = False
    mismatch_warning: Optional[str] = None
    document_type: Optional[str] = None
    is_medical_document: bool = True
    rejection_reason: Optional[str] = None
    status: str
    summary_en: Optional[str] = None
    summary_ur: Optional[str] = None
    questions_for_doctor: Optional[Any] = None
    overall_risk: Optional[str] = None
    overall_risk_evidence: List[str] = []
    confidence: Optional[str] = None
    verification_notes: Optional[str] = None
    created_at: Optional[str] = None
    values: List[ReportValueOut] = []
    medicines: List[PrescribedMedicine] = []
    diagnosis_or_notes: Optional[str] = None
    allergy_alerts: List[str] = []
    recommended_specialty: Optional[str] = None


def build_report_detail(row: Dict[str, Any], values: Optional[List[Dict[str, Any]]] = None) -> ReportDetailOut:
    raw_vals = values if values is not None else row.get("report_values") or []
    val_outs = [ReportValueOut(**v) for v in raw_vals]

    meta: Dict[str, Any] = {}
    v_notes = row.get("verification_notes")
    if v_notes:
        try:
            parsed = json.loads(v_notes)
            if isinstance(parsed, dict):
                meta = parsed
            else:
                meta = {"notes": str(v_notes)}
        except Exception:
            meta = {"notes": str(v_notes)}

    # Determine document type reliably
    doc_type = meta.get("document_type")
    if not doc_type:
        if len(val_outs) > 0:
            doc_type = "lab_report"
        elif len(meta.get("medicines", [])) > 0:
            doc_type = "prescription"
        else:
            doc_type = row.get("document_type") or "lab_report"

    # Prescription medicines
    med_items = []
    for m in meta.get("medicines", []):
        try:
            med_items.append(PrescribedMedicine(**m))
        except Exception:
            pass

    # Report date fallback: row.get("report_date") or created_at date
    r_date = row.get("report_date")
    if not r_date and row.get("created_at"):
        try:
            r_date = str(row["created_at"])[:10]
        except Exception:
            pass

    # Recommended specialty
    rec_spec = meta.get("recommended_specialty")
    if not rec_spec and val_outs:
        rec_spec = next((v.specialty_hint for v in val_outs if v.specialty_hint), None)

    return ReportDetailOut(
        id=str(row["id"]),
        patient_id=str(row["patient_id"]),
        file_path=row.get("file_path") or f"{row['patient_id']}/{row['id']}",
        file_type=row.get("file_type") or "image/jpeg",
        report_date=str(r_date) if r_date else None,
        patient_name_found=meta.get("patient_name_found") or row.get("patient_name_found"),
        lab_name=meta.get("lab_name") or row.get("lab_name"),
        doctor_name=meta.get("doctor_name"),
        patient_name_mismatch=meta.get("patient_name_mismatch", False),
        mismatch_warning=meta.get("mismatch_warning"),
        document_type=doc_type,
        is_medical_document=meta.get("is_medical_document", True),
        rejection_reason=meta.get("rejection_reason"),
        status=row.get("status") or "uploaded",
        summary_en=row.get("summary_en"),
        summary_ur=row.get("summary_ur"),
        questions_for_doctor=row.get("questions_for_doctor"),
        overall_risk=row.get("overall_risk"),
        overall_risk_evidence=meta.get("overall_risk_evidence", []),
        confidence=row.get("confidence") or "HIGH",
        verification_notes=meta.get("notes") or (v_notes if not meta else None),
        created_at=str(row.get("created_at")) if row.get("created_at") else None,
        values=val_outs,
        medicines=med_items,
        diagnosis_or_notes=meta.get("diagnosis_or_notes"),
        allergy_alerts=meta.get("allergy_alerts", []),
        recommended_specialty=rec_spec,
    )


class ValueConfirmItem(BaseModel):
    id: Optional[str] = None
    test_name: str
    canonical_name: Optional[str] = None
    value: Optional[float] = None
    raw_value: Optional[str] = None
    unit: Optional[str] = None
    ref_low: Optional[float] = None
    ref_high: Optional[float] = None
    is_user_edited: bool = False


class ReportConfirmRequest(BaseModel):
    values: List[ValueConfirmItem]
    patient_name_acknowledged: bool = False


class PrescriptionDetailOut(BaseModel):
    id: str
    patient_id: str
    file_path: str
    file_type: Optional[str] = None
    prescription_date: Optional[str] = None
    doctor_name: Optional[str] = None
    patient_name_found: Optional[str] = None
    patient_name_mismatch: bool = False
    mismatch_warning: Optional[str] = None
    document_type: str = "prescription"
    is_medical_document: bool = True
    quality: str = "good"
    rejection_reason: Optional[str] = None
    diagnosis_or_notes: Optional[str] = None
    medicines: List[PrescribedMedicine] = []
    general_advice_en: Optional[str] = None
    general_advice_ur: Optional[str] = None
    allergy_alerts: List[str] = []
    confidence: str = "high"
    status: str = "analyzed"
    created_at: Optional[str] = None


class PrescriptionConfirmRequest(BaseModel):
    medicines: List[PrescribedMedicine]
    diagnosis_or_notes: Optional[str] = None
    patient_name_acknowledged: bool = False
    save_to_memory: bool = True


@router.post("/upload", response_model=ReportUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_report(
    patient_id: Optional[str] = Form(None),
    file: UploadFile = File(...),
    user: AuthUser = Depends(get_current_user),
):
    """Uploads a lab report image or PDF. Patient profile is derived from authenticated user."""
    profile = await get_or_create_user_profile(user)
    target_patient_id: str = str(patient_id or profile["id"])

    report_id = str(uuid.uuid4())
    file_ext = os.path.splitext(file.filename or "")[1].lower() or ".pdf"
    storage_filename = f"{target_patient_id}/{report_id}{file_ext}"
    content = await file.read()

    # Save to local uploads folder as immediate cache
    local_path = os.path.join(UPLOAD_CACHE_DIR, f"{report_id}{file_ext}")
    with open(local_path, "wb") as f:
        f.write(content)

    supabase = get_supabase_admin()
    if supabase:
        try:
            # Upload to Supabase 'reports' private storage bucket
            supabase.storage.from_("reports").upload(
                path=storage_filename,
                file=content,
                file_options={"content-type": file.content_type or "application/octet-stream"},
            )
        except Exception:
            pass

        supabase.table("reports").insert({
            "id": report_id,
            "patient_id": target_patient_id,
            "file_path": storage_filename,
            "file_type": file.content_type,
            "status": "uploaded",
        }).execute()

    return ReportUploadResponse(
        report_id=report_id,
        patient_id=target_patient_id,
        file_path=storage_filename,
        status="uploaded",
    )


@router.post("/{report_id}/analyze", response_model=ReportDetailOut)
async def analyze_report(
    report_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """Runs the full extraction, verification, flags, and explanation pipeline."""
    profile = await get_or_create_user_profile(user)
    account_patient_id = profile["id"]
    account_patient_name = profile.get("name")
    supabase = get_supabase_admin()

    patient_gender = profile.get("gender")
    patient_age = profile.get("age")
    chronic_conditions = profile.get("chronic_conditions", [])
    active_meds = []
    file_bytes = b""
    content_type = "application/pdf"
    patient_id = account_patient_id

    if supabase:
        rep_res = supabase.table("reports").select("*").eq("id", report_id).execute()
        if not rep_res.data:
            raise HTTPException(status_code=404, detail="Report not found")
        report_row = rep_res.data[0]
        patient_id = report_row["patient_id"]
        content_type = report_row.get("file_type") or "application/pdf"

        # Download file
        try:
            file_bytes = supabase.storage.from_("reports").download(report_row["file_path"])
        except Exception:
            # Fallback to local uploads dir
            for fn in os.listdir(UPLOAD_CACHE_DIR):
                if fn.startswith(report_id):
                    with open(os.path.join(UPLOAD_CACHE_DIR, fn), "rb") as f:
                        file_bytes = f.read()
                    break

        pat_res = supabase.table("patients").select("*").eq("id", patient_id).execute()
        if pat_res.data:
            pat = pat_res.data[0]
            patient_gender = pat.get("gender") or patient_gender
            patient_age = pat.get("age") or patient_age
            chronic_conditions = pat.get("chronic_conditions", chronic_conditions)
            account_patient_name = pat.get("name") or account_patient_name

    else:
        # Dev fallback: read from local uploads cache
        for fn in os.listdir(UPLOAD_CACHE_DIR):
            if fn.startswith(report_id):
                with open(os.path.join(UPLOAD_CACHE_DIR, fn), "rb") as f:
                    file_bytes = f.read()
                break

    if not file_bytes:
        raise HTTPException(status_code=404, detail="Report file contents could not be retrieved")

    # Run AI pipeline with document classification & multi-page support
    verified_extraction, explanation, primary_specialty = await run_report_pipeline(
        file_bytes=file_bytes,
        content_type=content_type,
        patient_age=patient_age,
        patient_gender=patient_gender,
        account_name=account_patient_name,
        chronic_conditions=chronic_conditions,
        active_medications=active_meds,
    )

    # Compute overall risk level using evidence-based assessment
    overall_risk, overall_risk_evidence = compute_overall_risk(verified_extraction.values)

    report_status = "analyzed"
    if not verified_extraction.is_medical_document or verified_extraction.document_type.value in ("irrelevant", "unreadable"):
        report_status = "rejected"

    # Save to Supabase
    saved_values: List[ReportValueOut] = []
    if supabase:
        supabase.table("report_values").delete().eq("report_id", report_id).execute()
        val_rows = []
        for v in verified_extraction.values:
            val_rows.append({
                "report_id": report_id,
                "test_name": v.test_name,
                "canonical_name": v.canonical_name,
                "value": v.value,
                "unit": v.unit,
                "ref_low": v.ref_low,
                "ref_high": v.ref_high,
                "flag": v.flag,
                "specialty_hint": v.specialty_hint,
            })
        if val_rows:
            inserted = supabase.table("report_values").insert(val_rows).execute()
            saved_values = [
                ReportValueOut(
                    **r,
                    is_user_edited=False,
                    sanity_error=next((v.sanity_error for v in verified_extraction.values if v.test_name == r.get("test_name")), None),
                )
                for r in (inserted.data or [])
            ]

        questions_json = {
            "en": explanation.questions_for_doctor_en,
            "ur": explanation.questions_for_doctor_ur,
        }

        meta_payload = {
            "document_type": verified_extraction.document_type.value,
            "lab_name": verified_extraction.lab_name,
            "patient_name_found": verified_extraction.patient_name_found,
            "patient_name_mismatch": verified_extraction.patient_name_mismatch,
            "mismatch_warning": verified_extraction.mismatch_warning,
            "recommended_specialty": primary_specialty,
            "notes": verified_extraction.notes,
            "overall_risk_evidence": overall_risk_evidence,
        }

        try:
            supabase.table("reports").update({
                "status": report_status,
                "report_date": verified_extraction.report_date,
                "summary_en": explanation.summary_en,
                "summary_ur": explanation.summary_ur,
                "questions_for_doctor": questions_json,
                "overall_risk": overall_risk,
                "confidence": verified_extraction.confidence.value,
                "verification_notes": json.dumps(meta_payload),
            }).eq("id", report_id).execute()
        except Exception as e:
            logger.warning(f"Failed to update report record: {e}")

    else:
        saved_values = [
            ReportValueOut(
                report_id=report_id,
                test_name=v.test_name,
                canonical_name=v.canonical_name,
                value=v.value,
                raw_value=v.raw_value,
                unit=v.unit,
                ref_low=v.ref_low,
                ref_high=v.ref_high,
                flag=v.flag,
                specialty_hint=v.specialty_hint,
                is_user_edited=v.is_user_edited,
                sanity_error=v.sanity_error,
            )
            for v in verified_extraction.values
        ]

    return ReportDetailOut(
        id=report_id,
        patient_id=patient_id,
        file_path=f"{patient_id}/{report_id}",
        file_type=content_type,
        report_date=verified_extraction.report_date,
        patient_name_found=verified_extraction.patient_name_found,
        lab_name=verified_extraction.lab_name,
        patient_name_mismatch=verified_extraction.patient_name_mismatch,
        mismatch_warning=verified_extraction.mismatch_warning,
        document_type=verified_extraction.document_type.value,
        is_medical_document=verified_extraction.is_medical_document,
        rejection_reason=verified_extraction.rejection_reason,
        status=report_status,
        summary_en=explanation.summary_en,
        summary_ur=explanation.summary_ur,
        questions_for_doctor={
            "en": explanation.questions_for_doctor_en,
            "ur": explanation.questions_for_doctor_ur,
        },
        overall_risk=overall_risk,
        overall_risk_evidence=overall_risk_evidence,
        confidence=verified_extraction.confidence.value,
        verification_notes=verified_extraction.notes,
        values=saved_values,
        recommended_specialty=primary_specialty,
    )


@router.post("/{report_id}/confirm", response_model=ReportDetailOut)
async def confirm_report_values(
    report_id: str,
    payload: ReportConfirmRequest,
    user: AuthUser = Depends(get_current_user),
):
    """
    Human-in-the-loop review endpoint:
    Accepts user-confirmed or edited lab test values, recomputes clinical flags strictly in Python code,
    and updates the plain-language explanation accordingly.
    """
    profile = await get_or_create_user_profile(user)
    patient_id = profile["id"]
    patient_gender = profile.get("gender")
    patient_age = profile.get("age")
    chronic_conditions = profile.get("chronic_conditions", [])

    supabase = get_supabase_admin()
    report_row: Dict[str, Any] = {}
    if supabase:
        try:
            rep_res = supabase.table("reports").select("*").eq("id", report_id).eq("patient_id", patient_id).execute()
            if rep_res.data:
                report_row = rep_res.data[0]
        except Exception:
            pass

    # Convert incoming payload items to ExtractedValue instances
    extracted_items: List[ExtractedValue] = []
    for item in payload.values:
        extracted_items.append(
            ExtractedValue(
                test_name=item.test_name,
                canonical_name=item.canonical_name,
                value=item.value,
                raw_value=item.raw_value,
                unit=item.unit,
                ref_low=item.ref_low,
                ref_high=item.ref_high,
                is_user_edited=item.is_user_edited,
            )
        )

    # Pure deterministic flag computation in Python code
    flagged_values, primary_specialty = process_extracted_values(
        values=extracted_items,
        gender=patient_gender,
    )

    # Regenerate explanation grounded on confirmed values
    explanation = await generate_report_explanation(
        flagged_values=flagged_values,
        patient_age=patient_age,
        patient_gender=patient_gender,
        chronic_conditions=chronic_conditions,
        primary_specialty=primary_specialty,
    )

    # Compute overall risk level using evidence-based assessment
    overall_risk, overall_risk_evidence = compute_overall_risk(flagged_values)

    saved_values: List[ReportValueOut] = []
    if supabase and report_row:
        try:
            supabase.table("report_values").delete().eq("report_id", report_id).execute()
            val_rows = []
            for v in flagged_values:
                val_rows.append({
                    "report_id": report_id,
                    "test_name": v.test_name,
                    "canonical_name": v.canonical_name,
                    "value": v.value,
                    "unit": v.unit,
                    "ref_low": v.ref_low,
                    "ref_high": v.ref_high,
                    "flag": v.flag,
                    "specialty_hint": v.specialty_hint,
                })
            if val_rows:
                inserted = supabase.table("report_values").insert(val_rows).execute()
                saved_values = [
                    ReportValueOut(
                        **r,
                        is_user_edited=any(v.is_user_edited for v in flagged_values if v.test_name == r.get("test_name")),
                        sanity_error=next((v.sanity_error for v in flagged_values if v.test_name == r.get("test_name")), None),
                    )
                    for r in (inserted.data or [])
                ]

            questions_json = {
                "en": explanation.questions_for_doctor_en,
                "ur": explanation.questions_for_doctor_ur,
            }

            curr_meta: Dict[str, Any] = {}
            if report_row.get("verification_notes"):
                try:
                    loaded = json.loads(report_row["verification_notes"])
                    if isinstance(loaded, dict):
                        curr_meta = loaded
                    else:
                        curr_meta = {"notes": str(report_row["verification_notes"])}
                except Exception:
                    curr_meta = {"notes": str(report_row["verification_notes"])}
            curr_meta["recommended_specialty"] = primary_specialty
            curr_meta["overall_risk_evidence"] = overall_risk_evidence

            supabase.table("reports").update({
                "status": "confirmed",
                "summary_en": explanation.summary_en,
                "summary_ur": explanation.summary_ur,
                "questions_for_doctor": questions_json,
                "overall_risk": overall_risk,
                "verification_notes": json.dumps(curr_meta),
            }).eq("id", report_id).execute()
        except Exception as e:
            logger.warning(f"Failed to confirm report: {e}")
            saved_values = []

    if not saved_values:
        saved_values = [
            ReportValueOut(
                report_id=report_id,
                test_name=v.test_name,
                canonical_name=v.canonical_name,
                value=v.value,
                raw_value=v.raw_value,
                unit=v.unit,
                ref_low=v.ref_low,
                ref_high=v.ref_high,
                flag=v.flag,
                specialty_hint=v.specialty_hint,
                is_user_edited=v.is_user_edited,
                sanity_error=v.sanity_error,
            )
            for v in flagged_values
        ]

    return ReportDetailOut(
        id=report_id,
        patient_id=patient_id,
        file_path=report_row.get("file_path", f"{patient_id}/{report_id}"),
        file_type=report_row.get("file_type", "application/pdf"),
        report_date=report_row.get("report_date"),
        patient_name_found=report_row.get("patient_name_found"),
        lab_name=report_row.get("lab_name"),
        patient_name_mismatch=False if payload.patient_name_acknowledged else report_row.get("patient_name_mismatch", False),
        status="analyzed",
        summary_en=explanation.summary_en,
        summary_ur=explanation.summary_ur,
        questions_for_doctor={
            "en": explanation.questions_for_doctor_en,
            "ur": explanation.questions_for_doctor_ur,
        },
        overall_risk=overall_risk,
        overall_risk_evidence=overall_risk_evidence,
        values=saved_values,
        recommended_specialty=primary_specialty,
    )


@router.post("/{report_id}/analyze-prescription", response_model=PrescriptionDetailOut)
async def analyze_prescription(
    report_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """
    Extracts medicines, dosages, instructions, diagnosis from a prescription document,
    and cross-checks against patient allergy history.
    """
    profile = await get_or_create_user_profile(user)
    patient_id = profile["id"]
    account_name = profile.get("name")
    known_allergies = list(profile.get("allergies") or [])
    chronic_conditions = list(profile.get("chronic_conditions") or [])

    # Also pull any active allergies from memory_facts if not in profile yet
    supabase = get_supabase_admin()
    if supabase:
        try:
            mf_res = (
                supabase.table("memory_facts")
                .select("key, value")
                .eq("patient_id", patient_id)
                .eq("fact_type", "allergy")
                .eq("status", "active")
                .execute()
            )
            for r in (mf_res.data or []):
                val = r.get("value") or r.get("key")
                if val and val not in known_allergies:
                    known_allergies.append(val)
        except Exception:
            pass

    # Find the file in local cache or Supabase storage
    local_files = [f for f in os.listdir(UPLOAD_CACHE_DIR) if f.startswith(f"{report_id}.")]
    file_bytes: Optional[bytes] = None
    content_type = "image/jpeg"

    if local_files:
        cached_path = os.path.join(UPLOAD_CACHE_DIR, local_files[0])
        with open(cached_path, "rb") as f:
            file_bytes = f.read()
        file_ext = os.path.splitext(local_files[0])[1].lower()
        content_type = "application/pdf" if file_ext == ".pdf" else "image/jpeg"
    elif supabase:
        storage_res = (
            supabase.table("reports")
            .select("file_path, file_type")
            .eq("id", report_id)
            .eq("patient_id", patient_id)
            .execute()
        )
        if storage_res.data:
            storage_path = storage_res.data[0]["file_path"]
            content_type = storage_res.data[0].get("file_type") or "image/jpeg"
            file_bytes = supabase.storage.from_("reports").download(storage_path)

    if not file_bytes:
        raise HTTPException(
            status_code=404,
            detail=f"Report file {report_id} not found in local cache or storage.",
        )

    # Run Prescription extraction pipeline
    extraction = await run_prescription_pipeline(
        file_bytes=file_bytes,
        content_type=content_type,
        known_allergies=known_allergies,
        chronic_conditions=chronic_conditions,
        account_name=account_name,
    )

    doc_type_val = extraction.document_type.value if hasattr(extraction.document_type, "value") else str(extraction.document_type)
    quality_val = extraction.quality.value if hasattr(extraction.quality, "value") else str(extraction.quality)
    confidence_val = extraction.confidence.value if hasattr(extraction.confidence, "value") else str(extraction.confidence)

    report_status = "analyzed"
    if not extraction.is_medical_document or doc_type_val in ("irrelevant", "unreadable"):
        report_status = "rejected"

    # Save to Supabase reports table
    if supabase:
        try:
            prescription_meta = {
                "document_type": doc_type_val,
                "doctor_name": extraction.doctor_name,
                "patient_name_found": extraction.patient_name_found,
                "patient_name_mismatch": extraction.patient_name_mismatch,
                "mismatch_warning": extraction.mismatch_warning,
                "diagnosis_or_notes": extraction.diagnosis_or_notes,
                "medicines": [m.model_dump() for m in extraction.medicines],
                "allergy_alerts": extraction.allergy_alerts,
                "prescription_date": extraction.prescription_date,
                "is_medical_document": extraction.is_medical_document,
                "rejection_reason": extraction.rejection_reason,
            }
            supabase.table("reports").update({
                "status": report_status,
                "summary_en": extraction.general_advice_en,
                "summary_ur": extraction.general_advice_ur,
                "confidence": confidence_val,
                "report_date": extraction.prescription_date,
                "verification_notes": json.dumps(prescription_meta),
            }).eq("id", report_id).execute()
        except Exception as e:
            logger.warning(f"Failed to save prescription report: {e}")

    return PrescriptionDetailOut(
        id=report_id,
        patient_id=patient_id,
        file_path=f"{patient_id}/{report_id}",
        file_type=content_type,
        prescription_date=extraction.prescription_date,
        doctor_name=extraction.doctor_name,
        patient_name_found=extraction.patient_name_found,
        patient_name_mismatch=extraction.patient_name_mismatch,
        mismatch_warning=extraction.mismatch_warning,
        document_type=doc_type_val,
        is_medical_document=extraction.is_medical_document,
        quality=quality_val,
        rejection_reason=extraction.rejection_reason,
        diagnosis_or_notes=extraction.diagnosis_or_notes,
        medicines=extraction.medicines,
        general_advice_en=extraction.general_advice_en,
        general_advice_ur=extraction.general_advice_ur,
        allergy_alerts=extraction.allergy_alerts,
        confidence=confidence_val,
        status=report_status,
    )


@router.post("/{report_id}/confirm-prescription", response_model=PrescriptionDetailOut)
async def confirm_prescription(
    report_id: str,
    payload: PrescriptionConfirmRequest,
    user: AuthUser = Depends(get_current_user),
):
    """
    Saves confirmed medicines to patient profile and to persistent memory_facts so AI Doctor remembers them.
    """
    profile = await get_or_create_user_profile(user)
    patient_id = profile["id"]
    supabase = get_supabase_admin()

    # 1. Update report status and confirmed medicines
    if supabase:
        try:
            rep_res = supabase.table("reports").select("verification_notes").eq("id", report_id).execute()
            meta: Dict[str, Any] = {}
            if rep_res.data and rep_res.data[0].get("verification_notes"):
                try:
                    meta = json.loads(rep_res.data[0]["verification_notes"])
                    if not isinstance(meta, dict):
                        meta = {}
                except Exception:
                    meta = {}
            meta["medicines"] = [m.model_dump() for m in payload.medicines]
            if payload.diagnosis_or_notes:
                meta["diagnosis_or_notes"] = payload.diagnosis_or_notes
            if payload.patient_name_acknowledged:
                meta["patient_name_mismatch"] = False

            supabase.table("reports").update({
                "status": "confirmed",
                "verification_notes": json.dumps(meta),
            }).eq("id", report_id).execute()
        except Exception as e:
            logger.warning(f"Failed to confirm prescription: {e}")

    # 2. Persist to memory_facts & update profile active medications
    if payload.save_to_memory and payload.medicines:
        facts_to_save: List[MemoryFact] = []
        new_med_names: List[str] = []

        for med in payload.medicines:
            med_name = med.name.strip()
            if not med_name:
                continue
            new_med_names.append(med_name)
            desc_parts = []
            if med.dosage:
                desc_parts.append(med.dosage)
            if med.frequency:
                desc_parts.append(med.frequency)
            if med.instructions:
                desc_parts.append(f"({med.instructions})")
            val_str = " ".join(desc_parts).strip() or "prescribed"

            facts_to_save.append(
                MemoryFact(
                    fact_type=FactType.MEDICATION,
                    key=med_name.lower(),
                    value=val_str,
                    confidence=1.0,
                    status="active",
                )
            )

        if facts_to_save:
            await save_memory_facts(
                patient_id=patient_id,
                facts=facts_to_save,
                source_type="prescription",
                source_id=report_id,
            )

        # Merge with existing profile medications
        if supabase:
            try:
                curr_meds = profile.get("medications") or []
                if isinstance(curr_meds, list):
                    updated_meds = list(dict.fromkeys(curr_meds + new_med_names))
                    supabase.table("patients").update({"medications": updated_meds}).eq("id", patient_id).execute()
            except Exception:
                pass

    return PrescriptionDetailOut(
        id=report_id,
        patient_id=patient_id,
        file_path=f"{patient_id}/{report_id}",
        diagnosis_or_notes=payload.diagnosis_or_notes,
        medicines=payload.medicines,
        status="confirmed",
    )


@router.get("", response_model=List[ReportDetailOut])
async def list_reports(
    patient_id: Optional[str] = None,
    user: AuthUser = Depends(get_current_user),
):
    profile = await get_or_create_user_profile(user)
    target_patient_id = profile["id"]
    supabase = get_supabase_admin()
    if not supabase:
        return []

    res = (
        supabase.table("reports")
        .select("*, report_values(*)")
        .eq("patient_id", target_patient_id)
        .neq("status", "uploaded")
        .order("created_at", desc=True)
        .execute()
    )
    return [build_report_detail(r) for r in (res.data or [])]


@router.get("/{report_id}", response_model=ReportDetailOut)
async def get_report(
    report_id: str,
    user: AuthUser = Depends(get_current_user),
):
    profile = await get_or_create_user_profile(user)
    supabase = get_supabase_admin()
    if not supabase:
        raise HTTPException(status_code=404, detail="Report not found")

    rep_res = (
        supabase.table("reports")
        .select("*, report_values(*)")
        .eq("id", report_id)
        .eq("patient_id", profile["id"])
        .execute()
    )
    if not rep_res.data:
        raise HTTPException(status_code=404, detail="Report not found or access denied")

    report_row = rep_res.data[0]
    return build_report_detail(report_row)


@router.delete("/{report_id}", status_code=status.HTTP_200_OK)
async def delete_report(
    report_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """Deletes a report and its values for the authenticated patient."""
    profile = await get_or_create_user_profile(user)
    supabase = get_supabase_admin()
    if not supabase:
        return {"status": "deleted", "id": report_id}

    rep_res = (
        supabase.table("reports")
        .select("id, file_path")
        .eq("id", report_id)
        .eq("patient_id", profile["id"])
        .execute()
    )
    if not rep_res.data:
        raise HTTPException(status_code=404, detail="Report not found or access denied")

    report_row = rep_res.data[0]
    file_path = report_row.get("file_path")

    try:
        supabase.table("report_values").delete().eq("report_id", report_id).execute()
    except Exception:
        pass

    supabase.table("reports").delete().eq("id", report_id).eq("patient_id", profile["id"]).execute()

    if file_path:
        try:
            supabase.storage.from_("reports").remove([file_path])
        except Exception:
            pass

    return {"status": "deleted", "id": report_id}
