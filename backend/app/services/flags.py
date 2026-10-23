"""
Flags Engine for HealthMate Compass.
Computes lab abnormal flags ('low', 'normal', 'high', 'critical', 'unverified') purely in Python code.
Routes flagged test results to the correct clinical specialty using deterministic rules.
Never relies on LLMs for numeric comparison or medical flag thresholds.
"""
import json
import os
import re
from typing import Optional, List, Tuple, Dict, Any
from app.llm.schemas import ExtractedValue, Specialty

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def load_json(filename: str) -> dict:
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "r", encoding="utf-8-sig") as f:
        return json.load(f)


REFERENCE_DATA = load_json("reference_ranges.json")
SPECIALTY_DATA = load_json("specialty_map.json")

TEST_DEFINITIONS: dict = REFERENCE_DATA.get("tests", {})
TEST_TO_SPECIALTY: dict = SPECIALTY_DATA.get("test_to_specialty", {})
PRIORITY_RULES: list = SPECIALTY_DATA.get("priority_rules", [])
DEFAULT_SPECIALTY: str = SPECIALTY_DATA.get("default_specialty", "General Physician")

# Build synonym lookup cache: lower_synonym -> canonical_key
SYNONYM_MAP: Dict[str, str] = {}
for canonical_key, data in TEST_DEFINITIONS.items():
    SYNONYM_MAP[canonical_key.lower()] = canonical_key
    for syn in data.get("synonyms", []):
        SYNONYM_MAP[syn.lower().strip()] = canonical_key

# Additional standard clinical aliases & truncated report printout aliases
ADDITIONAL_ALIASES = {
    # CBC
    "platelet count": "platelets",
    "platelet": "platelets",
    "total platelet count": "platelets",
    "plt": "platelets",
    "total wbc count": "wbc",
    "wbc count": "wbc",
    "white blood count": "wbc",
    "tlc count": "wbc",
    "tlc": "wbc",
    "total leukocytes count": "wbc",
    "total leukocyte count": "wbc",
    "haemoglobin": "hemoglobin",
    "hb": "hemoglobin",
    "hgb": "hemoglobin",
    
    # Blood Glucose / Diabetes
    "glucose": "glucose",
    "blood glucose": "glucose",
    "serum glucose": "glucose",
    "blood sugar": "glucose",
    "fasting blood glucose": "fasting_glucose",
    "fasting glucose": "fasting_glucose",
    "blood sugar fasting": "fasting_glucose",
    "fbs": "fasting_glucose",
    "bsf": "fasting_glucose",
    "random blood glucose": "rbs",
    "blood sugar random": "rbs",
    "random blood sugar": "rbs",
    "rbs": "rbs",
    "bsr": "rbs",
    "hba1c": "hba1c",

    # Renal / Electrolytes / Osmolality
    "serum creatinine": "creatinine",
    "s. creatinine": "creatinine",
    "creat": "creatinine",
    "urea": "bun",
    "blood urea": "bun",
    "serum urea": "bun",
    "s. urea": "bun",
    "bun": "bun",
    "blood urea nitrogen": "bun",
    "b/c ratio": "bun_creatinine_ratio",
    "b/c": "bun_creatinine_ratio",
    "bc ratio": "bun_creatinine_ratio",
    "bun/creatinine ratio": "bun_creatinine_ratio",
    "bun creatinine ratio": "bun_creatinine_ratio",
    "calc osmo": "osmolality",
    "calc. osmo": "osmolality",
    "calculated osmolality": "osmolality",
    "osmolality": "osmolality",
    "sodium": "sodium",
    "potassium": "potassium",
    "chloride": "chloride",
    "total co2": "total_co2",
    "co2": "total_co2",
    "bicarbonate": "total_co2",
    "calcium": "calcium",
    "magnesium": "magnesium",

    # Liver Function (LFT)
    "total_bilirubin": "bilirubin_total",
    "total bilirubin": "bilirubin_total",
    "total bili": "bilirubin_total",
    "tot bili": "bilirubin_total",
    "bilirubin": "bilirubin_total",
    "serum bilirubin": "bilirubin_total",
    "s. bilirubin": "bilirubin_total",
    "total protein": "total_protein",
    "total prot": "total_protein",
    "tot prot": "total_protein",
    "protein total": "total_protein",
    "albumin": "albumin",
    "alk phos": "alkaline_phosphatase",
    "alkaline phosphatase": "alkaline_phosphatase",
    "alp": "alkaline_phosphatase",
    "sgpt": "alt",
    "alt (sgpt)": "alt",
    "gpt (alt)": "alt",
    "gpt": "alt",
    "sgot": "ast",
    "ast (sgot)": "ast",
    "got (ast)": "ast",
    "got": "ast",

    # Lipid Panel (Coronary Risk Profile)
    "total cholesterol": "total_cholesterol",
    "serum cholesterol": "total_cholesterol",
    "cholesterol": "total_cholesterol",
    "cholestero": "total_cholesterol",
    "triglycerides": "triglycerides",
    "triglyceri": "triglycerides",
    "tg": "triglycerides",
    "hdl cholesterol": "hdl",
    "hdl chol": "hdl",
    "hdl": "hdl",
    "vldl cholesterol": "vldl",
    "vldl chol": "vldl",
    "vldl": "vldl",
    "ldl cholesterol": "ldl",
    "ldl chol": "ldl",
    "ldl": "ldl",
}
for alias, canon in ADDITIONAL_ALIASES.items():
    SYNONYM_MAP[alias.lower().strip()] = canon


def clean_test_name(name: str) -> str:
    """Strips punctuation, parenthesis noise, prefixes, and extra whitespace."""
    if not name:
        return ""
    cleaned = name.lower().strip()
    cleaned = re.sub(r"^(serum|blood|plasma|s\.|b\.)\s+", "", cleaned)
    cleaned = cleaned.replace("(", " ").replace(")", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def resolve_canonical_name(test_name: str) -> Optional[str]:
    """
    Resolves a raw test name from a lab report to its canonical reference key.
    Strips noise prefixes like 'Serum', 'S.', 'Blood', 'Plasma', 'Total'.
    Handles dot-separated abbreviations (e.g., 'R.B.S.', 'H.B.', 'S.G.P.T.').
    Handles parenthesis abbreviations (e.g., 'GOT (AST)', 'GPT (ALT)', 'Alk Phos').
    """
    if not test_name:
        return None

    raw_clean = test_name.lower().strip()
    if raw_clean in SYNONYM_MAP:
        return SYNONYM_MAP[raw_clean]

    cleaned = clean_test_name(test_name)
    if cleaned in SYNONYM_MAP:
        return SYNONYM_MAP[cleaned]

    # Normalize dot-separated abbreviations: 'r.b.s.' -> 'rbs', 's.g.p.t.' -> 'sgpt'
    no_dots = raw_clean.replace(".", "").strip()
    if no_dots in SYNONYM_MAP:
        return SYNONYM_MAP[no_dots]

    no_dots_clean = cleaned.replace(".", "").strip()
    if no_dots_clean in SYNONYM_MAP:
        return SYNONYM_MAP[no_dots_clean]

    # Try token subsets: e.g. "got ast" -> check "ast" or "got"
    tokens = cleaned.split()
    for tok in tokens:
        if tok in SYNONYM_MAP:
            return SYNONYM_MAP[tok]

    # Try removing trailing noise tokens: 'count', 'test', 'level', 'panel', 'examination'
    stripped = re.sub(r"\s+(count|test|level|panel|examination|method|screening)$", "", cleaned).strip()
    if stripped in SYNONYM_MAP:
        return SYNONYM_MAP[stripped]

    # Substring / word matching
    for syn, canonical in SYNONYM_MAP.items():
        if syn == cleaned or syn == no_dots or f" {syn} " in f" {cleaned} ":
            return canonical

    return None


def parse_numeric_and_lab_flag(raw: Any) -> Tuple[Optional[float], Optional[str]]:
    """
    Parses a numeric value and any attached lab flag (e.g. '134L' -> 134.0, 'L'; '4.9H' -> 4.9, 'H').
    """
    if raw is None:
        return None, None
    if isinstance(raw, (int, float)):
        return float(raw), None

    s = str(raw).strip()
    if not s:
        return None, None

    # Check for trailing flag letter (L, H, C, *)
    match = re.match(r"^([+-]?\d+(?:\.\d+)?)\s*([A-Za-z*]+)?$", s)
    if match:
        val_str, flag_str = match.groups()
        try:
            val = float(val_str)
            lab_flag = flag_str.upper() if flag_str else None
            return val, lab_flag
        except ValueError:
            pass

    # Check for inequality: e.g. "< 200", "> 40"
    ineq_match = re.match(r"^[<>]\s*(\d+(?:\.\d+)?)$", s)
    if ineq_match:
        try:
            return float(ineq_match.group(1)), None
        except ValueError:
            pass

    return None, None


def validate_and_sanitize_range(
    ref_low: Optional[float],
    ref_high: Optional[float],
    ref_range_text: Optional[str] = None,
    range_text: Optional[str] = None,
    test_name: Optional[str] = None,
) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Validates reference interval boundaries:
    1. Rejects or corrects inverted/reversed ranges (low > high).
    2. Parses one-sided range text like '< 200' -> low=None, high=200; '> 40' -> low=40, high=None.
    Returns (clean_low, clean_high, warning_or_error_note).
    """
    warning = None
    txt = (ref_range_text or range_text or "").strip()

    # Check if range text gives explicit inequality
    if txt:
        lt_match = re.match(r"^<\s*(\d+(?:\.\d+)?)$", txt)
        if lt_match:
            return None, float(lt_match.group(1)), None
        gt_match = re.match(r"^>\s*(\d+(?:\.\d+)?)$", txt)
        if gt_match:
            return float(gt_match.group(1)), None, None
        hyphen_match = re.match(r"^(\d+(?:\.\d+)?)\s*[-–—to]+\s*(\d+(?:\.\d+)?)$", txt)
        if hyphen_match:
            p_low = float(hyphen_match.group(1))
            p_high = float(hyphen_match.group(2))
            if p_low <= p_high:
                return p_low, p_high, None
            else:
                warning = f"Reversed range detected in printed text '{txt}', swapped bounds."
                return p_high, p_low, warning

    if ref_low is not None and ref_high is not None:
        if ref_low > ref_high:
            # Reversed range! e.g. 40 - 32
            warning = f"Reversed reference range detected [{ref_low}, {ref_high}]. Inverted bounds corrected."
            ref_low, ref_high = ref_high, ref_low

    return ref_low, ref_high, warning


def compute_flag(
    value: Optional[float],
    canonical_name: Optional[str] = None,
    report_low: Optional[float] = None,
    report_high: Optional[float] = None,
    ref_range_text: Optional[str] = None,
    gender: Optional[str] = None,
    test_name: Optional[str] = None,
    range_text: Optional[str] = None,
) -> Tuple[str, Optional[float], Optional[float]]:
    """
    Computes flag strictly in code:
    - Lab report's printed bounds take priority for low/high if provided.
    - Default reference_ranges.json used when report bounds are absent.
    - Rejects invalid / reversed ranges.
    - Supports one-sided ranges (<200, >40).
    - Returns 3-tuple (flag, effective_low, effective_high).
    """
    if value is None:
        return "unverified", None, None

    if not canonical_name and test_name:
        canonical_name = resolve_canonical_name(test_name)

    actual_range_text = ref_range_text or range_text

    # Validate and correct reported bounds
    effective_low, effective_high, _ = validate_and_sanitize_range(
        report_low, report_high, actual_range_text
    )

    crit_low: Optional[float] = None
    crit_high: Optional[float] = None

    if canonical_name and canonical_name in TEST_DEFINITIONS:
        test_info = TEST_DEFINITIONS[canonical_name]
        ranges = test_info.get("ranges", {})
        gen_key = (gender or "default").lower()
        active_range = ranges.get(gen_key) or ranges.get("default") or {}

        if effective_low is None and active_range.get("low") is not None:
            effective_low = active_range.get("low")
        if effective_high is None and active_range.get("high") is not None:
            effective_high = active_range.get("high")

        crit_low = active_range.get("critical_low")
        crit_high = active_range.get("critical_high")

    # Final check for reversed range after merging default
    if effective_low is not None and effective_high is not None and effective_low > effective_high:
        effective_low, effective_high = effective_high, effective_low

    # 1. Critical thresholds evaluation
    if crit_low is not None and value <= crit_low:
        return "critical", effective_low, effective_high
    if crit_high is not None and value >= crit_high:
        return "critical", effective_low, effective_high

    # 2. Standard Low / High evaluation
    if effective_low is not None and value < effective_low:
        return "low", effective_low, effective_high
    if effective_high is not None and value > effective_high:
        return "high", effective_low, effective_high

    return "normal", effective_low, effective_high


def sanitize_and_convert_value(item: ExtractedValue) -> ExtractedValue:
    """
    Sanitizes extracted values and normalizes units into standard clinical units:
    1. Extracts numeric value and attached lab flag if present in raw string.
    2. Negative values are caught and suppressed.
    3. Units converted:
       - Glucose: mmol/L -> mg/dL (* 18.0182)
       - Hemoglobin: g/L -> g/dL (/ 10.0)
       - Cholesterol/Lipids: mmol/L -> mg/dL (* 38.67)
       - Creatinine: umol/L -> mg/dL (/ 88.4)
    4. Extreme biological impossibility thresholds are flagged.
    """
    # Extract value & lab_flag from raw string if value is missing or raw_value has flag suffix
    if item.value is None and item.raw_value:
        num, l_flag = parse_numeric_and_lab_flag(item.raw_value)
        if num is not None:
            item.value = num
        if l_flag and not item.lab_flag:
            item.lab_flag = l_flag
    elif item.value is not None and item.raw_value and not item.lab_flag:
        _, l_flag = parse_numeric_and_lab_flag(item.raw_value)
        if l_flag:
            item.lab_flag = l_flag

    if item.value is None:
        return item

    # 1. Negative numbers check
    if item.value < 0:
        item.sanity_error = f"Suppressed invalid negative reading ({item.value})."
        item.value = None
        item.flag = "unverified"
        return item

    unit_str = (item.unit or "").strip().lower()
    canonical = item.canonical_name or resolve_canonical_name(item.test_name)

    # 2. Unit conversions
    if canonical in ("fasting_glucose", "random_glucose", "blood_glucose", "glucose"):
        if "mmol" in unit_str or (item.value <= 35.0 and unit_str in ("mmol/l", "mmol")):
            converted = round(item.value * 18.0182, 1)
            item.sanity_error = f"Converted {item.value} mmol/L to {converted} mg/dL."
            item.value = converted
            item.unit = "mg/dL"
            if item.ref_low and item.ref_low < 30:
                item.ref_low = round(item.ref_low * 18.0182, 1)
            if item.ref_high and item.ref_high < 30:
                item.ref_high = round(item.ref_high * 18.0182, 1)

    elif canonical == "hemoglobin":
        if "g/l" in unit_str or (item.value >= 60.0 and item.value <= 220.0 and ("g/l" in unit_str or unit_str == "")):
            if "g/l" in unit_str or item.value > 40.0:
                converted = round(item.value / 10.0, 1)
                item.sanity_error = f"Converted {item.value} g/L to {converted} g/dL."
                item.value = converted
                item.unit = "g/dL"
                if item.ref_low and item.ref_low > 40:
                    item.ref_low = round(item.ref_low / 10.0, 1)
                if item.ref_high and item.ref_high > 40:
                    item.ref_high = round(item.ref_high / 10.0, 1)

    elif canonical in ("total_cholesterol", "triglycerides", "hdl", "ldl", "vldl"):
        if "mmol" in unit_str or (item.value <= 20.0 and unit_str in ("mmol/l", "mmol")):
            converted = round(item.value * 38.67, 1)
            item.sanity_error = f"Converted {item.value} mmol/L to {converted} mg/dL."
            item.value = converted
            item.unit = "mg/dL"
            if item.ref_low and item.ref_low < 30:
                item.ref_low = round(item.ref_low * 38.67, 1)
            if item.ref_high and item.ref_high < 30:
                item.ref_high = round(item.ref_high * 38.67, 1)

    elif canonical == "creatinine":
        if "umol" in unit_str or "μmol" in unit_str or (item.value >= 30.0 and ("mol" in unit_str or unit_str == "")):
            converted = round(item.value / 88.4, 2)
            item.sanity_error = f"Converted {item.value} μmol/L to {converted} mg/dL."
            item.value = converted
            item.unit = "mg/dL"
            if item.ref_low and item.ref_low > 20:
                item.ref_low = round(item.ref_low / 88.4, 2)
            if item.ref_high and item.ref_high > 20:
                item.ref_high = round(item.ref_high / 88.4, 2)

    # 3. Biological impossibility checks
    if canonical == "hemoglobin" and item.value is not None and item.value > 35.0:
        item.sanity_error = f"Physiologically impossible hemoglobin value ({item.value} g/dL)."
    elif canonical == "platelets" and item.value is not None and item.value > 3_000_000:
        item.sanity_error = f"Platelet count exceeds biological maximum ({item.value} /uL)."
    elif canonical in ("fasting_glucose", "random_glucose", "glucose") and item.value is not None and (item.value > 2000 or item.value < 10):
        item.sanity_error = f"Extreme glucose reading out of biological bounds ({item.value} mg/dL)."
    elif canonical == "creatinine" and item.value is not None and item.value > 40.0:
        item.sanity_error = f"Extreme creatinine reading out of biological bounds ({item.value} mg/dL)."
    elif canonical == "wbc" and item.value is not None and item.value > 500_000:
        item.sanity_error = f"WBC exceeds biological maximum ({item.value} /uL)."

    return item


def check_patient_name_mismatch(
    patient_name_found: Optional[str],
    account_name: Optional[str],
) -> Tuple[bool, Optional[str]]:
    """
    Checks if patient name extracted from lab report header matches user account profile name.
    Returns (is_mismatch, warning_message).
    """
    if not patient_name_found or not account_name:
        return False, None

    cleaned_rep = patient_name_found.lower().strip()
    cleaned_acc = account_name.lower().strip()

    # Strip titles/honorifics
    honorifics = r"\b(mr|mrs|ms|miss|dr|patient|syed|syeda|ch|choudhry|shaikh|malik|mian|hafiz|haji)\b"
    cleaned_rep = re.sub(honorifics, "", cleaned_rep)
    cleaned_acc = re.sub(honorifics, "", cleaned_acc)

    # Strip punctuation and multiple spaces
    cleaned_rep = re.sub(r"[^\w\s]", "", cleaned_rep)
    cleaned_acc = re.sub(r"[^\w\s]", "", cleaned_acc)
    rep_tokens = set(t for t in cleaned_rep.split() if len(t) > 1)
    acc_tokens = set(t for t in cleaned_acc.split() if len(t) > 1)

    if not rep_tokens or not acc_tokens:
        return False, None

    # Check if there is any shared name token (e.g. "Taha" in "Muhammad Taha" and "Taha", or "John" in "Smith, John")
    shared = rep_tokens.intersection(acc_tokens)
    if not shared:
        warning = (
            f"The name printed on this report is '{patient_name_found}', which does not match "
            f"your account profile name ('{account_name}'). Please verify you have uploaded the correct report."
        )
        return True, warning

    return False, None


def compute_overall_risk(values: List[ExtractedValue]) -> Tuple[str, List[str]]:
    """
    Computes transparent, evidence-based overall clinical risk status.
    Avoids arbitrary counting or weighted points.
    Returns (status, evidence_list).
    Status values:
    - 'POTENTIALLY_URGENT': Critical laboratory values detected requiring prompt physician review.
    - 'CLINICAL_REVIEW_RECOMMENDED': Specific abnormal findings detected outside reference intervals.
    - 'ROUTINE_NORMAL': All analyzed parameters are within physiological reference intervals.
    - 'MANUAL_REVIEW_REQUIRED': Results unverified or insufficient data to evaluate.
    """
    if not values:
        return "MANUAL_REVIEW_REQUIRED", ["No valid test observations extracted for risk evaluation."]

    critical_items = [v for v in values if v.flag == "critical"]
    abnormal_items = [v for v in values if v.flag in ("low", "high", "abnormal_qualitative")]
    unverified_items = [v for v in values if v.flag == "unverified" or v.value is None and not v.raw_value]

    evidence: List[str] = []

    if critical_items:
        for c in critical_items:
            ref_str = f"[{c.ref_low} - {c.ref_high} {c.unit or ''}]" if c.ref_low or c.ref_high else ""
            evidence.append(f"Potentially critical value for {c.test_name}: {c.value} {c.unit or ''} {ref_str}")
        return "POTENTIALLY_URGENT", evidence

    if abnormal_items:
        for a in abnormal_items:
            tag = "Elevated" if a.flag == "high" else ("Low" if a.flag == "low" else "Abnormal")
            ref_str = f"(reference interval: {a.ref_low} - {a.ref_high} {a.unit or ''})" if a.ref_low or a.ref_high else ""
            evidence.append(f"{tag} {a.test_name}: {a.value or a.raw_value} {a.unit or ''} {ref_str}".strip())
        return "CLINICAL_REVIEW_RECOMMENDED", evidence

    if unverified_items and len(unverified_items) == len(values):
        return "MANUAL_REVIEW_REQUIRED", ["Extracted test values could not be verified against clinical bounds."]

    return "ROUTINE_NORMAL", ["All analyzed laboratory test results fall within their established reference intervals."]


def process_extracted_values(
    values: List[ExtractedValue],
    gender: Optional[str] = None,
) -> Tuple[List[ExtractedValue], str]:
    """
    Iterates over extracted values:
    1. Resolves canonical test names.
    2. Runs sanity checks, unit conversions, and lab flag extraction.
    3. Computes flags ('low', 'normal', 'high', 'critical', 'unverified') with range validation.
    4. Populates specialty hints.
    5. Computes the overall primary specialist recommendation.
    """
    processed: List[ExtractedValue] = []

    for item in values:
        # Prioritize deterministic code resolution to protect against LLM canonical hallucinations
        resolved = resolve_canonical_name(item.test_name)
        if resolved:
            canonical = resolved
        elif item.canonical_name and item.canonical_name.lower().strip() in SYNONYM_MAP:
            canonical = SYNONYM_MAP[item.canonical_name.lower().strip()]
        else:
            canonical = item.canonical_name
        item.canonical_name = canonical

        # Sanitize and convert units
        item = sanitize_and_convert_value(item)

        if item.value is not None:
            flag, eff_low, eff_high = compute_flag(
                value=item.value,
                canonical_name=canonical,
                report_low=item.ref_low,
                report_high=item.ref_high,
                ref_range_text=item.ref_range_text,
                gender=gender,
                test_name=item.test_name,
            )
            item.flag = flag
            item.ref_low = eff_low
            item.ref_high = eff_high
            item.verification_status = "verified"
        else:
            # Qualitative lab results evaluation (e.g. Hepatitis, Malaria, Urine Albumin)
            raw_str = (item.raw_value or "").lower().strip()
            if any(pos in raw_str for pos in ["positive", "reactive", "detected", "abnormal"]):
                item.flag = "high"
                item.verification_status = "verified"
            elif any(neg in raw_str for neg in ["negative", "non-reactive", "not detected", "nil", "normal", "trace"]):
                item.flag = "normal"
                item.verification_status = "verified"
            else:
                item.flag = "unverified"
                item.verification_status = "review_required"

        if canonical and canonical in TEST_TO_SPECIALTY:
            item.specialty_hint = TEST_TO_SPECIALTY[canonical]
        elif canonical and canonical in TEST_DEFINITIONS:
            item.specialty_hint = TEST_DEFINITIONS[canonical].get("specialty_hint", DEFAULT_SPECIALTY)
        else:
            item.specialty_hint = DEFAULT_SPECIALTY

        processed.append(item)

    primary_specialty = route_to_specialty(processed)
    return processed, primary_specialty


def route_to_specialty(values: List[ExtractedValue]) -> str:
    """
    Determines overall specialist recommendation from all processed lab values.
    Clinically sound routing:
    - Routine abnormalities (e.g. mild electrolyte shifts, isolated BUN with normal creatinine) default to General Physician.
    - Priority rules only escalate when clinical criteria are met (e.g. abnormal creatinine for nephrology, critical hemoglobin).
    """
    abnormal_items = [v for v in values if v.flag in ("low", "high", "critical")]
    if not abnormal_items:
        return DEFAULT_SPECIALTY

    abnormal_canonicals = {v.canonical_name: v for v in abnormal_items if v.canonical_name}

    # Evaluate priority rules
    for rule in PRIORITY_RULES:
        tests = rule.get("tests", [])
        condition = rule.get("condition")
        override = rule.get("override_specialty")

        if condition == "any_abnormal":
            if any(t in abnormal_canonicals for t in tests):
                return override

        elif condition == "two_or_more_abnormal":
            matched = sum(1 for t in tests if t in abnormal_canonicals)
            if matched >= 2:
                return override

        elif condition == "critical":
            for t in tests:
                if t in abnormal_canonicals and abnormal_canonicals[t].flag == "critical":
                    return override

    # Fallback to tally of abnormal test specialties
    specialty_counts: Dict[str, int] = {}
    for item in abnormal_items:
        spec = item.specialty_hint or DEFAULT_SPECIALTY
        specialty_counts[spec] = specialty_counts.get(spec, 0) + 1

    sorted_specialties = sorted(specialty_counts.items(), key=lambda x: x[1], reverse=True)
    return sorted_specialties[0][0] if sorted_specialties else DEFAULT_SPECIALTY
