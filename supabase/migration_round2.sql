-- ─────────────────────────────────────────────────────────────────────────────
-- HealthMate Compass — Round 2 Database Migration
-- Enforces 1 User = 1 Profile, Chat Summaries, Conditions Tracking & Change Log
-- ─────────────────────────────────────────────────────────────────────────────

do $$
declare
  dup_count int;
begin
  -- Check for duplicate patient profiles per owner
  select count(*) into dup_count
  from (
    select owner_id from patients group by owner_id having count(*) > 1
  ) dups;

  if dup_count > 0 then
    raise notice 'Found % owners with multiple patient profiles. Consolidating to 1 profile per user...', dup_count;

    -- For each owner with multiple rows, keep the earliest row (or relation='self')
    -- Re-link any reports, chat_sessions, medications, or memories to the primary profile
    with primary_patients as (
      select distinct on (owner_id) id as keep_id, owner_id
      from patients
      order by owner_id, (relation = 'self') desc, created_at asc
    ),
    redundant_patients as (
      select p.id as drop_id, pp.keep_id
      from patients p
      join primary_patients pp on p.owner_id = pp.owner_id
      where p.id != pp.keep_id
    )
    -- Re-link child foreign keys before deleting redundant rows
    update reports r
    set patient_id = rp.keep_id
    from redundant_patients rp
    where r.patient_id = rp.drop_id;

    with primary_patients as (
      select distinct on (owner_id) id as keep_id, owner_id
      from patients
      order by owner_id, (relation = 'self') desc, created_at asc
    ),
    redundant_patients as (
      select p.id as drop_id, pp.keep_id
      from patients p
      join primary_patients pp on p.owner_id = pp.owner_id
      where p.id != pp.keep_id
    )
    update chat_sessions cs
    set patient_id = rp.keep_id
    from redundant_patients rp
    where cs.patient_id = rp.drop_id;

    with primary_patients as (
      select distinct on (owner_id) id as keep_id, owner_id
      from patients
      order by owner_id, (relation = 'self') desc, created_at asc
    ),
    redundant_patients as (
      select p.id as drop_id, pp.keep_id
      from patients p
      join primary_patients pp on p.owner_id = pp.owner_id
      where p.id != pp.keep_id
    )
    update medications m
    set patient_id = rp.keep_id
    from redundant_patients rp
    where m.patient_id = rp.drop_id;

    with primary_patients as (
      select distinct on (owner_id) id as keep_id, owner_id
      from patients
      order by owner_id, (relation = 'self') desc, created_at asc
    ),
    redundant_patients as (
      select p.id as drop_id, pp.keep_id
      from patients p
      join primary_patients pp on p.owner_id = pp.owner_id
      where p.id != pp.keep_id
    )
    update memory_facts mf
    set patient_id = rp.keep_id
    from redundant_patients rp
    where mf.patient_id = rp.drop_id;

    -- Delete redundant duplicate patient rows
    delete from patients
    where id in (
      select p.id
      from patients p
      join (
        select distinct on (owner_id) id as keep_id, owner_id
        from patients
        order by owner_id, (relation = 'self') desc, created_at asc
      ) pp on p.owner_id = pp.owner_id
      where p.id != pp.keep_id
    );

    raise notice 'Deduplication complete. Retained exactly 1 profile per user.';
  else
    raise notice 'No duplicate owner_id profiles found.';
  end if;
end $$;

-- Enforce strictly 1 patient profile per user
alter table patients drop constraint if exists unique_patient_owner;
alter table patients add constraint unique_patient_owner unique (owner_id);

-- Add rolling summary column to chat_sessions
alter table chat_sessions add column if not exists summary text;

-- Structured patient conditions with active/resolved status and dates
create table if not exists patient_conditions (
  id              uuid primary key default gen_random_uuid(),
  patient_id      uuid not null references patients(id) on delete cascade,
  name            text not null,
  status          text not null default 'active' check (status in ('active', 'resolved', 'superseded')),
  started_at      date default current_date,
  resolved_at     date,
  source          text default 'chat',          -- chat | report | manual
  note            text,
  created_at      timestamptz default now()
);

-- Transparent profile change log for audit and undo
create table if not exists profile_change_log (
  id                uuid primary key default gen_random_uuid(),
  patient_id        uuid not null references patients(id) on delete cascade,
  change_type       text not null check (change_type in ('condition', 'medication', 'allergy', 'general')),
  target_name       text not null,
  operation         text not null check (operation in ('add', 'update', 'resolve', 'remove')),
  old_value         jsonb,
  new_value         jsonb,
  evidence_quote    text,
  source_session_id text,
  source_message_id text,
  undone            boolean default false,
  created_at        timestamptz default now()
);

-- Row Level Security for new tables
alter table patient_conditions enable row level security;
alter table profile_change_log enable row level security;

drop policy if exists "patient_conditions: owner can read" on patient_conditions;
create policy "patient_conditions: owner can read"
  on patient_conditions for select using (is_owner(patient_id));

drop policy if exists "patient_conditions: owner can insert" on patient_conditions;
create policy "patient_conditions: owner can insert"
  on patient_conditions for insert with check (is_owner(patient_id));

drop policy if exists "patient_conditions: owner can update" on patient_conditions;
create policy "patient_conditions: owner can update"
  on patient_conditions for update using (is_owner(patient_id));

drop policy if exists "patient_conditions: owner can delete" on patient_conditions;
create policy "patient_conditions: owner can delete"
  on patient_conditions for delete using (is_owner(patient_id));

drop policy if exists "profile_change_log: owner can read" on profile_change_log;
create policy "profile_change_log: owner can read"
  on profile_change_log for select using (is_owner(patient_id));

drop policy if exists "profile_change_log: owner can insert" on profile_change_log;
create policy "profile_change_log: owner can insert"
  on profile_change_log for insert with check (is_owner(patient_id));

drop policy if exists "profile_change_log: owner can update" on profile_change_log;
create policy "profile_change_log: owner can update"
  on profile_change_log for update using (is_owner(patient_id));
