"""
Emergency Engine for HealthMate Compass.
Purely rule-based emergency detection in English, Urdu, and Roman Urdu.
Makes ZERO LLM calls. Runs before any LLM triage to instantly safeguard patients.
"""
import os
import json
import re
from typing import Optional, List
from pydantic import BaseModel

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def load_emergency_data() -> dict:
    filepath = os.path.join(DATA_DIR, "emergency_terms.json")
    with open(filepath, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_verified_helplines() -> List[dict]:
    filepath = os.path.join(DATA_DIR, "helplines.json")
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            pass
    return []


EMERGENCY_DATA = load_emergency_data()
VERIFIED_HELPLINES = load_verified_helplines()
EN_TERMS: List[str] = [t.lower().strip() for t in EMERGENCY_DATA.get("terms", {}).get("en", [])]
UR_TERMS: List[str] = [t.strip() for t in EMERGENCY_DATA.get("terms", {}).get("ur", [])]
ROMAN_UR_TERMS: List[str] = [t.lower().strip() for t in EMERGENCY_DATA.get("terms", {}).get("roman_ur", [])]
REGEX_PATTERNS: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in EMERGENCY_DATA.get("regex_patterns", [])
]
ACTION_INFO = EMERGENCY_DATA.get("action", {
    "emergency_number": "1122",
    "emergency_service": "Rescue 1122",
    "instruction_en": "This sounds like a medical emergency. Please call Rescue 1122 immediately or go to the nearest emergency room.",
    "instruction_ur": "یہ طبی ہنگامی صورتحال لگتی ہے۔ فوری طور پر ریسکیو 1122 پر کال کریں یا قریبی ہنگامی کمرے میں جائیں۔",
})


class EmergencyCheckResult(BaseModel):
    is_emergency: bool = False
    matched_term: Optional[str] = None
    language_detected: Optional[str] = None
    emergency_number: str = "1122"
    emergency_service: str = "Rescue 1122"
    instruction_en: str = ACTION_INFO.get("instruction_en", "")
    instruction_ur: str = ACTION_INFO.get("instruction_ur", "")
    helplines: List[dict] = []


def normalize_text(text: str) -> str:
    """Normalizes whitespace and converts to lower case."""
    return re.sub(r"\s+", " ", text).lower().strip()


def check_emergency(text: str) -> EmergencyCheckResult:
    """
    Checks user message for emergency keywords and patterns in English, Urdu, and Roman Urdu.
    Returns EmergencyCheckResult.
    """
    if not text:
        return EmergencyCheckResult(is_emergency=False)

    lower_text = normalize_text(text)
    raw_text = text.strip()

    # Crisis / mental health distress terms
    crisis_terms = {"suicide", "suicidal", "kill myself", "end my life", "want to die", "خودکشی", "خود کو نقصان", "مرنا چاہتا ہوں", "مرنا چاہتی ہوں", "khudkushi", "marna chahta hun", "marna chahti hun"}
    is_crisis = any(c in lower_text or c in raw_text for c in crisis_terms)

    instr_en = ACTION_INFO.get("instruction_en", "")
    instr_ur = ACTION_INFO.get("instruction_ur", "")
    if is_crisis:
        instr_en = "If you or someone you know is in crisis or having thoughts of self-harm, please reach out immediately. Call Rozan Counseling Helpline at 0800-22444 (toll-free) or Sehat Tahaffuz Helpline at 1166 (24/7). For immediate emergency medical assistance, call Rescue 1122."
        instr_ur = "اگر آپ یا آپ کا کوئی جاننے والا شدید ذہنی دباؤ یا خود کو نقصان پہنچانے کے خیالات میں مبتلا ہے تو فوری رابطہ کریں۔ روزن ٹیلی کاؤنسلنگ ہیلپ لائن 22444-0800 (ٹول فری) یا صحت تحفظ ہیلپ لائن 1166 پر کال کریں۔ ہنگامی طبی امداد کے لیے فوری ریسکیو 1122 ملائیں۔"

    # 1. Check Urdu script phrases
    for term in UR_TERMS:
        if term and term in raw_text:
            return EmergencyCheckResult(
                is_emergency=True,
                matched_term=term,
                language_detected="ur",
                instruction_en=instr_en,
                instruction_ur=instr_ur,
                helplines=VERIFIED_HELPLINES,
            )

    # 2. Check English emergency terms
    for term in EN_TERMS:
        if not term:
            continue
        # Check boundary or direct phrase
        pattern = r"\b" + re.escape(term) + r"\b"
        if re.search(pattern, lower_text):
            return EmergencyCheckResult(
                is_emergency=True,
                matched_term=term,
                language_detected="en",
                instruction_en=instr_en,
                instruction_ur=instr_ur,
                helplines=VERIFIED_HELPLINES,
            )

    # 3. Check Roman Urdu emergency terms
    for term in ROMAN_UR_TERMS:
        if not term:
            continue
        pattern = r"\b" + re.escape(term) + r"\b"
        if re.search(pattern, lower_text):
            return EmergencyCheckResult(
                is_emergency=True,
                matched_term=term,
                language_detected="roman_ur",
                instruction_en=instr_en,
                instruction_ur=instr_ur,
                helplines=VERIFIED_HELPLINES,
            )

    # 4. Check regex patterns (high fever, severe blood pressure spikes)
    for pattern in REGEX_PATTERNS:
        match = pattern.search(lower_text)
        if match:
            return EmergencyCheckResult(
                is_emergency=True,
                matched_term=match.group(0),
                language_detected="regex",
                instruction_en=instr_en,
                instruction_ur=instr_ur,
                helplines=VERIFIED_HELPLINES,
            )

    return EmergencyCheckResult(is_emergency=False, helplines=VERIFIED_HELPLINES)
