"""Spekulativer MCP-Prefetch (Port von ALT ``chat_prefetch``, P5/P6).

``run_speculative_prefetch`` startet — hinter der Pre-Route-Engine, gegated auf
Risiko/Such-Intent/Anchor-Entity — spekulative WLO-MCP-Such-Tasks, deren
Ergebnis der Tool-Loop spaeter statt eines frischen MCP-Calls konsumiert (reine
Latenz-Optimierung). Landeort ``services/`` (async MCP-I/O).

**Verbatim-Body-Port** von ALT ``_launch_speculative_prefetch``; jede Grenze ist
unter ihrem ALT-Namen importiert, sodass der Body AST-identisch bleibt.
Dokumentierte Deviationen (der AST-Diff-Gate beweist 0 Logik-Divergenz):
- Import-Roots — ``call_mcp_tool`` aus ``services/mcp/client``,
  ``_topic_pages_with_warmup`` aus ``services/topic_pages``,
  ``_retrieve_task_exception`` aus ``obs/tasks`` (statt der ALT-Router-Module);
- **Bare-7-Tupel → ``SpeculativePrefetch``-NamedTuple** (Feld-Reihenfolge =
  ALT-Tupel → ALT-Positional-Asserts halten, ALT-Default-Tupel == Defaults);
- oeffentlicher Name ``run_speculative_prefetch`` (ALT: privates
  ``_launch_speculative_prefetch``) — die Funktion ist die Modul-API;
- 2 E701-Einzeiler (``if _fach:``/``if _stufe:``) auf zwei Zeilen umbrochen
  (AST-erhaltend, ruff-clean) — sonst Body byte-ident.

**simplify (bewusste Ausnahme):** die Funktion ist deutlich laenger als der
~50-Zeilen-Schwellwert — ein 1:1-Verbatim-Port eines kohaesiven, getesteten ALT-
Blocks. Als AST-diffbare Einheit gehalten (0 Divergenz) statt in un-diffbare
Sub-Funktionen mit Zustands-Threading zu splitten.

Die Verdrahtung in den Tool-Loop (Konsum von ``spec_task``/``extra_spec_tasks``)
folgt als eigene Slice (P6-RAG) — hier ist nur der Producer portiert.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, NamedTuple

from boerdi.obs.tasks import _retrieve_task_exception
from boerdi.services.mcp.client import call_mcp_tool
from boerdi.services.topic_pages import _topic_pages_with_warmup

logger = logging.getLogger(__name__)


class SpeculativePrefetch(NamedTuple):
    """Ausgaben des Spekulativ-Prefetch (ALT-Bare-7-Tupel, gleiche Reihenfolge).

    Greift die Start-Bedingung nicht, traegt jedes Feld seinen Default
    (``spec_task=None``, ``spec_query=""``, leere Listen,
    ``spec_is_search_all=False``) — das ALT-Default-Tupel
    ``(None, None, None, "", [], False, [])``.
    """

    spec_task: asyncio.Task | None
    spec_tool_name: str | None
    spec_tool_args: dict[str, Any] | None
    spec_query: str
    extra_spec_tasks: list[tuple[str, asyncio.Task]]
    spec_is_search_all: bool
    search_all_extras: list[dict]


async def run_speculative_prefetch(req, classification, safety, *, engine="pattern"):
    """Spekulativen MCP-Prefetch hinter der Pre-Route-Engine starten (Verbatim-
    Port ALT ``chat_prefetch._launch_speculative_prefetch``). Startet je nach
    Intent/Hint/Entities einen primaeren + optionale Extra-MCP-Such-Tasks (O1:
    ein kombiniertes ``search_wlo_all`` statt primary+extras, wo moeglich) und
    gibt ein :class:`SpeculativePrefetch` zurueck; greift die Start-Bedingung
    nicht, tragen alle Felder ihre Defaults (= ALT-Default-7-Tupel).

    Der Konsument (Tool-Loop) reicht die gestarteten Tasks spaeter an
    ``generate_response`` durch — er wird als eigene Slice (P6-RAG) verdrahtet.
    """
    # ── Speculative MCP prefetch — Variablen-Stubs ────────────────────
    # Welle-A.3 (2026-05): Der eigentliche Spec-Start wurde HINTER die
    # Pre-Route-Engine verschoben. Begründung: Pre-Route kann den Intent
    # umrouten (R-17 Themenseite → I03/M06, R-15 Fachportal →
    # I01/M07, R-19 Lerninhalt-Doppel-Trigger → I03). Wenn
    # der Spec-Call vorher startet, vergiftet er bei einer falschen
    # initialen Intent-Klassifikation den MCP-Session-State (z.B. läuft
    # search_wlo_collections, was den topic_pages-Index verbiegt — der
    # eigentlich gewollte search_wlo_topic_pages-Call findet dann keine
    # Treffer mehr).
    # Welle C Sprint 4 (2026-05-15): I03 sind in I03 gemergt.
    _spec_search_intents = {"I03", "I04"}
    spec_task: asyncio.Task | None = None
    spec_tool_name: str | None = None
    spec_tool_args: dict[str, Any] | None = None
    spec_query: str = ""
    extra_spec_tasks: list[tuple[str, asyncio.Task]] = []
    # O1: speculative nutzt EIN kombiniertes search_wlo_all statt primary+extras.
    spec_is_search_all: bool = False
    # Aus dem search_wlo_all-Envelope gesplittete Extra-Payloads (collections/topic).
    _search_all_extras: list[dict] = []

    def _spec_query_from_classification() -> str:
        ents = classification.entities or {}
        for k in ("thema", "fach", "topic", "query", "schlagwort"):
            v = ents.get(k)
            if v:
                return str(v)[:120]
        # Fall back to the raw user message stripped of obvious noise
        return req.message[:120]

    def _spec_has_enough_signal() -> bool:
        """Gate speculative prefetch on having any usable search anchor.

        Anchors (in priority order): explicit ``thema`` / ``topic`` /
        ``schlagwort`` / ``query`` slot, or — as a softer fallback —
        ``fach`` (Subject). With ``fach`` alone we still get a useful
        broad search (Themenseiten/Sammlungen zum Fach), which is what
        the user expects when they ask "Material zum Fach Mathematik".

        Without ANY anchor we skip the prefetch — M03 (Geführte
        Klärung) takes over and asks for at least a Fach.
        """
        ents = classification.entities or {}
        thema = (ents.get("thema") or ents.get("topic")
                 or ents.get("query") or ents.get("schlagwort") or "")
        if str(thema).strip():
            return True
        fach = ents.get("fach")
        if fach and str(fach).strip():
            return True
        return False

    def _startet_der_vorabruf() -> bool:
        """Die Startbedingung — nur der Bestandsweg startet den Vorabruf.

        Die Schleifen-Maschinen (agent UND hybrid) starten KEINEN: ihre
        Ersatz-Klassifikation trägt ``I01`` und leere Entities, die Bedingung
        unten ist dort also immer falsch. H5 hatte für den Hybrid
        ``_looks_like_search_query`` als Ersatz-Gate eingebaut — zurückgenommen
        (Review-Befund 2, 2026-08-22): die Verbrauchsseite wurde nie gebaut,
        ``respond_agent._verwirf_vorabruf`` bricht ``spec_task`` unbedingt ab,
        und jeder such-artige Hybrid-Zug bezahlte einen verworfenen
        MCP-Roundtrip — dasselbe Muster, das die M16-/I04-Skips weiter unten
        ausdrücklich vermeiden. Wer den Vorabruf im Hybrid will, baut zuerst
        die Einspeisung in die Schleife (Fremdtext-Rahmen + Karten-Ernte +
        ``tools_called``-Annotation wie in ``tool_loop_messages``), dann
        dieses Gate.

        Der Zweig der Muster-Engine bleibt Ausdruck für Ausdruck derselbe.
        """
        return (classification.intent_id in _spec_search_intents
                and _spec_has_enough_signal())

    if (
        safety.risk_level != "high"
        and _startet_der_vorabruf()
        # Bedarfssteuerung: M16 (Themenseiten-Inhalt) macht weiter unten seine
        # EIGENE gezielte Auflösung (Sammlung → get_topic_page_content). Die
        # generische Spekulativ-Suche wäre hier verworfene MCP-Arbeit → skip.
        and (getattr(classification, "pattern_id_hint", "") or "").strip() != "M16"
        # B2 (2026-06-10): I04 mit gesetztem thema landet im LP-Fast-Path,
        # der seine EIGENEN MCP-Calls feuert und das Spekulativ-Ergebnis
        # immer verwirft (spec_blocked enthält _lp_routed) — die 1-3
        # Spekulativ-Roundtrips wären reine verworfene Arbeit → skip.
        and not (
            classification.intent_id == "I04"
            and str((classification.entities or {}).get("thema") or "").strip()
        )
    ):
        try:
            spec_query = _spec_query_from_classification()
            _ents_for_spec = classification.entities or {}
            _medientyp = _ents_for_spec.get("medientyp")
            _fach = _ents_for_spec.get("fach")
            _stufe = _ents_for_spec.get("stufe")
            _msg_low = (req.message or "").lower()
            _wants_topic = any(k in _msg_low for k in (
                "themenseite", "themenseiten", "fachportal", "portalseite",
            ))
            # _wants_content_only: True nur wenn explizit ein Medientyp
            # (Video / Arbeitsblatt / interaktive Übung / …) genannt ist.
            _wants_content_only = bool(_medientyp)

            # Welle-A.3 (rev. Welle E v4+12): Themenseiten-Primary-Switch.
            # Wenn der LLM-Hint M06 (Themenseiten-Suche) sagt ODER I03
            # vorliegt, soll der Primary-Call direkt search_wlo_topic_pages
            # sein — nicht erst Collections als Primary, was den Topic-
            # Pages-Index auf dem MCP-Server verbiegt.
            _hint_pattern = (getattr(classification, "pattern_id_hint", "") or "").strip()
            _topic_first = (
                _hint_pattern == "M06"
                or classification.intent_id == "I03"
                or _wants_topic
            )

            if spec_query:
                # 1. Primary tool — Welle E (2026-05-23): LLM-Klassifikator-
                #    Hint hat Vorrang vor der Heuristik. Wenn der Klassifikator
                #    explizit ein search_wlo_* Tool empfohlen hat, nutzen wir
                #    das. Heuristik dient nur noch als Fallback.
                _tool_hint = (getattr(classification, "tool_id_hint", "") or "").strip()
                _known_search_tools = {
                    "search_wlo_topic_pages",
                    "search_wlo_collections",
                    "search_wlo_content",
                    # W5-2a (Nutzer-Vorgabe 2026-07-30): das Kombi-Tool ist der
                    # Standard beim Suchen und darf die Heuristik überstimmen.
                    # Bis hierher fiel dieser Hint STILL durch — der
                    # Antwort-Prompt empfiehlt das Tool ausdrücklich
                    # (``response_prompt_tools_text``), die Zulassungsliste
                    # kannte es nicht, also entschied bei I03/M06 die
                    # Themenseiten-Heuristik gegen die Absicht des Modells.
                    "search_wlo_all",
                }
                if _tool_hint in _known_search_tools:
                    spec_tool_name = _tool_hint
                    logger.info(
                        "speculative tool from LLM-Hint: %s (reasoning=%s)",
                        _tool_hint,
                        (getattr(classification, "tool_reasoning", "") or "")[:80],
                    )
                elif _topic_first:
                    # W7 (Nutzer-Entscheid 2026-07-31): die HEURISTIK zwingt nicht
                    # mehr auf das zustandsbehaftete ``search_wlo_topic_pages``.
                    # Live gemessen: dessen Themenseiten-Index hängt serverseitig
                    # am letzten Collections-Call (siehe Kommentar bei
                    # ``_primary_max``), nicht an der Frage — beide Testzüge
                    # („Photosynthese", „Bruchrechnen") bekamen deshalb DIESELBEN
                    # drei Treffer, darunter zwei Redaktions-Vorlagen, und die
                    # standen als Karte 1-3 vor den echten Materialien.
                    # Das Kombi-Tool deckt topicPages in EINEM Round-Trip mit ab.
                    # Der ausdrückliche Nutzerwunsch bleibt unberührt: ``_wants_topic``
                    # dreht unten (Z. ~228) auf das dedizierte Tool zurück.
                    spec_tool_name = "search_wlo_all"
                elif _wants_content_only:
                    spec_tool_name = "search_wlo_content"
                else:
                    # Generic / collection / learning-path intent →
                    # start with collections (rich cards with preview/desc/chips)
                    spec_tool_name = "search_wlo_collections"

                # Medientyp-Fokus: der Nutzer will Einzelinhalte eines konkreten
                # Typs (Video/Arbeitsblatt/…). Ausschliesslich gefiltertes
                # search_wlo_content — KEIN Kombitool (search_wlo_all fetcht drei
                # Toepfe: zu langsam + unnoetige MCP-Last) und KEINE Sammlungen/
                # Themenseiten (will der Nutzer hier nicht sehen). Ueberschreibt
                # den _topic_first-/Fallback-Zweig oben.
                if _wants_content_only:
                    spec_tool_name = "search_wlo_content"

                # W5-2a: Hat der Nutzer ausdrücklich nach einer Themenseite
                # gefragt, schlägt dieser Wunsch das Kombi-Tool — „Sammlungen und
                # Themenseiten, wenn danach gefragt wird". Ohne diese Zeile bliebe
                # ``search_wlo_all`` als Name stehen, während ``_use_search_all``
                # unten wegen ``_wants_topic`` False ist: der Aufruf ginge mit den
                # Primary-Argumenten raus und die Antwort liefe in den falschen
                # Parser (``spec_is_search_all`` wählt ihn).
                if spec_tool_name == "search_wlo_all" and _wants_topic:
                    spec_tool_name = "search_wlo_topic_pages"

                # Primary collections requests get capped at maxResults=5
                # whenever a topic_pages-search is also expected: the WLO MCP
                # server's session-state index for ``search_wlo_topic_pages``
                # is determined by the LAST collections call, and only sticks
                # for small result sets.
                _primary_max = 10
                if spec_tool_name == "search_wlo_collections" and (
                    _wants_topic
                    or classification.intent_id in (
                        "I03", "I04",
                    )
                ):
                    _primary_max = 5
                spec_tool_args = {
                    "query": spec_query, "maxResults": _primary_max,
                }
                if _medientyp and spec_tool_name == "search_wlo_content":
                    spec_tool_args["learningResourceType"] = _medientyp
                if _fach:
                    spec_tool_args["discipline"] = _fach
                if _stufe:
                    spec_tool_args["educationalContext"] = _stufe

                # O1: Generischer Inhalts-/Sammlungs-Such-Turn → EIN kombinierter
                # search_wlo_all-Call (deckt content + collections + topicPages in
                # EINEM MCP-Round-Trip ab) statt primary + Extras.
                # Gate auf den AUFGELÖSTEN Primary-Tool-Namen, nicht auf den
                # Pattern-Hint: der Klassifikator routet viele breite Suchen auf
                # I03/M06 (Themenseiten), wählt als Tool aber search_wlo_content/
                # _collections — genau diese Fälle profitieren am stärksten.
                # Das dedizierte, session-stateful search_wlo_topic_pages bleibt
                # nur, wenn es der aufgelöste Primary ist ODER der Nutzer explizit
                # "Themenseite"/"Fachportal" getippt hat (_wants_topic).
                _use_search_all = (
                    spec_tool_name != "search_wlo_topic_pages"
                    and not _wants_topic
                    # Medientyp-Fokus nutzt NUR gefiltertes search_wlo_content
                    # (s.o.) — nie das kombinierte, langsamere search_wlo_all.
                    and not _wants_content_only
                )
                # Primary launch — bei Topic-Pages mit Warmup, sonst direkt.
                if _use_search_all:
                    spec_is_search_all = True
                    spec_tool_name = "search_wlo_all"
                    spec_tool_args = {
                        "query": spec_query,
                        "maxContent": max(_primary_max, 8),
                        "maxCollections": 5,
                        # Facetten-Zähler mitholen (parallel, ~0 Latenz) — nur
                        # hier, weil _use_search_all bei Medientyp-Fokus False ist,
                        # also genau die breiten Suchen, wo Eingrenzen hilft.
                        "includeFacets": True,
                    }
                    # Kein learningResourceType hier: _use_search_all ist bei
                    # Medientyp-Fokus False (s.o.), dieser Zweig laeuft also nur
                    # ohne Medientyp.
                    if _fach:
                        spec_tool_args["discipline"] = _fach
                    if _stufe:
                        spec_tool_args["educationalContext"] = _stufe
                    spec_task = asyncio.create_task(
                        call_mcp_tool("search_wlo_all", spec_tool_args)
                    )
                elif spec_tool_name == "search_wlo_topic_pages":
                    spec_task = asyncio.create_task(
                        _topic_pages_with_warmup(spec_query, spec_tool_args),
                    )
                else:
                    spec_task = asyncio.create_task(
                        call_mcp_tool(spec_tool_name, spec_tool_args)
                    )
                spec_task.add_done_callback(_retrieve_task_exception)
                logger.info(
                    "speculative primary=%s for intent=%s hint_pattern=%s args=%s",
                    spec_tool_name, classification.intent_id,
                    _hint_pattern, spec_tool_args,
                )

                # 2. Extra tools — fire in parallel to enrich the response.
                _extras: list[str] = []
                _all_search_intents = (
                    "I03", "I04",
                )
                if _topic_first:
                    # Primary war schon topic_pages → ergänze Collections
                    # + Content für die "staircase" (Themenseiten →
                    # Sammlungen → Inhalte).
                    _extras.append("search_wlo_collections")
                    if not _wants_content_only:
                        _extras.append("search_wlo_content")
                elif _wants_topic:
                    # Frontend hat "themenseite" im Text — primary war
                    # collections (R-17 hat nicht gegriffen), wir holen
                    # topic_pages dazu.
                    _extras.append("search_wlo_topic_pages")
                elif classification.intent_id in _all_search_intents:
                    # Generische Suche → Themenseiten als zusätzliche
                    # Card-Quelle (top of staircase) anbieten.
                    _extras.append("search_wlo_topic_pages")

                if classification.intent_id in _all_search_intents:
                    # Sicherstellen dass alle drei Tool-Klassen gelaufen
                    # sind. Doppelungen filtert das spätere Dedup anhand
                    # des Tool-Namens. (Der frühere _wants_samml-/Content-
                    # Collections-Append war seit O1 wirkungslos — entfernt
                    # 2026-07-09, Wächter-Test in test_chat_prefetch.py.)
                    if not _wants_content_only:
                        _extras.append("search_wlo_content")

                if _use_search_all:
                    # search_wlo_all deckt content + collections + topicPages
                    # bereits ab → keine separaten Extra-Calls feuern.
                    _extras = []
                if _wants_content_only:
                    # Medientyp-Fokus: nur der gefilterte Content-Primary,
                    # keine Sammlungs-/Themenseiten-Extras (s.o.).
                    _extras = []
                # Dedup: jede Tool-Klasse höchstens EINMAL als Extra (das frühere
                # „spätere Dedup" gab es nie → der Topic-First-Pfad feuerte z.B.
                # search_wlo_collections + _content je 2× = 2 identische MCP-Suchen).
                # Reihenfolge erhalten, Primary rausfiltern.
                _seen_extra: set[str] = set()
                _extras = [
                    e for e in _extras
                    if e != spec_tool_name
                    and not (e in _seen_extra or _seen_extra.add(e))
                ]
                for extra_name in _extras:
                    if extra_name == spec_tool_name:
                        continue
                    extra_args: dict[str, Any] = {"query": spec_query, "maxResults": 5}
                    if _fach:
                        extra_args["discipline"] = _fach
                    if _stufe:
                        extra_args["educationalContext"] = _stufe

                    # search_wlo_topic_pages is session-stateful on the
                    # WLO MCP server. Run a dedicated warmup before the
                    # topic_pages call (unless we already are the primary).
                    if extra_name == "search_wlo_topic_pages":
                        t = asyncio.create_task(
                            _topic_pages_with_warmup(spec_query, extra_args),
                        )
                    else:
                        t = asyncio.create_task(call_mcp_tool(extra_name, extra_args))

                    t.add_done_callback(_retrieve_task_exception)
                    extra_spec_tasks.append((extra_name, t))
                    logger.info("speculative extra=%s args=%s", extra_name, extra_args)
        except Exception as _e:
            logger.warning("speculative tool spawn failed: %s", _e)
            spec_task = None
    return SpeculativePrefetch(
        spec_task, spec_tool_name, spec_tool_args, spec_query,
        extra_spec_tasks, spec_is_search_all, _search_all_extras,
    )


async def _fallback_inline_search(message: str, classification_entities: dict) -> list[Any]:
    """Kompakter Fallback-Search wenn der LLM eine Liefer-Aussage gemacht
    hat aber keine Cards in der Response sind (Inline-Mode-Bug).

    Strategie: ``search_wlo_content`` mit dem User-Message als ``query``,
    plus optional ``discipline``/``educationalContext`` aus den
    klassifizierten Entities — damit der Treffer thematisch passt.
    Maximal 5 Treffer (passt zum Inline-Limit). Bei Fehlern leere Liste,
    NIEMALS exception nach außen.
    """
    try:
        from boerdi.services.mcp.client import call_mcp_tool as _ct
        from boerdi.services.mcp.parsers import parse_wlo_cards as _pc
        args: dict[str, Any] = {"query": message, "maxResults": 5}
        # Optional Filter aus den klassifizierten Entities übernehmen
        fach = (
            classification_entities.get("fach")
            if isinstance(classification_entities, dict)
            else None
        )
        stufe = (
            classification_entities.get("stufe")
            if isinstance(classification_entities, dict)
            else None
        )
        if isinstance(fach, str) and fach.strip():
            args["discipline"] = fach.strip()
        if isinstance(stufe, str) and stufe.strip():
            args["educationalContext"] = stufe.strip()
        raw = await _ct("search_wlo_content", args)
        if not raw:
            logger.info("fallback inline search: leer für query='%s'", message[:60])
            return []
        cards = _pc(raw)
        logger.info(
            "fallback inline search: %d Cards für query='%s'",
            len(cards or []), message[:60],
        )
        return cards or []
    except Exception as _e:
        # WICHTIG: warning statt debug, damit Import-/MCP-Fehler nicht
        # stillschweigend Fallback + Auto-Augmentation lahmlegen.
        logger.warning("fallback inline search failed: %s", _e)
        return []
