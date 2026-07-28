"""0001 — full schema (spec §6 DDL, verbatim; vector dim parametrized).

Revision ID: 0001
Revises:
Create Date: 2026-07-11
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _embed_dim() -> int:
    from boerdi.services.llm_models import get_embed_dim

    return get_embed_dim()


def upgrade() -> None:
    dim = _embed_dim()
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute("""
        CREATE TABLE sessions (
          session_id text PRIMARY KEY,            -- 'bb-<uuid>'
          persona_id text NOT NULL DEFAULT '',
          state_id   text NOT NULL DEFAULT 'S1',
          entities   jsonb NOT NULL DEFAULT '{}'::jsonb,
          signal_history jsonb NOT NULL DEFAULT '[]'::jsonb,
          turn_count int  NOT NULL DEFAULT 0,
          tour_state jsonb NOT NULL DEFAULT '{}'::jsonb,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now())
    """)
    op.execute("CREATE INDEX idx_sessions_updated ON sessions(updated_at)")

    op.execute("""
        CREATE TABLE messages (
          id bigserial PRIMARY KEY,
          session_id text NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
          role text NOT NULL CHECK (role IN ('user','assistant')),
          content text NOT NULL,
          cards jsonb, debug jsonb,
          created_at timestamptz NOT NULL DEFAULT now())
    """)
    op.execute("CREATE INDEX idx_messages_session ON messages(session_id, id)")

    op.execute("""
        CREATE TABLE memory (
          id bigserial PRIMARY KEY,
          session_id text NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
          key text NOT NULL, value text NOT NULL, memory_type text NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE(session_id, key, memory_type))
    """)

    # Columns 1:1 like ALT (risk_level, stages_run, reasons, legal_flags,
    # flagged_categories, blocked_tools, enforced_pattern, escalated,
    # rate_limited, message, categories_json) live in ``data`` jsonb +
    # promoted columns for the hot filters.
    op.execute("""
        CREATE TABLE safety_logs (
          id bigserial PRIMARY KEY,
          session_id text, ip text,
          data jsonb NOT NULL,
          risk_level text, created_at timestamptz NOT NULL DEFAULT now())
    """)
    op.execute("CREATE INDEX idx_safety_created ON safety_logs(created_at)")
    op.execute("CREATE INDEX idx_safety_risk ON safety_logs(risk_level)")

    # Promoted: session_id, pattern_id, intent_id, created_at; the remaining
    # 28 ALT columns live in ``data`` jsonb (analytics queries ported P7).
    op.execute("""
        CREATE TABLE quality_logs (
          id bigserial PRIMARY KEY,
          session_id text, pattern_id text, intent_id text,
          data jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now())
    """)
    op.execute("CREATE INDEX idx_quality_created ON quality_logs(created_at)")
    op.execute("CREATE INDEX idx_quality_pattern ON quality_logs(pattern_id)")

    op.execute("""
        CREATE TABLE eval_runs (
          id text PRIMARY KEY,
          created_at timestamptz NOT NULL DEFAULT now(),
          completed_at timestamptz,
          status text NOT NULL DEFAULT 'running',
          mode text NOT NULL DEFAULT '',
          config jsonb, totals jsonb, summary jsonb, conversations jsonb,
          error_message text)
    """)

    op.execute("""
        CREATE TABLE loadtest_runs (
          id text PRIMARY KEY,
          created_at timestamptz NOT NULL DEFAULT now(),
          status text NOT NULL DEFAULT 'running',
          config jsonb, result jsonb)
    """)

    op.execute("""
        CREATE TABLE config_areas (
          area text PRIMARY KEY,                  -- e.g. '01-base/welcome-config'
          data jsonb NOT NULL,                    -- MD areas: {"body": ..., "frontmatter": {...}}
          version int NOT NULL DEFAULT 1,
          updated_at timestamptz NOT NULL DEFAULT now(),
          updated_by text NOT NULL DEFAULT '')
    """)
    op.execute("""
        CREATE TABLE config_history (
          id bigserial PRIMARY KEY,
          area text NOT NULL, version int NOT NULL, data jsonb NOT NULL,
          updated_at timestamptz NOT NULL DEFAULT now(),
          updated_by text NOT NULL DEFAULT '')
    """)
    op.execute("""
        CREATE TABLE config_snapshots (
          id text PRIMARY KEY,
          created_at timestamptz NOT NULL DEFAULT now(),
          label text NOT NULL DEFAULT '',
          include_db bool NOT NULL DEFAULT false,
          blob bytea NOT NULL)                    -- ZIP bytes; factory = row id='factory'
    """)

    op.execute("""
        CREATE TABLE rag_documents (
          id bigserial PRIMARY KEY,
          area text NOT NULL, title text, source text,
          created_at timestamptz DEFAULT now())
    """)
    op.execute(f"""
        CREATE TABLE rag_chunks (
          id bigserial PRIMARY KEY,
          document_id bigint REFERENCES rag_documents(id) ON DELETE CASCADE,
          area text NOT NULL, chunk_index int NOT NULL, content text NOT NULL,
          embedding vector({dim}))
    """)
    op.execute("CREATE INDEX idx_rag_area ON rag_chunks(area)")
    op.execute("""
        CREATE INDEX idx_rag_embedding ON rag_chunks
          USING hnsw (embedding vector_cosine_ops)
    """)

    # Config invalidation (cluster): trigger on config_areas -> NOTIFY
    op.execute("""
        CREATE OR REPLACE FUNCTION notify_config_changed() RETURNS trigger AS $$
        BEGIN PERFORM pg_notify('config_changed', NEW.area); RETURN NEW; END $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_config_notify AFTER INSERT OR UPDATE ON config_areas
          FOR EACH ROW EXECUTE FUNCTION notify_config_changed()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_config_notify ON config_areas")
    op.execute("DROP FUNCTION IF EXISTS notify_config_changed()")
    for table in (
        "rag_chunks", "rag_documents", "config_snapshots", "config_history",
        "config_areas", "loadtest_runs", "eval_runs", "quality_logs",
        "safety_logs", "memory", "messages", "sessions",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")
