"""
Pydantic schemas for LLM inputs and structured outputs in HealthMate Compass.
Follows PRD section 17 strictly.
"""
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class Specialty(str, Enum):
    GENERAL_PHYSICIAN = "General Physician"
    CARDIOLOGIST = "Cardiologist"
    ENDOCRINOLOGIST = "Endocrinologist"
    NEPHROLOGIST = "Nephrologist"
    GASTROENTEROLOGIST = "Gastroenterologist"
    HEMATOLOGIST = "Hematologist"
    DERMATOLOGIST = "Dermatologist"
    NEUROLOGIST = "Neurologist"
    PULMONOLOGIST = "Pulmonologist"
    ORTHOPEDIC = "Orthopedic"
    ENT = "ENT"
    OPHTHALMOLOGIST = "Ophthalmologist"
    GYNECOLOGIST = "Gynecologist"
    PEDIATRICIAN = "Pediatrician"
    PSYCHIATRIST = "Psychiatrist"
    UROLOGIST = "Urologist"
    RHEUMATOLOGIST = "Rheumatologist"
    DENTIST = "Dentist"


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FactType(str, Enum):
    CONDITION = "condition"
    ALLERGY = "allergy"
    MEDICATION = "medication"
    EVENT = "event"
    LIFESTYLE = "lifestyle"
    PREFERENCE = "preference"
    GENERAL = "general"
    CHAT_SUMMARY = "chat_summary"


class DocumentType(str, Enum):
    LAB_REPORT = "lab_report"
    PRESCRIPTION = "prescription"
    OTHER_MEDICAL = "other_medical_document"
    IRRELEVANT = "irrelevant"
    UNREADABLE = "unreadable"


class DocumentQuality(str, Enum):
    GOOD = "good"
    BLURRY = "blurry"
    CROPPED = "cropped"
    TOO_DARK = "too_dark"


class ExtractedValue(BaseModel):
    """A single lab test observation extracted from a report image/PDF."""
    test_name: str = Field(description="Exact or standard test name as printed on the report")
    canonical_name: Optional[str] = Field(default=None, description="Standardized canonical key matching reference_ranges if recognized")
    value: Optional[float] = Field(default=None, description="Numeric lab test result")
    raw_value: Optional[str] = Field(default=None, description="Original string if non-numeric or unparsed")
    unit: Optional[str] = Field(default=None, description="Measurement unit (e.g. g/dL, mg/dL, /uL)")
    ref_low: Optional[float] = Field(default=None, description="Report-specified lower reference range if present")
    ref_high: Optional[float] = Field(default=None, description="Report-specified upper reference range if present")
    ref_range_text: Optional[str] = Field(default=None, description="Original reference range text as printed on report (e.g. 32-72, <200, <40)")
    lab_flag: Optional[str] = Field(default=None, description="Laboratory-reported flag if present on report (e.g. L, H, High, Low)")
    flag: Optional[str] = Field(default=None, description="Computed in code: low | normal | high | critical | unverified")
    specialty_hint: Optional[str] = Field(default=None, description="Computed in code: suggested specialty")
    is_user_edited: bool = Field(default=False, description="True if value was manually modified or verified by patient")
    sanity_error: Optional[str] = Field(default=None, description="Note if code sanity check adjusted or flagged this value")
    verification_status: str = Field(default="unverified", description="unverified | source_checked | verified | review_required")


class ReportExtraction(BaseModel):
    """Output schema for Pass 1: Vision-based medical report value extraction and classification."""
    document_type: DocumentType = Field(default=DocumentType.LAB_REPORT, description="Classification of the document")
    is_medical_document: bool = Field(default=True, description="False if image is a selfie, meme, landscape, or non-medical")
    quality: DocumentQuality = Field(default=DocumentQuality.GOOD, description="Document image quality")
    rejection_reason: Optional[str] = Field(default=None, description="Friendly explanation if document is irrelevant or unreadable")
    report_date: Optional[str] = Field(default=None, description="Date of the lab test if present (YYYY-MM-DD)")
    patient_name_found: Optional[str] = Field(default=None, description="Name of the patient printed on report if any")
    lab_name: Optional[str] = Field(default=None, description="Laboratory or hospital name")
    patient_name_mismatch: bool = Field(default=False, description="True if report patient name does not match user account profile")
    mismatch_warning: Optional[str] = Field(default=None, description="Warning message shown when name mismatch is detected")
    values: List[ExtractedValue] = Field(default_factory=list, description="All parsed test values")
    confidence: Confidence = Field(default=Confidence.HIGH, description="Extraction confidence")
    notes: Optional[str] = Field(default=None, description="Any readability, quality or anomaly notes")


class ReportExplanation(BaseModel):
    """Output schema for Pass 3: Plain-language explanation for the patient."""
    summary_en: str = Field(description="Clear explanation in plain English (~Grade 8 reading level)")
    summary_ur: str = Field(description="Clear explanation in natural Urdu script (اردو رسم الخط)")
    questions_for_doctor_en: List[str] = Field(
        default_factory=list,
        description="Thoughtful questions for the patient to ask their doctor in English"
    )
    questions_for_doctor_ur: List[str] = Field(
        default_factory=list,
        description="Questions for the doctor in natural Urdu"
    )
    lifestyle_notes: List[str] = Field(
        default_factory=list,
        description="General lifestyle or hydration pointers (non-prescriptive, no drug dosing)"
    )
    specialist_recommendation: Optional[str] = Field(
        default=None,
        description="Recommended doctor specialty based on abnormal flags"
    )


class PrescribedMedicine(BaseModel):
    """A single prescribed medication extracted from a doctor's prescription."""
    name: str = Field(description="Name of the medicine or drug (brand or generic salt)")
    dosage: Optional[str] = Field(default=None, description="Dosage (e.g. 500mg, 10mg, 1 puff, 5ml)")
    frequency: Optional[str] = Field(default=None, description="Frequency (e.g. Once daily, Twice daily, 1+0+1, As needed / SOS)")
    duration: Optional[str] = Field(default=None, description="Duration (e.g. 5 days, 1 month, ongoing)")
    instructions: Optional[str] = Field(default=None, description="Timing or dietary instructions (e.g. After meals, before bed)")
    purpose_en: Optional[str] = Field(default=None, description="Simple explanation of what this medicine is used for in plain English")
    purpose_ur: Optional[str] = Field(default=None, description="Simple explanation of what this medicine is used for in plain Urdu script")
    allergy_warning: Optional[str] = Field(default=None, description="Safety alert if this medicine conflicts with known patient allergies")


class PrescriptionExtraction(BaseModel):
    """Output schema for Doctor's Prescription Extraction & Safety Cross-Verification."""
    document_type: DocumentType = Field(default=DocumentType.PRESCRIPTION, description="Document classification")
    is_medical_document: bool = Field(default=True, description="True if valid prescription or clinical slip")
    quality: DocumentQuality = Field(default=DocumentQuality.GOOD, description="Document image clarity")
    rejection_reason: Optional[str] = Field(default=None, description="Reason if document is irrelevant, unreadable, or a lab report")
    doctor_name: Optional[str] = Field(default=None, description="Doctor or clinic name on the prescription header")
    patient_name_found: Optional[str] = Field(default=None, description="Patient name printed or written on prescription")
    patient_name_mismatch: bool = Field(default=False, description="True if patient name differs from user profile")
    mismatch_warning: Optional[str] = Field(default=None, description="Warning if name differs from active account")
    prescription_date: Optional[str] = Field(default=None, description="Date of prescription (YYYY-MM-DD)")
    diagnosis_or_notes: Optional[str] = Field(default=None, description="Diagnosed condition or clinical remarks written by physician")
    medicines: List[PrescribedMedicine] = Field(default_factory=list, description="List of prescribed medications")
    general_advice_en: Optional[str] = Field(default=None, description="General lifestyle or doctor advice translated to plain English")
    general_advice_ur: Optional[str] = Field(default=None, description="General doctor advice in natural Urdu script")
    allergy_alerts: List[str] = Field(default_factory=list, description="Cross-checked alerts against patient's known allergy history")
    confidence: Confidence = Field(default=Confidence.HIGH, description="Overall extraction confidence")


class MemoryFact(BaseModel):
    """A single persistent medical fact remembered for a patient."""
    fact_type: FactType = Field(description="Category of fact")
    key: str = Field(description="Normalized key e.g. diabetes_type2, penicillin_allergy")
    value: str = Field(description="Fact value or status e.g. diagnosed, severe, stopped")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence score")
    status: str = Field(default="active", description="active | superseded | resolved")


class TriageResult(BaseModel):
    """Output schema for AI doctor symptom chat and triage."""
    risk: RiskLevel = Field(description="Assessment risk level")
    urgency: str = Field(default="ROUTINE", description="IMMEDIATE | NEXT_DAY | ROUTINE | SELF_CARE")
    answer_en: str = Field(description="Sympathetic, medically grounded explanation in plain English")
    answer_ur: str = Field(description="Sympathetic explanation in natural Urdu script (اردو)")
    possible_causes: List[str] = Field(
        default_factory=list,
        description="Potential general causes prefixed with 'May relate to...'"
    )
    self_care: List[str] = Field(
        default_factory=list,
        description="Safe home comfort measures (hydration, rest; no drug dosages)"
    )
    specialty: Specialty = Field(
        default=Specialty.GENERAL_PHYSICIAN,
        description="Recommended medical specialty strictly from Specialty enum"
    )
    questions_for_doctor: List[str] = Field(
        default_factory=list,
        description="Actionable questions the patient can ask their physician"
    )
    new_facts: List[MemoryFact] = Field(
        default_factory=list,
        description="Any new chronic conditions, allergies, or lifestyle facts learned from this interaction"
    )
    profile_updates: List["ProfileUpdateItem"] = Field(
        default_factory=list,
        description="Explicit first-person profile changes (add, update, resolve, remove) stated directly by the user about themselves"
    )


class ProfileOperation(str, Enum):
    ADD = "add"
    UPDATE = "update"
    RESOLVE = "resolve"
    REMOVE = "remove"


class ProfileTargetType(str, Enum):
    CONDITION = "condition"
    MEDICATION = "medication"
    ALLERGY = "allergy"
    GENERAL = "general"


class ProfileUpdateItem(BaseModel):
    """An explicit first-person update to the patient's personal medical profile."""
    operation: ProfileOperation = Field(description="Action to take: add, update, resolve, or remove")
    target_type: ProfileTargetType = Field(description="Target category: condition, medication, allergy, or general")
    name: str = Field(description="Name of condition, medicine, or allergen, e.g. 'Flu', 'Asthma', 'Penicillin'")
    value: Optional[str] = Field(default=None, description="Status or detail, e.g. 'resolved', 'active', '500mg daily'")
    evidence_quote: str = Field(description="Exact or near-exact first-person quote from user text, e.g. 'I recovered from the flu'")


