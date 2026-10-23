---
name: safe-lab-report-explainer
description: Translates medical laboratory test reports into patient-friendly explanations with code-computed flags, specialist routing, and doctor questions. Use when a user uploads or describes diagnostic lab values, blood tests, metabolic panels, or pathology reports.
version: 1.0.0
license: MIT
compatibility: "Python 3.10+, any LLM or Agent runtime"
metadata:
  author: HealthMate Compass Team
  framework: Agent Skills open standard (agentskills.io v1.0)
---

# Safe Lab Report Explainer

A clinical safety workflow for parsing, validating, flagging, and explaining diagnostic laboratory reports to patients in plain language.

## 1. When to Use

Activate this skill whenever:
- A user uploads or provides text/images of a laboratory test report (e.g., Complete Blood Count, Metabolic Panel, Lipid Profile, Liver Function Tests, Thyroid Panel, Renal Function Tests).
- A user asks what specific lab test numbers, units, or reference intervals mean.
- A user asks which specialist to consult regarding abnormal blood work.

Do NOT activate this skill for:
- Doctor prescriptions without lab values (route to prescription medication extraction).
- Non-medical images or everyday queries.
- Acute life-threatening emergency symptoms (chest pain, stroke signs, difficulty breathing) — route immediately to emergency care.

---

## 2. Step-by-Step Workflow

Follow these steps sequentially. Never skip steps or re-order deterministic computation.

```
[1. Classify Document]
         ↓
[2. Extract Values As Printed]
         ↓
[3. Normalize Names & Units]
         ↓
[4. Validate Bounds & Run scripts/flag_values.py]
         ↓
[5. Route to Specialist (references/specialty-map.json)]
         ↓
[6. Generate Cautious Explanation & Doctor Questions]
```

### Step 1: Classify the Document
Examine the image or text input and categorize into one of:
- `lab_report`: A valid laboratory, biochemistry, pathology, or diagnostic report. Proceed to Step 2.
- `prescription`: A doctor's medication slip. Do not calculate flags; extract medications and allergy warnings.
- `other_medical_document`: Discharge summaries, clinical notes, vaccine cards.
- `irrelevant`: Non-medical images (selfies, receipts, landscapes). Politely refuse and request a valid lab report.
- `unreadable`: Blurry, severely cropped, dark, or illegible scan. Request a clearer, well-lit image.

### Step 2: Extract Values Exactly as Printed
For every test parameter, record:
- **Test name** exactly as printed (including abbreviations like `GOT (AST)`, `Hb`, `S.G.P.T.`, `T.L.C.`).
- **Numeric value** (distinguish missing values from zero; preserve attached flags like `134L` as value `134.0`, lab flag `L`).
- **Unit** (e.g., `mg/dL`, `mmol/L`, `g/dL`, `g/L`, `/uL`).
- **Printed reference range** as printed (e.g., `136–146`, `< 200`, `> 40`, `32–72`).
- Never invent missing values or missing reference intervals.

### Step 3: Normalize Names & Units
1. Map raw test names to canonical names using `references/reference-ranges.json` synonyms.
2. Standardize units:
   - Glucose: `mmol/L` × 18.0182 → `mg/dL`
   - Hemoglobin: `g/L` ÷ 10.0 → `g/dL`
   - Cholesterol / Triglycerides: `mmol/L` × 38.67 → `mg/dL`
   - Creatinine: `µmol/L` ÷ 88.4 → `mg/dL`

### Step 4: Validate Bounds & Run `scripts/flag_values.py`
1. Prioritize the laboratory's printed reference range over default tables.
2. If printed range is reversed (`low > high`, e.g., HDL misread as `40–32`), automatically swap boundaries (`32–40`) or fall back to standard reference intervals (`32–72 mg/dL`).
3. Run the deterministic script to obtain flags:
   ```bash
   python scripts/flag_values.py input_extracted.json --gender female
   ```
4. Flags returned: `low`, `normal`, `high`, `critical`, or `unverified`.
5. **The agent must NEVER invent, alter, or judge high/low flags independently.**

### Step 5: Route Specialist
Use `references/specialty-map.json`:
- Check priority rules:
  - Abnormal creatinine → **Nephrologist**.
  - Isolated elevated BUN or B/C ratio with normal creatinine → **General Physician** (do NOT route to Nephrologist).
  - Two or more abnormal lipid markers (`total_cholesterol`, `ldl`, `triglycerides`) → **Cardiologist**.
  - Critically low hemoglobin (≤ 7.0 g/dL) → **Hematologist**.
  - TSH / Glucose / HbA1c → **Endocrinologist**.
  - All normal parameters → **General Physician**.

### Step 6: Generate Patient Explanation
- Formulate a calm, sympathetic summary explaining only what was tested and what the flagged values indicate.
- Focus primarily on abnormal findings while reassuring normal markers.
- Provide 3–4 practical, actionable questions for the patient's doctor visit.

---

## 3. Hard Safety Rules

1. **No Diagnosis:** Never state "You have [Condition]". Always state "This value may relate to...", "Often observed in...", or "Factors may include...".
2. **No Dosing Advice:** Never prescribe medications, suggest dosages, or advise altering existing prescription regimens.
3. **Never Invent Data:** If a number, date, or range is blurry, state that it is unverified rather than guessing.
4. **Emergency Interception:** If accompanying symptoms indicate acute distress (chest pressure, stroke symptoms, acute respiratory distress), advise calling emergency services (**Rescue 1122**) immediately before discussing report findings.
5. **Mandatory Disclaimer:** Always include the complete medical disclaimer.

---

## 4. Output Template

Present results using this exact structure:

```markdown
### 📋 Laboratory Report Overview
- **Document Status:** Verified Laboratory Report
- **Overall Assessment:** [ROUTINE_NORMAL | CLINICAL_REVIEW_RECOMMENDED | POTENTIALLY_URGENT]
- **Recommended Specialist:** [Specialist Name from specialty-map.json]

### 🧪 Summary of Findings
| Test Name | Result | Reference Interval | Flag | Clinical Context |
|---|---|---|---|---|
| [Test] | [Val] [Unit] | [Printed or Default Range] | [NORMAL/HIGH/LOW] | [Brief note] |

### 🔍 Plain-Language Explanation
[2 to 3 paragraphs explaining findings. Explain what normal results mean, then discuss flagged results using 'may relate to' wording. Mention fasting status or hydration context if relevant.]

### 🩺 Questions to Ask Your Doctor
1. "[Specific question about repeated testing or lifestyle adjustments]?"
2. "[Specific question about symptoms or family history correlation]?"
3. "[Specific question about next diagnostic steps]?"

> **Disclaimer:** HealthMate Compass provides educational information and is not a substitute for professional medical advice, diagnosis, or treatment. Always consult a qualified healthcare provider with any questions you may have regarding a medical condition.
```

---

## 5. Edge Cases & Handling

- **Unreadable or Blurry Image:**
  Return: *"The uploaded document image is too blurry or low-resolution to reliably read the numbers. Please take a clear, well-lit photo of the report laid flat and re-upload."*
- **Non-Medical Document:**
  Return: *"The uploaded image does not appear to be a medical lab report. Please upload a clear photo or PDF of your laboratory test results."*
- **Prescription Uploaded Instead of Lab Report:**
  Do not compute laboratory flags or claim the patient is healthy. Extract medication names, dosage, instructions, and verify against patient allergies.
- **Pregnancy & Pediatric Ranges:**
  Standard population reference intervals differ significantly during pregnancy and in pediatric patients. Explicitly state: *"Standard laboratory reference intervals may not apply to pediatric patients or during pregnancy; consult your pediatrician or obstetrician for specialized range interpretation."*

---

## 6. Bundled References & Scripts

- [references/reference-ranges.json](references/reference-ranges.json): Standard adult physiological reference intervals and critical limits for 40+ tests.
- [references/specialty-map.json](references/specialty-map.json): Deterministic routing rules mapping canonical tests to the 18 approved medical specialties.
- [references/safety-rules.md](references/safety-rules.md): Non-negotiable clinical safety boundaries and phrasing constraints.
- [references/example-output.md](references/example-output.md): Complete worked reference example with synthetic demo data.
- [scripts/flag_values.py](scripts/flag_values.py): Standalone CLI tool to validate ranges and calculate flags deterministically.
