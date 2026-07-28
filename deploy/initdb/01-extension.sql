-- pgvector must be active in the app DB (spec §6).
-- Migration 0001 re-asserts this idempotently for non-compose environments.
CREATE EXTENSION IF NOT EXISTS vector;
