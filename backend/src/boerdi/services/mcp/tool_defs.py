"""Statische MCP-Tool-Schemas + Argument-Validierung.

1:1-Port aus ALT ``app/services/mcp_tool_defs.py``: die OpenAI-Tool-Definitionen,
das Tool->Pydantic-Model-Mapping, die JSON-fähigen Tools und die reine
``validate_tool_args``-Funktion. Kein geteilter Laufzeit-Zustand — der pure Leaf
des ``services/mcp``-Pakets. Deviation ggü. ALT: die Argument-Modelle kommen aus
der Neubau-Fassade ``boerdi.api.schemas`` statt aus ``app.models.schemas``.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from boerdi.api.schemas import (
    CollectionContentsArgs,
    CollectionTreeArgs,
    HealthCheckArgs,
    LookupVocabularyArgs,
    NodeDetailsArgs,
    NodesDetailsArgs,
    SearchTopicPagesArgs,
    SearchWloArgs,
    SubjectPortalsArgs,
)

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
}


# All 10 WLO MCP tools v2 (for OpenAI function calling)
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_wlo_collections",
            "description": "Search WirLernenOnline (WLO) for Sammlungen (= Themenseiten) — kuratierte thematische Seiten, die Lerninhalte buendeln. Sammlungen koennen NICHT nach Inhaltstyp (Video/Arbeitsblatt/...) gefiltert werden — dafuer search_wlo_content verwenden.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Suchanfrage auf Deutsch, z.B. 'Klimawandel' oder 'Algebra'. Leer lassen fuer Top-Level-Sammlungen."},
                    "parentNodeId": {"type": "string", "description": "NodeId einer Eltern-Sammlung, um darin zu suchen. Leer fuer Suche ab WLO-Root."},
                    "educationalContext": {"type": "string", "description": "Bildungsstufe als Label ODER URI — z.B. 'Primarstufe', 'Sekundarstufe I', 'Sekundarstufe II', 'Hochschule'. Mappe Klassenangaben IMMER auf eine Bildungsstufe (Kl. 1-4=Grundschule, 5-10=Sek I, 11-13=Sek II). Eine Filterebene 'Klassenstufe' existiert NICHT."},
                    "discipline": {"type": "string", "description": "Fach/Schulfach als Label ODER URI — z.B. 'Mathematik', 'Biologie', 'Informatik', 'Deutsch'."},
                    "userRole": {"type": "string", "description": "Zielgruppe als Label ODER URI — z.B. 'Lehrer/in', 'Lerner/in', 'Eltern'."},
                    "maxResults": {"type": "integer", "description": "Anzahl Treffer (1-20, Default 5)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_wlo_content",
            "description": "Search WirLernenOnline (WLO) for einzelne Lerninhalte (Arbeitsblaetter, Videos, interaktive Medien, Unterrichtsplaene, Quizze, Bilder, Kurse, ...). Nutze diese Funktion wenn der Nutzer nach einem konkreten Inhaltstyp fragt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Suchanfrage auf Deutsch, z.B. 'Bruchrechnung Grundschule' oder 'Klimawandel interaktiv'."},
                    "educationalContext": {"type": "string", "description": "Bildungsstufe als Label ODER URI — z.B. 'Primarstufe', 'Sekundarstufe I', 'Sekundarstufe II', 'Hochschule', 'Berufliche Bildung'. Mappe Klassenangaben IMMER auf eine Bildungsstufe (Kl. 1-4=Grundschule, 5-10=Sek I, 11-13=Sek II). Eine Filterebene 'Klassenstufe' existiert NICHT."},
                    "discipline": {"type": "string", "description": "Fach/Schulfach als Label ODER URI — z.B. 'Mathematik', 'Biologie', 'Deutsch', 'Informatik'."},
                    "userRole": {"type": "string", "description": "Zielgruppe als Label ODER URI — z.B. 'Lehrer/in', 'Lerner/in'."},
                    "learningResourceType": {"type": "string", "description": "Inhaltstyp / Lernressourcentyp (lrt) als Label ODER URI — z.B. 'Video', 'Arbeitsblatt', 'Bild', 'Interaktives medium', 'Unterrichtsplan', 'Quiz', 'Audio', 'Kurs'. PFLICHT wenn der Nutzer einen Inhaltstyp nennt. Labels aus lookup_wlo_vocabulary(vocabulary='lrt'). Ohne diesen Filter kommen gemischte Treffer zurueck."},
                    "publisher": {"type": "string", "description": "Anbieter-Filter, z.B. 'Klexikon', 'ZUM', 'Serlo', 'Khan Academy'."},
                    "maxResults": {"type": "integer", "description": "Anzahl Treffer (1-20, Default 8)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_wlo_topic_pages",
            "description": "Themenseiten suchen oder pruefen ob eine Sammlung eine Themenseite hat. Themenseiten sind kuratierte Seiten-Layouts mit Swimlanes, zugeschnitten auf Zielgruppen (Lehrkraefte, Lernende, Allgemein). Nutze per query fuer Themen-Suche oder per collectionId um eine konkrete Sammlung zu pruefen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Thematische Suchanfrage, z.B. 'Physik' oder 'Farben'. Leer lassen um alle aufzulisten."},
                    "collectionId": {"type": "string", "description": "NodeId einer Sammlung, um direkt zu pruefen ob sie eine Themenseite hat."},
                    "targetGroup": {"type": "string", "enum": ["teacher", "learner", "general"], "description": "Zielgruppe: teacher (Lehrkraefte), learner (Lernende), general (Allgemein)"},
                    "educationalContext": {"type": "string", "description": "Bildungsstufe, z.B. 'Grundschule', 'Sekundarstufe I'"},
                    "maxResults": {"type": "integer", "description": "Max. Ergebnisse (1-20, Standard 5)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_wlo_all",
            "description": "KOMBINIERTE WLO-Suche: liefert einzelne Lerninhalte, Sammlungen UND Themenseiten in EINEM Aufruf (intern parallel). BEVORZUGT diese Funktion nutzen statt search_wlo_content + search_wlo_collections nacheinander aufzurufen — das spart Zeit. Gibt getrennte Toepfe zurueck (content / collections / topicPages). Filter wie bei search_wlo_content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Suchanfrage auf Deutsch, z.B. 'Bruchrechnung Klasse 7' oder 'Klimawandel'."},
                    "educationalContext": {"type": "string", "description": "Bildungsstufe als Label ODER URI — Klassenangaben IMMER auf Bildungsstufe mappen (Kl. 1-4=Grundschule, 5-10=Sek I, 11-13=Sek II)."},
                    "discipline": {"type": "string", "description": "Fach/Schulfach als Label ODER URI, z.B. 'Mathematik', 'Biologie'."},
                    "userRole": {"type": "string", "description": "Zielgruppe als Label ODER URI, z.B. 'Lehrer/in', 'Lerner/in'."},
                    "learningResourceType": {"type": "string", "description": "Inhaltstyp (lrt) als Label ODER URI — nur setzen wenn der Nutzer einen Typ nennt (Video, Arbeitsblatt, ...)."},
                    "publisher": {"type": "string", "description": "Anbieter-Filter, z.B. 'Klexikon', 'Serlo'."},
                    "maxContent": {"type": "integer", "description": "Max. Einzel-Inhalte (Default 8)."},
                    "maxCollections": {"type": "integer", "description": "Max. je Sammlungen/Themenseiten (Default 5)."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_topic_page_content",
            "description": "INHALTE EINER THEMENSEITE abrufen: liefert die Abschnitte (Schwimmlinien) einer Themenseite — je Schwimmlinie Ueberschrift + die echten Inhalts-Karten (Top-Treffer der jeweiligen Widget-Abfrage) + einen Absprung-Link auf die Themenseite. Nutze NACH search_wlo_topic_pages mit der collectionId (oder variantId) der gefundenen Themenseite.",
            "parameters": {
                "type": "object",
                "properties": {
                    "collectionId": {"type": "string", "description": "NodeId der Themenseiten-Sammlung (aus search_wlo_topic_pages)."},
                    "variantId": {"type": "string", "description": "Optional: konkrete Varianten-NodeId (schneller als collectionId)."},
                    "targetGroup": {"type": "string", "enum": ["teacher", "learner", "general"], "description": "Beim Aufloesen per collectionId die Variante dieser Zielgruppe waehlen."},
                    "maxPerSwimlane": {"type": "integer", "description": "Max. Inhalts-Karten je Schwimmlinie (Default 3)."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_collection_contents",
            "description": "Inhalte und/oder Sub-Sammlungen einer WLO-Sammlung (Themenseite) per nodeId abrufen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nodeId": {"type": "string", "description": "NodeId der Sammlung (aus search_wlo_collections)"},
                    "query": {"type": "string", "description": "Optionale Such-/Filter-Anfrage, um Ergebnisse innerhalb der Sammlung zu re-ranken."},
                    "contentFilter": {"type": "string", "enum": ["files", "folders", "both"], "description": "files = Lernmaterialien (Default), folders = Sub-Sammlungen, both = alles"},
                    "includeSubcollections": {"type": "boolean", "description": "Wenn true: Sub-Sammlungen rekursiv durchsuchen (nur fuer contentFilter=files)"},
                    "maxResults": {"type": "integer", "description": "Max. Treffer (1-100, Default 20)"},
                    "skipCount": {"type": "integer", "description": "Pagination-Offset (Default 0)"},
                },
                "required": ["nodeId"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_node_details",
            "description": "Get detailed metadata for a specific WLO content node.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nodeId": {"type": "string", "description": "Node ID"},
                },
                "required": ["nodeId"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_wlo_vocabulary",
            "description": "Look up valid filter values for WLO search. Use 'discipline' for subjects, 'educationalContext' for education levels, 'lrt' for resource types, 'userRole' for target groups. Returns entries with URIs — use the URI as the filter value on search_wlo_content / search_wlo_collections (resourceType / educationalLevel / discipline).",
            "parameters": {
                "type": "object",
                "properties": {
                    "vocabulary": {
                        "type": "string",
                        "enum": ["educationalContext", "discipline", "userRole", "lrt", "license", "targetGroup"],
                        "description": "Which vocabulary to look up. educationalContext=Bildungsstufen, discipline=Fächer, lrt=Lernressourcentypen, userRole=Zielgruppen, license=CC-Lizenzen, targetGroup=Themenseiten-Zielgruppen.",
                    },
                },
                "required": ["vocabulary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_subject_portals",
            "description": (
                "Listet die WLO-Fachportale — die Top-Level-Sammlungen direkt unter dem WLO-Wurzelknoten "
                "(Mathematik, Informatik, Deutsch, Biologie, …). Nutze dies, um dem Nutzer einen Überblick "
                "über alle abgedeckten Fächer zu geben oder als Einstiegspunkt für einen geführten Drilldown. "
                "Liefert pro Portal nodeId, Name, Beschreibung, optional Themenseiten-URL und Anzahl der "
                "Sub-Sammlungen."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "educationalContext": {
                        "type": "string",
                        "description": "Optionaler Filter, z.B. 'Sekundarstufe I'.",
                    },
                    "includeContentCounts": {
                        "type": "boolean",
                        "description": "Wenn true, fügt pro Portal die Anzahl der direkten Sub-Sammlungen hinzu.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_collection_tree",
            "description": (
                "Strukturierter Drilldown unter eine Sammlung. Liefert die direkten Sub-Sammlungen "
                "(depth=1) oder zwei Ebenen (depth=2), optional mit der Anzahl Files je Sub-Sammlung. "
                "Nutze für 'Zeig mir Themenbereiche unter Mathematik', NICHT für die Files selbst — "
                "dafür ist get_collection_contents zuständig."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nodeId": {
                        "type": "string",
                        "description": "UUID der Eltern-Sammlung im Format 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'. NIEMALS einen Fach-Namen wie 'Informatik' oder 'Mathe' uebergeben — das funktioniert nicht. NIEMALS eine UUID aus Tool-Beschreibungen oder Beispielen kopieren — die zeigen NICHT auf das vom User gewuenschte Fach. Wenn nur ein Fach-Name vorliegt, ZUERST get_subject_portals aufrufen, in dessen Antwort den Eintrag mit `title == <Fachname>` finden und DESSEN nodeId hier uebergeben.",
                    },
                    "depth": {
                        "type": "integer",
                        "description": "1=direkte Kinder (schnell, Default), 2=auch Enkel (mehr API-Calls)",
                    },
                    "includeContentCounts": {
                        "type": "boolean",
                        "description": "Wenn true, holt die Anzahl Files pro Sub-Sammlung (Extra-Round-Trip).",
                    },
                    "maxResults": {
                        "type": "integer",
                        "description": "Max. Sub-Sammlungen auf Top-Level (1-100, Default 50)",
                    },
                },
                "required": ["nodeId"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wlo_health_check",
            "description": (
                "Probt die WLO-Repository-API auf Erreichbarkeit. Liefert ok-Status, Latenz und den "
                "Wurzel-Knoten zurück. Nützlich um 'WLO ist down' von 'keine Treffer für deine Anfrage' "
                "zu unterscheiden."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_nodes_details",
            "description": (
                "Bulk-Abfrage von Metadaten für mehrere nodeIds parallel (max. 50). Spart Round-Trips, "
                "wenn man Details für viele bereits gefundene Karten braucht. Liefert dieselbe Feldmenge "
                "wie get_node_details mit outputFormat='json' — disciplines/educationalContexts als Labels."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nodeIds": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Liste von Node-IDs (max. 50)",
                    },
                },
                "required": ["nodeIds"],
            },
        },
    },
]


def validate_tool_args(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Validate and clean tool arguments using Pydantic models.

    Returns the validated arguments as a dict (with defaults applied,
    empty strings stripped). Passes through unchanged if no model is registered.
    """
    model = _TOOL_ARG_MODELS.get(tool_name)
    if not model:
        return arguments
    try:
        validated = model.model_validate(arguments)
        # Export only non-empty values (strip empty optional strings).
        # Nur LEERE STRINGS strippen — explizite False/0-Werte behalten
        # (``v != 0`` fraß wegen ``False == 0`` auch Bool-False, C7).
        return {
            k: v for k, v in validated.model_dump().items()
            if v != "" or (k in model.model_fields and model.model_fields[k].is_required())
        }
    except ValidationError as e:
        logger.warning("Tool arg validation for %s: %s — using raw args", tool_name, e)
        return arguments


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
})
