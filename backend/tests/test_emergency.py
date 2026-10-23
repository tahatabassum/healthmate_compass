"""
Unit tests for the Emergency Engine (backend/app/services/emergency.py).
Tests rule-based detection across English, Urdu script, Roman Urdu, and Regex patterns.
Zero LLM calls required.
"""
import pytest
from app.services.emergency import check_emergency


def test_english_emergency_triggers():
    # Direct phrases
    res1 = check_emergency("Doctor please help, I am having severe chest pain")
    assert res1.is_emergency is True
    assert res1.matched_term == "chest pain"
    assert res1.language_detected == "en"
    assert res1.emergency_number == "1122"

    res2 = check_emergency("Patient cannot breathe and has shortness of breath")
    assert res2.is_emergency is True
    assert res2.language_detected == "en"

    res3 = check_emergency("My father passed out suddenly on the floor")
    assert res3.is_emergency is True
    assert res3.matched_term == "passed out"


def test_urdu_script_emergency_triggers():
    # Urdu text
    res1 = check_emergency("مریض کے سینے میں درد ہے بہت شدید")
    assert res1.is_emergency is True
    assert res1.matched_term == "سینے میں درد"
    assert res1.language_detected == "ur"

    res2 = check_emergency("سانس نہیں آرہا جلدی بتائیں کیا کریں")
    assert res2.is_emergency is True
    assert res2.matched_term == "سانس نہیں آرہا"
    assert res2.language_detected == "ur"

    res3 = check_emergency("بچے کو دورہ پڑ رہا ہے")
    assert res3.is_emergency is True
    assert res3.language_detected == "ur"


def test_roman_urdu_emergency_triggers():
    # Roman Urdu phrases
    res1 = check_emergency("mere abbu ke seene mein dard ho raha hai")
    assert res1.is_emergency is True
    assert res1.matched_term == "seene mein dard"
    assert res1.language_detected == "roman_ur"

    res2 = check_emergency("sans lene mein takleef ho rahi hai emergency")
    assert res2.is_emergency is True
    assert res2.matched_term == "sans lene mein takleef"
    assert res2.language_detected == "roman_ur"

    res3 = check_emergency("patient be hosh ho gaya achanak")
    assert res3.is_emergency is True
    assert res3.matched_term == "be hosh ho gaya"


def test_regex_patterns():
    # High fever patterns
    res1 = check_emergency("The child has 105 F temperature")
    assert res1.is_emergency is True
    assert res1.language_detected == "regex"

    res2 = check_emergency("patient has 103 degree fever")
    assert res2.is_emergency is True
    assert res2.language_detected == "regex"

    # Extreme BP spike
    res3 = check_emergency("my blood pressure is 210 right now")
    assert res3.is_emergency is True
    assert res3.language_detected == "regex"


def test_non_emergency_safe_messages():
    # Routine symptoms and questions should NOT trigger emergency
    non_emergencies = [
        "I have a mild headache since yesterday morning.",
        "Can you explain my CBC lab report?",
        "What does high fasting glucose mean?",
        "halka sa sar dard hai do din se",
        "مجھے ہلکا نزلہ اور زکام ہے",
        "Which doctor should I consult for skin rash?",
    ]
    for text in non_emergencies:
        res = check_emergency(text)
        assert res.is_emergency is False, f"False positive triggered for: '{text}' (matched: {res.matched_term})"
