-- ─────────────────────────────────────────────────────────────────────────────
-- HealthMate Compass — Guideline Chunks Seed (structure stub)
-- Phase 4 will populate this with real embeddings via the seed script.
-- Run this AFTER schema.sql to verify the table structure is correct.
-- ─────────────────────────────────────────────────────────────────────────────
-- The actual seeding is done by: backend/scripts/seed_guidelines.py
-- which chunks WHO/CDC text, embeds via gemini-embedding-001 (768d),
-- and upserts into guideline_chunks.

-- This file serves as a reference for the expected structure only.
-- The embedding column will be populated by the Python seed script,
-- not by raw SQL (we cannot embed text in SQL without the Gemini API).

-- Verify table exists:
select count(*) as guideline_count from guideline_chunks;
