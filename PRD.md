# PRD: HealthMate Compass (working title)

> AI health-report translator + AI doctor chat + nearby specialist finder, with permanent per-person memory.
> Built for **Himmatkaar x HacktoberFest'26 Faisalabad: Gemma 4 Build Challenge** (NIC Faisalabad, Fri Oct 23, 2:00-5:00 PM; community event Sat Oct 24).
> Owner: Taha (solo). Pre-planning and pre-building are allowed by the organizers. Friday is for polish, testing and demo.

---

## 1. One-line pitch

Upload a lab report or describe a symptom. Get a plain-language explanation in English or Urdu, the abnormal values flagged by code (not by AI), the right type of specialist, and real nearby doctors on a map. The app remembers each person's health details forever, so every future answer is personal.

## 2. Problem

- Medical reports are full of terms and numbers most people cannot read. People panic or ignore real warning signs.
- People do not know which type of doctor to see, or where to find one nearby.
- Existing AI chatbots forget everything between sessions and are not grounded in the user's own health history.

## 3. Goals and non-goals

### Goals
1. Turn a report image/PDF into structured values, flags, and a simple explanation (EN/UR).
2. Route abnormal values and symptoms to the correct specialty.
3. Show real nearby doctors/labs/pharmacies on a map, with a click to open directions.
4. Remember patient facts permanently (structured profile + extracted facts + vector memory).
5. Run on the **Gemini API free tier with Gemma 4**, with an automatic **OpenRouter fallback (same Gemma 4 model)**.
6. Be responsive, bug-free on mobile and desktop, and demo-ready in under 3 minutes.

### Non-goals (do NOT build)
- No diagnosis, no dosing advice, no prescriptions.
- No WhatsApp booking, no payments, no medicine delivery, no doctor-side portal.
- No microservices, no Redis, no separate vector DB (use pgvector inside Supabase).
- No switching frameworks mid-build.

## 4. Target users

- **Primary:** Pakistani/South Asian patients and families who receive lab reports and prescriptions and want to understand them.
- **Secondary:** caregivers managing a parent's or child's health (family profiles).
- **Demo judges:** developers; the demo must be clear in the first 30 seconds.

## 5. Hackathon context

| Item | Detail |
|---|---|
| Event | Himmatkaar x HacktoberFest'26 Faisalabad |
| Challenge | "Gemma 4 Build Challenge": lightweight open-weights multimodal model via the **Gemini API** |
| Tracks | Context-Aware Assistants (text + image); Targeted Solutions (productivity/learning/creative); Rapid Prototyping |
| Format | Individual only; Fri Oct 23, 2:00-5:00 PM mini-hackathon; Sat Oct 24, 10:00 AM-4:00 PM community event |
| Rule | Organizers confirmed projects may be pre-planned and pre-made |
| Primary model | Gemma 4 through the Gemini API (free tier) |
| Fallback | Gemma 4 through OpenRouter |

Judging likely rewards: Gemma 4 use (multimodal), working prototype, impact, clarity of demo. State openly in the demo that the project was built in advance and what was polished on the day.

## 6. Core features and priorities

**P0 (must ship, this is the demo)**
1. Real Supabase Authentication: Email + password signup/login, session persistence, route protection, automatic single-profile creation on first signup. Per-user data isolation (RLS).
2. One User = One Profile: Family profiles removed completely. Single personal health profile per account.
3. ChatGPT / Claude style Chat History: Left sidebar (desktop) and slide-in drawer (mobile 100dvh) with time grouping (Today, Yesterday, Previous 7 days, Older), search, new chat, rename, delete, auto-titling, deep link `/chat/:sessionId`, and Supabase Realtime channel.
4. Cross-chat conversation memory: Rolling chat summaries embedded at 768d (`memory_embeddings`), loaded via `match_memories(user_id, query, k=4)`.
5. Profile-aware chat & Auto Profile Updates: Injects structured profile; extracts first-person profile operations (`add | update | resolve | remove`) for conditions, medications, allergies; maintains `profile_change_log` and provides in-chat Undo button.
6. Report upload & accuracy upgrade: Pre-processing (auto-rotate, resize, compress), document classification, vision extraction, pass 2 verification, normalization, sanity checks (reject impossible values, conversions), human-in-the-loop editable confirmation table, patient name mismatch warning.
7. Code-computed abnormal flags against printed bounds and reference ranges; deterministic specialty routing.
8. Single language mode: English default; Urdu only upon explicit selection in Settings (RTL, natural script, numbers/units/test names preserved). Never mix English and Urdu.
9. Medical-only scope guardrails: Fast rule prefilter + LLM scope evaluation; polite refusal for off-topic queries; crisis/self-harm triggers supportive care + Rescue 1122 + verified helplines.
10. Image/Document classifier guardrail: `lab_report | prescription | other_medical_document | irrelevant | unreadable`. Irrelevant files rejected immediately without saving.
11. Real-time Doctor finder: OpenStreetMap live healthcare search + Google Places API New (server-side), interactive Google Maps embed iframe, turn-by-turn navigation links.
12. Rule-based emergency detection (zero LLM calls) with Rescue 1122 action.
13. Dual LLM provider layer: Gemini (Gemma 4) primary + OpenRouter Gemma 4 fallback.

**P1 (should ship)**
14. Golden test set for report extraction accuracy reporting.
15. Doctor summary PDF (print view) for appointments.
16. Automated i18n key consistency test script (`en.json` vs `ur.json`).

**P2 (only if time remains)**
17. Forgot password flow.
18. Trend charts across historical reports (same test over time).

## 7. User flows

### Flow A: Report to doctor (Human-in-the-Loop)
1. User signs in to their personal account.
2. Uploads report (image or multi-page PDF).
3. Document Classifier checks if file is medical; if irrelevant, purges immediately and shows helpful tips.
4. Vision extraction + second-pass verification + sanity checks (reject impossible values, handle unit conversions).
5. Code flags abnormal values against report-printed bounds or age/sex reference ranges.
6. **Editable Confirmation Table**: UI shows extracted values for user review/correction before generating explanation.
7. Gemma writes plain-language explanation and doctor questions strictly in user's active language.
8. Real nearby specialists displayed on interactive Google Map with direct navigation links.

### Flow B: Symptom chat (ChatGPT-style + Cross-Chat Memory)
1. User enters chat page; sees past chat history in sidebar/drawer. Can create New Chat or resume previous chat.
2. User types symptoms or health question.
3. Fast rule-based Emergency check; if critical, triggers Rescue 1122 immediately (zero LLM calls).
4. Guardrail check: if off-topic (coding, finance, etc.), returns polite refusal with health guidance redirection.
5. In-scope query loads: structured profile + active facts + last ~10 turns of current chat + top-k (4) relevant snippets from PAST chats via `match_memories`.
6. Triage response generated in active language; first-person health statements generate `profile_updates` with in-chat Undo chip.
7. Rolling summary of chat session generated every ~6 turns and embedded at 768d.

### Flow C: Memory & Profile Management
1. Open "My Health Memory".
2. View active conditions, resolved conditions with dates, active medications, allergies, and lab history.
3. View `profile_change_log` audit trail showing when facts were updated or resolved from chat, with manual edit/delete capabilities.

## 8. Safety rules (non-negotiable)

1. **No diagnosis.** Use "may relate to", "could be associated with". Always show a disclaimer.
2. **Flags come from code**, never from the model. The model explains flags it is given.
3. **Doctors come only from verified Places/OSM data.** Strict location confinement to requested city/coordinates.
4. **Emergency path is rule-based** (keyword/regex in EN + Urdu/Roman Urdu) and bypasses all LLM calls. Show Rescue 1122 and "go to nearest emergency room".
5. **No dosing, no medicine changes.**
6. **Low confidence handling:** if extraction confidence is LOW, ask for a clearer photo instead of guessing.
7. **Privacy & Data Isolation:** RLS on every table; JWT verified on every backend request; patient ID derived from authenticated user.
8. **Memory conflicts:** newer facts supersede older ones; never keep two active contradictory facts.
9. **Medical scope:** strictly health topics; courteous refusal for non-medical requests; empathetic de-escalation + Rescue 1122 for crisis/self-harm.
10. **Single language purity:** never render English and Urdu simultaneously.

## 9. Tech stack

### Backend
- Python 3.11, **FastAPI** + Uvicorn
- **LangGraph** for agent flow; **LangChain** only for text splitters/utilities
- **Pydantic + Instructor** for schema-validated JSON output
- **OpenAI SDK** as the single client for both providers (Gemini OpenAI-compatible endpoint and OpenRouter)
- **supabase-py** (service role on server only)
- PDF handling: `pypdf` for text PDFs, rasterize scanned PDFs to images with `pdf2image` or `pymupdf` (keep memory light; dev machine has 8GB RAM; no PyTorch/EasyOCR)

### LLM layer
| Role | Provider | Model |
|---|---|---|
| Primary | Gemini API (OpenAI-compatible endpoint `https://generativelanguage.googleapis.com/v1beta/openai/`) | Gemma 4 (exact model ID from AI Studio, set via `GEMINI_GEMMA_MODEL`) |
| Fallback 1 | OpenRouter (`https://openrouter.ai/api/v1`) | `google/gemma-4-26b-a4b-it` (paid slug preferred) |
| Fallback 2 (last resort) | OpenRouter | `google/gemma-4-26b-a4b-it:free` |
| Embeddings | Gemini Embedding API (one model only, fixed dimension, e.g. 768) | do not switch after data is stored |

Fallback triggers: HTTP 429, 5xx, timeout, or invalid JSON after one retry. Log provider, latency, status to `llm_logs`. Keep prompts and schemas identical across providers.

Free-tier limits are per project and not fully published; check the real Gemma 4 numbers at aistudio.google.com/rate-limit. Reduce calls: one structured call returns answer + new memory facts; embed only on save; cache; pre-analyze demo reports.

### Data
- **Supabase**: Auth, Postgres, Storage (private bucket `reports`), Row Level Security.
- **pgvector** extension for memory and guideline retrieval.

### Maps
- **Google Places API (New)** Text Search + Place Details (server-side, key restricted).
- **Google Maps JavaScript API** for the map (browser key restricted by HTTP referrer), with Leaflet + OpenStreetMap as fallback display.
- Directions link: `https://www.google.com/maps/dir/?api=1&destination=LAT,LNG&destination_place_id=PLACE_ID`

### Frontend
- React 18 + TypeScript + Vite, Tailwind CSS (design from Google Stitch, implemented by Antigravity), React Router, i18next (EN/UR, RTL), Recharts, Lucide icons, Axios.

### Deploy
- Frontend: Vercel. Backend: Render or Railway. Env vars in dashboards only.

## 10. System architecture

```
React (Vite) ──HTTPS──> FastAPI ──> LangGraph agent
     |                     |            |-- call_llm() ──> Gemini API (Gemma 4) ──fallback──> OpenRouter (Gemma 4)
     |                     |            |-- Memory service ──> Supabase (Postgres + pgvector)
     |                     |            |-- Doctor tool ──> Google Places API
     |                     |-- Reference-range engine (pure Python)
     |                     |-- Emergency rules (pure Python)
     └── Supabase Auth (JWT) + Storage (signed URLs)
```

## 11. Memory system ("remember forever")

Three layers plus a separate knowledge base. Do not rely on RAG alone for personal facts.

1. **Structured profile (always injected into every prompt):** name, age, gender, blood group, allergies, chronic conditions, active medicines. Small and exact.
2. **Extracted facts (`memory_facts`):** after each chat turn or report, extract facts as JSON, e.g. `{fact_type:"condition", key:"diabetes_type2", value:"diagnosed", ...}`. Merge rules: same `fact_type+key` supersedes the older one (set old row `status='superseded'`); "no longer takes X" deactivates the medicine fact.
3. **Vector memory (`memory_embeddings`):** embed report summaries and chat-session summaries; retrieve top-k (k=4) per question filtered by `patient_id`.
4. **Knowledge RAG (`guideline_chunks`):** WHO/CDC guideline chunks used to ground medical explanations. Kept separate from personal memory.

Rules: every fact has `source_type`, `source_id`, `created_at`, `confidence`. The user can edit/delete facts; deleted facts are excluded from prompts and embeddings are removed. Extraction runs as a background task so it never blocks the response.

## 12. LangGraph flow

State: `patient_id, user_text, lang, profile, facts, memories, guidelines, emergency, triage, doctors_query, response`.

```
load_profile -> emergency_check --(yes)--> emergency_response --> END
                    |
                   (no)
                    v
        retrieve_memory -> retrieve_guidelines -> triage_answer (call_llm, schema: TriageResult incl. new_facts)
                    -> maybe_find_doctors (tool: Places) -> save_memory (background) -> respond
```

Minimum LLM calls per chat turn: **1** (answer + new facts in one schema). Report analysis: extract (1) + verify (1) + explain (1).

## 13. Reference ranges and specialty routing (code, not LLM)

`backend/app/data/reference_ranges.json` holds default adult ranges per test with sex-specific values where relevant, units, and synonyms (e.g. "Hb", "Haemoglobin" -> `hemoglobin`). **Verify all ranges against a trusted source before the demo; the lab's own printed range on the report takes priority when extracted.**

Example seed (defaults, to be verified):

| Test | Unit | Range |
|---|---|---|
| Hemoglobin | g/dL | M 13.5-17.5, F 12.0-15.5 |
| WBC | /uL | 4,000-11,000 |
| Platelets | /uL | 150,000-450,000 |
| Fasting glucose | mg/dL | 70-99 |
| HbA1c | % | below 5.7 |
| Total cholesterol | mg/dL | below 200 |
| LDL | mg/dL | below 100 |
| Triglycerides | mg/dL | below 150 |
| Creatinine | mg/dL | M 0.7-1.3, F 0.6-1.1 |
| TSH | mIU/L | 0.4-4.0 |
| ALT | U/L | 7-56 |
| Vitamin D | ng/mL | 30-100 |

Flag logic: `low | normal | high`, plus `critical` for values beyond configurable multiples (e.g. far outside range), which shows an urgent-care notice.

Specialty routing table (`specialty_map.json`): creatinine/urea -> Nephrologist; TSH/T3/T4 -> Endocrinologist; glucose/HbA1c -> Endocrinologist (Diabetes); cholesterol/LDL/triglycerides -> Cardiologist; ALT/AST/bilirubin -> Gastroenterologist/Hepatologist; low hemoglobin/platelets/abnormal WBC -> Hematologist or General Physician; vitamin D/B12 -> General Physician; uric acid -> Rheumatologist or General Physician. For symptoms, the model returns `specialty` from a **fixed enum**; invalid values fall back to General Physician.

## 14. Doctor finder (map feature)

- Input: `specialty` (enum), `lat/lng` (browser geolocation) or typed city (geocode), radius (default 5 km, expand to 15 km if empty).
- Server calls Places Text Search with query like `"{specialty} near me"` using `locationBias`, requests fields: id, displayName, formattedAddress, location, rating, userRatingCount, nationalPhoneNumber, regularOpeningHours, googleMapsUri.
- Response shape to frontend: list of `{place_id, name, address, lat, lng, rating, rating_count, phone, open_now, maps_url, distance_m}`.
- UI: list + map; sort by distance/rating; "open now" filter; marker click opens detail panel with **Open in Google Maps**.
- Fallback: no results -> widen radius -> General Physician (tell the user). Cache results per `(specialty, rounded lat/lng)` for 24h to save quota.
- Never display model-generated doctor data. Show "Data from Google Maps" attribution.

## 15. Database schema (Supabase / Postgres)

```sql
create extension if not exists vector;

create table patients (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  full_name text not null,
  relation text default 'self',
  dob date, gender text, blood_group text,
  allergies text[] default '{}',
  chronic_conditions text[] default '{}',
  preferred_language text default 'en',
  created_at timestamptz default now()
);

create table medications (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid references patients(id) on delete cascade,
  name text not null, dosage text, frequency text, purpose text,
  is_active boolean default true,
  confidence text, verification_notes text,
  source_report_id uuid, created_at timestamptz default now()
);

create table reports (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid references patients(id) on delete cascade,
  file_path text not null, file_type text,
  report_date date, status text default 'uploaded',
  summary_en text, summary_ur text,
  questions_for_doctor jsonb,
  overall_risk text, confidence text, verification_notes text,
  created_at timestamptz default now()
);

create table report_values (
  id uuid primary key default gen_random_uuid(),
  report_id uuid references reports(id) on delete cascade,
  test_name text not null, canonical_name text,
  value numeric, unit text, ref_low numeric, ref_high numeric,
  flag text check (flag in ('low','normal','high','critical')),
  specialty_hint text
);

create table chat_sessions (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid references patients(id) on delete cascade,
  title text, risk_level text, created_at timestamptz default now()
);

create table chat_messages (
  id bigserial primary key,
  session_id uuid references chat_sessions(id) on delete cascade,
  role text check (role in ('user','assistant')),
  content text not null, meta jsonb, created_at timestamptz default now()
);

create table memory_facts (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid references patients(id) on delete cascade,
  fact_type text not null,      -- condition | allergy | medication | event | lifestyle
  key text not null, value text not null,
  status text default 'active', -- active | superseded | deleted
  source_type text, source_id text, confidence numeric,
  created_at timestamptz default now(), superseded_by uuid
);

create table memory_embeddings (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid references patients(id) on delete cascade,
  content text not null, source_type text, source_id text,
  embedding vector(768), created_at timestamptz default now()
);

create table guideline_chunks (
  id uuid primary key default gen_random_uuid(),
  source text, title text, content text, embedding vector(768)
);

create table llm_logs (
  id bigserial primary key, provider text, model text,
  latency_ms int, status text, created_at timestamptz default now()
);

create or replace function match_memories(p_patient uuid, q vector(768), k int default 4)
returns table (id uuid, content text, similarity float)
language sql stable as $$
  select id, content, 1 - (embedding <=> q) as similarity
  from memory_embeddings where patient_id = p_patient
  order by embedding <=> q limit k;
$$;
```

**RLS:** enable on every patient-linked table; policy pattern: a row is accessible if its `patient_id` belongs to a patient whose `owner_id = auth.uid()`. Storage bucket `reports` is private; use signed URLs. The embedding dimension must equal the chosen embedding model's output dimension; set it once and never mix models.

## 16. API endpoints (FastAPI, all require Supabase JWT except /health)

- `GET /health`
- `GET/POST/PUT/DELETE /api/patients` (family profiles)
- `POST /api/reports/upload` -> returns `report_id`
- `POST /api/reports/{id}/analyze` -> extract, verify, flag, explain (EN+UR), specialty
- `GET /api/reports?patient_id=` and `GET /api/reports/{id}`
- `POST /api/medicines/upload-prescription` and `POST /api/medicines/{id}/analyze`
- `POST /api/chat/session`, `POST /api/chat/message` (LangGraph), `GET /api/chat/sessions`
- `GET /api/doctors?specialty=&lat=&lng=&radius=&city=`
- `GET /api/memory?patient_id=`, `PATCH /api/memory/{fact_id}`, `DELETE /api/memory/{fact_id}`
- `GET /api/trends?patient_id=&test=` (P2)
- `DELETE /api/account/data` (delete all my data)
- `GET /api/export/summary/{patient_id}` (doctor summary, print-friendly)

## 17. Pydantic schemas (core)

- `ExtractedValue{test_name, value, unit, ref_low?, ref_high?}`; `ReportExtraction{report_date?, values[], confidence: HIGH|MEDIUM|LOW, notes}`
- `ReportExplanation{summary_en, summary_ur, questions_for_doctor_en[], questions_for_doctor_ur[], lifestyle_notes[]}`: input is **already-flagged values only**.
- `TriageResult{risk: LOW|MEDIUM|HIGH, answer_en, answer_ur, possible_causes[], self_care[], specialty: enum, new_facts: MemoryFact[]}`
- `MemoryFact{fact_type: enum, key, value, confidence}`
- Specialty enum is fixed (General Physician, Cardiologist, Endocrinologist, Nephrologist, Gastroenterologist, Hematologist, Dermatologist, Neurologist, Pulmonologist, Orthopedic, ENT, Ophthalmologist, Gynecologist, Pediatrician, Psychiatrist, Urologist, Rheumatologist, Dentist).

## 18. AI prompting rules

- System prompt states: not a doctor, no diagnosis, no dosing, output JSON only matching schema, simple language (reading level ~grade 8), Urdu in natural Urdu script (not transliteration) when `*_ur` fields are requested.
- Image extraction prompt: "Read only what is visible. Do not infer missing values. If unreadable, omit and lower confidence."
- Verification pass receives image + first extraction and lists discrepancies; mismatch lowers confidence.
- Explanation prompt receives only flagged data plus profile facts; it must not add new numbers.
- Memory extraction prompt: only facts the user or the report explicitly states; no inference.

## 19. Frontend scope (see `STITCH_PROMPT.md` for design)

Pages: Landing/Login, Dashboard, Upload & Analyze, Report Result, AI Doctor Chat, Find Doctors (map), My Health Memory, History & Trends, Family Profiles, Settings (language, delete data). Mobile: bottom navigation; desktop: left sidebar. Full EN/UR with RTL. Emergency banner pattern reused everywhere.

## 20. Repository structure

```
healthmate-compass/
  brain.md                  # agent memory file (read first, update after each task)
  PRD.md
  README.md
  .gitignore  .env.example
  backend/
    app/main.py
    app/core/{config.py, supabase.py, security.py}
    app/llm/{client.py (call_llm + fallback), schemas.py, prompts.py}
    app/graph/{state.py, nodes.py, build.py}
    app/services/{reports.py, medicines.py, memory.py, doctors.py, flags.py, emergency.py, embeddings.py, export.py}
    app/data/{reference_ranges.json, specialty_map.json, emergency_terms.json, guidelines/}
    app/routers/{patients.py, reports.py, medicines.py, chat.py, doctors.py, memory.py, account.py}
    tests/
    requirements.txt
  frontend/
    src/{pages, components, hooks, lib(api, supabase, i18n), locales/{en.json, ur.json}}
  supabase/{schema.sql, policies.sql, seed_guidelines.sql}
```

## 21. Environment variables (`.env.example`)

```
GEMINI_API_KEY=
GEMINI_GEMMA_MODEL=            # exact Gemma 4 ID from AI Studio
GEMINI_EMBED_MODEL=
OPENROUTER_API_KEY=
OPENROUTER_MODEL=google/gemma-4-26b-a4b-it
OPENROUTER_MODEL_FREE=google/gemma-4-26b-a4b-it:free
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=     # backend only, never in frontend
GOOGLE_PLACES_API_KEY=         # server-side, restricted
VITE_GOOGLE_MAPS_BROWSER_KEY=  # frontend, referrer-restricted
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
VITE_API_BASE_URL=
```

## 22. Build plan (today is Tue Oct 20; event is Fri Oct 23)

### Phase 0: Prep (Tue Oct 20)
1. Create repo, push existing fixes from the laptop first. Add `.gitignore` (`.env`, `uploads/`, `*.db`, `node_modules`, `dist`).
2. Create Supabase project; run `schema.sql`; enable RLS; create private bucket `reports`.
3. Get Gemini API key; check Gemma 4 limits at aistudio.google.com/rate-limit; confirm the exact model ID.
4. Get OpenRouter key (add a few dollars so the fallback is dependable).
5. Enable Google Places API (New) and Maps JavaScript API; add billing; restrict keys.
6. Test the same image + schema against **both** providers.
7. Put `brain.md` in the repo root.

### Phase 1: Backend foundation (Tue)
- FastAPI skeleton, config, Supabase JWT verification, `call_llm()` with fallback and `llm_logs`.
- Flags engine and emergency engine with unit tests.

### Phase 2: Report pipeline (Wed AM)
- Upload to Storage; extract (vision) -> verify -> flag -> explain EN/UR -> store. Test with 5 sample reports (fake data).

### Phase 3: Doctor finder (Wed PM)
- Places service, cache, endpoint, specialty mapping; test with 5 specialties around Faisalabad.

### Phase 4: Memory (Wed night)
- Facts extraction + merge rules, embeddings on save, `match_memories`, memory endpoints. Prove: tell the app a fact in session 1, ask in session 2.

### Phase 5: Chat graph (Thu AM)
- LangGraph flow with single-call triage; emergency gate; doctor tool; background memory save.

### Phase 6: Frontend (Thu, using the Stitch design)
- Implement pages, bottom nav/sidebar, EN/UR RTL, map page, memory page. Test at 360, 390, 768, 1024, 1440 widths.

### Phase 7: Hardening (Thu night)
- Rate-limit handling with friendly retry message, error states, empty states, loading skeletons, deploy backend + frontend, run the full checklist below.

### Phase 8: Friday (event, polish only)
- Fix bugs, rehearse demo 3 times, record backup video, make sure the README and repo are public-ready.

## 23. Demo script (3 minutes)

1. (20s) Problem: "People get a lab report and don't understand it."
2. (60s) Upload a sample report -> values flagged -> Urdu/English explanation -> questions for doctor.
3. (40s) "See a nephrologist" -> real nearby doctors on the map -> tap marker -> open directions.
4. (30s) New session: ask a question; the app uses an earlier fact ("remembers forever"); show the Memory page.
5. (15s) Emergency input -> instant emergency card (no LLM).
6. (15s) Architecture: Gemma 4 via Gemini API, automatic OpenRouter fallback, code-based flags, Places-only doctors.

## 24. Testing checklist

- [ ] Both LLM providers return valid JSON for text and image requests
- [ ] Forced 429 on primary triggers fallback successfully
- [ ] Flags match reference ranges for all seed tests (unit tests)
- [ ] Emergency phrases (EN, Urdu, Roman Urdu) trigger the emergency card without LLM calls
- [ ] Doctor search returns results for each specialty near Faisalabad; empty result widens radius
- [ ] Cross-session memory works; superseding and deleting facts works
- [ ] RLS: user A cannot read user B's data
- [ ] No horizontal scroll at 360px; tables become cards on mobile; map usable on mobile
- [ ] Urdu RTL layout correct on every page
- [ ] No keys in git history; `.env.example` present
- [ ] Demo works on venue Wi-Fi and on mobile data

## 25. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Free-tier rate limits (429) | Fallback provider, fewer calls per turn, caching, pre-analyzed demo reports |
| Model returns bad JSON | Instructor retries, schema validation, fallback provider |
| Misread report values | Dual-pass verification, confidence rating, retake-photo prompt |
| Model invents doctors | Doctors only from Places data |
| Places quota/billing | Cache results, restrict keys, Leaflet fallback for display |
| Privacy of health data on free tier | Fake demo data, disclose in README |
| Scope creep | P0 first; P2 only after full checklist passes |
| Looks like "just another wrapper" | Code-based flags, 3-layer memory, fallback architecture, report-to-specialist-to-map flow |

## 26. Success criteria

- Complete flow (upload -> explanation -> specialist -> map) works live in under 60 seconds.
- Memory demo works across two sessions.
- No visual or functional bugs on desktop and mobile.
- Repo is clean, documented, and public.
