"""Response-prompt tools/degradation/recency text (P3-3a, P6 + P8 + P9).

1:1 port of the verbatim text blocks from ALT ``llm_prompt_builder.py``: the
degradation Pflicht-Rückfrage rules (P6, 621-635), the two no-tools rule sets
(P8, 659-679), the ``## Verfuegbare Werkzeuge`` + Tool-Routing-Regeln block with
the session-context injection (P8, 681-854), and the recency anchor (P9,
861-876).

Two dead ALT locals are intentionally not carried (they were assigned and never
read — F841 under NEU's ruff): the per-area ``mode`` in the knowledge-tool loop
and ``has_rag_tools``. Neither affected the prompt output.

Line length is dictated by the verbatim prompt text (per-file ``E501`` ignore in
pyproject.toml): wrapping would alter the bytes the LLM sees.
"""

from __future__ import annotations

import json
from typing import Any


def render_degradation_rules(missing_slots: list, blocked_patterns: list) -> str:
    """P6: signal-driven degradation block — a mandatory clarifying question,
    listing the missing slots and any blocked patterns. Appended in addition to
    the P8 no-tools rules when ``pattern_output['degradation']`` is set."""
    blocked_info = ""
    if blocked_patterns:
        blocked_info = " Blockierte Patterns: " + ", ".join(
            f"{b['id']} ({b['label']}, braucht: {', '.join(b['missing'])})"
            for b in blocked_patterns
        ) + "."
    return (
        f"\n## Degradation aktiv: Fehlende Slots: {missing_slots}.{blocked_info}\n"
        "PFLICHT-RUECKFRAGE: Dir fehlen Informationen fuer die gewuenschte Aufgabe.\n"
        "Deine Antwort MUSS eine DIREKTE FRAGE nach den fehlenden Infos enthalten.\n"
        "- Wenn 'thema' fehlt: Frage EXPLIZIT nach dem konkreten Thema.\n"
        "  Beispiel: 'Mathe, super! Welches Thema steht an — Bruchrechnung, Geometrie, Gleichungen?'\n"
        "- Wenn 'stufe' fehlt: Frage nach der Bildungsstufe — NICHT nach der Klassenstufe. "
        "(WLO-Inhalte sind nur auf Bildungsstufen-Ebene getaggt: Grundschule, Sek I, Sek II, "
        "Berufliche Bildung, Hochschule, Erwachsenenbildung.) Wenn der Nutzer trotzdem eine "
        "Klassenstufe nennt, uebernimm das Mapping still im Hintergrund.\n"
        "- Baue KEINEN Lernpfad oder Unterrichtsentwurf ohne konkretes Thema.\n"
        "- Die Frage soll am ANFANG deiner Antwort stehen, nicht versteckt am Ende.\n"
        "- Rufe KEINE Tools auf und zeige KEINE Materialien/Sammlungen an — die Rueckfrage\n"
        "  ist ein reiner Text-Dialog. Erst NACH der Antwort des Nutzers wird gesucht."
    )


# P8: pattern wants no tools because degradation blocks tool use — ask for the
# missing info, no tool calls.
DEGRADATION_NO_TOOLS_RULES = """
## Antwort-Regeln
- Antworte NUR mit Text — rufe KEINE Tools auf.
- Stelle die Rueckfrage nach den fehlenden Informationen.
- Erfinde KEINE Sammlungen oder Materialien.

Antworte auf Deutsch. Formatiere mit Markdown."""

# P8: pattern like M15 Orientierungs-Guide — pure text, no tool calls.
M15_NO_TOOLS_RULES = """
## Antwort-Regeln
- Antworte NUR mit flieszendem Text.
- Rufe KEINE Tools auf.
- Stelle die Faehigkeiten des Chatbots vor und biete konkrete Einstiegspunkte an.
- Erfinde KEINE Sammlungen oder Materialien.
- Schliesse mit einer offenen Frage die hilft, die Persona des Nutzers zu klaeren.
- WICHTIG: Antwortvorschlaege / Quick Replies werden automatisch als Buttons
  unter dem Text gerendert. Schreibe sie NIEMALS in den Antworttext
  (keine Liste wie "**Quick Replies:**", keine Aufzaehlung von Vorschlaegen).

Antworte auf Deutsch. Formatiere mit Markdown."""


def _render_session_context(session_state: dict) -> str:
    """P8: inject collections + content items the user saw in previous turns,
    so chat-based browsing / learning-path prep can reference them by nodeId.
    Corrupt JSON degrades silently (matches ALT's ``except (JSONDecodeError,
    KeyError): pass``)."""
    last_collections_json = session_state.get("entities", {}).get("_last_collections", "")
    collection_context = ""
    if last_collections_json:
        try:
            cols = json.loads(last_collections_json)
            col_lines = [f'  - "{c["title"]}" (nodeId: {c["node_id"]})' for c in cols]
            collection_context = f"""
## Verfuegbare Sammlungen aus vorherigen Ergebnissen
Der Nutzer hat diese Sammlungen bereits gesehen:
{chr(10).join(col_lines)}

Wenn der Nutzer "zeig mir die Inhalte von [Sammlung]" oder aehnlich sagt,
nutze get_collection_contents mit der passenden nodeId."""
        except (json.JSONDecodeError, KeyError):
            pass

    last_contents_json = session_state.get("entities", {}).get("_last_contents", "")
    if last_contents_json:
        try:
            contents = json.loads(last_contents_json)
            if contents:
                content_lines = []
                for i, c in enumerate(contents, 1):
                    types = ", ".join(c.get("learning_resource_types", [])) or "Material"
                    content_lines.append(
                        f'  {i}. "{c["title"]}" ({types})'
                        + (f' — {c["description"][:100]}' if c.get("description") else "")
                    )
                collection_context += f"""

## Zuvor gezeigte Materialien
Der Nutzer hat diese Einzelinhalte in vorherigen Suchergebnissen gesehen:
{chr(10).join(content_lines)}

Wenn der Nutzer einen Lernpfad, eine Unterrichtsvorbereitung oder eine Strukturierung
dieser Materialien wuenscht, nutze diese Liste als Grundlage. Du kannst:
- Die Materialien in eine sinnvolle didaktische Reihenfolge bringen
- Lernziele fuer jeden Schritt formulieren
- Zeitvorschlaege machen
- Ergaenzende Materialien per search_wlo_content nachsuchen wenn noetig
Du musst dafuer KEINE neuen Such-Tools aufrufen — die Materialien sind bereits bekannt."""
        except (json.JSONDecodeError, KeyError):
            pass
    return collection_context


def render_tools_block(
    session_state: dict,
    available_rag_areas: list[str] | None,
    rag_config: dict[str, Any] | None,
) -> str:
    """P8: the ``## Verfuegbare Werkzeuge`` + Tool-Routing-Regeln block, with the
    per-session collection/content context and the query_knowledge area list
    injected. This is the tools branch (pattern DOES want tools)."""
    collection_context = _render_session_context(session_state)

    knowledge_tool_desc = ""
    if available_rag_areas and rag_config:
        area_lines = []
        for area in available_rag_areas:
            desc = rag_config.get(area, {}).get("description", area)
            area_lines.append(f'  - query_knowledge(area="{area}"): {desc}')
        knowledge_tool_desc = "\n".join(area_lines)

    return f"""
## Verfuegbare Werkzeuge

Du hast zwei Arten von Werkzeugen:

### A) Wissensdatenbank (query_knowledge)
Internes Wissen aus hochgeladenen Dokumenten. Nutze diese Tools wenn die Frage
durch internes Wissen beantwortet werden kann (z.B. Prozesse, Konzepte, Richtlinien).
{knowledge_tool_desc if knowledge_tool_desc else '  (Keine Wissensbereiche verfuegbar)'}

### B) MCP-Tools (externe Suche & Datenquellen — WLO-MCP v2)
- search_wlo_collections: Kuratierte WLO-Sammlungen nach Thema suchen
- search_wlo_content: Einzelne Lernmaterialien suchen (Arbeitsblaetter, Videos, etc.)
- search_wlo_topic_pages: Themenseiten suchen oder pruefen ob eine Sammlung eine hat
  (per query ODER per collectionId; filtert nach targetGroup: teacher/learner/general;
   Varianten werden serverseitig gemerged)
- get_collection_contents: Inhalte einer Sammlung per nodeId abrufen
- get_node_details: Metadaten eines WLO-Knotens abrufen
- lookup_wlo_vocabulary: Filter-Werte nachschlagen (Faecher, Bildungsstufen, Lizenzen, Zielgruppen)
- get_subject_portals: Liste aller WLO-Fachportale (alphabetisch, mit nodeId)
- browse_collection_tree: Strukturierter Drilldown unter eine Sammlung (depth 1 oder 2)
- get_nodes_details: Bulk-Metadaten fuer mehrere nodeIds parallel
- wlo_health_check: Verfuegbarkeit/Latenz der WLO-API pruefen
{collection_context}

## Tool-Routing-Regeln

SCHRITT 1 — RICHTIGES WERKZEUG WAEHLEN (IN DIESER REIHENFOLGE PRUEFEN!):

1. ZUERST pruefen: Passt die Frage zu einem Wissensbereich in query_knowledge?
   Wenn ja → query_knowledge aufrufen! Beispiele:
   - "Was ist WirLernenOnline?" → query_knowledge(area="WirLernenOnline", ...)
   - "Was macht edu-sharing?" → query_knowledge(area="Edu-Sharing-Metaventis", ...)
   - Jede Frage zu internen Prozessen, Konzepten, Dokumenten → query_knowledge
   WICHTIG: Die "always"-Bereiche werden beim Start AUTOMATISCH vorab durchsucht.
   Wenn du ein query_knowledge-Ergebnis mit "[Bereits durchsuchte Bereiche: ...]"
   siehst, sind diese Bereiche SCHON abgefragt — rufe query_knowledge fuer diese
   Bereiche NICHT nochmal auf! Nur fuer andere Bereiche oder bei einer ganz
   anderen Suchanfrage darfst du query_knowledge erneut aufrufen.

2. DANN: Frage nach Lernmaterialien, Sammlungen, OER-Inhalten?
   → search_wlo_collections oder search_wlo_content

3. DANN: Frage ueber WLO, edu-sharing, metaVentis als Plattform/Projekt?
   → query_knowledge mit dem passenden RAG-Bereich (wirlernenonline.de-webseite,
     edu-sharing-com-webseite, edu-sharing-net-webseite, wissenlebtonline-webseite).
     Es gibt KEINE MCP-Web-Crawler-Tools mehr.

4. NAVIGATION/UEBERBLICK statt Suche?
   → "Welche Faecher gibt es?" / "alle Fachportale" / "Uebersicht WLO":
     get_subject_portals (KEINE Suche, KEIN search_wlo_collections — die
     Top-Level-Portale stehen separat unter dem WLO-Wurzelknoten).
   → "Welche Themen unter X?" / "Bereiche unter Y" / "Wie ist Z gegliedert?":
     browse_collection_tree(nodeId=<X.id>, depth=1, includeContentCounts=true)
     — liefert die Sub-Sammlungen, NICHT die Files.
   → Bei "ist die WLO-API erreichbar?" / Diagnose: wlo_health_check.
   → Wenn du fuer >3 nodeIds Metadaten brauchst: get_nodes_details (Bulk
     statt N x get_node_details).

Du DARFST query_knowledge und MCP-Tools in derselben Antwort kombinieren!

SCHRITT 2 — REGELN:
1. Erfinde KEINE Materialien — nur was die Tools zurueckgeben.
2. SOFORT handeln: Wenn der User ein Thema nennt, rufe sofort das passende
   Tool auf. Keine Rueckfragen wenn du genug Kontext hast.
3. lookup_wlo_vocabulary nur fuer Filter-Werte, NIE als Ersatz fuer Suche.
4. BREITE Suche (Thema genannt, kein enger Medientyp-Filter): Wenn
   search_wlo_all verfuegbar ist, nutze es — EIN Aufruf liefert Inhalte,
   Sammlungen UND Themenseiten zugleich. Rufe dann NICHT zusaetzlich
   search_wlo_collections/search_wlo_content einzeln fuer dasselbe Thema auf.
   Die Einzel-Tools sind fuer GEZIELTE Rueckfragen zu EINEM Treffer da
   (Drilldown/Details zu einer konkreten Sammlung).
   Ist search_wlo_all NICHT verfuegbar: ZUERST search_wlo_collections
   (kuratiert), search_wlo_content nur bei explizitem Wunsch nach
   Einzelmaterialien; danach mit search_wlo_topic_pages(collectionId=...)
   pruefen ob die Top-Sammlungen Themenseiten haben und die URL liefern.
5. DIREKTE Themenseiten-Suche: Wenn der User explizit nach "Themenseite",
   "Themenseiten" oder "Topic Page" fragt, rufe DIREKT search_wlo_topic_pages(query=...)
   auf — NICHT erst search_wlo_collections. Zeige die gefundenen Themenseiten mit URL.
   Wenn keine Themenseiten gefunden werden, sage das ehrlich und biete stattdessen
   eine Sammlungs-Suche an.
6. Frage NIE "Fuer welches Fach suchst du?" -- hoechstens nach dem Thema.
7. Wenn query_knowledge Ergebnisse liefert, nutze diese als Hauptquelle.
   Du kannst zusaetzlich MCP-Tools aufrufen um ergaenzende Materialien zu finden.
8. FILTER-PFLICHT bei medientyp (STRIKT): Wenn in den Entities ein `medientyp`
   gesetzt ist (z.B. "Video", "Arbeitsblatt", "Bild", "interaktiv",
   "Simulation", "Quiz", "Kurs"), gilt OHNE AUSNAHME:
   a) Ziel-Tool ist search_wlo_content (Sammlungen lassen sich nicht nach
      Inhaltstyp filtern — search_wlo_collections taugt NICHT als
      Fallback fuer medientyp-Anfragen).
   b) Uebergib den Wert als `learningResourceType`-Parameter an
      search_wlo_content. Der MCP-Server akzeptiert sowohl Labels als
      auch URIs — beides funktioniert:
        "Video", "Arbeitsblatt", "Bild", "Audio", "Interaktives medium",
        "Unterrichtsplan", "Quiz", "Kurs", "Praesentation", "Lernspiel",
        "Simulation", "Webseite", ...
      Wenn du dir bei der genauen Form unsicher bist, hilft
      lookup_wlo_vocabulary(vocabulary="lrt") — aber oft ist der Label
      ausreichend.
   c) WICHTIG: Der Parameter heisst `learningResourceType` (NICHT
      `resourceType`!). Der MCP-Server ignoriert den alten Namen.
   d) Rufe search_wlo_content NIE OHNE learningResourceType auf, wenn
      entities.medientyp gesetzt ist — auch nicht als Fallback nach
      leerem search_wlo_collections-Ergebnis.
   e) Wenn kein passender Eintrag gefunden wird, weise kurz im
      Antworttext darauf hin ("Ich konnte nicht exakt nach '<medientyp>'
      filtern") und suche ungefiltert.
9. Fach & Bildungsstufe als Filter: Wenn entities `fach` bzw. `stufe` enthalten,
   setze sie als `discipline` bzw. `educationalContext` (NICHT
   `educationalLevel`!) in search_wlo_content / search_wlo_collections.
   Der MCP-Server akzeptiert sowohl Klartext-Labels ("Mathematik",
   "Sekundarstufe I") als auch URIs aus lookup_wlo_vocabulary. Eine
   Filter-Ebene "Klassenstufe" gibt es NICHT — mappe Klassenangaben
   immer auf die Bildungsstufe (Kl. 1-4=Grundschule, 5-10=Sek I,
   11-13=Sek II).

Antworte auf Deutsch. Formatiere mit Markdown."""


def render_recency_anchor(pattern_label: str, body_md: str | None) -> str:
    """P9: Recency anchor (2026-05-23) — mirror the pattern-brief core at the
    very end. At 22k+ token prompts the LLM follows the last instructions most
    closely, so the anti-patterns / answer schema stay dominant. Returns ``""``
    when the pattern has no ``body_md``."""
    _body_recap = (body_md or "").strip()
    if not _body_recap:
        return ""
    return f"""
## ⚡ LETZTE ERINNERUNG — verbindlich vor jeder Antwort

Aktives Pattern: **{pattern_label}**.

Du musst dich strikt an folgenden Pattern-Brief halten. Andere
Direktiven in diesem Prompt (z.B. „nutze RAG reich aus", „füge
URL-Links ein") gelten NUR im Rahmen dessen, was der Pattern-Brief
zulässt. Wenn der Pattern-Brief sagt „max. 2 Sätze" oder „keine
Material-Aufzählung", dann **gilt das**, auch wenn das Wissen für eine
lange Antwort vorhanden wäre.

{_body_recap}
"""
