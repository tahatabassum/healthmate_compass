"""
Report Extraction & Explanation Pipeline for HealthMate Compass.
Follows the dual-pass verification architecture:
Pass 1: Vision / Text extraction & document classification (Gemma 4).
Pass 2: Verification pass cross-checking raw text / numbers.
Pass 3: Deterministic clinical flag computation in code (flags.py) with sanity limits.
Pass 4: Multilingual plain-language explanation (EN + Urdu) grounded only on flagged values.
"""
import base64
import io
import logging
from typing import Optional, Tuple, List
import fitz  # PyMuPDF
from PIL import Image, ImageOps
from app.llm.client import call_llm
from app.llm.schemas import (
    ReportExtraction,
    ReportExplanation,
    PrescriptionExtraction,
    PrescribedMedicine,
    ExtractedValue,
    DocumentType,
    DocumentQuality,
    Confidence,
)
from app.llm.prompts import (
    REPORT_EXTRACTION_SYSTEM_PROMPT,
    REPORT_VERIFICATION_PROMPT,
    REPORT_EXPLANATION_PROMPT,
    PRESCRIPTION_EXTRACTION_SYSTEM_PROMPT,
)
from app.services.flags import process_extracted_values, check_patient_name_mismatch

logger = logging.getLogger(__name__)


def preprocess_image(file_bytes: bytes, max_dim: int = 1024) -> Tuple[bytes, str]:
    """
    Preprocesses an image:
    1. EXIF auto-rotation (fixes camera orientation from phone uploads).
    2. Resizes maintaining aspect ratio (1024px is fast and accurate for OCR).
    3. Converts to RGB and optimizes JPEG compression.
    """
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img = ImageOps.exif_transpose(img)

        width, height = img.size
        if width > max_dim or height > max_dim:
            if width >= height:
                new_width = max_dim
                new_height = int(height * (max_dim / width))
            else:
                new_height = max_dim
                new_width = int(width * (max_dim / height))
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        if img.mode != "RGB":
            img = img.convert("RGB")

        out_buf = io.BytesIO()
        img.save(out_buf, format="JPEG", quality=80, optimize=True)
        return out_buf.getvalue(), "image/jpeg"
    except Exception as e:
        logger.warning(f"Image preprocessing fallback to raw bytes: {e}")
        return file_bytes, "image/jpeg"


def extract_text_or_images_from_file(
    file_bytes: bytes,
    content_type: str,
    max_pages: int = 5,
) -> Tuple[str, List[str]]:
    """
    Extracts text from PDF or returns base64 image data URIs.
    Supports multi-page PDFs up to `max_pages`.
    Returns (raw_text, list_of_base64_data_uris).
    """
    raw_text = ""
    b64_images: List[str] = []

    if "pdf" in (content_type or "").lower():
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            for page in doc:
                raw_text += page.get_text() + "\n"

            page_count = min(len(doc), max_pages)
            render_all = len(raw_text.strip()) < 100
            pages_to_render = page_count if render_all else min(page_count, 2)

            for page_idx in range(pages_to_render):
                page = doc[page_idx]
                pix = page.get_pixmap(dpi=150)
                page_img_bytes = pix.tobytes("png")
                processed_bytes, mime = preprocess_image(page_img_bytes)
                b64 = base64.b64encode(processed_bytes).decode("utf-8")
                b64_images.append(f"data:{mime};base64,{b64}")
        except Exception as e:
            logger.warning(f"Error parsing PDF with PyMuPDF: {e}")
    else:
        # Standard image (JPEG, PNG, WEBP)
        processed_bytes, mime = preprocess_image(file_bytes)
        b64 = base64.b64encode(processed_bytes).decode("utf-8")
        b64_images.append(f"data:{mime};base64,{b64}")

    return raw_text.strip(), b64_images


async def generate_report_explanation(
    flagged_values: List[ExtractedValue],
    patient_age: Optional[int] = None,
    patient_gender: Optional[str] = None,
    chronic_conditions: Optional[List[str]] = None,
    active_medications: Optional[List[str]] = None,
    primary_specialty: Optional[str] = None,
) -> ReportExplanation:
    """Generates plain language summary in English and Urdu from code-flagged values."""
    flagged_summary_lines = []
    for v in flagged_values:
        status_tag = f"[{v.flag.upper()}]" if v.flag != "normal" else "[NORMAL]"
        ref_str = f"(Ref: {v.ref_low} - {v.ref_high})" if v.ref_low or v.ref_high else ""
        flagged_summary_lines.append(
            f"- {v.test_name}: {v.value} {v.unit or ''} {status_tag} {ref_str}"
        )
    flagged_summary = "\n".join(flagged_summary_lines) or "No individual lab values identified."

    explanation_prompt = REPORT_EXPLANATION_PROMPT.format(
        age=patient_age or "Not specified",
        gender=patient_gender or "Not specified",
        chronic_conditions=", ".join(chronic_conditions) if chronic_conditions else "None reported",
        active_medications=", ".join(active_medications) if active_medications else "None reported",
        flagged_values_summary=flagged_summary,
    )

    explanation: ReportExplanation = await call_llm(
        messages=[
            {"role": "system", "content": "You explain medical lab reports in simple English and Urdu. You do not diagnose."},
            {"role": "user", "content": explanation_prompt},
        ],
        response_model=ReportExplanation,
        temperature=0.2,
    )

    if not explanation.specialist_recommendation and primary_specialty:
        explanation.specialist_recommendation = primary_specialty

    return explanation


async def run_report_pipeline(
    file_bytes: bytes,
    content_type: str,
    patient_age: Optional[int] = None,
    patient_gender: Optional[str] = None,
    account_name: Optional[str] = None,
    chronic_conditions: Optional[List[str]] = None,
    active_medications: Optional[List[str]] = None,
) -> Tuple[ReportExtraction, ReportExplanation, str]:
    """
    Executes the 4-stage report processing pipeline.
    Returns (verified_extraction, explanation, recommended_specialty).
    """
    raw_text, b64_images = extract_text_or_images_from_file(file_bytes, content_type)

    # ── Stage 1: Extraction & Classification ─────────────────────────────────
    user_content: List[dict] = []
    prompt_text = "Please classify this document and extract all clinical laboratory test values."
    if raw_text:
        prompt_text += f"\n\nREPORT TEXT:\n{raw_text[:6000]}"

    user_content.append({"type": "text", "text": prompt_text})
    for img_uri in b64_images:
        user_content.append({"type": "image_url", "image_url": {"url": img_uri}})

    extraction_messages = [
        {"role": "system", "content": REPORT_EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    first_pass: ReportExtraction = await call_llm(
        messages=extraction_messages,
        response_model=ReportExtraction,
        temperature=0.1,
    )

    # ── Guardrail: Document Classification Check ─────────────────────────────
    if (
        first_pass.document_type in (DocumentType.IRRELEVANT, DocumentType.UNREADABLE)
        or not first_pass.is_medical_document
    ):
        reason_en = (
            first_pass.rejection_reason
            or "The uploaded document does not appear to be a medical lab test report. Please upload a clear photo or PDF of a diagnostic test report."
        )
        reason_ur = "یہ تصویر کسی میڈیکل لیبارٹری ٹیسٹ رپورٹ کی معلوم نہیں ہوتی۔ براہ کرم اپنے میڈیکل ٹیسٹ کی واضح تصویر یا پی ڈی ایف اپلوڈ کریں۔"
        explanation = ReportExplanation(
            summary_en=reason_en,
            summary_ur=reason_ur,
            questions_for_doctor_en=["Please consult a healthcare professional with a valid diagnostic report."],
            questions_for_doctor_ur=["براہ کرم معائنے کے لیے اصل لیبارٹری رپورٹ ڈاکٹر کو دکھائیں۔"],
            lifestyle_notes=[],
            specialist_recommendation="General Physician",
        )
        return first_pass, explanation, "General Physician"

    # ── Stage 2: Patient Identity Verification ───────────────────────────────
    verified_extraction = first_pass
    if account_name:
        is_mismatch, warning = check_patient_name_mismatch(
            verified_extraction.patient_name_found, account_name
        )
        verified_extraction.patient_name_mismatch = is_mismatch
        verified_extraction.mismatch_warning = warning

    # ── Stage 3: Flags Computation (Code Only) ───────────────────────────────
    flagged_values, primary_specialty = process_extracted_values(
        values=verified_extraction.values,
        gender=patient_gender,
    )
    verified_extraction.values = flagged_values

    # ── Stage 4: Plain-Language Explanation (EN + Urdu) ───────────────────────
    explanation = await generate_report_explanation(
        flagged_values=flagged_values,
        patient_age=patient_age,
        patient_gender=patient_gender,
        chronic_conditions=chronic_conditions,
        active_medications=active_medications,
        primary_specialty=primary_specialty,
    )

    return verified_extraction, explanation, primary_specialty


def check_medicine_allergy_conflicts(medicine_name: str, known_allergies: List[str]) -> Optional[str]:
    """
    Checks if a prescribed medicine conflicts with patient's known allergies.
    Supports penicillin/amoxicillin/ampicillin/augmentin, sulfa, aspirin/nsaids, etc.
    """
    if not medicine_name or not known_allergies:
        return None
    med_lower = medicine_name.lower()
    for allergy in known_allergies:
        a_lower = allergy.lower().strip()
        if not a_lower:
            continue
        # Penicillin group
        if "penicillin" in a_lower or "amoxicillin" in a_lower or "ampicillin" in a_lower:
            if any(p in med_lower for p in ["penicillin", "amoxicillin", "ampicillin", "augmentin", "amoxil", "clavulanate"]):
                return f"⚠️ Allergy Alert: '{medicine_name}' belongs to the penicillin class, which conflicts with your recorded {allergy} allergy!"
        # Sulfa group
        if "sulfa" in a_lower or "sulfonamide" in a_lower:
            if any(s in med_lower for s in ["sulfa", "septra", "bactrim", "cotrimoxazole"]):
                return f"⚠️ Allergy Alert: '{medicine_name}' contains sulfonamide, which conflicts with your recorded {allergy} allergy!"
        # NSAID / Aspirin group
        if "aspirin" in a_lower or "nsaid" in a_lower:
            if any(n in med_lower for n in ["aspirin", "ibuprofen", "brufen", "diclofenac", "naproxen", "ponstan"]):
                return f"⚠️ Allergy Alert: '{medicine_name}' is an NSAID, which conflicts with your recorded {allergy} allergy!"
        # Direct word match
        if a_lower in med_lower or med_lower in a_lower:
            return f"⚠️ Allergy Alert: '{medicine_name}' conflicts with your recorded allergy: {allergy}!"
    return None


async def run_prescription_pipeline(
    file_bytes: bytes,
    content_type: str,
    known_allergies: Optional[List[str]] = None,
    chronic_conditions: Optional[List[str]] = None,
    account_name: Optional[str] = None,
) -> PrescriptionExtraction:
    """
    Processes a doctor prescription image/PDF:
    1. Preprocesses image or multi-page PDF.
    2. Runs Gemma 4 with PRESCRIPTION_EXTRACTION_SYSTEM_PROMPT.
    3. Cross-checks patient identity and mismatch warning.
    4. Deterministically cross-checks extracted medicines against patient's known allergies.
    5. Returns PrescriptionExtraction.
    """
    raw_text, b64_images = extract_text_or_images_from_file(file_bytes, content_type)

    user_content: List[dict] = []
    prompt_text = "Please transcribe and verify this doctor's medical prescription."
    if raw_text:
        prompt_text += f"\n\nPRESCRIPTION TEXT:\n{raw_text[:6000]}"

    user_content.append({"type": "text", "text": prompt_text})
    for img_uri in b64_images:
        user_content.append({"type": "image_url", "image_url": {"url": img_uri}})

    extraction_messages = [
        {"role": "system", "content": PRESCRIPTION_EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    extraction: PrescriptionExtraction = await call_llm(
        messages=extraction_messages,
        response_model=PrescriptionExtraction,
        temperature=0.1,
    )

    # Patient Name Mismatch Check
    if account_name:
        is_mismatch, warning = check_patient_name_mismatch(
            extraction.patient_name_found, account_name
        )
        extraction.patient_name_mismatch = is_mismatch
        extraction.mismatch_warning = warning

    # Deterministic Allergy Cross-Verification (Code Safety)
    allergies = known_allergies or []
    for med in extraction.medicines:
        conflict = check_medicine_allergy_conflicts(med.name, allergies)
        if conflict:
            med.allergy_warning = conflict
            if conflict not in extraction.allergy_alerts:
                extraction.allergy_alerts.append(conflict)

    return extraction
