# Non-Negotiable Clinical Safety Rules

This document outlines the strict clinical safety constraints enforced by HealthMate Compass for laboratory report extraction, flagging, and patient communication.

## 1. No Diagnosis
- AI models must never state a diagnostic conclusion (e.g., never say "You have diabetes", "You have chronic kidney disease", or "You are anemic").
- All explanatory language must use cautious, non-diagnostic phrasing such as "May relate to...", "Often associated with...", or "Possible factors include...".
- Normal creatinine alone does not rule out kidney disease, and elevated glucose on an isolated random test does not establish diabetes.

## 2. Deterministic Flag Calculation
- Abnormal flags (`LOW`, `NORMAL`, `HIGH`, `CRITICAL_LOW`, `CRITICAL_HIGH`, `UNVERIFIED`) must be computed strictly in Python code.
- The LLM must **never** decide, guess, or re-classify high/low/normal status. The LLM receives pre-computed flags and only explains them.

## 3. Printed Reference Interval Priority
- When a laboratory report prints explicit reference intervals, those printed bounds must take precedence over population defaults.
- Population reference ranges (from `reference-ranges.json`) are used solely as fallback when printed bounds are absent.
- Never invent missing reference ranges. If no range is available and cannot be matched, mark the result as `UNVERIFIED`.

## 4. Range Boundary Validation & Sanitization
- Validate that lower bound is less than or equal to upper bound (`low <= high`).
- Inverted/reversed bounds produced by OCR alignment errors (e.g., HDL printed as `32–72` but misread as `40–32`) must be caught and sanitized, preventing false `HIGH` flags.
- Support one-sided inequality intervals (e.g., `< 200`, `< 130`, `< 40`, `> 40`).
- Do not reverse lower and upper bounds; distinguish missing values from zero (`0.0`).

## 5. Specialty Referral Boundaries
- Recommended medical specialties must strictly belong to the fixed 18-specialty enum defined in `specialty-map.json`.
- Do not recommend a Nephrologist solely because BUN or B/C ratio is elevated if Creatinine is within normal range (0.4–1.5 mg/dL). Such cases must route to **General Physician**.
- Multi-marker cardiac risks (elevated cholesterol + triglycerides) prioritize **Cardiologist**.
- Critically low hemoglobin (<= 7.0 g/dL) prioritizes **Hematologist**.

## 6. No Dosing or Medication Advice
- Never recommend specific drug dosages, adjustments, or discontinuation based on laboratory test results.
- Never prescribe medication. Direct all treatment decisions to treating clinicians.

## 7. Document Classification Guardrails
- Scans must be classified into one of: `lab_report`, `prescription`, `other_medical_document`, `irrelevant`, or `unreadable`.
- Irrelevant images (receipts, selfies, memes) must be immediately rejected with advice to upload a medical document.
- Prescriptions must be processed for medication names and allergy cross-checks, never analyzed with laboratory reference ranges.

## 8. Emergency Symptoms Escalate to Rescue 1122
- If symptoms accompanying a report indicate acute life-threatening distress (severe chest pain, breathing difficulty, acute stroke signs), emergency guidance overrides report analysis with Rescue 1122 notification.

## 9. Mandatory Clinical Disclaimer
Every patient report summary must end with the prominent clinical disclaimer:
> *"Disclaimer: HealthMate Compass provides educational information and is not a substitute for professional medical advice, diagnosis, or treatment. Always consult a qualified healthcare provider with any questions you may have regarding a medical condition."*
