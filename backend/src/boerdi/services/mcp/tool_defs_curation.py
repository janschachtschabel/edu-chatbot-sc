"""Katalog der kuratierenden MCP-Werkzeuge (E2) — 19 Definitionen (Stand K2d-3).

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
    CollectionsAddArgs,
    CollectionTreeCreateArgs,
    CompendiumUpdateArgs,
    ContentCreateArgs,
    ContentSubmitArgs,
    ContentsUpdateArgs,
    ContentUpdateArgs,
    FulltextAttachArgs,
    FulltextsAttachArgs,
    MetadataSuggestArgs,
    NodeOnlyArgs,
    SuggestionDecideArgs,
    SuggestionsListArgs,
    TopicPageSetArgs,
)
from boerdi.services.mcp.werte_hinzufuegen import NUR_ERSETZEN

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

#: Paket M5 (Review 2026-11-07): Pläne löst nur der Chat ein — der Satz „rufe … erneut auf“ aus
#: :data:`_ZWEISTUFIG` stimmt für sie nicht (ein erneuter Aufruf ergibt nur eine neue Vorschau).
_ZWEISTUFIG_PLAN = (
    " ZWEISTUFIG: Dein Aufruf loest NUR eine Vorschau aus — es wird nichts "
    "geschrieben. Den Vorschautext legt der Chat dem Nutzer selbst vor, "
    "woertlich und mit Rueckfrage; erzaehle ihn NICHT nach, sondern ordne ihn "
    "in EINEM Satz ein. Das Ja des Nutzers loest der Chat SELBST ein — rufe das "
    "Werkzeug danach NICHT erneut auf (das ergaebe nur eine neue Vorschau). "
    "Behaupte nie, etwas sei schon geaendert."
)

def _baumknoten(tiefe: int) -> dict:
    """Ein Knoten von ``wlo_create_collection_tree`` bis ``tiefe`` Ebenen — der Server prüft jede
    Ebene streng (``.strict()``); ein fremdes Feld tiefer unten kippte den ganzen Baum."""
    felder: dict = {"title": {"type": "string"}, "description": {"type": "string"}}
    if tiefe > 1:
        felder["children"] = {"type": "array", "items": _baumknoten(tiefe - 1)}
    return {"type": "object", "additionalProperties": False, "properties": felder,
            "required": ["title"]}


_TEXTFELDER = {
    "title": {"type": "string", "description": "Titel des Materials."},
    "description": {"type": "string", "description": "Kurzbeschreibung."},
    "keywords": {
        "type": "array", "items": {"type": "string"},
        "description": "Schlagworte; beim Aendern werden sie zu den vorhandenen ergaenzt.",
    },
    "url": {"type": "string", "description": "Quell-URL des Materials."},
    "language": {"type": "string", "description": "Sprache, z.B. 'de'."},
    "author": {"type": "string", "description": "Urheber."},
    "publisher": {"type": "string", "description": "Anbieter."},
    "licenseKey": {"type": "string", "description": "Lizenz, z.B. 'CC_BY'."},
    "licenseVersion": {"type": "string", "description": "Lizenzversion, z.B. '4.0'."},
    "contentType": {"type": "string",
                    "description": "Inhaltstyp als Bezeichnung, z.B. 'Arbeitsblatt' oder 'Audio'. "
                                   "Lehnt der Server sie ab, einen Vorschlag aus seiner "
                                   "Ablehnung nehmen (nicht nachschlagen); nennt sie zwei "
                                   "Bedeutungen oder keinen, die Person fragen."},
    "educationalContext": {"type": "string",
                           "description": "Bildungsstufe als Bezeichnung, z.B. 'Sekundarstufe I'. "
                                          "Ablehnung und Kandidaten wie beim Fach."},
    "discipline": {"type": "string",
                   "description": "Fach als Bezeichnung, z.B. 'Mathematik'. Eine unbekannte "
                                  "lehnt der Server ab und nennt Kandidaten: einen passenden "
                                  "nehmen oder die Person waehlen lassen. Die Vorschau zeigt den "
                                  "Wert, der geschrieben wuerde."},
    "userRole": {"type": "string",
                 "description": "Zielgruppe als Bezeichnung, z.B. 'Lehrer'. Ablehnung und "
                                "Kandidaten wie beim Fach."},
    "content": {"type": "string", "description": "Der Inhalt selbst, als Text."},
    "contentFormat": {
        "type": "string", "enum": ["markdown", "text"],
        "description": "Format von content.",
    },
    "fileBase64": {"type": "string", "description": "Datei-Inhalt base64-kodiert."},
}


#: Paket K2d-3: ``would_replace_file`` ist kein Fehler (Nutzer-Entscheid 2026-11-08). Seit dem
#: 14.11.2026 steht fest, dass es so bleibt (Messung des MCP-Teams, Auskunft des Nutzers): das
#: Schreiben eines Volltexts ersetzt die Datei im Inhalt. Bei einem Datensatz mit Datei gewinnt
#: das Repository den Text selbst, sobald sein Text-Endpunkt gelesen wird.
_NUR_OHNE_DATEI = (
    " Lehnt der Server einen Datensatz mit Code would_replace_file ab, ist das KEIN Fehler: der "
    "Datensatz traegt schon Inhalt (eine Datei oder einen Text), und ein geschriebener Volltext "
    "wuerde ihn ersetzen. Das bleibt so: ein Volltext laesst sich nur an einen Datensatz ohne "
    "Datei haengen; aus einer Datei gewinnt das Repository den Text selbst. Sag der Person das; "
    "es ist nichts verloren und nichts geaendert. Gemerkt wird der Text dabei NICHT — "
    "versprich kein Nachtragen. link_record heisst: ein verlinkter Datensatz, dessen Text das "
    "Repository von der Webseite liest — dort gibt es keinen eigenen Volltext."
)

_VOLLTEXT_FELDER = {
    "nodeId": {"type": "string", "description": "nodeId des Datensatzes."},
    "markdown": {"type": "string", "description": "Der Volltext als Markdown."},
    "source": {"type": "string", "enum": ["binary", "website", "manual"],
               "description": "binary = aus der Datei, website = von einer Webseite, "
                              "manual = von Hand."},
    "sourceUrl": {"type": "string", "description": "Quelle des Texts (http/https), bei website."},
    "language": {"type": "string", "description": "Sprachcode, z.B. 'de'."},
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
        "ein kuratierter Bestand, kein Ablageort fuer Duplikate. Zu einer Adresse "
        "zuerst find_content_by_url fragen (die Vorschau prueft nur die genaue "
        "Schreibweise der Adresse, bereinigte findet allein find_content_by_url). "
        "Soll das Material in eine Sammlung, "
        "addToCollectionId mitgeben — dann genuegt EINE Bestaetigung fuer Anlegen "
        "und Einsortieren (kein wlo_add_to_collection hinterher)."
        + _ZWEISTUFIG,
        {
            **_TEXTFELDER,
            "addToCollectionId": {
                "type": "string",
                "description": "Optional: nodeId der Sammlung, in die das neue Material mit "
                               "derselben Bestaetigung aufgenommen wird. Gibt es zur url schon "
                               "einen Datensatz, bietet die Vorschau an, diesen aufzunehmen.",
            },
        },
        ["title"],
    ),
    _fn(
        "wlo_update_content",
        "Aendert die Metadaten oder den Inhalt eines vorhandenen Materials. Nur "
        "die Felder angeben, die sich aendern sollen; alles andere bleibt "
        "stehen. " + NUR_ERSETZEN +
        "Die Vorschau nennt den Datensatz und zeigt je Feld alt und neu. Weicht ein Wert "
        "der Vorschau vom genannten ab, sag das. get_node_details davor nur, wenn die "
        "nodeId nicht aus dem Gespraech stammt oder die Aenderung auf dem bisherigen "
        "Wert aufbaut (Text ergaenzen, korrigieren). "
        "Fuer das blosse Vorschlagen einer Korrektur ohne eigene "
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
        "wlo_create_collection_tree",
        "Legt einen ganzen Baum von Untersammlungen unter einer Sammlung an — mit EINER "
        "Bestaetigung fuer das Ganze (statt je Sammlung). Gleichnamige vorhandene Untersammlungen "
        "werden uebernommen (onExisting=merge). Grosse Baeume arbeitet der Server in Abschnitten "
        "ab; ist danach noch etwas offen, setzt die Person den Plan ueber den Knopf 'Weiter "
        "anlegen' fort, ohne neue Bestaetigung — du setzt nicht selbst fort."
        + _ZWEISTUFIG_PLAN,
        {
            "parentCollectionId": {"type": "string", "description": "nodeId der Eltern-Sammlung."},
            "tree": {
                "type": "array",
                "items": _baumknoten(4),
                "description": "Knoten {title, description?, children?} — hoechstens 250, Tiefe 4, "
                               "15 Kinder je Knoten.",
            },
            "onExisting": {
                "type": "string", "enum": ["merge", "fail"],
                "description": "merge (Vorgabe) uebernimmt gleichnamige Untersammlungen."},
        },
        ["parentCollectionId", "tree"],
    ),
    _fn(
        "wlo_add_to_collections",
        "Nimmt bis zu 200 Materialien in Sammlungen auf — mit EINER Bestaetigung fuer alle Paare. "
        "Ein schon vorhandenes Paar zaehlt als erledigt, ein gescheitertes haelt die anderen nicht "
        "auf. Fortsetzen wie bei wlo_create_collection_tree (Knopf 'Plan fortsetzen')."
        + _ZWEISTUFIG_PLAN,
        {
            "pairs": {
                "type": "array",
                "items": {"type": "object", "properties": {
                    "nodeId": {"type": "string"}, "collectionId": {"type": "string"}},
                    "required": ["nodeId", "collectionId"]},
                "description": "Paare {nodeId des Materials, collectionId der Sammlung}, max. 200.",
            },
        },
        ["pairs"],
    ),
    _fn(
        "wlo_attach_fulltext",
        "Legt einen Volltext (Markdown) im textContent eines vorhandenen Datensatzes ab — dort, "
        "wo get_wlo_content_text ihn liest. Fuer Texte aus einer Datei, einer Webseite oder von "
        "Hand (source). replace=true ersetzt einen vorhandenen Volltext (vorerst lehnt der Server "
        "das ab, siehe would_replace_file); steht derselbe Text schon da, gibt es nichts zu "
        "bestaetigen. Fuer viele Datensaetze: "
        "wlo_attach_fulltexts." + _NUR_OHNE_DATEI + _ZWEISTUFIG,
        {**_VOLLTEXT_FELDER,
         "replace": {"type": "boolean", "description": "Einen vorhandenen Volltext ersetzen."}},
        ["nodeId", "markdown", "source"],
    ),
    _fn(
        "wlo_attach_fulltexts",
        "Legt Volltexte fuer bis zu 200 Datensaetze mit EINER Bestaetigung ab — je Datensatz "
        "dieselben Regeln wie wlo_attach_fulltext. Die Vorschau zaehlt neu, ersetzt, unveraendert "
        "und abgelehnt. Grosse Mengen arbeitet der Server in Abschnitten ab; die Person setzt "
        "ueber den Knopf 'Plan fortsetzen' fort, ohne neue Bestaetigung — du setzt nicht selbst "
        "fort."
        + _NUR_OHNE_DATEI + _ZWEISTUFIG_PLAN,
        {
            "items": {"type": "array",
                      "items": {"type": "object", "properties": _VOLLTEXT_FELDER,
                                "required": ["nodeId", "markdown", "source"]},
                      "description": "Eintraege {nodeId, markdown, source, sourceUrl?, language?}, "
                                     "max. 200 (sourceUrl bis 2000, language bis 10 Zeichen)."},
            "replace": {"type": "boolean", "description": "Vorhandene Volltexte ersetzen."},
        },
        ["items"],
    ),
    _fn(
        "wlo_update_contents",
        "Aendert die Metadaten von bis zu 200 vorhandenen Datensaetzen mit EINER Bestaetigung — je "
        "Eintrag nodeId und Felder wie bei wlo_update_content (ohne Inhalt und Datei). Der Server "
        "entscheidet je Feld: manches schreibt er direkt, was redaktionell bestaetigt werden muss "
        "(Lizenz, Urheber, Herausgeber, Quell-URL, Sprache, Zielgruppe), hinterlegt er als "
        "Vorschlag — reason ist dessen Begruendung. Fortsetzen wie bei wlo_add_to_collections "
        "(Knopf 'Plan fortsetzen'). Fuer einen einzelnen Datensatz: wlo_update_content."
        + _ZWEISTUFIG_PLAN,
        {
            "items": {"type": "array",
                      "items": {"type": "object", "properties": {
                          "nodeId": {"type": "string", "description": "nodeId des Datensatzes."},
                          "reason": {"type": "string",
                                     "description": "Begruendung fuer die Vorschlaege, "
                                                    "hoechstens 500 Zeichen — laenger weist der "
                                                    "Server den ganzen Aufruf ab."},
                          **{k: v for k, v in _TEXTFELDER.items()
                             if k not in ("content", "contentFormat", "fileBase64")}},
                          "required": ["nodeId"]},
                      "description": "Eintraege {nodeId, reason?, Felder}, max. 200."},
        },
        ["items"],
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
        "triff sie nie von dir aus, sondern nur auf ausdruecklichen Wunsch. "
        # MCP-Stand nach dem Audit (Plan 2026-11-13, C2)
        "Nur offene Vorschlaege (PENDING) sind entscheidbar; already_decided heisst: schon "
        "entschieden, nicht erneut versuchen. Annehmen ERGAENZT bei mehrwertigen Feldern (Fach, "
        "Bildungsstufe, Inhaltstyp, Zielgruppe, Sprache, Schlagwoerter) die vorhandenen Werte, "
        "es ersetzt sie nicht."
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
    "wlo_create_collection_tree": CollectionTreeCreateArgs,
    "wlo_add_to_collections":     CollectionsAddArgs,
    "wlo_attach_fulltext":        FulltextAttachArgs,
    "wlo_attach_fulltexts":       FulltextsAttachArgs,
    "wlo_update_contents":        ContentsUpdateArgs,
    "wlo_remove_from_collection": CollectionMembershipArgs,
    "wlo_update_compendium":      CompendiumUpdateArgs,
    "wlo_set_topic_page":         TopicPageSetArgs,
    "wlo_suggest_metadata":       MetadataSuggestArgs,
    "wlo_list_suggestions":       SuggestionsListArgs,
    "wlo_decide_suggestion":      SuggestionDecideArgs,
}
