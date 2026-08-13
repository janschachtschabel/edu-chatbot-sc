"""Wie ein MCP-Aufruf geformt wird: Argument-Modelle, Validierung, Deckel.

Aus ``tool_defs`` herausgelöst — dort steht seither nur noch der Katalog, den das
Modell zu sehen bekommt. Die Trennlinie ist die Frage, die beide beantworten:
``tool_defs`` sagt WELCHE Werkzeuge es gibt, dieses Modul sagt, wie ein Aufruf
gültig aussieht. ``client.py`` braucht ausschliesslich diese Seite.

1:1-Port aus ALT ``app/services/mcp_tool_defs.py``. Kein geteilter Laufzeit-
Zustand. Deviation ggü. ALT: die Argument-Modelle kommen aus der Neubau-Fassade
``boerdi.api.schemas`` statt aus ``app.models.schemas``.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from boerdi.api.schemas import (
    AuthStatusArgs,
    CollectionContentsArgs,
    CollectionStatsArgs,
    CollectionTreeArgs,
    CompendiumTextArgs,
    HealthCheckArgs,
    LookupVocabularyArgs,
    NodeBreadcrumbArgs,
    NodeCollectionsArgs,
    NodeDetailsArgs,
    NodesDetailsArgs,
    PublishersLookupArgs,
    RelatedContentArgs,
    SearchTopicPagesArgs,
    SearchWloArgs,
    SkillGetArgs,
    SkillRegistryArgs,
    SkillSearchArgs,
    SubjectPortalsArgs,
    UrlTextArgs,
    WikipediaSummaryArgs,
    WithinCollectionArgs,
)
from boerdi.services.mcp.tool_defs_curation import CURATION_ARG_MODELS

logger = logging.getLogger(__name__)


# Map tool names to their Pydantic argument models. Reflects the MCP
# server v2 toolkit (10 tools) — the four web-content scrapers from v1
# have been removed because RAG handles those topics in Boerdi.
_TOOL_ARG_MODELS: dict[str, type] = {
    "search_wlo_collections": SearchWloArgs,
    "search_wlo_content":     SearchWloArgs,
    "search_wlo_topic_pages": SearchTopicPagesArgs,
    "get_collection_contents":CollectionContentsArgs,
    "get_node_details":       NodeDetailsArgs,
    "lookup_wlo_vocabulary":  LookupVocabularyArgs,
    "get_subject_portals":    SubjectPortalsArgs,
    "browse_collection_tree": CollectionTreeArgs,
    "wlo_health_check":       HealthCheckArgs,
    "get_nodes_details":      NodesDetailsArgs,
    # W9a (2026-08-01), Server-Schemata per ``tools/list`` geholt.
    "get_collection_stats":   CollectionStatsArgs,
    "get_node_breadcrumb":    NodeBreadcrumbArgs,
    "get_compendium_text":    CompendiumTextArgs,
    "lookup_wlo_publishers":  PublishersLookupArgs,
    # W9b: die zwei Karten-Werkzeuge.
    "search_wlo_within_collection": WithinCollectionArgs,
    "get_related_content":    RelatedContentArgs,
    # A2 (2026-08-10): Verortung eines Materials.
    "get_node_collections":   NodeCollectionsArgs,
    # D1 (2026-08-10): Anleitungen aus dem Bestand.
    "search_skill":           SkillSearchArgs,
    "get_skill":              SkillGetArgs,
    # H9 (2026-08-10): die Freigabeliste EINER Sammlung.
    "get_skill_registry":     SkillRegistryArgs,
    # H5 (2026-08-10): offenes Netz + Anmeldestatus.
    "get_url_text":           UrlTextArgs,
    "get_wikipedia_summary":  WikipediaSummaryArgs,
    "wlo_auth_status":        AuthStatusArgs,
    # E2 (2026-08-10): die kuratierende Oberfläche. Ihre Definitionen wohnen in
    # ``tool_defs_curation`` (eigene Sichtbarkeitsregel — nur mit Zugangsblock),
    # die Argument-Modelle werden hier eingemischt, damit ``validate_tool_args``
    # die eine Anlaufstelle bleibt. Ohne Modell reicht sie Rohargumente durch —
    # bei einem Schreibwerkzeug wäre das die Stelle, an der ein vertippter
    # Feldname unbemerkt zum Server geht.
    **CURATION_ARG_MODELS,
}


def _export_non_empty(model: type, validated: Any) -> dict[str, Any]:
    """Export only non-empty values (strip empty optional strings).

    Nur LEERE STRINGS strippen — explizite False/0-Werte behalten
    (``v != 0`` fraß wegen ``False == 0`` auch Bool-False, C7).
    """
    return {
        k: v for k, v in validated.model_dump().items()
        if v != "" or (k in model.model_fields and model.model_fields[k].is_required())
    }


# W10 (2026-08-01): Ohne den Reparaturschritt unten ist jede ``Field(ge=…/le=…)``-
# Grenze bloße Dekoration — der except-Zweig reicht bei einer ValidationError die
# ROHEN Argumente weiter, ein ``maxResults: 100`` gegen ``le=20`` ging also
# ungebremst an den Server und blies den Kontext des nächsten Zuges auf. Bewusst
# nur ``ge``/``le``: ``gt``/``lt`` kommt in keinem Argument-Modell vor, und für
# eine dort erfundene Grenze wäre der bisherige Fail-Open-Pfad ehrlicher als ein
# still danebenliegender Wert.
_KLEMMBARE_GRENZEN = {"greater_than_equal": "ge", "less_than_equal": "le"}


def _clamp_bound_violations(
    arguments: dict[str, Any], exc: ValidationError
) -> dict[str, Any] | None:
    """Setzt jedes Feld mit verletzter ge/le-Grenze auf genau diese Grenze.

    Gibt ``None`` zurück, wenn kein einziger Fehler klemmbar war — dann bleibt es
    beim Fail-Open-Pfad. Der Feldname kommt aus der Fehlermeldung und ist deshalb
    der KANONISCHE: bei ``maxItems: 100`` meldet pydantic ``maxResults``, weil der
    Pre-Validator den Alt-Namen vorher aufgelöst hat (gemessen 2026-08-01). Der
    Alt-Name bleibt im Dict stehen und wird beim zweiten Lauf ignoriert.
    """
    geklemmt = dict(arguments)
    getroffen = False
    for err in exc.errors():
        art = _KLEMMBARE_GRENZEN.get(err.get("type") or "")
        loc = err.get("loc") or ()
        grenze = (err.get("ctx") or {}).get(art) if art else None
        if grenze is None or len(loc) != 1 or not isinstance(loc[0], str):
            continue
        geklemmt[loc[0]] = grenze
        getroffen = True
    return geklemmt if getroffen else None


def validate_tool_args(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Validate and clean tool arguments using Pydantic models.

    Returns the validated arguments as a dict (with defaults applied,
    empty strings stripped). Passes through unchanged if no model is registered.
    Überschrittene ``ge``/``le``-Grenzen werden geklemmt statt verworfen; jeder
    andere Fehler fällt weiterhin auf die Rohargumente zurück.
    """
    model = _TOOL_ARG_MODELS.get(tool_name)
    if not model:
        return arguments
    try:
        return _export_non_empty(model, model.model_validate(arguments))
    except ValidationError as e:
        geklemmt = _clamp_bound_violations(arguments, e)
        if geklemmt is not None:
            try:
                exportiert = _export_non_empty(model, model.model_validate(geklemmt))
            except ValidationError:
                pass
            else:
                logger.info(
                    "Tool-Argumente für %s auf Modellgrenzen geklemmt: %s",
                    tool_name,
                    {k: v for k, v in geklemmt.items() if arguments.get(k) != v},
                )
                return exportiert
        logger.warning("Tool arg validation for %s: %s — using raw args", tool_name, e)
        return arguments

# W5-3b: Deckel für ``get_wlo_content_text``. Der Server-Standard sind 8000
# Zeichen — live schnitt das 2 von 6 Arbeitsblättern ab, eines davon um mehr als
# die Hälfte. Nutzer-Vorgabe 2026-07-30: gar nicht abschneiden, deshalb die
# Schema-Obergrenze des Tools (``content-text.ts``: ``min(500).max(50000)``).
# Höher geht nicht — der Server lehnte einen größeren Wert ab.
#
# Bewusst in Kauf genommen: ein wirklich ausgereizter Text sind ~13-17k Tokens im
# Modell-Kontext. Das trifft nur den Volltext-Pfad (der Nutzer will dann mit dem
# Material arbeiten) und ist dort der Zweck; für Titel/Fach/Lizenz genügt
# ``get_node_details``, worauf die Tool-Beschreibung ausdrücklich hinweist.
CONTENT_TEXT_MAX_CHARS = 50000


# Tools that support `outputFormat="json"` on MCP server v2+. We auto-set
# JSON for them so callers can rely on a structured response without each
# call site repeating the parameter. Tools NOT in this set keep their
# native format (e.g. `lookup_wlo_vocabulary` only emits Markdown that
# `_ensure_label_cache` parses).
_JSON_CAPABLE_TOOLS: frozenset[str] = frozenset({
    "search_wlo_collections",
    "search_wlo_content",
    "get_collection_contents",
    "get_node_details",
    "search_wlo_topic_pages",
    "search_wlo_all",
    "get_topic_page_content",
    "get_subject_portals",
    "browse_collection_tree",
    # W5-3a: nur im JSON-Format trägt die Antwort ``reason``/``source``/
    # ``truncated``. In Markdown ist „kein Volltext" nicht von „Material ist aus
    # Rechtegründen gesperrt" zu unterscheiden — und genau daran hängt, ob der
    # Bot eine KI-Generierung anbietet oder es nochmal versucht.
    "get_wlo_content_text",
    # 2026-08-01: nur als JSON trägt die Antwort Titel und URL getrennt. Der
    # Markdown-Modus liefert eine Überschrift plus Fließtext — daraus den
    # aufgelösten Artikeltitel zurückzuparsen wäre genau die Bastelei, die der
    # Envelope erspart. Titel und URL landen in der Quellenangabe des Materials.
    "get_wikipedia_summary",
    # W9b: beide liefern Karten, die WIR parsen — nur der JSON-Envelope
    # trägt die serverseitig label-aufgelösten Felder (Fach, Stufe, Lizenz).
    "search_wlo_within_collection",
    "get_related_content",
})
