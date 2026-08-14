"""Active-tools assembly (P3-3b) — byte-parity port of ALT
``llm_prompt_builder.py:883-1219`` (``_select_active_tools``, phases P10-P11).

Assembles the function-calling ``tools=[...]`` list handed to the LLM in the tool
loop, from the routed pattern + classification + RAG availability + two ENV
feature-gates. Sibling of the 3-3a ``response_prompt_builder`` (both derive from
ALT ``llm_prompt_builder.py``); kept in its own module because tool-LIST selection
is a distinct responsibility from prompt-TEXT composition (contract §8.4).

Single function, ~340 lines: deliberately one unit and above the ~300-line
smoke-detector threshold, because it is a verbatim byte-parity port whose three
inline tool-schema literals (``query_knowledge`` / ``select_top_cards`` /
``respond_to_user``) must stay AST-identical to ALT for the fidelity gate —
extracting them into helper builders would break that parity. Same rationale as
the sibling ``response_prompt_display_blocks``.

Deviations from ALT (documented): the function body is byte-identical to ALT; the
only change is the import root — ``app.services.mcp_client`` →
``boerdi.services.mcp.tool_defs`` (NEU has no ``mcp_client`` re-export facade;
``TOOL_DEFINITIONS`` comes from its leaf module directly). E501 is per-file-ignored
(pyproject) as for the sibling verbatim-prompt-byte modules — the tool-description
strings are load-bearing bytes and must not be reflowed.

Behobener ALT-Defekt (E2, 2026-08-10): der ``has_mcp_source``-Zweig wies ALT-treu
``active_tools = TOOL_DEFINITIONS`` zu — eine *Referenz*, keine Kopie —, und das
spätere ``active_tools.append(...)`` schrieb damit in die Modul-Globale. Der
Katalog wuchs bei jedem Aufruf um einen Eintrag (gemessen 22 → 27 über fünf
Aufrufe); das Modell bekam ``select_top_cards`` mehrfach angeboten. Bis dahin war
das als ``simplify:``-Vermerk notiert und latent, weil kein Test den Zweig traf.
Ein E2-Test tat es und kippte zwei fremde Tests über die Reihenfolge. Jetzt
``list(TOOL_DEFINITIONS)``; Rückgabewert unverändert, gepinnt von
``test_mcp_source_waechst_den_katalog_nicht``.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from boerdi.domain.write_confirm import CURATION_TOOLS
from boerdi.services.agent_tools import AUS_DEM_KATALOG
from boerdi.services.mcp.auth import has_auth_token
from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS
from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS

_logger = logging.getLogger(__name__)


def _nameable_tools() -> list[dict]:
    """Werkzeuge, die ein Muster in ``tools`` NAMENTLICH anfordern darf (E2).

    Der Lesekatalog immer, die kuratierenden nur mit hinterlegtem Zugangsblock
    (C3). Ohne Block verweigert der Server sie ohnehin — sie gar nicht erst
    anzubieten ist trotzdem richtig: sonst kündigt der Bot eine Fähigkeit an,
    die der nächste Schritt zurücknimmt.

    Bewusst NUR für den namentlichen Zweig. Der ``has_mcp_source``-Zweig reicht
    ``TOOL_DEFINITIONS`` als Ganzes weiter; stünden die schreibenden darin,
    bekäme sie jedes Muster mit ``sources: [mcp]`` — also auch die reinen
    Suchmuster. Kuratieren muss ein Muster ausdrücklich nennen.

    **``AUS_DEM_KATALOG`` fällt hier heraus** (P3, Nutzer-Entscheid 2026-08-13).
    Die Agent-Schleife filtert dieselbe Menge in ``build_agent_tools``; für den
    Muster-Weg hing die Entscheidung bis dahin allein daran, dass kein Seed das
    Werkzeug mehr nennt. Muster leben aber in der Datenbank: bis zum
    Seed-Import stehen dort die alten, und im Studio lässt sich der Name wieder
    eintragen. „Darf ein Muster namentlich anfordern" ist genau die Frage, die
    diese Funktion beantwortet — also gehört die Antwort hierher und nicht in
    die Daten.
    """
    katalog = (
        TOOL_DEFINITIONS if not has_auth_token()
        else [*TOOL_DEFINITIONS, *CURATION_TOOL_DEFINITIONS]
    )
    return [t for t in katalog if t["function"]["name"] not in AUS_DEM_KATALOG]


def _pattern_curates(pattern_output: dict[str, Any]) -> bool:
    """Will dieses Muster den Bestand ÄNDERN — unabhängig davon, ob es darf?

    Absichtlich ohne Blick auf den Zugangsblock: gefragt ist die Absicht des
    Musters, nicht seine Erlaubnis. Beide Aufrufer brauchen sie so — der eine,
    um den Verlust zu melden, der andere, um den Medientyp-Strip zu übergehen.
    """
    return bool(set(pattern_output.get("tools") or ()) & CURATION_TOOLS)


def curation_blocked_by_mode(pattern_output: dict[str, Any]) -> bool:
    """Wollte das Muster kuratieren, ohne dass ein Zugangsblock hinterlegt ist? (E3)

    Genau dieser Fall geht sonst spurlos verloren: der Namensfilter oben lässt
    das Werkzeug einfach weg. Das Muster verspricht dann etwas, wovon der Rest
    des Zuges nichts weiß — der Prompt-Bauer fragt hier nach, um dem Modell die
    Wahrheit über seine Fähigkeiten mitzugeben.

    Nur der namentliche Zweig kann betroffen sein: die anderen bieten
    kuratierende Werkzeuge ohnehin nie an.
    """
    return _pattern_curates(pattern_output) and not has_auth_token()


def _select_active_tools(
    classification: dict[str, Any],
    pattern_output: dict[str, Any],
    available_rag_areas: list[str] | None,
    rag_config: dict[str, Any] | None,
    _cards_inline_mode: bool,
    _degradation_no_tools: bool,
    *,
    pattern_label: str = "",
) -> tuple[list[dict], Any, bool, bool]:
    """Stellt die aktive Tool-Liste fuer ``generate_response`` zusammen
    (Phasen P10-P11: pattern.tools / tools=[] / mcp-Source / Fallback,
    medientyp-Strip, RAG-Gate + query_knowledge-Tool, select_top_cards
    (ENV-Gate), Degradation-Tool-Wipe, respond_to_user (ENV-Gate)).

    Parameter-Reihenfolge: classification, pattern_output,
    available_rag_areas, rag_config, _cards_inline_mode,
    _degradation_no_tools.

    ``pattern_label`` ist NEU (F-neu, 2026-08-10) und rein diagnostisch: die
    E3-Protokollwarnung wollte das Muster benennen und griff dafür auf
    ``pattern_output["id"]`` zu — den Schlüssel schreibt ``phase3_modulate``
    nicht, im Betrieb stand dort also immer „?". Schlüsselwort mit Vorgabe,
    damit kein Aufrufer angefasst werden muss; ohne ihn bleibt der Eintrag,
    was er war.

    Returns ``(active_tools, _pattern_sources_decl,
    _rag_allowed_for_pattern, _inline_qr_enabled)`` — die Tool-Liste plus
    die vom RAG-Prefetch-Gate bzw. Tool-Loop weitergelesenen Werte.
    """
    # Determine which tools to offer

    # In MCP-v2 there are no more Web-Crawler "info tools" — Plattform-/
    # Projekt-Themen werden ausschliesslich vom RAG-Kontext (query_knowledge)
    # abgedeckt. Daher leeres Set, das wir aber als Variable behalten,
    # damit die Set-Vereinigungen unten weiterhin funktionieren ohne
    # Sonderfaelle.
    INFO_TOOLS: set[str] = set()
    active_tools = []
    has_explicit_tools = "tools" in pattern_output
    has_mcp_source = pattern_output.get("sources") and "mcp" in pattern_output["sources"]

    if pattern_output.get("tools"):
        # Pattern defines specific tools → use those
        tool_names = set(pattern_output["tools"]) | INFO_TOOLS
        active_tools = [t for t in _nameable_tools() if t["function"]["name"] in tool_names]
        # E3: der Verlust bekommt eine Stimme — für den, der ihn beheben kann.
        # Ein Betreiber sieht sonst nur, dass „der Bot nicht kuratiert", ohne
        # Hinweis darauf, dass sein Block fehlt oder nicht greift.
        #
        # Seit C5-a hat der Satz zwei Ursachen, und keine ist von hier aus von
        # der anderen zu unterscheiden: hier anzukommen heisst, dass WEDER die
        # Person angemeldet ist NOCH die Anlage einen Block hat. Beide werden
        # deshalb genannt.
        if not has_auth_token():
            _verloren = sorted(tool_names & CURATION_TOOLS)
            if _verloren:
                _logger.warning(
                    "Muster %s verlangt kuratierende Werkzeuge %s, aber für diesen "
                    "Zug gilt kein Zugangsblock — weder von der Person (nicht beim "
                    "MCP-Server angemeldet) noch von der Anlage (MCP_AUTH_TOKEN). "
                    "Sie werden dem Modell nicht angeboten. Siehe deploy/README.md.",
                    pattern_label or "?",
                    _verloren,
                )
    elif has_explicit_tools and not pattern_output["tools"]:
        # Leere Werkzeugliste → KEINE Werkzeuge. Für 8 der 17 Muster (M01–M04,
        # M11, M13–M15) ist das richtig: sie verbieten Tool-Calls in ihren
        # eigenen Regeln.
        #
        # F-neu (2026-08-10): der ALT-Kommentar sprach hier von „Pattern
        # explicitly set tools=[]" — das tut kein einziges Muster. Sie kommen
        # durch WEGLASSEN hierher, weil ``phase3_modulate`` den Schlüssel
        # bedingungslos schreibt (``PatternDef.tools`` hat
        # ``default_factory=list``). Damit ist dieser Zweig der lebende und die
        # beiden darunter sind unerreichbar — siehe ``test_pattern_tool_naht``.
        active_tools = []
    elif has_mcp_source:
        # UNERREICHBAR über ``phase3_modulate`` (F-neu, 2026-08-10): der Zweig
        # darüber fängt jedes Muster ab, weil ``tools`` immer im Dict steht.
        # Gemessen an derselben Muster-Definition (``sources: [mcp]``, kein
        # ``tools``): über den Betriebspfad 0 Werkzeuge, als handgebautes Dict
        # 23. Bewusst NICHT gelöscht — er ist ALT-Verbatim und hält fest, was
        # gemeint war; ihn zu beleben wäre eine Produktentscheidung (jedes
        # Suchmuster bekäme schlagartig den ganzen Katalog).
        #
        # ``list(...)`` und NICHT die Modul-Globale selbst: weiter unten hängt
        # ``active_tools.append(...)`` Werkzeuge an, und eine Referenz hätte
        # damit in den Katalog geschrieben. Gemessen 2026-08-10 (E2): über fünf
        # Aufrufe wuchs er 22 → 27, das Modell bekam ``select_top_cards``
        # fünfmal angeboten — im Betrieb ein Eintrag pro Zug, unbegrenzt. Der
        # Rückgabewert ist unverändert; nur die Aliasierung entfällt. Damit ist
        # der ``simplify:``-Vermerk im Modulkopf eingelöst.
        active_tools = list(TOOL_DEFINITIONS)
    else:
        # Fallback: search + topic pages — ebenfalls UNERREICHBAR über
        # ``phase3_modulate`` (F-neu, 2026-08-10), aus demselben Grund wie der
        # Zweig darüber. Der Plan vermutete hier den Gegenteil-Fehler („neun
        # Muster bekommen still Such-Werkzeuge, darunter M15, das sie sich
        # selbst verbietet"); die Messung zeigt, dass kein Muster je hier
        # ankommt und M15 seine eigene Regel gar nicht verletzen kann.
        fallback_tools = {"search_wlo_collections", "search_wlo_topic_pages"} | INFO_TOOLS
        active_tools = [t for t in TOOL_DEFINITIONS if t["function"]["name"] in fallback_tools]

    # ── Route medientyp queries away from search_wlo_collections ──────
    # Sammlungen (collections) cannot be filtered by resourceType, so if the
    # classifier extracted a medientyp the only correct path is
    # search_wlo_content. Removing the collection tool here prevents the
    # LLM from "falling back" to collections when content search could
    # satisfy the filter — a pattern we saw it enter after empty
    # collection results.
    #
    # R2 (2026-08-11): NICHT bei einem Schreibauftrag. Die Begründung oben trägt
    # nur, solange der Medientyp ein SUCHFILTER ist. In „Pack das Arbeitsblatt in
    # meine Sammlung Optik" — der eigenen Trigger-Phrase von I09 — ist er der
    # Gegenstand, und ``search_wlo_collections`` sucht nicht Material, sondern
    # das Ziel der Änderung. Gemessen: M18 verlor es und konnte die Sammlung
    # nicht mehr über ihren Titel finden; es blieb ``browse_collection_tree``,
    # das eine nodeId oder einen Fachportal-Namen verlangt. Suchmuster (M06,
    # M09, M12) sind unberührt — sie nennen keine kuratierenden Werkzeuge.
    _classif_entities_top = classification.get("entities", {}) or {}
    if _classif_entities_top.get("medientyp") and not _pattern_curates(pattern_output):
        before = {t["function"]["name"] for t in active_tools}
        # Welle C.5+ (2026-05-22): zusätzlich ``search_wlo_topic_pages``
        # entfernen. Bei medientyp-Fokus will der User Einzelinhalte mit
        # konkretem Filter — Themenseiten-Vorschläge sind ähnlich
        # irreführend wie Sammlungs-Vorschläge (siehe User-Feedback:
        # „auf 'nur videos bitte' sollte der Bot KEINE Sammlungen oder
        # Themenseiten anzeigen oder im Prompt berücksichtigen").
        _strip_in_type_focus = {
            "search_wlo_collections",
            "search_wlo_topic_pages",
            # search_wlo_all ist ein Superset (content + collections +
            # topicPages) — bei Medientyp-Fokus würde es die eben entfernten
            # Sammlungen/Themenseiten wieder hereinholen. Deshalb ebenfalls
            # strippen; der gefilterte search_wlo_content bleibt der Pfad.
            "search_wlo_all",
        }
        active_tools = [
            t for t in active_tools
            if t["function"]["name"] not in _strip_in_type_focus
        ]
        removed = before - {t["function"]["name"] for t in active_tools}
        if removed:
            _logger.info(
                "medientyp=%r → removed %s from active_tools to force content search",
                _classif_entities_top.get("medientyp"), sorted(removed),
            )
        # Ensure search_wlo_content is available even if pattern didn't list it.
        if not any(t["function"]["name"] == "search_wlo_content" for t in active_tools):
            for td in TOOL_DEFINITIONS:
                if td["function"]["name"] == "search_wlo_content":
                    active_tools.append(td)
                    _logger.info("medientyp set — added search_wlo_content to active_tools")
                    break

    # ── Pattern-Sources-Gate (Welle C.5+, 2026-05-22) ─────────────
    # Wenn das aktive Pattern ``sources`` deklariert hat UND "rag" NICHT
    # darin steht, schalten wir die RAG-Pipeline komplett aus — weder
    # Prefetch noch ``query_knowledge``-Tool werden bereitgestellt.
    # Patterns ohne ``sources``-Deklaration (Default) bekommen alles.
    _pattern_sources_decl = pattern_output.get("sources")
    _rag_allowed_for_pattern = (
        _pattern_sources_decl is None
        or "rag" in _pattern_sources_decl
    )
    # ── Add RAG knowledge areas as virtual tools ──────────────────
    if available_rag_areas and rag_config and _rag_allowed_for_pattern:
        area_descriptions = []
        for area in available_rag_areas:
            desc = rag_config.get(area, {}).get("description", f"Wissensbereich: {area}")
            area_descriptions.append(f"{area}: {desc}")

        knowledge_tool = {
            "type": "function",
            "function": {
                "name": "query_knowledge",
                "description": (
                    "PRIMAERE WISSENSQUELLE: Durchsuche die interne Wissensdatenbank. "
                    "Rufe dieses Tool ZUERST auf bevor du externe Such-Tools nutzt! "
                    "Nutze es bei Fragen zu: internem Wissen, Prozessen, Richtlinien, "
                    "Konzepten, Dokumenten, rechtlichen Themen, Qualitaetssicherung. "
                    "Verfuegbare Bereiche: "
                    + "; ".join(area_descriptions)
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "area": {
                            "type": "string",
                            "description": "Wissensbereich. Verfuegbar: " + ", ".join(available_rag_areas),
                            "enum": available_rag_areas,
                        },
                        "query": {
                            "type": "string",
                            "description": "Suchanfrage an die Wissensdatenbank",
                        },
                    },
                    "required": ["area", "query"],
                },
            },
        }
        active_tools = [knowledge_tool] + active_tools  # Knowledge first!

    # ── Curation-Tool: select_top_cards (immer verfügbar) ─────────────
    # Im Inline-Mode ist der Tool-Call obligatorisch — sonst weiß das
    # Backend nicht, welche IDs als Inline-Links gerendert werden sollen.
    # Im Kachel-Mode ist der Call optional, dient aber als Re-Rank-Hint
    # für Card-Pipeline v2: wenn das LLM eine thematisch sinnvolle
    # Reihenfolge der 5 besten Treffer angibt, übernimmt v2 die.
    # Wird das Tool nicht aufgerufen, wählt v2 deterministisch nach
    # Relevance-Score (Title/Keywords/Disciplines/Description-Match).
    if _cards_inline_mode:
        _select_description_lead = (
            "FINAL-SELECTION für Inline-Modus. RUFE DIESES TOOL NACH "
            "DEN SEARCH-TOOLS AUF. Wähle aus den eben gefundenen "
            "Treffern 1-5 IDs aus, in der Reihenfolge in der sie dem "
            "User gezeigt werden sollen. Wenn du gar nichts gefunden "
            "hast, RUFE DIESES TOOL NICHT — antworte stattdessen mit "
            "einer Klärungsfrage.\n\n"
            "**Wenn etwas gefunden wurde, ist dieser Tool-Call "
            "obligatorisch.** Ohne diesen Call sieht der User keinen "
            "Link — nur deinen Text."
        )
    else:
        _select_description_lead = (
            "RE-RANK-HINT für Kachel-Modus. Optional aufrufbar, NACHDEM "
            "die Search-Tools Treffer geliefert haben. Wenn du eine "
            "thematisch sinnvolle Reihenfolge der 5 passendsten Treffer "
            "hast (z.B. Sammlung zum Thema zuerst, dann passende Einzel-"
            "inhalte), übergib sie hier — das Backend ordnet die Kacheln "
            "dann genau in dieser Reihenfolge an. Wenn du keine Präferenz "
            "hast oder die Treffer ohnehin schon thematisch matchen, "
            "kannst du den Call weglassen — das Backend wählt dann "
            "deterministisch nach Relevance-Score (Title/Keywords/"
            "Disciplines-Match).\n\n"
            "**Nur sinnvoll, wenn echte Treffer da sind.** Bei "
            "Klärungs-Turn / leeren Tool-Results: nicht aufrufen."
        )
    select_cards_tool = {
        "type": "function",
        "function": {
            "name": "select_top_cards",
            "description": (
                _select_description_lead + "\n\n"
                "AUSWAHL-REGELN:\n"
                "1. **ZIEL: bis zu 5 IDs** — wenn die Tools genug geliefert "
                "haben. Aber auch 1, 2 oder 3 sind OK, wenn wirklich nicht "
                "mehr Passendes da ist. Lieber wenige gute als gar keine.\n"
                "2. **Typ-Priorität (DEFAULT)**: Themenseiten zuerst "
                "(geben Überblick), dann Sammlungen, dann Einzelinhalte. "
                "Themenseiten erkennst du an Tool-Result-Einträgen mit "
                "node_type='collection' UND nicht-leerem topic_pages-Array.\n"
                "3. **MIX**: Wenn nur 1 Themenseite oder 1 Sammlung "
                "perfekt passt, fülle die freien Slots mit passenden "
                "Einzelinhalten auf (z.B. 1 Sammlung + 3 Einzelinhalte). "
                "1 Sammlung + Mix von Einzelinhalten ist meist besser als "
                "nur 1 Sammlung alleine.\n"
                "4. AUSNAHME (Typ-Fokus): Wenn der User explizit nach "
                "Material-Typ fragt (Video, Arbeitsblatt, Übung, Quiz, "
                "Audio, Präsentation, Interaktiv, Kurs) → bis zu 5 "
                "Einzelinhalte dieses Typs, KEINE Themenseiten/Sammlungen "
                "dazwischen.\n"
                "5. Klar Unpassendes (falsches Fach, falsche Klassenstufe) "
                "weglassen. Thematisch verwandte Treffer sind erlaubt.\n\n"
                "Die IDs sind die ``node_id``-Werte aus den search-Tool-"
                "Ergebnissen — exakt im UUID-Format wie geliefert."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "card_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "1-5 node_ids in Anzeige-Reihenfolge. Erste ID "
                            "wird oben angezeigt."
                        ),
                        "minItems": 1,
                        "maxItems": 5,
                    },
                    "reasoning": {
                        "type": "string",
                        "description": (
                            "1 Satz: warum diese Auswahl in dieser "
                            "Reihenfolge — landet im Debug-Log."
                        ),
                    },
                },
                "required": ["card_ids"],
            },
        },
    }
    # Perf-Schalter: select_top_cards ist im Kachel-Modus nur ein OPTIONALER
    # Re-Rank-Hint (sonst wählt das Backend deterministisch nach MCP-Ranking).
    # Mit CHAT_DISABLE_SELECT_TOP_CARDS=1 lässt sich dieser zusätzliche
    # LLM-Tool-Turn abschalten → ~1 Round-Trip/Such-Turn schneller (zum
    # Messen/Tunen). Default: an (Verhalten unverändert).
    if (os.getenv("CHAT_DISABLE_SELECT_TOP_CARDS") or "").strip() not in ("1", "true", "True"):
        active_tools.append(select_cards_tool)
    else:
        _logger.info(
            "select_top_cards via CHAT_DISABLE_SELECT_TOP_CARDS deaktiviert — "
            "Backend nutzt deterministische Karten-Auswahl (MCP-Ranking)."
        )

    # Degradation (Pflicht-Slot fehlt): Tool-Liste wirklich leeren statt nur
    # per Prompt-Regel zu bitten — gegen einen Pattern-Body mit
    # "Pflicht-Pipeline: rufe search_*" verliert die Regel sonst, und
    # force_tool_use koennte die Suche sogar erzwingen. Nur respond_to_user
    # (unten) bleibt als Antwortkanal erlaubt.
    if _degradation_no_tools and active_tools:
        _logger.info(
            "degradation: %d aktive Tools entfernt (fehlende Slots: %s) — "
            "Bot stellt zuerst die Rueckfrage",
            len(active_tools),
            pattern_output.get("missing_slots"),
        )
        active_tools = []

    # Combined-output tool (opt-in) — see env CHAT_INLINE_QUICK_REPLIES.
    # When enabled, the model is instructed to call ``respond_to_user`` for
    # the FINAL answer instead of plain content, with both ``text`` and
    # ``quick_replies`` in one shot. This saves the separate quick_replies
    # LLM round-trip (~1-2s) for ~70% of turns. Default OFF until measured.
    _inline_qr_enabled = (
        (os.getenv("CHAT_INLINE_QUICK_REPLIES") or "").strip() in ("1", "true", "yes")
    )
    if _inline_qr_enabled:
        respond_tool = {
            "type": "function",
            "function": {
                "name": "respond_to_user",
                "description": (
                    "FINALE Antwort an den Nutzer. Nutze dieses Tool NUR wenn du "
                    "alle nötigen Such-/Vokabular-/Knowledge-Tools bereits gerufen "
                    "hast und die finale Antwort fertig ist. Liefere die Markdown-"
                    "formatierte Antwort als ``text`` und 2-4 kurze nutzerseitige "
                    "Folgevorschläge als ``quick_replies`` (max 6-8 Wörter pro "
                    "Vorschlag, vom NUTZER formuliert — der Text MUSS so klingen, "
                    "als würde der Nutzer ihn selbst tippen, z.B. 'Mehr davon "
                    "zeigen', 'Anderes Thema wählen', 'Ja, gerne', 'Nein danke'). "
                    "ANREDE-REGEL (kritisch): Der Nutzer spricht BOERDi mit DU an, "
                    "nicht mit Sie — auch wenn die Persona-Modulation 'siezen' "
                    "auf den BOT-Text gesetzt ist (das gilt nur für die Antwort "
                    "des Bots an den Nutzer, NICHT für die Pillen-Vorschläge). "
                    "Quick-Replies dürfen daher NICHT 'Können Sie mir helfen?' "
                    "enthalten, sondern 'Kannst du mir helfen?' / 'Zeig mir mehr' / "
                    "'Erklär mir den Unterschied'. Du-Form ist Pflicht. "
                    "Wenn keine Folgevorschläge passen (z.B. CRISIS), gib leere Liste. "
                    "BRING-MICH-HIN-VORSCHLAG: Wenn deine Antwort eine konkrete "
                    "WLO-Webseiten-URL adressiert (z.B. /themenseite/<slug>, "
                    "/fachportale, /mitmachen, /ueber-uns), darfst du EINEN Eintrag "
                    "in folgendem Spezialformat einfügen: "
                    "``__guide__|<kurzer Anzeigetext>|<vollständige URL>`` — "
                    "Frontend rendert das als hervorgehobenen Same-Tab-Navigations-"
                    "Button. Beispiel: "
                    "``__guide__|Themenseite Klimawandel|https://wirlernenonline.de/themenseite/klimawandel``. "
                    "Nutze NUR vollständige URLs (Schema + Host), keine relativen "
                    "Pfade. Maximal EIN solcher Eintrag pro Antwort."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": (
                                "Die Markdown-formatierte Antwort an den Nutzer. "
                                "WICHTIG: Schreibe die Folgevorschläge (quick_replies) "
                                "und den ``__guide__``-Link NICHT zusätzlich in den "
                                "text — die erscheinen separat als Pillen/Buttons UNTER "
                                "der Antwort. Der text endet mit dem letzten "
                                "inhaltlichen Satz; KEINE aufgelisteten Klick-Optionen "
                                "am Ende (kein 'Zeig mir mehr' / 'Anderes Thema wählen' "
                                "und keine 'Bring mich hin:'-Zeile)."
                            ),
                        },
                        "quick_replies": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "2-4 kurze Folgevorschläge. Jeder Vorschlag ist ein "
                                "Satz, den der Nutzer als nächste Eingabe sagen würde "
                                "(NICHT was der Bot vorschlägt zu tun). "
                                "ANREDE: Du-Form, weil der Nutzer den Bot duzt — "
                                "auch dann, wenn die Bot-Antwort selbst siezt. "
                                "Beispiele: 'Zeig mir mehr', 'Anderes Thema wählen', "
                                "'Kannst du das genauer erklären?'. KEINE Sie-Form "
                                "wie 'Können Sie mir ...?' / 'Zeigen Sie mir ...'. "
                                "EIN Eintrag darf optional ein Bring-mich-hin-"
                                "Spezialformat sein: ``__guide__|<Label>|<URL>`` — "
                                "siehe Tool-Description."
                            ),
                            "minItems": 0,
                            "maxItems": 4,
                        },
                    },
                    "required": ["text"],
                },
            },
        }
        active_tools = active_tools + [respond_tool]
    return active_tools, _pattern_sources_decl, _rag_allowed_for_pattern, _inline_qr_enabled
