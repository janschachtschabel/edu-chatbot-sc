"""Card selection & ranking (P5-4b) — byte-parity port of the pure selection half
of ALT ``card_pipeline.py``.

Second sub-module of the ``domain/cards`` package (after ``normalize``): the
Pipeline-v2 final-selection core — relevance scoring, deterministic type-mix, the
LLM ``select_top_cards`` re-rank merge, type-focus filtering, and the log summary.
Consumes a normalized pool (from ``normalize.normalize_cards``) and the
``select_top_cards`` ids the LLM tool (3-3b) produces.

Pure domain logic: the only outward call is the config read-fassade
``load_card_pipeline_config`` (sanctioned from ``domain/``); ``IntentKind`` comes
from the sibling ``normalize`` module.

Deviation from ALT: import roots only (``app.`` → ``boerdi.``; ``IntentKind`` is
imported from ``.normalize`` instead of being defined in the same file). Ported
function bodies are byte-identical (AST-diff gate).
"""

from __future__ import annotations

import logging
from typing import Any

from boerdi.domain.cards.normalize import IntentKind
from boerdi.services.config_loader import load_card_pipeline_config

logger = logging.getLogger(__name__)

_RELEVANCE_STOPWORDS = frozenset({
    "der", "die", "das", "den", "dem", "des",
    "ein", "eine", "einen", "einer", "einem", "eines",
    "zu", "zur", "zum", "im", "in", "an", "am", "auf", "mit", "und",
    "oder", "aber", "wie", "was", "wer", "wo", "wann", "wieso", "warum",
    "ist", "sind", "war", "waren", "sein", "haben", "hat", "wird", "werden",
    "kann", "können", "soll", "sollen", "muss", "müssen", "will", "wollen",
    "material", "materialien", "inhalt", "inhalte", "thema", "themen",
    "zeig", "zeige", "such", "suche", "find", "finde", "gib", "ich", "mir",
    "du", "wir", "ihr", "sie", "es",
})


def _tokenize_query(query: str) -> set[str]:
    """Liefert lowercase-Token aus ``query``, minus Stopwörter.

    Splittet an Whitespace + Satzzeichen, hält nur Tokens mit 2+ Zeichen.
    Wird im Hot-Path aufgerufen, deshalb bewusst simpel statt NLP-Library.
    """
    if not query:
        return set()
    import re as _re
    tokens = _re.findall(r"[\wäöüÄÖÜß]+", query.lower(), _re.UNICODE)
    return {
        t for t in tokens
        if len(t) >= 2 and t not in _RELEVANCE_STOPWORDS
    }


def _relevance_score(card: dict[str, Any], query_tokens: set[str]) -> float:
    """Heuristischer Relevance-Score: Match-Häufigkeit in Title/Description/
    Keywords/Disciplines.

    Score ist 0.0 wenn keiner der Query-Token irgendwo vorkommt — solche
    Cards bleiben am Ende ihrer Gruppe.

    Gewichtung:
      * Titel-Match:        2.0 pro Token (stärkstes Signal)
      * Keywords-Match:     1.0 pro Token
      * Disciplines-Match:  0.5 pro Token
      * Description-Match:  0.3 pro Token

    Multi-Token-Queries summieren sich auf — "Eiszeit Geographie" matcht
    auf "Eiszeit (Geographie)" → 4.0 (zwei Titel-Matches).
    """
    if not query_tokens or not isinstance(card, dict):
        return 0.0
    score = 0.0
    title = (card.get("title") or "").lower()
    desc = (card.get("description") or "").lower()
    keywords = " ".join(str(k) for k in (card.get("keywords") or [])).lower()
    disciplines = " ".join(str(d) for d in (card.get("disciplines") or [])).lower()
    for tok in query_tokens:
        if tok in title:
            score += 2.0
        if tok in keywords:
            score += 1.0
        if tok in disciplines:
            score += 0.5
        if tok in desc:
            score += 0.3
    return score


def _sort_by_relevance(
    cards: list[dict[str, Any]],
    query_tokens: set[str],
) -> list[dict[str, Any]]:
    """Stabile Sortierung absteigend nach :func:`_relevance_score`.

    Innerhalb gleichen Scores bleibt die Original-Reihenfolge erhalten
    (Python sort ist stable) — d.h. wenn der Score 0 ist (keine Query-
    Tokens oder kein Match), kommt die MCP-Original-Reihenfolge raus.
    """
    if not query_tokens or not cards:
        return list(cards)
    return sorted(
        cards,
        key=lambda c: _relevance_score(c, query_tokens),
        reverse=True,
    )


def _filter_to_wanted_content_types(
    cards: list[dict[str, Any]],
    wanted: set[str],
) -> list[dict[str, Any]]:
    """Behält nur Cards mit ``node_type == "content"`` UND mindestens einem
    matching Eintrag in ``learning_resource_types`` (Substring-Match
    case-insensitive auf der konkatenierten LRT-Liste).

    Sammlungen + Themenseiten werden bei aktivem Type-Fokus rausgefiltert,
    weil der User-Intent eindeutig auf Einzelinhalte zielt.
    """
    if not wanted:
        return list(cards)
    out: list[dict[str, Any]] = []
    for c in cards:
        if not isinstance(c, dict):
            continue
        if c.get("node_type") != "content":
            continue
        lrt = c.get("learning_resource_types") or []
        blob = " ".join(str(t).lower() for t in lrt if t)
        if any(w in blob for w in wanted):
            out.append(c)
    return out


def _deterministic_mix(
    cards: list[dict[str, Any]],
    target_size: int,
    query_tokens: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Mix-Strategie für ``intent_kind="general"``:

      * 1 Themenseite (falls verfügbar)
      * 1 Sammlung (falls verfügbar)
      * Rest mit Einzelinhalten auffüllen
      * Wenn ein Slot leer bleibt, mit Cards aus den anderen Pools
        weitergefüllt (Prio: content > collection > topic_page für die
        Resterampe).

    Wenn ``query_tokens`` übergeben wird, werden Cards **innerhalb** jeder
    Type-Gruppe nach Relevance-Score absteigend sortiert (Title/Keywords/
    Disciplines/Description-Match). Bei Score 0 oder fehlenden Tokens
    bleibt die MCP-Original-Reihenfolge erhalten (stable sort).
    """
    if not cards or target_size <= 0:
        return []

    by_type: dict[str, list[dict[str, Any]]] = {
        "topic_page": [], "collection": [], "content": [],
    }
    for c in cards:
        nt = c.get("node_type")
        if nt in by_type:
            by_type[nt].append(c)

    # Wenn Query-Tokens gegeben: erst nach Relevance sortieren, dann
    # Score-0-Cards aus jeder Gruppe entfernen — ABER nur, wenn mindestens
    # EINE Gruppe relevante Cards hat. Wenn alle Pools komplett irrelevant
    # sind (vage Query oder Stopwort-only), behalten wir alle Cards in
    # MCP-Reihenfolge — sonst bekommt der User leere Hände.
    #
    # Beispiel: Query "Material zu Bruchrechnung" → query_tokens={"bruchrechnung"}.
    # Pool hat 7 Sammlungen, davon 0 mit "Bruchrechnung" im Titel.
    # Pool hat 7 Inhalte, davon 4 mit "Bruchrechnung"-Match.
    # → Sammlungs-Gruppe wird auf [] gefiltert (keine relevante Sammlung)
    # → Inhalts-Gruppe wird auf 4 gefiltert
    # → Mix nimmt 0 Sammlungen, 5 Inhalte (aus 4 + 1 Auffüller? Nein —
    #    Auffüllung passiert nur OHNE Filter, also bleiben 4 relevante).
    if query_tokens:
        for key in by_type:
            by_type[key] = _sort_by_relevance(by_type[key], query_tokens)
        any_relevant = any(
            _relevance_score(c, query_tokens) > 0
            for cards_in_group in by_type.values()
            for c in cards_in_group
        )
        if any_relevant:
            for key in by_type:
                by_type[key] = [
                    c for c in by_type[key]
                    if _relevance_score(c, query_tokens) > 0
                ]
            logger.info(
                "_deterministic_mix: relevance-filtered pools tp=%d col=%d con=%d "
                "(query_tokens=%s)",
                len(by_type["topic_page"]), len(by_type["collection"]),
                len(by_type["content"]), sorted(query_tokens),
            )

    out: list[dict[str, Any]] = []

    # Slot 1: 1× Themenseite
    if by_type["topic_page"]:
        out.append(by_type["topic_page"].pop(0))

    # Slot 2: 1× Sammlung
    if len(out) < target_size and by_type["collection"]:
        out.append(by_type["collection"].pop(0))

    # Restplätze: erstmal mit Einzelinhalten auffüllen
    while len(out) < target_size and by_type["content"]:
        out.append(by_type["content"].pop(0))

    # Wenn noch Plätze offen: rest aus Sammlungen, dann Themenseiten.
    # Sammlungen-Prio höher, weil sie ein zusammenhängendes Materialset
    # darstellen — bei knappem Pool sinnvoller als "noch eine Themenseite".
    while len(out) < target_size and by_type["collection"]:
        out.append(by_type["collection"].pop(0))
    while len(out) < target_size and by_type["topic_page"]:
        out.append(by_type["topic_page"].pop(0))

    return out


def _select_by_ids(
    cards: list[dict[str, Any]],
    selected_ids: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Splittet ``cards`` in zwei Listen:
      * ``picked``: Cards, deren ``node_id`` in ``selected_ids`` steht, in
        der vom LLM angegebenen Reihenfolge.
      * ``rest``: alle anderen Pool-Cards, in der Pool-Reihenfolge.

    IDs aus ``selected_ids``, zu denen keine Card im Pool passt, werden
    ignoriert (LLM kann halluzinieren).
    """
    if not selected_ids:
        return [], list(cards)
    by_id: dict[str, dict[str, Any]] = {}
    for c in cards:
        nid = str(c.get("node_id") or "").strip()
        if nid:
            by_id[nid] = c
    picked: list[dict[str, Any]] = []
    seen_picked: set[str] = set()
    for sid in selected_ids:
        s = str(sid or "").strip()
        if not s or s in seen_picked:
            continue
        if s in by_id:
            picked.append(by_id[s])
            seen_picked.add(s)
    rest = [c for c in cards
            if str(c.get("node_id") or "").strip() not in seen_picked]
    return picked, rest


def select_final_cards(
    pool: list[dict[str, Any]],
    *,
    intent_kind: IntentKind,
    final_size: int | None = None,
    min_displayed: int | None = None,
    wanted_content_types: set[str] | None = None,
    selected_node_ids: list[str] | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    """Final-Auswahl-Pipeline (Phase 3a).

    Args:
        pool: Normalisierter Card-Pool (idealerweise aus :func:`fetch_card_pool`
            + :func:`normalize_cards`).
        intent_kind: ``"general"`` / ``"type-focus"`` / ``"collection-contents"``.
        final_size: Wie viele Cards zurückgeben. Default: aus
            ``card-pipeline.yaml``.
        min_displayed: Mindest-Anzahl. Wenn die LLM-Auswahl weniger liefert,
            wird mit deterministischer Auswahl aufgefüllt. Default aus YAML.
        wanted_content_types: Bei ``intent_kind="type-focus"`` Pflicht —
            die Pool-Cards werden vor der Auswahl strikt darauf gefiltert.
        selected_node_ids: Optionale LLM-Output. Cards mit diesen IDs werden
            in genau dieser Reihenfolge vorgereiht. IDs ohne matching Pool-
            Card werden ignoriert.
        query: Optional. Die User-Anfrage, aus der Relevance-Tokens gebildet
            werden. Cards mit Query-Match im Title/Keywords/Description
            werden nach oben sortiert (innerhalb ihrer Type-Gruppe bei
            general, gesamt bei type-focus). Bei ``None`` oder leerer Query
            bleibt die MCP-Reihenfolge erhalten.

    Returns:
        Liste von genau ``min(final_size, len(verfügbar))`` Cards.
    """
    cfg = load_card_pipeline_config()
    eff_final = final_size if final_size is not None else cfg["final_selection_size"]
    eff_min = min_displayed if min_displayed is not None else cfg["min_displayed_cards"]
    eff_min = min(eff_min, eff_final)

    if not pool:
        return []

    # Relevance-Tokens nur einmal pro Anruf berechnen.
    q_tokens = _tokenize_query(query or "")

    # Schritt 1: Bei type-focus strikt filtern.
    working: list[dict[str, Any]] = list(pool)
    if intent_kind == "type-focus" and wanted_content_types:
        before = len(working)
        working = _filter_to_wanted_content_types(working, wanted_content_types)
        logger.info(
            "select_final_cards type-focus filter: %d → %d (wanted=%s)",
            before, len(working), sorted(wanted_content_types),
        )

    # Schritt 2: Deterministische Reihenfolge — bei "general" Mix mit
    # innerhalb-der-Gruppe-Relevance-Sort, sonst gesamt-Relevance.
    # Bei "collection-contents" KEINE Relevance-Sortierung — die Sammlung
    # ist eine kuratierte Reihenfolge, die wollen wir nicht umstellen.
    if intent_kind == "general":
        det_order = _deterministic_mix(working, eff_final * 2, query_tokens=q_tokens)
    elif intent_kind == "type-focus":
        det_order = _sort_by_relevance(working, q_tokens)
    else:
        det_order = list(working)

    # Schritt 3: LLM-Re-Rank (wenn angegeben) — picked cards vorne, rest
    # aus der deterministischen Ordnung dahinter.
    if selected_node_ids:
        picked, _rest = _select_by_ids(working, selected_node_ids)
        # Auffüllen aus der deterministischen Ordnung (det_order), ohne
        # Duplikate.
        seen_ids = {str(c.get("node_id") or "").strip() for c in picked}
        seen_ids.discard("")
        ordered: list[dict[str, Any]] = list(picked)
        for c in det_order:
            nid = str(c.get("node_id") or "").strip()
            if nid and nid in seen_ids:
                continue
            ordered.append(c)
            if nid:
                seen_ids.add(nid)
    else:
        ordered = det_order

    # Schritt 4: Auf final_size schneiden, aber sicherstellen dass min_displayed
    # erreicht wird (falls Pool reicht).
    target = max(eff_min, 1) if len(ordered) >= eff_min else len(ordered)
    target = min(eff_final, max(target, len(ordered[:eff_final])))
    out = ordered[:target]

    logger.info(
        "select_final_cards: intent=%s pool=%d → %d (final=%d, min=%d, "
        "llm_pick=%s)",
        intent_kind, len(pool), len(out), eff_final, eff_min,
        bool(selected_node_ids),
    )
    return out


def summarize_pipeline_result(result: dict[str, Any]) -> str:
    """Eine kompakte, log-freundliche Zusammenfassung des Pipeline-Outputs.

    Format: ``[v2] intent=X pool=N>M>K | TYPE/ID/title-30 | ...``

    Schreibt jede Card als ``TYPE/ID/Titel-gekuerzt-30-Zeichen``. Wird vom
    A/B-Log in chat.py geloggt — leicht grep-bar, gut diff-bar gegen die
    v1-Liste. Bewusst ASCII-only ("``>``" statt Unicode-Pfeil), damit der
    Log auf jedem Stdout sauber landet (Windows-CP1252 inklusive).
    """
    parts: list[str] = []
    for c in result.get("cards") or []:
        nt = str(c.get("node_type") or "")[:3]  # tp/col/con
        nid = str(c.get("node_id") or "")[:8]
        t = str(c.get("title") or "")[:30]
        parts.append(f"{nt}/{nid}/{t}")
    return (
        f"[v2] intent={result.get('intent_kind', '?')} "
        f"pool={result.get('pool_size', 0)}>"
        f"{result.get('normalized_size', 0)}>"
        f"{result.get('final_size', 0)} | "
        + " | ".join(parts)
    )
