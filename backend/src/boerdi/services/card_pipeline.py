"""Card-Pipeline v2 — I/O-Orchestrierung (P5-4-Tail).

Der async I/O-Teil der Card-Pipeline: ``fetch_card_pool`` beschafft den Roh-Pool
über die MCP-Tools, ``run_pipeline_v2`` verkettet Fetch → Normalisierung →
Selektion → Link-Annotation zum End-to-End-Lauf. Die reine Logik der Stufen liegt
in ``boerdi.domain.cards`` (normalize/select/links); dieses Modul ist nur der
dünne Service-Draht drumherum (daher ``services/`` statt ``domain/``).

1:1-Port der beiden async-Funktionen aus ALT ``card_pipeline.py``; der Rest des
1285-Z.-Monolithen ist bereits nach ``domain/cards/`` gesplittet. Einzige
Deviation: die lazy MCP-Importe zeigen auf die NEU-Leaf-Module (kein Facade).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from boerdi.domain.cards.links import annotate_cards_with_link
from boerdi.domain.cards.normalize import IntentKind, infer_intent_kind, normalize_cards
from boerdi.domain.cards.select import select_final_cards
from boerdi.services.config_loader import load_card_pipeline_config

logger = logging.getLogger(__name__)


async def fetch_card_pool(
    *,
    query: str,
    intent_kind: IntentKind,
    pool_size: int | None = None,
    collection_id: str | None = None,
    learning_resource_type_uri: str | None = None,
    discipline_uri: str | None = None,
    educational_context_uri: str | None = None,
) -> list[dict[str, Any]]:
    """Beschaffungs-Phase: ein einziger Aufruf liefert den Card-Pool.

    Je nach ``intent_kind`` werden ein oder drei MCP-Tools parallel gerufen,
    die Ergebnisse parsed und in eine einheitliche Card-Liste gegossen. Der
    Caller bekommt einen großen Pool (Default 20 Cards) zurück — die Final-
    Auswahl auf 5 Cards passiert in Phase 3.

    Args:
        query: User-Suchstring (für search_wlo_*-Tools).
        intent_kind: Bestimmt, welche Tools wir rufen.
        pool_size: Override für die Pool-Größe. Default: aus
            ``card-pipeline.yaml``.
        collection_id: Pflicht für ``intent_kind="collection-contents"``.
        learning_resource_type_uri: Optional bei ``"type-focus"``. URI des
            LRT-Filters (z.B. der WLO-LRT-URI für "Video").
        discipline_uri: Optional bei ``"general"``/``"type-focus"``.
        educational_context_uri: Optional, gleicher Anwendungsfall.

    Returns:
        Liste von Card-Dicts im internen Boerdi-Schema (Felder wie
        ``node_id``, ``title``, ``wlo_url``, …). NICHT-normalisiert —
        Host-Rewrite und node_type-Mapping macht :func:`normalize_cards`.

    Raises:
        Nichts. Tool-Fehler werden geloggt und liefern leere Teilmengen.
    """
    # Lazy-Import, damit das Modul auch in Test-Suiten ohne MCP-Server-Setup
    # importierbar bleibt (z.B. für Phase 9 Smoke-Tests).
    from boerdi.services.mcp.client import call_mcp_tool
    from boerdi.services.mcp.parsers import parse_wlo_cards, parse_wlo_topic_page_cards

    cfg = load_card_pipeline_config()
    effective_pool = pool_size if pool_size is not None else cfg["pool_size"]
    # Defensiv-Clamp — sollte schon aus der YAML clamped sein, aber Caller
    # könnten einen Override mit None > YAML-Cap übergeben.
    effective_pool = max(1, min(50, int(effective_pool)))

    logger.info(
        "fetch_card_pool: kind=%s query=%r pool=%d coll=%s lrt=%s",
        intent_kind, query[:60] if query else "", effective_pool,
        collection_id or "-", learning_resource_type_uri or "-",
    )

    # ── intent_kind == "collection-contents" ──────────────────────────
    if intent_kind == "collection-contents":
        if not collection_id:
            logger.warning(
                "fetch_card_pool: collection-contents ohne collection_id — leer."
            )
            return []
        try:
            # B7 (2026-06-10): das Tool verlangt ``nodeId`` (Pydantic +
            # MCP-Schema, required) — ``collectionId`` fiel durch die
            # Validierung, der v2-Collection-Branch war funktional tot.
            raw = await call_mcp_tool(
                "get_collection_contents",
                {"nodeId": collection_id, "maxResults": effective_pool},
            )
        except Exception as e:  # pragma: no cover — network failure
            logger.warning("get_collection_contents failed: %s", e)
            return []
        cards = parse_wlo_cards(raw) or []
        logger.info(
            "fetch_card_pool kind=collection-contents → %d cards", len(cards),
        )
        return cards

    # ── intent_kind == "type-focus" ────────────────────────────────────
    if intent_kind == "type-focus":
        args: dict[str, Any] = {
            "query": query or "",
            "maxResults": effective_pool,
        }
        if learning_resource_type_uri:
            args["learningResourceType"] = learning_resource_type_uri
        if discipline_uri:
            args["discipline"] = discipline_uri
        if educational_context_uri:
            args["educationalContext"] = educational_context_uri
        try:
            raw = await call_mcp_tool("search_wlo_content", args)
        except Exception as e:  # pragma: no cover
            logger.warning("search_wlo_content (type-focus) failed: %s", e)
            return []
        cards = parse_wlo_cards(raw) or []
        logger.info("fetch_card_pool kind=type-focus → %d cards", len(cards))
        return cards

    # ── intent_kind == "general" (Default) ────────────────────────────
    # Pool wird auf 3 Tools verteilt. Wir nehmen je ein Drittel + 1 Sicher-
    # heits-Spielraum (ungerade Aufteilungen runden hoch).
    per_tool = max(3, (effective_pool + 2) // 3)
    base_args: dict[str, Any] = {"query": query or "", "maxResults": per_tool}
    if discipline_uri:
        base_args["discipline"] = discipline_uri
    if educational_context_uri:
        base_args["educationalContext"] = educational_context_uri

    async def _call(tool_name: str, args: dict[str, Any]) -> str:
        try:
            return await call_mcp_tool(tool_name, args)
        except Exception as e:  # pragma: no cover
            logger.warning("%s failed: %s", tool_name, e)
            return ""

    raw_tp, raw_col, raw_con = await asyncio.gather(
        _call("search_wlo_topic_pages", dict(base_args)),
        _call("search_wlo_collections", dict(base_args)),
        _call("search_wlo_content", dict(base_args)),
    )

    cards_tp = parse_wlo_topic_page_cards(raw_tp) or []
    cards_col = parse_wlo_cards(raw_col) or []
    cards_con = parse_wlo_cards(raw_con) or []

    logger.info(
        "fetch_card_pool kind=general → tp=%d col=%d con=%d",
        len(cards_tp), len(cards_col), len(cards_con),
    )

    # Themenseiten zuerst, dann Sammlungen, dann Einzelinhalte. Normalisierung
    # (inkl. node_type-Inferenz + Dedup) macht der Caller.
    return [*cards_tp, *cards_col, *cards_con]


async def run_pipeline_v2(
    *,
    user_message: str,
    guide_mode: bool = False,
    wanted_content_types: set[str] | None = None,
    collection_id: str | None = None,
    learning_resource_type_uri: str | None = None,
    discipline_uri: str | None = None,
    educational_context_uri: str | None = None,
    selected_node_ids: list[str] | None = None,
    repo_base: str | None = None,
    prefetched_pool: list[Any] | None = None,
) -> dict[str, Any]:
    """End-to-End-Lauf der Card-Pipeline v2.

    Wrapper-Funktion, die :func:`fetch_card_pool`, :func:`normalize_cards`,
    :func:`select_final_cards` und :func:`annotate_cards_with_link`
    hintereinander aufruft.

    Args:
        prefetched_pool: Wenn gegeben, wird :func:`fetch_card_pool`
            ÜBERSPRUNGEN und stattdessen dieser bereits beschaffte Pool
            als Eingabe für die Normalisierung benutzt. Genutzt in der
            Migrations-Phase, wo v1's MCP-Calls weiter laufen und v2 als
            reiner Curation-Layer (Normalize + Select + Link) drauf läuft.
            Spart einen kompletten MCP-Roundtrip und garantiert, dass v1
            und v2 auf dem gleichen Pool arbeiten — LLM-Re-Rank funktioniert
            dann konsistent, weil ``selected_node_ids`` aus dem v1-Pool
            im v2-Pool auch existieren.

    Returns:
        Ein Diagnose-Dict mit:
          * ``intent_kind`` — was die Heuristik abgeleitet hat
          * ``pool_size``, ``normalized_size``, ``final_size`` — Counts für
            den A/B-Log
          * ``cards`` — die finale Card-Liste mit ``link``-Feld
    """
    intent_kind = infer_intent_kind(
        user_message=user_message,
        wanted_content_types=wanted_content_types,
        collection_id=collection_id,
    )

    if prefetched_pool is not None:
        # Curation-Modus: Pool kommt vom Caller (v1-Cards). Pydantic-Models
        # in Dicts konvertieren, damit normalize_cards/select_final_cards
        # gleichmäßig arbeiten.
        pool: list[dict[str, Any]] = []
        for c in prefetched_pool:
            if isinstance(c, dict):
                pool.append(c)
            elif hasattr(c, "model_dump"):
                try:
                    pool.append(c.model_dump())
                except Exception:
                    logger.debug("prefetched card model_dump failed", exc_info=True)
            else:
                try:
                    pool.append(dict(c))  # type: ignore[arg-type]
                except Exception:
                    logger.debug("prefetched card dict() conversion failed", exc_info=True)
        logger.info(
            "run_pipeline_v2: using prefetched_pool of %d cards (no MCP fetch)",
            len(pool),
        )
    else:
        pool = await fetch_card_pool(
            query=user_message,
            intent_kind=intent_kind,
            collection_id=collection_id,
            learning_resource_type_uri=learning_resource_type_uri,
            discipline_uri=discipline_uri,
            educational_context_uri=educational_context_uri,
        )
    normalized = normalize_cards(
        pool, target_repo_base=repo_base, intent_kind=intent_kind,
    )
    final = select_final_cards(
        normalized,
        intent_kind=intent_kind,
        wanted_content_types=wanted_content_types,
        selected_node_ids=selected_node_ids,
        query=user_message,
    )
    annotated = annotate_cards_with_link(
        final,
        guide_mode=guide_mode,
        repo_base=repo_base,
        search_query=user_message or "",
        require_allowed=guide_mode,  # Im Lotsen-Modus strikt Allow-Liste
    )

    return {
        "intent_kind": intent_kind,
        "pool_size": len(pool),
        "normalized_size": len(normalized),
        "final_size": len(annotated),
        "cards": annotated,
    }
