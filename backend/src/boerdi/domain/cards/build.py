"""Card construction + topic relevance (P4-5 prerequisite, port of ALT
chat_cards.py's build/relevance cluster): raw-dict -> ``WloCard`` assembly with
metadata inheritance and persona-sorted topic-page variants (``_build_cards`` /
``_sort_topic_pages`` / ``_PERSONA_TO_TARGET``) plus word-boundary title/topic
relevance (``_collection_matches_topic`` / ``_norm_words``).

The last-mile card prep the Respond/Assembly step sits on: build the display
cards and judge whether a collection actually matches the requested topic. Pure
domain logic (stdlib ``re`` + the ``WloCard`` schema); ``WloCard`` is imported
from ``boerdi.api.schemas`` — the sanctioned domain->schema import already used
by ``domain/context`` and ``domain/policy``.

The sibling chat_cards helpers live elsewhere: the used-id/diversity cluster in
``lp_diversity``. ALT's ``_apply_llm_card_selection`` (filter built cards to the LLM
``select_top_cards`` choice, in LLM order, with salvage fallback) lives here — added
when the widget-postprocess step (``_apply_widget_modes_postprocess``) needed it.

``PAGE_SIZE`` (max cards per page — the assembly's pagination threshold; ALT kept
it in ``chat_direct_actions``) and the object-form ``_is_themenseite_card``
(``getattr``-based, for built ``WloCard`` objects) live here too. The dict-form
``_is_themenseite_card`` in ``inline_grouping`` (``.get()``-based, for raw dicts)
is a *distinct* ALT sibling — both are kept verbatim.

Deviation from ALT: import roots only (``app.models.schemas`` ->
``boerdi.api.schemas``). Every function body is byte-identical (AST-diff gate);
``PAGE_SIZE`` is the verbatim constant from ALT ``chat_direct_actions``.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from boerdi.api.schemas import WloCard

logger = logging.getLogger(__name__)


def _norm_words(s: str) -> list[str]:
    """Lower-cased tokenization for title/topic relevance comparisons.

    Strips punctuation and splits on whitespace. Used by
    _collection_matches_topic to check topic-in-title with word boundaries
    (plain substring would accept 'eis' in 'eisen' etc.).
    """
    if not s:
        return []
    s = re.sub(r"[^\w\säöüÄÖÜß-]+", " ", s.lower())
    return [w for w in s.split() if w]


def _collection_matches_topic(cards: list[WloCard], topic: str) -> bool:
    """True if at least one collection title contains the topic as a word.

    Uses word-boundary matching — 'Eiszeit' would match the title
    'Eiszeit und Klimawandel', but NOT 'Eisen-Erzeugung'. Multi-word
    topics require the longest content word to appear as a full token.
    """
    if not topic or not cards:
        return False
    topic_tokens = _norm_words(topic)
    # Prefer the longest token (typically the most specific keyword)
    content = [t for t in topic_tokens if len(t) >= 4]
    if not content:
        # Topic was only stopwords / short tokens — accept conservatively
        return True
    key = max(content, key=len)
    for c in cards:
        title_tokens = _norm_words(getattr(c, "title", "") or "")
        if key in title_tokens:
            return True
        # Also allow morphological neighbours: prefix match ≥5 chars
        # (e.g. topic 'Eiszeit' ↔ title token 'Eiszeiten' / 'Eiszeitalter')
        for tt in title_tokens:
            if len(tt) >= 5 and (tt.startswith(key) or key.startswith(tt)):
                return True
    return False


# -- Card construction: raw dict -> WloCard with metadata inheritance ------
# Persona → preferred topic-page target group
_PERSONA_TO_TARGET = {
    "P-LEH": "teacher",
    "P-LER": "learner",
    "P-ELT": "learner",
    "P-RED": "teacher",   # Redaktion + Presse
    "P-ENT": "general",   # Entscheider (Verwaltung + Politik + Beratung)
    "P-AND": "general",
}


def _sort_topic_pages(pages: list[dict], persona_id: str) -> list[dict]:
    """Sort topic-page variants so the best match for the persona comes first."""
    if not pages or len(pages) <= 1:
        return pages
    preferred = _PERSONA_TO_TARGET.get(persona_id, "general")

    def _rank(tp: dict) -> int:
        tg = tp.get("target_group", "").lower()
        if tg == preferred:
            return 0  # exact match first
        if tg == "general":
            return 1  # general as fallback
        if not tg:
            return 2  # unset
        return 3  # other

    return sorted(pages, key=_rank)


def _build_cards(raw: list[dict], persona_id: str = "") -> list[WloCard]:
    # ── Metadata inheritance: Themenseiten-Karten aus search_wlo_topic_pages
    # kommen nur mit Titel + Beschreibung + Varianten zurueck (keine
    # preview_url, disciplines, educational_contexts). Wenn in derselben
    # Ergebnis-Liste eine "normale" Sammlungskarte mit derselben node_id
    # existiert, uebernehmen wir deren reichere Metadaten in die
    # Themenseiten-Karte. Ergebnis: optisch konsistente Karten mit
    # Vorschau-Bild, Fach und Bildungsstufen auf Themenseiten-Ebene.
    by_nid: dict[str, dict] = {}
    for c in raw:
        nid = c.get("node_id") or ""
        if nid and nid in by_nid:
            # Merge: richer fields of one partner fill gaps in the other.
            existing = by_nid[nid]
            for k in (
                "preview_url", "description", "disciplines",
                "educational_contexts", "keywords",
                "learning_resource_types", "license", "publisher",
                "url", "wlo_url",
                # Die Freigabeliste haengt am Treffer der Sammlungssuche; die
                # Themenseiten-Karte derselben node_id kennt sie nicht. Ohne
                # sie hier gewinnt der Erstfund mit 0.
                "skill_count",
            ):
                if not existing.get(k) and c.get(k):
                    existing[k] = c[k]
            # Merge topic_pages by variant_id (no duplicates)
            existing_tps = existing.setdefault("topic_pages", [])
            existing_vids = {v.get("variant_id") for v in existing_tps if isinstance(v, dict)}
            for v in c.get("topic_pages") or []:
                if isinstance(v, dict) and v.get("variant_id") not in existing_vids:
                    existing_tps.append(v)
                    existing_vids.add(v.get("variant_id"))
            # If the merged card now has topic_pages, ensure it's a collection.
            if existing_tps:
                existing["node_type"] = "collection"
        elif nid:
            by_nid[nid] = dict(c)

    cards = []
    seen: set[str] = set()
    # Emit in original order — first occurrence of each node_id wins position.
    for c in raw:
        nid = c.get("node_id") or ""
        if nid and nid in seen:
            continue
        if nid:
            seen.add(nid)
            merged = by_nid[nid]
        else:
            merged = c
        tp = _sort_topic_pages(merged.get("topic_pages", []), persona_id)
        cards.append(WloCard(
            node_id=merged.get("node_id", ""),
            title=merged.get("title", ""),
            description=merged.get("description", ""),
            disciplines=merged.get("disciplines", []),
            educational_contexts=merged.get("educational_contexts", []),
            keywords=merged.get("keywords", []),
            learning_resource_types=merged.get("learning_resource_types", []),
            url=merged.get("url", ""),
            wlo_url=merged.get("wlo_url", ""),
            preview_url=merged.get("preview_url", ""),
            license=merged.get("license", ""),
            publisher=merged.get("publisher", ""),
            node_type=merged.get("node_type", "content"),
            # Zaehlt die Felder einzeln auf: was hier fehlt, ist weg, egal was
            # Parser und Schema fuehren. Genau daran ist der Skill-Hinweis
            # zunaechst gescheitert (Review-Befund 2026-08-14) — Parser-Test
            # und Kachel-Test blieben gruen, weil beide neben dieser Naht
            # liegen.
            skill_count=merged.get("skill_count", 0),
            topic_pages=tp,
        ))
    return cards


# Assembly-Pagination-Schwelle — verbatim aus ALT chat_direct_actions.
PAGE_SIZE = 5  # Max cards per page


def _is_themenseite_card(c: Any) -> bool:
    """True, wenn eine Card eine Themenseite ist — in BEIDEN Repräsentationen.

    Themenseiten kommen in zwei Formen durch die Pipeline:
      * neu: ``node_type == "topic_page"`` (parse_wlo_topic_page_cards /
        _infer_node_type), Link = topic-pages-Renderer,
      * alt: ``node_type == "collection"`` mit nicht-leerer
        ``topic_pages``-Variantenliste (Sammlungs-Suche).

    Beide müssen in die Themenseiten-Box und als „echter Treffer" zählen.
    Sonst fallen Themenseiten bei der Box-Zuordnung komplett durch
    (Regression 2026-06-02: node_type-Umstellung collection→topic_page ließ
    die Themenseiten-Box leer, weil die Filter nur node_type=="collection"
    kannten).
    """
    nt = getattr(c, "node_type", "") or ""
    if nt == "topic_page":
        return True
    return nt == "collection" and bool(getattr(c, "topic_pages", None))


def _feld(c: Any, name: str, default: Any = None) -> Any:
    """Ein Kartenfeld lesen, gleich ob die Karte ein dict oder ein Objekt ist.

    ``_apply_llm_card_selection`` bekommt beide Formen (die ID-Suche darunter
    macht dasselbe von Hand). Die beiden ``_is_themenseite_card``-Geschwister
    im Bestand sind je auf EINE Form festgelegt — hier hilft keins von beiden.
    """
    return c.get(name, default) if isinstance(c, dict) else getattr(c, name, default)


def _ist_sammlungs_karte(c: Any) -> bool:
    """Karte, die in die Sammlungs-Box läuft.

    Themenseiten zählen mit (seit 15.08.2026). Vorher waren sie ausgenommen,
    weil sie ihre eigene Box haben — seit dem Optik-Befund zeigt der
    Sammlungen-Kasten Sammlungen MIT Themenseite ebenfalls, mit der
    Sammlungs-Adresse als Ziel. Zwei Folgen für den Nachzug oben:
    eine gewählte Themenseiten-Sammlung füllt den Kasten bereits (kein
    überflüssiger Nachzug mehr), und wenn nachgezogen wird, kommt die
    vorderste passende Karte des Pools — nicht die vorderste, die zufällig
    keine Themenseite hat. Genau daran scheiterte „Optik": es kam
    „Geometrische Optik".
    """
    nt = _feld(c, "node_type", "") or ""
    return nt in ("collection", "topic_page")


def _apply_llm_card_selection(
    cards: list[Any], selected_ids: list[str] | None,
) -> list[Any]:
    """Filtere ``cards`` auf die vom LLM via ``select_top_cards`` gewählten
    IDs, in der vom LLM angegebenen Reihenfolge.

    ID-Vergleich auf ``node_id``-Feld (UUID-String). Nicht-Matching-IDs
    werden ignoriert (LLM könnte mal halluziniert haben). Cards, die im
    Original sind aber NICHT in der Auswahl, werden weggelassen — der LLM
    hat sich bewusst gegen sie entschieden.

    Bei leerer/None-Selection → unveränderte Card-Liste zurückgeben
    (Caller fällt auf algorithmische Sortierung zurück).
    """
    if not selected_ids:
        return list(cards or [])
    if not cards:
        return []
    # Build node_id → card lookup
    by_id: dict[str, Any] = {}
    for c in cards:
        nid = c.get("node_id") if isinstance(c, dict) else getattr(c, "node_id", None)
        if isinstance(nid, str) and nid:
            by_id[nid] = c
    # Pick in LLM order; skip IDs the LLM produced but we can't find
    ordered: list[Any] = []
    for nid in selected_ids:
        c = by_id.get(nid)
        if c is not None:
            ordered.append(c)
    # Salvage: wenn die LLM-Auswahl ZERO matches produziert (typisch wenn
    # das Modell IDs aus früheren Turns oder Halluzinationen liefert),
    # nehmen wir lieber die ungefilterte Card-Liste als gar nichts —
    # algorithmisch sortiert ist immer noch besser als leere Inline-Liste.
    if not ordered and cards:
        logger.warning(
            "select_top_cards: %d selected IDs aber 0 Matches in %d cards — "
            "fallback auf ungefilterte Liste",
            len(selected_ids), len(cards),
        )
        return list(cards)
    # Zusicherung statt Bitte (Nutzer-Vorgabe 2026-08-14: „Die Optiksammlung
    # MUSS gefunden werden, wenn der MCP diese liefern kann"). #193 hat das
    # strukturelle Aushungern beseitigt und der Prompt bittet um die Sammlung —
    # eine Bitte ist aber keine Zusage, und was das Modell nicht wählt, sieht
    # der User nie. Hatte der Pool eine Sammlung und die Auswahl keine, kommt
    # genau EINE nach, ans Ende: die Reihenfolge des Modells bleibt vorn, und
    # die Box-Deckel in ``turn_persist`` kürzen danach wie immer.
    if ordered and not any(_ist_sammlungs_karte(c) for c in ordered):
        gewaehlt = set(selected_ids)
        nachzug = next(
            (c for c in cards
             if _ist_sammlungs_karte(c) and _feld(c, "node_id", "") not in gewaehlt),
            None,
        )
        if nachzug is not None:
            logger.info(
                "select_top_cards: Sammlung %r nachgezogen — der Pool hatte "
                "eine, die Auswahl des Modells keine",
                _feld(nachzug, "title", ""),
            )
            ordered.append(nachzug)
    return ordered
