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
