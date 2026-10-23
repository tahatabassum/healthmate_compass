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
