-- =============================================================================
-- HealthMate Compass — Complete Database Setup
-- Run this once in the Supabase SQL Editor (Dashboard -> SQL Editor -> New Query)
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- HealthMate Compass — Supabase Database Schema
-- Run this in the Supabase SQL Editor (Dashboard → SQL Editor → New query).
-- Run ONCE on a fresh project. For subsequent changes, use a migration file
-- and log it in brain.md Decisions Log.
-- ─────────────────────────────────────────────────────────────────────────────

-- Enable pgvector extension (required for embedding columns)
create extension if not exists vector;

-- ─── patients ─────────────────────────────────────────────────────────────────
-- One row per managed person. owner_id = the authenticated Supabase user.
-- A user can have multiple patients (self + family members).
create table if not exists patients (
  id              uuid primary key default gen_random_uuid(),
  owner_id        uuid not null references auth.users(id) on delete cascade,
  full_name       text not null,
  relation        text default 'self',          -- self | spouse | parent | child | other
  dob             date,
  gender          text,                          -- male | female | other
  blood_group     text,
  allergies       text[] default '{}',
  chronic_conditions text[] default '{}',
  preferred_language text default 'en',          -- en | ur
  created_at      timestamptz default now()
);

-- ─── medications ──────────────────────────────────────────────────────────────
create table if not exists medications (
  id              uuid primary key default gen_random_uuid(),
  patient_id      uuid not null references patients(id) on delete cascade,
  name            text not null,
  dosage          text,
  frequency       text,
  purpose         text,
  is_active       boolean default true,
  confidence      text,                          -- HIGH | MEDIUM | LOW
  verification_notes text,
  source_report_id uuid,
  created_at      timestamptz default now()
);

-- ─── reports ──────────────────────────────────────────────────────────────────
create table if not exists reports (
  id              uuid primary key default gen_random_uuid(),
  patient_id      uuid not null references patients(id) on delete cascade,
  file_path       text not null,                 -- Supabase Storage path in bucket 'reports'
  file_type       text,                          -- image | pdf
  report_date     date,
  status          text default 'uploaded',       -- uploaded | processing | ready | failed
  summary_en      text,
  summary_ur      text,
  questions_for_doctor jsonb,
  overall_risk    text,                          -- LOW | MEDIUM | HIGH
  confidence      text,                          -- HIGH | MEDIUM | LOW
  verification_notes text,
  created_at      timestamptz default now()
);

-- ─── report_values ────────────────────────────────────────────────────────────
-- One row per extracted test result. Flags are computed in Python, never by LLM.
create table if not exists report_values (
  id              uuid primary key default gen_random_uuid(),
  report_id       uuid not null references reports(id) on delete cascade,
  test_name       text not null,
  canonical_name  text,                          -- normalised key (e.g. 'hemoglobin')
  value           numeric,
  unit            text,
  ref_low         numeric,
  ref_high        numeric,
  flag            text check (flag in ('low', 'normal', 'high', 'critical')),
  specialty_hint  text                           -- specialty enum value, code-assigned
);

-- ─── chat_sessions ────────────────────────────────────────────────────────────
create table if not exists chat_sessions (
  id              uuid primary key default gen_random_uuid(),
  patient_id      uuid not null references patients(id) on delete cascade,
  title           text,
  risk_level      text,                          -- LOW | MEDIUM | HIGH
  created_at      timestamptz default now()
);

-- ─── chat_messages ────────────────────────────────────────────────────────────
create table if not exists chat_messages (
  id              bigserial primary key,
  session_id      uuid not null references chat_sessions(id) on delete cascade,
  role            text not null check (role in ('user', 'assistant')),
  content         text not null,
  meta            jsonb,                         -- emergency flag, specialty hint, etc.
  created_at      timestamptz default now()
);

-- ─── memory_facts ─────────────────────────────────────────────────────────────
-- Structured per-patient facts. Same fact_type+key supersedes older rows.
create table if not exists memory_facts (
  id              uuid primary key default gen_random_uuid(),
  patient_id      uuid not null references patients(id) on delete cascade,
  fact_type       text not null,   -- condition | allergy | medication | event | lifestyle
  key             text not null,
  value           text not null,
  status          text default 'active', -- active | superseded | deleted
  source_type     text,            -- report | chat | manual
  source_id       text,            -- report_id or session_id
  confidence      numeric,         -- 0.0–1.0
  created_at      timestamptz default now(),
  superseded_by   uuid             -- points to the newer memory_facts.id
);

-- ─── memory_embeddings ────────────────────────────────────────────────────────
-- Vector store for report/session summaries. Queried by match_memories().
-- IMPORTANT: embedding column is vector(768). Use gemini-embedding-001 with
-- output_dimensionality=768 ALWAYS. Never mix embedding models in this table.
create table if not exists memory_embeddings (
  id              uuid primary key default gen_random_uuid(),
  patient_id      uuid not null references patients(id) on delete cascade,
  content         text not null,
  source_type     text,            -- report | chat
  source_id       text,
  embedding       vector(768),
  created_at      timestamptz default now()
);

-- ─── guideline_chunks ─────────────────────────────────────────────────────────
-- WHO/CDC knowledge base. Separate from personal memory.
-- embedding must also be vector(768).
create table if not exists guideline_chunks (
  id              uuid primary key default gen_random_uuid(),
  source          text,            -- e.g. 'WHO 2023' or 'CDC diabetes guidelines'
  title           text,
  content         text,
  embedding       vector(768)
);

-- ─── llm_logs ─────────────────────────────────────────────────────────────────
-- Every call_llm() invocation is logged here. Used for debugging and rate tracking.
create table if not exists llm_logs (
  id              bigserial primary key,
  provider        text,            -- gemini | openrouter_paid | openrouter_free
  model           text,
  latency_ms      int,
  status          text,            -- success | fallback | error
  created_at      timestamptz default now()
);

-- ─── doctor_cache ─────────────────────────────────────────────────────────────
-- 24h cache for Places API results keyed by specialty + rounded lat/lng.
create table if not exists doctor_cache (
  id              uuid primary key default gen_random_uuid(),
  cache_key       text not null unique, -- '{specialty}:{lat_r}:{lng_r}'
  results         jsonb not null,
  created_at      timestamptz default now(),
  expires_at      timestamptz not null
);

-- ─── Indexes ──────────────────────────────────────────────────────────────────
create index if not exists idx_patients_owner    on patients(owner_id);
create index if not exists idx_reports_patient   on reports(patient_id);
create index if not exists idx_rv_report         on report_values(report_id);
create index if not exists idx_chat_msg_session  on chat_messages(session_id);
create index if not exists idx_mf_patient_status on memory_facts(patient_id, status);
create index if not exists idx_me_patient        on memory_embeddings(patient_id);
create index if not exists idx_dc_expires        on doctor_cache(expires_at);

-- pgvector IVFFlat index for cosine similarity search on memory_embeddings.
-- Run AFTER seeding data (needs rows to train). Safe to run on empty table too.
create index if not exists idx_me_embedding on memory_embeddings
  using ivfflat (embedding vector_cosine_ops) with (lists = 50);

create index if not exists idx_gc_embedding on guideline_chunks
  using ivfflat (embedding vector_cosine_ops) with (lists = 50);

-- ─── match_memories() ─────────────────────────────────────────────────────────
-- Returns the top-k most similar memory embeddings for a given patient and query vector.
create or replace function match_memories(
  p_patient uuid,
  q         vector(768),
  k         int default 4
)
returns table (id uuid, content text, similarity float)
language sql stable as $$
  select id, content, 1 - (embedding <=> q) as similarity
  from   memory_embeddings
  where  patient_id = p_patient
  order  by embedding <=> q
  limit  k;
$$;

-- ─── match_guidelines() ───────────────────────────────────────────────────────
-- Returns the top-k most relevant WHO/CDC guideline chunks for a query vector.
create or replace function match_guidelines(
  q  vector(768),
  k  int default 4
)
returns table (id uuid, title text, content text, similarity float)
language sql stable as $$
  select id, title, content, 1 - (embedding <=> q) as similarity
  from   guideline_chunks
  order  by embedding <=> q
  limit  k;
$$;


-- =============================================================================
-- Row Level Security Policies
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- HealthMate Compass — Row Level Security Policies
-- Run AFTER schema.sql in the Supabase SQL Editor.
-- ─────────────────────────────────────────────────────────────────────────────
-- Pattern: a row is accessible only if its patient_id references a patient
-- whose owner_id matches the currently authenticated user (auth.uid()).
-- The backend uses the SERVICE ROLE KEY which bypasses RLS intentionally;
-- all direct browser/frontend calls use the ANON KEY + Supabase Auth JWT
-- and are therefore subject to RLS.
-- ─────────────────────────────────────────────────────────────────────────────

-- ─── Helper function ──────────────────────────────────────────────────────────
-- Returns true if the given patient_id belongs to the calling user.
create or replace function is_owner(p_patient_id uuid)
returns boolean language sql stable security definer as $$
  select exists (
    select 1 from patients
    where id = p_patient_id and owner_id = auth.uid()
  );
$$;

-- ─── patients ─────────────────────────────────────────────────────────────────
alter table patients enable row level security;

create policy "patients: owner can read own"
  on patients for select using (owner_id = auth.uid());

create policy "patients: owner can insert own"
  on patients for insert with check (owner_id = auth.uid());

create policy "patients: owner can update own"
  on patients for update using (owner_id = auth.uid());

create policy "patients: owner can delete own"
  on patients for delete using (owner_id = auth.uid());

-- ─── medications ──────────────────────────────────────────────────────────────
alter table medications enable row level security;

create policy "medications: owner can read"
  on medications for select using (is_owner(patient_id));

create policy "medications: owner can insert"
  on medications for insert with check (is_owner(patient_id));

create policy "medications: owner can update"
  on medications for update using (is_owner(patient_id));

create policy "medications: owner can delete"
  on medications for delete using (is_owner(patient_id));

-- ─── reports ──────────────────────────────────────────────────────────────────
alter table reports enable row level security;

create policy "reports: owner can read"
  on reports for select using (is_owner(patient_id));

create policy "reports: owner can insert"
  on reports for insert with check (is_owner(patient_id));

create policy "reports: owner can update"
  on reports for update using (is_owner(patient_id));

create policy "reports: owner can delete"
  on reports for delete using (is_owner(patient_id));

-- ─── report_values ────────────────────────────────────────────────────────────
alter table report_values enable row level security;

create policy "report_values: owner can read"
  on report_values for select
  using (exists (
    select 1 from reports r where r.id = report_id and is_owner(r.patient_id)
  ));

create policy "report_values: owner can insert"
  on report_values for insert
  with check (exists (
    select 1 from reports r where r.id = report_id and is_owner(r.patient_id)
  ));

create policy "report_values: owner can delete"
  on report_values for delete
  using (exists (
    select 1 from reports r where r.id = report_id and is_owner(r.patient_id)
  ));

-- ─── chat_sessions ────────────────────────────────────────────────────────────
alter table chat_sessions enable row level security;

create policy "chat_sessions: owner can read"
  on chat_sessions for select using (is_owner(patient_id));

create policy "chat_sessions: owner can insert"
  on chat_sessions for insert with check (is_owner(patient_id));

create policy "chat_sessions: owner can update"
  on chat_sessions for update using (is_owner(patient_id));

create policy "chat_sessions: owner can delete"
  on chat_sessions for delete using (is_owner(patient_id));

-- ─── chat_messages ────────────────────────────────────────────────────────────
alter table chat_messages enable row level security;

create policy "chat_messages: owner can read"
  on chat_messages for select
  using (exists (
    select 1 from chat_sessions s where s.id = session_id and is_owner(s.patient_id)
  ));

create policy "chat_messages: owner can insert"
  on chat_messages for insert
  with check (exists (
    select 1 from chat_sessions s where s.id = session_id and is_owner(s.patient_id)
  ));

-- ─── memory_facts ─────────────────────────────────────────────────────────────
alter table memory_facts enable row level security;

create policy "memory_facts: owner can read"
  on memory_facts for select using (is_owner(patient_id));

create policy "memory_facts: owner can insert"
  on memory_facts for insert with check (is_owner(patient_id));

create policy "memory_facts: owner can update"
  on memory_facts for update using (is_owner(patient_id));

create policy "memory_facts: owner can delete"
  on memory_facts for delete using (is_owner(patient_id));

-- ─── memory_embeddings ────────────────────────────────────────────────────────
alter table memory_embeddings enable row level security;

create policy "memory_embeddings: owner can read"
  on memory_embeddings for select using (is_owner(patient_id));

create policy "memory_embeddings: owner can insert"
  on memory_embeddings for insert with check (is_owner(patient_id));

create policy "memory_embeddings: owner can delete"
  on memory_embeddings for delete using (is_owner(patient_id));

-- ─── guideline_chunks ─────────────────────────────────────────────────────────
-- Public read (no patient data); write restricted to service role only.
alter table guideline_chunks enable row level security;

create policy "guideline_chunks: anyone can read"
  on guideline_chunks for select using (true);

-- ─── llm_logs ─────────────────────────────────────────────────────────────────
-- Backend-only (service role); frontend should never touch this table.
alter table llm_logs enable row level security;
-- No client policies: only the service role (which bypasses RLS) writes here.

-- ─── doctor_cache ─────────────────────────────────────────────────────────────
-- Backend-only cache; frontend never reads directly.
alter table doctor_cache enable row level security;
-- No client policies.

-- ─── Storage: reports bucket ──────────────────────────────────────────────────
-- Create the private bucket via the Supabase Dashboard:
--   Storage → New bucket → Name: "reports" → Private (uncheck Public)
-- Then add storage policies below (or via Dashboard Storage → Policies tab).

-- Authenticated users can upload to their own folder: reports/{user_id}/...
-- The backend generates signed URLs for downloads using the service role key.

-- NOTE: Storage policies use a different syntax (storage.objects table).
-- Run these in the SQL editor:

create policy "storage: owner can upload reports"
  on storage.objects for insert
  with check (
    bucket_id = 'reports' and
    auth.uid()::text = (storage.foldername(name))[1]
  );

create policy "storage: owner can read own reports"
  on storage.objects for select
  using (
    bucket_id = 'reports' and
    auth.uid()::text = (storage.foldername(name))[1]
  );

create policy "storage: owner can delete own reports"
  on storage.objects for delete
  using (
    bucket_id = 'reports' and
    auth.uid()::text = (storage.foldername(name))[1]
  );

