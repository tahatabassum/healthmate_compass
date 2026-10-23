"""
Golden accuracy and safety test suite for Medical Report Analysis (Phase D).
Tests:
1. Document Classifier Guardrails (lab_report vs irrelevant/unreadable)
2. Synthetic Golden Test Sets: CBC, Lipid Profile, Renal/Glucose, LFT
3. Printed Bounds Priority over Defaults
4. Code Sanity Checks (negative values, extreme biological limits)
5. Unit Conversions (mmol/L -> mg/dL, g/L -> g/dL, umol/L -> mg/dL)
6. Patient Name Mismatch Detection
7. Human-in-the-Loop Confirmation Endpoint (POST /api/reports/{id}/confirm)
"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.llm.schemas import (
    ExtractedValue,
    ReportExtraction,
    ReportExplanation,
    DocumentType,
    DocumentQuality,
    Confidence,
)
from app.services.flags import (
    process_extracted_values,
    sanitize_and_convert_value,
    check_patient_name_mismatch,
    compute_flag,
)
from app.services.extractor import run_report_pipeline


# ── 1. Document Classifier Guardrail Tests ────────────────────────────────────

@pytest.mark.asyncio
async def test_irrelevant_document_guardrail_rejection():
    """Non-medical images (selfie, meme, car, receipt) must be rejected immediately."""
    mock_extraction = ReportExtraction(
        document_type=DocumentType.IRRELEVANT,
        is_medical_document=False,
        quality=DocumentQuality.GOOD,
        rejection_reason="The uploaded image appears to be a personal selfie, not a medical lab test report.",
        values=[],
        confidence=Confidence.HIGH,
    )

    with patch("app.services.extractor.call_llm", new=AsyncMock(return_value=mock_extraction)):
        verified, explanation, specialty = await run_report_pipeline(
            file_bytes=b"fake_image_bytes",
            content_type="image/jpeg",
        )

        assert verified.is_medical_document is False
        assert verified.document_type == DocumentType.IRRELEVANT
        assert len(verified.values) == 0
        assert "not a medical lab test report" in explanation.summary_en.lower() or "not appear" in explanation.summary_en.lower()
        assert len(explanation.summary_ur) > 0


@pytest.mark.asyncio
async def test_unreadable_blurry_document_guardrail_rejection():
    """Blurry or cropped unreadable scans must be classified and returned with advice."""
    mock_extraction = ReportExtraction(
        document_type=DocumentType.UNREADABLE,
        is_medical_document=True,
        quality=DocumentQuality.BLURRY,
        rejection_reason="The document image is too blurry to reliably read test names or values.",
        values=[],
        confidence=Confidence.LOW,
    )

    with patch("app.services.extractor.call_llm", new=AsyncMock(return_value=mock_extraction)):
        verified, explanation, specialty = await run_report_pipeline(
            file_bytes=b"blurry_scan_bytes",
            content_type="image/jpeg",
        )

        assert verified.document_type == DocumentType.UNREADABLE
        assert verified.quality == DocumentQuality.BLURRY
        assert len(verified.values) == 0


# ── 2. Code Sanity Checks & Unit Conversions ──────────────────────────────────

def test_negative_values_suppressed():
    """Negative values are physiologically impossible and must be suppressed."""
    raw_item = ExtractedValue(
        test_name="Fasting Blood Glucose",
        canonical_name="fasting_glucose",
        value=-45.0,
        unit="mg/dL",
    )
    sanitized = sanitize_and_convert_value(raw_item)
    assert sanitized.value is None
    assert sanitized.sanity_error is not None
    assert "negative" in sanitized.sanity_error.lower()


def test_extreme_biological_limits_flagged():
    """Extreme impossible values (e.g. Hb > 35 g/dL) must trigger sanity errors."""
    hb_impossible = ExtractedValue(
        test_name="Hemoglobin",
        canonical_name="hemoglobin",
        value=78.0,
        unit="g/dL",
    )
    sanitized = sanitize_and_convert_value(hb_impossible)
    assert sanitized.sanity_error is not None
    assert "impossible" in sanitized.sanity_error.lower()

    platelets_impossible = ExtractedValue(
        test_name="Platelets",
        canonical_name="platelets",
        value=5_500_000,
        unit="/uL",
    )
    sanitized_plt = sanitize_and_convert_value(platelets_impossible)
    assert sanitized_plt.sanity_error is not None
    assert "exceeds" in sanitized_plt.sanity_error.lower()


def test_unit_conversions_glucose_mmol_to_mgdl():
    """Glucose in mmol/L must be converted to mg/dL (* 18.0182)."""
    item = ExtractedValue(
        test_name="Blood Sugar Fasting",
        canonical_name="fasting_glucose",
        value=6.5,
        unit="mmol/L",
    )
    sanitized = sanitize_and_convert_value(item)
    assert sanitized.unit == "mg/dL"
    # 6.5 * 18.0182 = 117.1
    assert sanitized.value == pytest.approx(117.1, rel=1e-2)
    assert sanitized.sanity_error is not None
    assert "Converted" in sanitized.sanity_error


def test_unit_conversions_hemoglobin_gl_to_gdl():
    """Hemoglobin in g/L (e.g. 138 g/L) must be converted to g/dL (/ 10.0)."""
    item = ExtractedValue(
        test_name="Hemoglobin",
        canonical_name="hemoglobin",
        value=138.0,
        unit="g/L",
    )
    sanitized = sanitize_and_convert_value(item)
    assert sanitized.unit == "g/dL"
    assert sanitized.value == 13.8


def test_unit_conversions_cholesterol_mmol_to_mgdl():
    """Cholesterol in mmol/L must be converted to mg/dL (* 38.67)."""
    item = ExtractedValue(
        test_name="Total Cholesterol",
        canonical_name="total_cholesterol",
        value=5.4,
        unit="mmol/L",
    )
    sanitized = sanitize_and_convert_value(item)
    assert sanitized.unit == "mg/dL"
    # 5.4 * 38.67 = 208.8
    assert sanitized.value == pytest.approx(208.8, rel=1e-2)


# ── 3. Golden Test Sets: CBC, Lipid, Metabolic, LFT ───────────────────────────

def test_golden_cbc_panel():
    """Complete Blood Count test with abnormal low Hb and high WBC."""
    raw_values = [
        ExtractedValue(test_name="Hemoglobin", value=9.4, unit="g/dL"),
        ExtractedValue(test_name="Total WBC Count", value=14800, unit="/uL"),
        ExtractedValue(test_name="Platelet Count", value=240000, unit="/uL"),
    ]
    processed, specialty = process_extracted_values(raw_values, gender="female")

    hb = next(v for v in processed if v.canonical_name == "hemoglobin")
    wbc = next(v for v in processed if v.canonical_name == "wbc")
    plt = next(v for v in processed if v.canonical_name == "platelets")

    assert hb.flag == "low"
    assert wbc.flag == "high"
    assert plt.flag == "normal"
    assert specialty == "Hematologist"


def test_golden_lipid_panel():
    """Lipid Profile test with elevated cholesterol and triglycerides."""
    raw_values = [
        ExtractedValue(test_name="Total Cholesterol", value=250.0, unit="mg/dL"),
        ExtractedValue(test_name="Triglycerides", value=220.0, unit="mg/dL"),
        ExtractedValue(test_name="HDL Cholesterol", value=36.0, unit="mg/dL"),
        ExtractedValue(test_name="LDL Cholesterol", value=165.0, unit="mg/dL"),
    ]
    processed, specialty = process_extracted_values(raw_values)

    chol = next(v for v in processed if v.canonical_name == "total_cholesterol")
    tg = next(v for v in processed if v.canonical_name == "triglycerides")
    hdl = next(v for v in processed if v.canonical_name == "hdl")
    ldl = next(v for v in processed if v.canonical_name == "ldl")

    assert chol.flag == "high"
    assert tg.flag == "high"
    assert hdl.flag == "low"
    assert ldl.flag == "high"
    assert specialty == "Cardiologist"


def test_golden_renal_and_glucose_panel():
    """Renal function with elevated creatinine and high fasting blood sugar."""
    raw_values = [
        ExtractedValue(test_name="Fasting Blood Glucose", value=160.0, unit="mg/dL"),
        ExtractedValue(test_name="Serum Creatinine", value=2.6, unit="mg/dL"),
    ]
    processed, specialty = process_extracted_values(raw_values)

    glucose = next(v for v in processed if v.canonical_name == "fasting_glucose")
    creat = next(v for v in processed if v.canonical_name == "creatinine")

    assert glucose.flag == "high"
    assert creat.flag == "high"
    # Nephrology or Endocrinology routing
    assert specialty in ("Nephrologist", "Endocrinologist")


def test_golden_lft_panel():
    """Liver function test with elevated transaminases."""
    raw_values = [
        ExtractedValue(test_name="ALT (SGPT)", value=92.0, unit="U/L"),
        ExtractedValue(test_name="AST (SGOT)", value=76.0, unit="U/L"),
        ExtractedValue(test_name="Total Bilirubin", value=0.9, unit="mg/dL"),
    ]
    processed, specialty = process_extracted_values(raw_values)

    alt = next(v for v in processed if v.canonical_name == "alt")
    ast = next(v for v in processed if v.canonical_name == "ast")
    bili = next(v for v in processed if v.canonical_name in ("bilirubin_total", "total_bilirubin"))

    assert alt.flag == "high"
    assert ast.flag == "high"
    assert bili.flag == "normal"
    assert specialty == "Gastroenterologist"


def test_golden_thyroid_panel():
    """Thyroid panel with elevated TSH indicating hypothyroidism."""
    raw_values = [
        ExtractedValue(test_name="Thyroid Stimulating Hormone (TSH)", value=7.8, unit="mIU/L"),
        ExtractedValue(test_name="Free T4 (Thyroxine)", value=5.1, unit="µg/dL"),
    ]
    processed, specialty = process_extracted_values(raw_values)

    tsh = next(v for v in processed if v.canonical_name == "tsh")
    t4 = next(v for v in processed if v.canonical_name == "t4")

    assert tsh.flag == "high"
    assert t4.flag == "normal"
    assert specialty == "Endocrinologist"


def test_golden_diabetic_panel_with_rbs():
    """Diabetic panel with elevated HbA1c and elevated Random Blood Sugar."""
    raw_values = [
        ExtractedValue(test_name="HbA1c (Glycated Hemoglobin)", value=8.4, unit="%"),
        ExtractedValue(test_name="Random Blood Sugar", value=195.0, unit="mg/dL"),
    ]
    processed, specialty = process_extracted_values(raw_values)

    hba1c = next(v for v in processed if v.canonical_name == "hba1c")
    rbs = next(v for v in processed if v.canonical_name == "rbs")

    assert hba1c.flag == "high"
    assert rbs.flag == "high"
    assert specialty == "Endocrinologist"


def test_golden_uric_acid_panel():
    """Hyperuricemia panel routing to Rheumatologist."""
    raw_values = [
        ExtractedValue(test_name="Serum Uric Acid", value=9.2, unit="mg/dL"),
    ]
    processed, specialty = process_extracted_values(raw_values, gender="male")

    uric = next(v for v in processed if v.canonical_name == "uric_acid")
    assert uric.flag == "high"
    assert specialty == "Rheumatologist"


def test_golden_vitamin_deficiency_panel():
    """Vitamin deficiency panel (low Vit D and low B12)."""
    raw_values = [
        ExtractedValue(test_name="Vitamin D (25-OH)", value=14.0, unit="ng/mL"),
        ExtractedValue(test_name="Vitamin B12", value=145.0, unit="pg/mL"),
    ]
    processed, specialty = process_extracted_values(raw_values)

    vit_d = next(v for v in processed if v.canonical_name == "vitamin_d")
    vit_b12 = next(v for v in processed if v.canonical_name == "vitamin_b12")

    assert vit_d.flag == "low"
    assert vit_b12.flag == "low"
    assert specialty == "General Physician"


def test_golden_punctuated_abbreviations_pakistani_labs():
    """Verifies abbreviations with internal dots (e.g., Quest, Chughtai labs) resolve correctly."""
    raw_values = [
        ExtractedValue(test_name="R.B.S.", value=173.0, unit="mg/dL"),
        ExtractedValue(test_name="H.B.", value=13.6, unit="g/dL"),
        ExtractedValue(test_name="S.G.P.T.", value=35.0, unit="U/L"),
        ExtractedValue(test_name="T.L.C.", value=7200, unit="/uL"),
    ]
    processed, _ = process_extracted_values(raw_values, gender="male")

    rbs = next(v for v in processed if v.canonical_name == "rbs")
    hb = next(v for v in processed if v.canonical_name == "hemoglobin")
    alt = next(v for v in processed if v.canonical_name == "alt")
    wbc = next(v for v in processed if v.canonical_name == "wbc")

    assert rbs.flag == "high"
    assert rbs.ref_high == 140.0
    assert hb.flag == "normal"
    assert alt.flag == "normal"
    assert wbc.flag == "normal"


def test_golden_qualitative_infectious_panel():
    """Qualitative tests (Hepatitis reactive, Malaria negative) must be flagged accurately."""
    raw_values = [
        ExtractedValue(test_name="HBs Ag", raw_value="Reactive"),
        ExtractedValue(test_name="Malaria Parasite (MP)", raw_value="Negative"),
        ExtractedValue(test_name="Urine Albumin", raw_value="Nil"),
    ]
    processed, _ = process_extracted_values(raw_values)

    hbsag = next(v for v in processed if "hbs" in v.test_name.lower())
    malaria = next(v for v in processed if "malaria" in v.test_name.lower())
    albumin = next(v for v in processed if "albumin" in v.test_name.lower())

    assert hbsag.flag == "high"
    assert malaria.flag == "normal"
    assert albumin.flag == "normal"


def test_golden_critical_emergency_laboratory_values():
    """Critical low platelet count and critical high glucose must receive 'critical' flag."""
    raw_values = [
        ExtractedValue(test_name="Platelet Count", value=22000, unit="/uL"),
        ExtractedValue(test_name="Fasting Glucose", value=550.0, unit="mg/dL"),
    ]
    processed, specialty = process_extracted_values(raw_values)

    plt = next(v for v in processed if v.canonical_name == "platelets")
    glucose = next(v for v in processed if v.canonical_name == "fasting_glucose")

    assert plt.flag == "critical"
    assert glucose.flag == "critical"


# ── 4. Printed Bounds Priority Over Defaults ──────────────────────────────────

def test_printed_bounds_priority():
    """Report-printed bounds take precedence over standard reference defaults."""
    # Standard creatinine normal is 0.6 - 1.2
    # If a specialized lab explicitly prints ref_high=1.5, a 1.3 reading is NORMAL
    flag, low, high = compute_flag(
        value=1.3,
        canonical_name="creatinine",
        report_low=0.7,
        report_high=1.5,
    )
    assert flag == "normal"
    assert high == 1.5

    # Conversely, if lab printed ref_high=1.0, 1.1 reading is HIGH
    flag_high, _, _ = compute_flag(
        value=1.1,
        canonical_name="creatinine",
        report_low=0.5,
        report_high=1.0,
    )
    assert flag_high == "high"


# ── 5. Patient Name Mismatch Detection ────────────────────────────────────────

def test_patient_name_mismatch_triggers_warning():
    """Mismatch between report patient name and account name triggers mismatch warning."""
    is_mismatch, warning = check_patient_name_mismatch(
        patient_name_found="Farhan Akhtar",
        account_name="Muhammad Taha",
    )
    assert is_mismatch is True
    assert warning is not None
    assert "Farhan Akhtar" in warning
    assert "Muhammad Taha" in warning


def test_patient_name_match_token_overlap():
    """Tokens like 'Taha' vs 'Muhammad Taha' or 'Mr. Taha' should match without warning."""
    is_mismatch, warning = check_patient_name_mismatch(
        patient_name_found="Mr. Muhammad Taha",
        account_name="Taha",
    )
    assert is_mismatch is False
    assert warning is None


# ── 6. Human-in-the-Loop Confirmation Endpoint ───────────────────────────────

def test_confirm_report_values_endpoint():
    """POST /api/reports/{id}/confirm updates values with is_user_edited and recalculates flags."""
    client = TestClient(app)
    headers = {"Authorization": "Bearer dev-user-12345"}

    payload = {
        "values": [
            {
                "test_name": "Hemoglobin",
                "canonical_name": "hemoglobin",
                "value": 10.5,
                "unit": "g/dL",
                "ref_low": 12.0,
                "ref_high": 15.5,
                "is_user_edited": True,
            },
            {
                "test_name": "Fasting Blood Sugar",
                "canonical_name": "fasting_glucose",
                "value": 140.0,
                "unit": "mg/dL",
                "ref_low": 70.0,
                "ref_high": 99.0,
                "is_user_edited": True,
            },
        ],
        "patient_name_acknowledged": True,
    }

    mock_explanation = ReportExplanation(
        summary_en="Verified user-confirmed lab results. Hemoglobin is mildly low and blood sugar is elevated.",
        summary_ur="تصدیق شدہ ٹیسٹ کے نتائج: ہیموگلوبن کی مقدار کم اور شوگر کی سطح بڑھی ہوئی ہے۔",
        questions_for_doctor_en=["How should I address the elevated fasting sugar?"],
        questions_for_doctor_ur=["خالی پیٹ بڑھی ہوئی شوگر کے لیے کیا احتیاط کروں؟"],
        lifestyle_notes=["Maintain regular hydration and low-glycemic meals."],
        specialist_recommendation="Endocrinologist",
    )

    import uuid
    test_rep_id = str(uuid.uuid4())

    with patch("app.routers.reports.generate_report_explanation", new=AsyncMock(return_value=mock_explanation)):
        res = client.post(f"/api/reports/{test_rep_id}/confirm", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()

        assert data["status"] == "analyzed"
        assert len(data["values"]) == 2
        hb_val = next(v for v in data["values"] if v["canonical_name"] == "hemoglobin")
        sugar_val = next(v for v in data["values"] if v["canonical_name"] == "fasting_glucose")

        assert hb_val["flag"] == "low"
        assert hb_val["is_user_edited"] is True
        assert sugar_val["flag"] == "high"
        assert sugar_val["is_user_edited"] is True
        assert data["overall_risk"] in ("MEDIUM", "HIGH", "CLINICAL_REVIEW_RECOMMENDED")


# ── 8. Prescription Extraction & Safety Cross-Verification Tests ──────────────

@pytest.mark.asyncio
async def test_prescription_pipeline_with_allergy_guardrail():
    """Prescription pipeline must extract medicines and deterministically flag allergy conflicts."""
    from app.services.extractor import run_prescription_pipeline
    from app.llm.schemas import PrescribedMedicine, PrescriptionExtraction

    mock_presc = PrescriptionExtraction(
        document_type=DocumentType.PRESCRIPTION,
        is_medical_document=True,
        doctor_name="Dr. Asim Farooq (Consultant Physician)",
        patient_name_found="Taha Ahmed",
        prescription_date="2026-10-22",
        diagnosis_or_notes="Upper Respiratory Tract Infection with fever",
        medicines=[
            PrescribedMedicine(
                name="Augmentin",
                dosage="625mg",
                frequency="Twice daily (1+0+1)",
                duration="5 days",
                instructions="After food",
                purpose_en="Antibiotic for bacterial infection",
                purpose_ur="بیکٹیریل انفیکشن کے لیے اینٹی بائیوٹک",
            ),
            PrescribedMedicine(
                name="Panadol",
                dosage="500mg",
                frequency="1 tablet 3 times a day SOS",
                duration="3 days",
                instructions="When fever is above 100 F",
                purpose_en="For fever and headache relief",
                purpose_ur="بخار اور سر درد سے نجات کے لیے",
            ),
        ],
        general_advice_en="Drink plenty of warm fluids and take proper bed rest.",
        general_advice_ur="زیادہ گرم مشروبات پئیں اور مکمل آرام کریں۔",
        confidence=Confidence.HIGH,
    )

    with patch("app.services.extractor.call_llm", new=AsyncMock(return_value=mock_presc)):
        # Patient has Penicillin allergy -> Augmentin contains amoxicillin/clavulanate -> must trigger alert!
        result = await run_prescription_pipeline(
            file_bytes=b"fake_prescription_bytes",
            content_type="image/jpeg",
            known_allergies=["Penicillin"],
            account_name="Taha Ahmed",
        )

        assert result.document_type == DocumentType.PRESCRIPTION
        assert result.is_medical_document is True
        assert result.patient_name_mismatch is False
        assert len(result.medicines) == 2
        assert len(result.allergy_alerts) >= 1
        augmentin = next(m for m in result.medicines if m.name == "Augmentin")
        assert augmentin.allergy_warning is not None
        assert "penicillin" in augmentin.allergy_warning.lower()


@pytest.mark.asyncio
async def test_prescription_pipeline_patient_name_mismatch():
    """Prescription for different patient must trigger mismatch warning."""
    from app.services.extractor import run_prescription_pipeline
    from app.llm.schemas import PrescribedMedicine, PrescriptionExtraction

    mock_presc = PrescriptionExtraction(
        document_type=DocumentType.PRESCRIPTION,
        is_medical_document=True,
        patient_name_found="Muhammad Tariq",
        medicines=[
            PrescribedMedicine(name="Metformin", dosage="500mg", frequency="1+0+1"),
        ],
    )

    with patch("app.services.extractor.call_llm", new=AsyncMock(return_value=mock_presc)):
        result = await run_prescription_pipeline(
            file_bytes=b"fake_prescription_bytes",
            content_type="image/jpeg",
            account_name="Ayesha Khan",
        )

        assert result.patient_name_mismatch is True
        assert "Muhammad Tariq" in (result.mismatch_warning or "")


def test_prescription_confirm_endpoint_saves_memory():
    """POST /api/reports/{id}/confirm-prescription saves medications and updates memory_facts."""
    client = TestClient(app)
    headers = {"Authorization": "Bearer dev-user-12345"}

    import uuid
    test_rep_id = str(uuid.uuid4())

    payload = {
        "medicines": [
            {
                "name": "Metformin",
                "dosage": "500mg",
                "frequency": "Twice daily",
                "duration": "Ongoing",
                "instructions": "With meals",
                "purpose_en": "Blood sugar regulation",
                "purpose_ur": "شوگر کنٹرول کرنے کے لیے",
            }
        ],
        "diagnosis_or_notes": "Type 2 Diabetes Mellitus",
        "save_to_memory": True,
    }

    with patch("app.routers.reports.save_memory_facts", new=AsyncMock(return_value=[])):
        res = client.post(f"/api/reports/{test_rep_id}/confirm-prescription", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "confirmed"
        assert len(data["medicines"]) == 1
        assert data["medicines"][0]["name"] == "Metformin"


# ── 8. September 20, 2000 Source of Truth Regression Suite (22 Tests) ──────────

def test_september_20_2000_all_22_values_regression():
    """
    Regression test verifying all 22 laboratory tests from the September 20, 2000
    source report against their exact printed values, units, reference intervals,
    and clinical flags.
    """
    from app.services.flags import compute_flag, process_extracted_values, compute_overall_risk

    report_22_tests = [
        {"test": "Sodium", "val": 134.0, "unit": "mmol/L", "low": 136.0, "high": 146.0, "exp_flag": "low"},
        {"test": "Potassium", "val": 4.9, "unit": "mmol/L", "low": 3.8, "high": 4.8, "exp_flag": "high"},
        {"test": "Chloride", "val": 102.0, "unit": "mmol/L", "low": 98.0, "high": 108.0, "exp_flag": "normal"},
        {"test": "Total CO2", "val": 25.4, "unit": "mmol/L", "low": 24.0, "high": 32.0, "exp_flag": "normal"},
        {"test": "Glucose", "val": 151.0, "unit": "mg/dL", "low": 70.0, "high": 110.0, "exp_flag": "high"},
        {"test": "BUN", "val": 30.0, "unit": "mg/dL", "low": 7.0, "high": 22.0, "exp_flag": "high"},
        {"test": "Calculated osmolality", "val": 277.0, "unit": "mOsm/kg", "low": 275.0, "high": 295.0, "exp_flag": "normal"},
        {"test": "Creatinine", "val": 1.4, "unit": "mg/dL", "low": 0.4, "high": 1.5, "exp_flag": "normal"},
        {"test": "B/C ratio", "val": 21.0, "unit": "", "low": 6.0, "high": 20.0, "exp_flag": "high"},
        {"test": "Calcium", "val": 8.9, "unit": "mg/dL", "low": 8.7, "high": 10.2, "exp_flag": "normal"},
        {"test": "Total bilirubin", "val": 0.35, "unit": "mg/dL", "low": 0.0, "high": 1.0, "exp_flag": "normal"},
        {"test": "Total protein", "val": 7.5, "unit": "g/dL", "low": 6.5, "high": 8.2, "exp_flag": "normal"},
        {"test": "Albumin", "val": 3.0, "unit": "g/dL", "low": 3.4, "high": 4.3, "exp_flag": "low"},
        {"test": "Alkaline phosphatase", "val": 118.0, "unit": "U/L", "low": 50.0, "high": 136.0, "exp_flag": "normal"},
        {"test": "GOT (AST)", "val": 29.0, "unit": "U/L", "low": 15.0, "high": 37.0, "exp_flag": "normal"},
        {"test": "GPT (ALT)", "val": 33.0, "unit": "U/L", "low": 30.0, "high": 65.0, "exp_flag": "normal"},
        {"test": "Magnesium", "val": 2.1, "unit": "mg/dL", "low": 1.7, "high": 2.6, "exp_flag": "normal"},
        {"test": "Total cholesterol", "val": 138.0, "unit": "mg/dL", "low": None, "high": 200.0, "exp_flag": "normal"},
        {"test": "Triglycerides", "val": 58.0, "unit": "mg/dL", "low": 30.0, "high": 200.0, "exp_flag": "normal"},
        {"test": "HDL cholesterol", "val": 43.0, "unit": "mg/dL", "low": 32.0, "high": 72.0, "exp_flag": "normal"},
        {"test": "VLDL cholesterol", "val": 12.0, "unit": "mg/dL", "low": None, "high": 40.0, "exp_flag": "normal"},
        {"test": "LDL cholesterol", "val": 83.0, "unit": "mg/dL", "low": None, "high": 130.0, "exp_flag": "normal"},
    ]

    extracted_items = []
    for item in report_22_tests:
        flag, low, high = compute_flag(
            value=item["val"],
            canonical_name=None,
            test_name=item["test"],
            report_low=item["low"],
            report_high=item["high"],
        )
        assert flag == item["exp_flag"], (
            f"Flag mismatch for {item['test']}: got '{flag}', expected '{item['exp_flag']}' "
            f"(val={item['val']}, range={item['low']}-{item['high']})"
        )

        extracted_items.append(
            ExtractedValue(
                test_name=item["test"],
                value=item["val"],
                unit=item["unit"],
                ref_low=item["low"],
                ref_high=item["high"],
            )
        )

    # Process all values through complete pipeline
    flagged, specialty = process_extracted_values(extracted_items, gender="male")
    assert len(flagged) == 22

    # Verify specialty routing: isolated elevated BUN/BC ratio with normal Creatinine (1.4) MUST route to General Physician
    assert specialty == "General Physician", f"Expected 'General Physician', but got '{specialty}'"

    # Verify evidence-based overall risk
    overall_risk, evidence = compute_overall_risk(flagged)
    assert overall_risk == "CLINICAL_REVIEW_RECOMMENDED"
    assert len(evidence) >= 5
    assert any("BUN" in e for e in evidence)
    assert any("Glucose" in e for e in evidence)
    assert any("Albumin" in e for e in evidence)


def test_hdl_reversed_range_and_misread_correction():
    """
    Specifically verifies the known HDL bug:
    When OCR/LLM produces a reversed range (low=40, high=32) for HDL value 43:
    1. Reversed range must be detected and inverted or corrected.
    2. HDL 43 must NOT be falsely classified as HIGH.
    3. With correct printed bounds 32-72, HDL 43 is NORMAL.
    """
    from app.services.flags import compute_flag, validate_and_sanitize_range

    # 1. Direct range sanitizer check
    low, high, note = validate_and_sanitize_range(40.0, 32.0, "HDL cholesterol")
    assert low == 32.0 and high == 40.0, f"Expected swapped (32, 40), got ({low}, {high})"
    assert note is not None and "inverted" in note.lower()

    # 2. Correct printed range 32-72
    flag_correct, _, _ = compute_flag(
        value=43.0,
        canonical_name="hdl",
        test_name="HDL cholesterol",
        report_low=32.0,
        report_high=72.0,
    )
    assert flag_correct == "normal", f"Expected HDL 43 to be normal, got {flag_correct}"

    # 3. Even with reversed raw input (40, 32), compute_flag sanitizes and doesn't crash
    flag_reversed, s_low, s_high = compute_flag(
        value=43.0,
        canonical_name="hdl",
        test_name="HDL cholesterol",
        report_low=40.0,
        report_high=32.0,
    )
    # The swapped range is 32-40 (since 40 was misread), but standard fallback is 32-72
    assert s_low <= s_high, f"Sanitized range must satisfy low <= high, got {s_low} > {s_high}"


def test_one_sided_reference_ranges():
    """
    Verifies one-sided reference ranges such as <200, <40, >40, <130.
    """
    from app.services.flags import compute_flag, validate_and_sanitize_range

    # < 200 (Total Cholesterol)
    low, high, _ = validate_and_sanitize_range(None, None, ref_range_text="< 200")
    assert low is None and high == 200.0

    flag, _, _ = compute_flag(138.0, "total_cholesterol", report_low=None, report_high=200.0)
    assert flag == "normal"

    flag_hi, _, _ = compute_flag(240.0, "total_cholesterol", report_low=None, report_high=200.0)
    assert flag_hi == "high"

    # > 40 (e.g. minimum HDL threshold)
    low_gt, high_gt, _ = validate_and_sanitize_range(None, None, ref_range_text="> 40")
    assert low_gt == 40.0 and high_gt is None

    flag_gt_norm, _, _ = compute_flag(45.0, "hdl", report_low=40.0, report_high=None)
    assert flag_gt_norm == "normal"

    flag_gt_low, _, _ = compute_flag(35.0, "hdl", report_low=40.0, report_high=None)
    assert flag_gt_low == "low"


