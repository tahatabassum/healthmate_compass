"""
Unit tests for the Flags Engine (backend/app/services/flags.py).
Tests reference ranges, sex-specific ranges, critical bounds, and specialty routing.
"""
import pytest
from app.services.flags import (
    resolve_canonical_name,
    compute_flag,
    process_extracted_values,
    route_to_specialty,
)
from app.llm.schemas import ExtractedValue


def test_canonical_name_resolution():
    assert resolve_canonical_name("Hb") == "hemoglobin"
    assert resolve_canonical_name("Haemoglobin") == "hemoglobin"
    assert resolve_canonical_name("Serum Creatinine") == "creatinine"
    assert resolve_canonical_name("Fasting Blood Sugar") == "fasting_glucose"
    assert resolve_canonical_name("S. Cholesterol") == "total_cholesterol"
    assert resolve_canonical_name("TLC") == "wbc"
    assert resolve_canonical_name("Plt") == "platelets"
    assert resolve_canonical_name("SGPT") == "alt"


def test_hemoglobin_ranges_sex_specific():
    # Male: 13.5 - 17.5
    flag_m_normal, _, _ = compute_flag(15.0, "hemoglobin", gender="male")
    assert flag_m_normal == "normal"

    flag_m_low, _, _ = compute_flag(12.5, "hemoglobin", gender="male")
    assert flag_m_low == "low"

    # Female: 12.0 - 15.5 (12.5 is normal for female, but low for male)
    flag_f_normal, _, _ = compute_flag(12.5, "hemoglobin", gender="female")
    assert flag_f_normal == "normal"

    flag_f_low, _, _ = compute_flag(10.0, "hemoglobin", gender="female")
    assert flag_f_low == "low"

    # Critical low (<= 7.0)
    flag_crit, _, _ = compute_flag(6.5, "hemoglobin", gender="female")
    assert flag_crit == "critical"


def test_report_printed_bounds_override_defaults():
    # If lab report specifically prints custom bounds 80 - 120
    flag, low, high = compute_flag(
        value=110,
        canonical_name="fasting_glucose",
        report_low=80.0,
        report_high=120.0,
    )
    assert flag == "normal"
    assert low == 80.0
    assert high == 120.0

    flag_high, _, _ = compute_flag(
        value=125,
        canonical_name="fasting_glucose",
        report_low=80.0,
        report_high=120.0,
    )
    assert flag_high == "high"


def test_critical_thresholds():
    # Fasting glucose critical high >= 500
    flag, _, _ = compute_flag(520, "fasting_glucose")
    assert flag == "critical"

    # Fasting glucose critical low <= 40
    flag_hypo, _, _ = compute_flag(35, "fasting_glucose")
    assert flag_hypo == "critical"

    # Platelets critical low <= 50,000
    flag_plt, _, _ = compute_flag(30000, "platelets")
    assert flag_plt == "critical"


def test_specialty_routing_priority_rules():
    # Creatinine abnormal -> Nephrologist override
    vals = [
        ExtractedValue(test_name="Hemoglobin", value=10.0), # low
        ExtractedValue(test_name="Serum Creatinine", value=2.5), # high
    ]
    processed, specialty = process_extracted_values(vals, gender="male")
    assert specialty == "Nephrologist"

    # Two cardiac markers abnormal -> Cardiologist override
    vals_cardiac = [
        ExtractedValue(test_name="Total Cholesterol", value=240),
        ExtractedValue(test_name="Triglycerides", value=220),
        ExtractedValue(test_name="ALT", value=65), # 1 liver marker
    ]
    processed, specialty = process_extracted_values(vals_cardiac)
    assert specialty == "Cardiologist"

    # Critically low hemoglobin -> Hematologist priority override
    vals_crit_hb = [
        ExtractedValue(test_name="Hb", value=5.5), # critical
        ExtractedValue(test_name="ALT", value=75),
    ]
    processed, specialty = process_extracted_values(vals_crit_hb)
    assert specialty == "Hematologist"


def test_all_normal_routes_to_general_physician():
    vals = [
        ExtractedValue(test_name="Hemoglobin", value=14.5),
        ExtractedValue(test_name="Fasting Blood Sugar", value=85),
    ]
    processed, specialty = process_extracted_values(vals, gender="male")
    assert specialty == "General Physician"
    assert all(v.flag == "normal" for v in processed)
