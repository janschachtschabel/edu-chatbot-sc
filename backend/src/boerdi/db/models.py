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
    Index,
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
    # Paket 18C/D (0016): Trace-ID der Anfrage — aus Log und Fehlernummer zum Zug.
    trace_id: Mapped[str | None] = mapped_column(Text, nullable=True)


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
    trace_id: Mapped[str | None] = mapped_column(Text, nullable=True)  # 0016


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
    trace_id: Mapped[str | None] = mapped_column(Text, nullable=True)  # 0016


class UsageEvent(Base):
    """Token-Verbrauch EINES Zuges, je verwendetem Modell eine Zeile (K2a).

    Eigene Tabelle statt Auswertung des JSONB in ``messages.debug``
    (Nutzer-Entscheid): abrechnungsfest, indizierbar, mit eigener
    Aufbewahrungsfrist und unabhängig davon, wie sich das Debug-Format ändert.

    **Die zwei „davon"-Felder sind der Kern und die häufigste Falle.**
    ``cached_tokens`` ist in ``prompt_tokens`` ENTHALTEN und
    ``reasoning_tokens`` in ``completion_tokens`` — so zählt es der Anbieter.
    Wer sie addiert, rechnet doppelt.

    Eine Zeile je Zug und Modell, nicht je LLM-Aufruf: der Merkposten
    (``obs/usage.py``) summiert schon über den Zug, und abgerechnet wird die
    Sitzung. Je Aufruf wären es 5–10× mehr Zeilen für eine Auflösung, die
    niemand abrechnet — die Phasen-Aufteilung bleibt zur Diagnose im Debug-JSONB.
    """

    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Paket 7 (P3, Migration 0009): NULL bei Aufträgen der Agent-API — sie
    # gehören keiner Chat-Sitzung; ``quelle`` sagt dann, woher die Zeile kommt.
    session_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=True
    )
    model: Mapped[str] = mapped_column(Text)  # aufgelöster Modellname der Antwort
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0)  # davon gecacht
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, default=0)  # davon Reasoning
    calls: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # AG-1 (Migration 0004): die Maschine des Zugs, wie sie im Debug-Block
    # steht. NULL bei Zeilen von vor der Migration und bei Frühausstiegen.
    engine: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Paket 7 (P3, Migration 0009): ``agent-api`` bei Aufträgen ohne Sitzung;
    # Chat-Zeilen lassen sie leer.
    quelle: Mapped[str | None] = mapped_column(Text, nullable=True)


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
    # Paket 17 (0014): alle 15 s, solange der Lauf lebt (``obs/herzschlag``).
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    # Paket 17 (0014): alle 15 s, solange der Lauf lebt (``obs/herzschlag``).
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConfigArea(Base):
    __tablename__ = "config_areas"

    area: Mapped[str] = mapped_column(Text, primary_key=True)  # '01-base/welcome-config'
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_by: Mapped[str] = mapped_column(Text, default="")
    # Paket 12 (0011): Werksfassung, auf der der Bereich steht, und die stillgelegte eigene Fassung.
    werk_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    eigene_fassung: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    eigene_basis: Mapped[str | None] = mapped_column(Text, nullable=True)


class ConfigWerkEntfernt(Base):
    """Im Studio gelöschte Werksbereiche — der Werksabgleich legt sie nicht wieder an (0011)."""

    __tablename__ = "config_werk_entfernt"

    area: Mapped[str] = mapped_column(Text, primary_key=True)
    entfernt_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PromptVersion(Base):
    """Eine Fassung eines festen Prompt-Bausteins, Schlüssel ist die Prüfsumme (0012)."""

    __tablename__ = "prompt_versions"

    hash: Mapped[str] = mapped_column(Text, primary_key=True)
    art: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    erstmals: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    zuletzt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


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
    art: Mapped[str] = mapped_column(Text, server_default="hand")  # 'hand' | 'auto' (0011)


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


class DokumentUpload(Base):
    """Ein im Chat hochgeladenes Strukturdokument (Paket U3-2a, Migration 0017).

    Nur das bereinigte Markdown, die Gliederung und der Befund — nie die Rohdatei. Eins je Sitzung.
    """

    __tablename__ = "dokument_uploads"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        Text, ForeignKey("sessions.session_id", ondelete="CASCADE"), unique=True
    )
    block_id: Mapped[str] = mapped_column(Text)
    #: Kennzeichen der angemeldeten Person (``aufrufer_kennung``), sonst NULL.
    aufrufer: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str] = mapped_column(Text)
    format: Mapped[str] = mapped_column(Text)
    groesse: Mapped[int] = mapped_column(Integer)
    befund: Mapped[dict[str, Any]] = mapped_column(JSONB)
    gliederung: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    markdown: Mapped[str] = mapped_column(Text)
    erstellt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    genutzt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    verfaellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Vorgang(Base):
    """Arbeitsstand einer Person (Paket V1, Migration 0018): Akte ``wlo.vorgang@1`` mit benannten
    Teilen. Gehört ``aufrufer`` (bestätigte Person oder ``sitzung:<id>``)."""

    __tablename__ = "vorgaenge"
    # Migration 0020: Präfixsuche nach anonymen Vorgängen (``aufrufer LIKE 'sitzung:%'``); derselbe
    # Index trägt die Gleichheit (``aufrufer = :a``) — ein zweiter auf ``aufrufer`` wäre doppelt.
    __table_args__ = (
        Index("ix_vorgaenge_aufrufer_muster", "aufrufer",
              postgresql_ops={"aufrufer": "text_pattern_ops"}),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    aufrufer: Mapped[str] = mapped_column(Text)
    session_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("sessions.session_id", ondelete="SET NULL"), nullable=True, index=True
    )
    titel: Mapped[str] = mapped_column(Text)
    zweck: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    akte: Mapped[dict[str, Any]] = mapped_column(JSONB)
    akte_version: Mapped[int] = mapped_column(Integer, server_default="0")
    erstellt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    geaendert: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    verfaellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class VorgangAuftrag(Base):
    """Ein b-api-Auftrag (Kestra-Job) eines Vorgangs (Paket K1a, Migration 0019) — nur die Job-ID,
    nie der Schlüssel, mit dem er gestartet wurde."""

    __tablename__ = "vorgang_auftraege"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    vorgang_id: Mapped[str] = mapped_column(
        Text, ForeignKey("vorgaenge.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[str] = mapped_column(Text)
    flow: Mapped[str] = mapped_column(Text)
    schritt: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    erstellt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    geaendert: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VorgangAblage(Base):
    """Große Teile und frühere Fassungen eines Vorgangs (Paket V1) — die Akte bleibt klein."""

    __tablename__ = "vorgang_ablage"

    vorgang_id: Mapped[str] = mapped_column(
        Text, ForeignKey("vorgaenge.id", ondelete="CASCADE"), primary_key=True
    )
    schluessel: Mapped[str] = mapped_column(Text, primary_key=True)
    typ: Mapped[str] = mapped_column(Text)
    inhalt: Mapped[Any] = mapped_column(JSONB)
    groesse: Mapped[int] = mapped_column(Integer)
    erstellt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
