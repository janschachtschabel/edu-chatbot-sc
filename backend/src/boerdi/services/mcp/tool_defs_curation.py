"""Katalog der kuratierenden MCP-Werkzeuge (E2) — 14 Definitionen.

Eigenes Modul und nicht in ``tool_defs.py``, aus einem Grund, der über die
Dateigröße hinausgeht: dieser Katalog hat einen **anderen Änderungsgrund** und
eine **andere Sichtbarkeitsregel**. Die Werkzeuge dort werden dem Modell
angeboten, sobald ein Muster sie zulässt; die hier zusätzlich nur, wenn ein
Zugangsblock hinterlegt ist (C3). Beides in einer Liste zu führen hieße, die
Regel bei jedem Zugriff mitzudenken.

**Zwei Auslassungen, beide Absicht:**

* ``confirmToken`` steht in keinem Schema. Er kommt ausschließlich von uns —
  ``domain/write_confirm`` entfernt einen selbst gesetzten und setzt den echten
  erst im Folgezug ein. Im Schema angeboten würde er zum Erfinden einladen.
* ``outputFormat`` steht ebenfalls nicht drin: die kuratierenden Werkzeuge
  führen es gar nicht (live an ``tools/list`` geprüft), sie antworten in Prosa.
  Genau davon lebt die Vorschau — und davon, dass ``_JSON_CAPABLE_TOOLS`` sie
  nicht enthält.

Die Beschreibungen sind die Server-Texte plus boerdi-eigene Führung (wann NICHT,
und was die Vorschau bedeutet) — dieselbe Konvention wie bei den
Einordnungs-Werkzeugen in ``tool_defs.py``.

Zur Länge (über der 300-Zeilen-Marke, wie der Nachbar ``tool_defs.py``): das hier
ist ein **Datenkatalog mit einem Änderungsgrund** — die kuratierende Oberfläche
des Servers. Ein Schnitt müsste ihn willkürlich in der Mitte teilen; die Marke
ist der Anlass zum Prüfen, nicht der Befund.
"""

from __future__ import annotations

from boerdi.api.schemas import (
    CollectionCreateArgs,
    CollectionMembershipArgs,
    CollectionRenameArgs,
    CompendiumUpdateArgs,
    ContentCreateArgs,
    ContentSubmitArgs,
    ContentUpdateArgs,
    MetadataSuggestArgs,
    NodeOnlyArgs,
    SuggestionDecideArgs,
    SuggestionsListArgs,
    TopicPageSetArgs,
)

# Satz, der in jeder Beschreibung eines zweistufigen Werkzeugs steht. Ohne ihn
# liest das Modell die Vorschau als Fehlschlag und versucht es erneut, statt den
# Nutzer entscheiden zu lassen — und genau die Entscheidung ist ihr Zweck.
#
# S4 (2026-08-11): Der Satz sagte bis dahin „Zeige dem Nutzer, was sich aendern
# wuerde". Seit S2 tut das der Chat selbst — der Vorschautext des Servers wird
# woertlich als gerahmter Kasten vorgelegt. Die alte Fassung hiesse jetzt: zeig
# es ein zweites Mal, in eigenen Worten. Der Zwilling dieses Satzes ist die
# Kernregel von M18 im Seed; beide sprechen zum selben Modell und muessen
# dasselbe sagen (Waechter: ``test_keine_beschreibung_verlangt_die_nacherzaehlung``
# und ``test_m18_laesst_die_vorschau_zeigen_statt_nacherzaehlen``).
_ZWEISTUFIG = (
    " ZWEISTUFIG: Dein Aufruf loest NUR eine Vorschau aus — es wird nichts "
    "geschrieben. Den Vorschautext legt der Chat dem Nutzer selbst vor, "
    "woertlich und mit Rueckfrage; erzaehle ihn NICHT nach, sondern ordne ihn "
    "in EINEM Satz ein. Stimmt der Nutzer zu, rufe dasselbe Werkzeug im "
    "NAECHSTEN Zug mit denselben Argumenten erneut auf; die Bestaetigung wird "
    "dann ergaenzt. Erfinde keinen confirmToken und behaupte nie, etwas sei "
    "schon geaendert."
)

_TEXTFELDER = {
    "title": {"type": "string", "description": "Titel des Materials."},
    "description": {"type": "string", "description": "Kurzbeschreibung."},
    "keywords": {
        "type": "array", "items": {"type": "string"},
        "description": "Schlagworte.",
    },
    "url": {"type": "string", "description": "Quell-URL des Materials."},
    "language": {"type": "string", "description": "Sprache, z.B. 'de'."},
    "author": {"type": "string", "description": "Urheber."},
    "publisher": {"type": "string", "description": "Anbieter."},
    "licenseKey": {"type": "string", "description": "Lizenz, z.B. 'CC_BY'."},
    "licenseVersion": {"type": "string", "description": "Lizenzversion, z.B. '4.0'."},
    "contentType": {"type": "string", "description": "Inhaltstyp/Medientyp."},
    "educationalContext": {"type": "string", "description": "Bildungsstufe."},
    "discipline": {"type": "string", "description": "Fach."},
    "userRole": {"type": "string", "description": "Zielgruppe, z.B. 'Lehrer'."},
    "content": {"type": "string", "description": "Der Inhalt selbst, als Text."},
    "contentFormat": {
        "type": "string", "enum": ["markdown", "text"],
        "description": "Format von content.",
    },
    "fileBase64": {"type": "string", "description": "Datei-Inhalt base64-kodiert."},
}


def _fn(name: str, beschreibung: str, eigenschaften: dict, pflicht: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": beschreibung,
            "parameters": {
                "type": "object",
                "properties": eigenschaften,
                "required": pflicht,
            },
        },
    }


CURATION_TOOL_DEFINITIONS = [
    _fn(
        "wlo_create_content",
        "Legt ein NEUES Material im WLO-Repositorium an. Nutze das erst, wenn "
        "die Suche belegt hat, dass es das Material noch nicht gibt — WLO ist "
        "ein kuratierter Bestand, kein Ablageort fuer Duplikate."
        + _ZWEISTUFIG,
        _TEXTFELDER,
        ["title"],
    ),
    _fn(
        "wlo_update_content",
        "Aendert die Metadaten oder den Inhalt eines vorhandenen Materials. Nur "
        "die Felder angeben, die sich aendern sollen; alles andere bleibt "
        "stehen. Fuer das blosse Vorschlagen einer Korrektur ohne eigene "
        "Schreibhoheit ist wlo_suggest_metadata der richtige Weg."
        + _ZWEISTUFIG,
        {
            "nodeId": {"type": "string", "description": "nodeId des Materials."},
            **_TEXTFELDER,
            "commit": {
                "type": "boolean",
                "description": "Neue Version anlegen. Standard: nein.",
            },
            "versionComment": {
                "type": "string", "description": "Kommentar zur neuen Version.",
            },
        },
        ["nodeId"],
    ),
    _fn(
        "wlo_delete_content",
        "Loescht ein Material. Das ist nicht rueckgaengig zu machen — frage im "
        "Zweifel nach, ob wirklich geloescht und nicht nur aus einer Sammlung "
        "entfernt werden soll (dafuer wlo_remove_from_collection)."
        + _ZWEISTUFIG,
        {"nodeId": {"type": "string", "description": "nodeId des Materials."}},
        ["nodeId"],
    ),
    _fn(
        "wlo_submit_content",
        "Reicht ein Material zur redaktionellen Pruefung ein. Danach entscheidet "
        "die Redaktion; der Beitrag ist nicht sofort veroeffentlicht."
        + _ZWEISTUFIG,
        {
            "nodeId": {"type": "string", "description": "nodeId des Materials."},
            "comment": {
                "type": "string",
                "description": "Hinweis an die Redaktion, z.B. warum es passt.",
            },
        },
        ["nodeId"],
    ),
    _fn(
        "wlo_create_collection",
        "Legt eine neue Sammlung an — ohne parentId auf oberster Ebene, mit "
        "parentId als Untersammlung. Pruefe vorher mit der Suche, ob es eine "
        "passende Sammlung schon gibt." + _ZWEISTUFIG,
        {
            "title": {"type": "string", "description": "Titel der Sammlung."},
            "description": {"type": "string", "description": "Beschreibung."},
            "parentId": {
                "type": "string",
                "description": "nodeId der Eltern-Sammlung. Leer = oberste Ebene.",
            },
        },
        ["title"],
    ),
    _fn(
        "wlo_rename_collection",
        "Aendert Titel und Beschreibung einer Sammlung." + _ZWEISTUFIG,
        {
            "nodeId": {"type": "string", "description": "nodeId der Sammlung."},
            "title": {"type": "string", "description": "Neuer Titel."},
            "description": {"type": "string", "description": "Neue Beschreibung."},
        },
        ["nodeId", "title"],
    ),
    _fn(
        "wlo_delete_collection",
        "Loescht eine Sammlung. Die enthaltenen Materialien bleiben bestehen — "
        "eine Sammlung haelt Verweise. Nicht rueckgaengig zu machen."
        + _ZWEISTUFIG,
        {"nodeId": {"type": "string", "description": "nodeId der Sammlung."}},
        ["nodeId"],
    ),
    _fn(
        "wlo_add_to_collection",
        "Nimmt ein Material in eine Sammlung auf. Eine Sammlung enthaelt "
        "Verweise: es wird nichts verschoben und nichts kopiert, dasselbe "
        "Material kann in mehreren Sammlungen stehen." + _ZWEISTUFIG,
        {
            "collectionId": {"type": "string", "description": "nodeId der Sammlung."},
            "nodeId": {"type": "string", "description": "nodeId des Materials."},
        },
        ["collectionId", "nodeId"],
    ),
    _fn(
        "wlo_remove_from_collection",
        "Nimmt ein Material wieder aus einer Sammlung. Das Material selbst "
        "bleibt im Bestand — zum wirklichen Loeschen gibt es wlo_delete_content."
        + _ZWEISTUFIG,
        {
            "collectionId": {"type": "string", "description": "nodeId der Sammlung."},
            "nodeId": {"type": "string", "description": "nodeId des Materials."},
        },
        ["collectionId", "nodeId"],
    ),
    _fn(
        "wlo_update_compendium",
        "Setzt oder loescht den Kompendiumstext einer Sammlung — die "
        "redaktionelle Einfuehrung, die Nutzer oben auf der Sammlung lesen. "
        "Hole mit get_compendium_text erst den vorhandenen Text, sonst "
        "ueberschreibst du fremde Redaktionsarbeit." + _ZWEISTUFIG,
        {
            "nodeId": {"type": "string", "description": "nodeId der Sammlung."},
            "text": {"type": "string", "description": "Der neue Text (Markdown)."},
            "remove": {
                "type": "boolean",
                "description": "Vorhandenen Text loeschen statt ersetzen.",
            },
        },
        ["nodeId"],
    ),
    _fn(
        "wlo_set_topic_page",
        "Macht eine Sammlung zur Themenseite einer Variante. ACHTUNG: das "
        "Ergebnis ist SOFORT oeffentlich sichtbar — anders als bei den uebrigen "
        "Werkzeugen gibt es keine redaktionelle Zwischenstufe. Sag dem Nutzer "
        "das ausdruecklich, bevor er zustimmt." + _ZWEISTUFIG,
        {
            "collectionId": {"type": "string", "description": "nodeId der Sammlung."},
            "variantId": {"type": "string", "description": "Kennung der Variante."},
        },
        ["collectionId", "variantId"],
    ),
    _fn(
        "wlo_suggest_metadata",
        "Schlaegt Metadaten-Aenderungen zu einem Material VOR, ohne sie "
        "anzuwenden — eine Person der Redaktion entscheidet darueber. Der "
        "richtige Weg, wenn dir an fremdem Material etwas auffaellt. Jeder "
        "Vorschlag braucht eine Begruendung: daran entscheidet die pruefende "
        "Person." + _ZWEISTUFIG,
        {
            "nodeId": {"type": "string", "description": "nodeId des Materials."},
            "suggestions": {
                "type": "array",
                "description": "Die Vorschlaege.",
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {
                            "type": "string",
                            "enum": [
                                "title", "description", "keywords", "url",
                                "language", "author", "publisher", "licenseKey",
                                "licenseVersion", "contentType",
                                "educationalContext", "discipline", "userRole",
                            ],
                            "description": "Welches Feld.",
                        },
                        "value": {"type": "string", "description": "Der Vorschlag."},
                        "reason": {
                            "type": "string",
                            "description": "Warum das besser ist. Pflicht.",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Wie sicher (0-1). Weglassen, wenn unklar.",
                        },
                    },
                    "required": ["field", "value", "reason"],
                },
            },
        },
        ["nodeId", "suggestions"],
    ),
    _fn(
        "wlo_list_suggestions",
        "Listet die Metadaten-Vorschlaege zu einem Material auf. Aendert "
        "nichts — als einziges Werkzeug dieser Gruppe ohne Vorschau-Schritt. "
        "Nutze es, bevor du etwas vorschlaegst: vielleicht liegt derselbe "
        "Vorschlag schon in der Warteschlange.",
        {
            "nodeId": {"type": "string", "description": "nodeId des Materials."},
            "status": {
                "type": "string", "enum": ["PENDING", "ACCEPTED", "DECLINED"],
                "description": "Nur Vorschlaege in diesem Zustand.",
            },
        },
        ["nodeId"],
    ),
    _fn(
        "wlo_decide_suggestion",
        "Nimmt einen Metadaten-Vorschlag an oder lehnt ihn ab. Das ist eine "
        "redaktionelle Entscheidung ueber die Arbeit einer anderen Person — "
        "triff sie nie von dir aus, sondern nur auf ausdruecklichen Wunsch."
        + _ZWEISTUFIG,
        {
            "nodeId": {"type": "string", "description": "nodeId des Materials."},
            "suggestionId": {"type": "string", "description": "Kennung des Vorschlags."},
            "decision": {
                "type": "string", "enum": ["accept", "decline"],
                "description": "annehmen oder ablehnen.",
            },
        },
        ["nodeId", "suggestionId", "decision"],
    ),
]


# Werkzeugname -> Argument-Modell. Wird in ``tool_defs._TOOL_ARG_MODELS``
# eingemischt, damit ``validate_tool_args`` eine Anlaufstelle bleibt.
CURATION_ARG_MODELS: dict[str, type] = {
    "wlo_create_content":         ContentCreateArgs,
    "wlo_update_content":         ContentUpdateArgs,
    "wlo_delete_content":         NodeOnlyArgs,
    "wlo_submit_content":         ContentSubmitArgs,
    "wlo_create_collection":      CollectionCreateArgs,
    "wlo_rename_collection":      CollectionRenameArgs,
    "wlo_delete_collection":      NodeOnlyArgs,
    "wlo_add_to_collection":      CollectionMembershipArgs,
    "wlo_remove_from_collection": CollectionMembershipArgs,
    "wlo_update_compendium":      CompendiumUpdateArgs,
    "wlo_set_topic_page":         TopicPageSetArgs,
    "wlo_suggest_metadata":       MetadataSuggestArgs,
    "wlo_list_suggestions":       SuggestionsListArgs,
    "wlo_decide_suggestion":      SuggestionDecideArgs,
}
