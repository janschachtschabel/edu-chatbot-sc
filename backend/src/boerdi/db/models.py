"""ORM models mirroring alembic migration 0001 (spec §6).

The MIGRATION owns the DDL — these mappings exist for app-side reads/writes
and are never used to CREATE tables. Vector columns are declared without a
dimension here; the real dim (EMBED_DIM) is baked into the migration.
"""

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSONB, list[Any]: JSONB}


class ChatSession(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(Text, primary_key=True)  # 'bb-<uuid>'
    persona_id: Mapped[str] = mapped_column(Text, default="")
    state_id: Mapped[str] = mapped_column(Text, default="S1")
    entities: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    signal_history: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    tour_state: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ChatMessage(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        Text, ForeignKey("sessions.session_id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(Text)  # 'user' | 'assistant' (DB CHECK)
    content: Mapped[str] = mapped_column(Text)
    cards: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    debug: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MemoryItem(Base):
    __tablename__ = "memory"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        Text, ForeignKey("sessions.session_id", ondelete="CASCADE")
    )
    key: Mapped[str] = mapped_column(Text)
    value: Mapped[str] = mapped_column(Text)
    memory_type: Mapped[str] = mapped_column(Text)  # short | long
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SafetyLog(Base):
    __tablename__ = "safety_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    risk_level: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class QualityLog(Base):
    __tablename__ = "quality_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    pattern_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, default="running")
    mode: Mapped[str] = mapped_column(Text, default="")
    config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    totals: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    conversations: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class LoadtestRun(Base):
    __tablename__ = "loadtest_runs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    status: Mapped[str] = mapped_column(Text, default="running")
    config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class ConfigArea(Base):
    __tablename__ = "config_areas"

    area: Mapped[str] = mapped_column(Text, primary_key=True)  # '01-base/welcome-config'
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_by: Mapped[str] = mapped_column(Text, default="")


class ConfigHistory(Base):
    __tablename__ = "config_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    area: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_by: Mapped[str] = mapped_column(Text, default="")


class ConfigSnapshot(Base):
    __tablename__ = "config_snapshots"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # factory = 'factory'
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    label: Mapped[str] = mapped_column(Text, default="")
    include_db: Mapped[bool] = mapped_column(Boolean, default=False)
    blob: Mapped[bytes] = mapped_column(LargeBinary)  # ZIP bytes


class RagDocument(Base):
    __tablename__ = "rag_documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    area: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RagChunk(Base):
    __tablename__ = "rag_chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("rag_documents.id", ondelete="CASCADE"), nullable=True
    )
    area: Mapped[str] = mapped_column(Text)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[Any | None] = mapped_column(Vector(), nullable=True)
