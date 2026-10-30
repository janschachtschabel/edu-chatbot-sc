"""Tool-calling loop for the chat turn (P5-3, port of ALT llm_tool_loop.py).

Fidelity-Port-Ausnahme to the ~300-line rule (spec §0.7): once the two neighbours were
split off, what remains is ONE function — ``_run_tool_loop`` at 685 lines, taken through
the AST gate ("206 nested stmts after sanctioned transforms, 24 pins"). Cutting it
further means rewriting it. Lapses at cutover.

This is the middle of three phases ``generate_response`` runs; the two around it
were split off and now live next door: assembling the messages (P12/P14) in
``tool_loop_messages``, and the closing fallback for a loop that exhausts its
iterations without a final answer (P16) in ``tool_loop_fallback``. What remains
here is the loop itself (P15). It is deliberately
independent of the downstream SSE layer — the loop *returns* the finished
``(response_text, cards, tools_called, outcomes)`` tuple; streaming to the
widget is the caller's concern (the optional ``on_token`` seam is the only
streaming touchpoint, and it injects the *upstream* LLM-token stream, not SSE).

Home: ``services/tool_loop.py`` drops ALT's ``llm_`` module prefix, mirroring
how ALT ``chat_prefetch`` → NEU ``services/prefetch.py`` — this sits with the
other turn-orchestration services (``prefetch``, ``turn_assembly``,
``card_pipeline``, ``outcome_service``), not the ``llm_*`` generators.

The pure inline-grouping helpers ALT co-located here (``_strip_trailing_option_
lines``, the card predicates, ``_ui_box_state_footer``, ``_redact_search_
content_for_llm``) already live framework-free in ``domain/inline_grouping.py``.

Transport seam (NEU-deviation, same rewrite as every ported LLM consumer):
ALT held module-level ``client``/``MODEL`` singletons and called
``client.chat.completions.create(**build_chat_kwargs(...))``. Eiserne Regel 3
forbids module-global connection state, so the call goes through
``llm.chat_completion`` (which wires model/routing/timeout/retry/semaphore
internally). Prompt text and control flow are ALT-verbatim. Precedent:
llm_curation.py / llm_learning_path.py.

Slice status: all three phases are ported — ``_max_iterations_fallback``
(P16, now in ``tool_loop_fallback``), ``_assemble_messages`` (P12/P14, now in
``tool_loop_messages``) and ``_run_tool_loop`` (P15, here).
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

from boerdi.domain.antwort_werkzeug import RESPOND_TO_USER, antwort_aus_argumenten
from boerdi.domain.content_types import als_liste
from boerdi.domain.host_capabilities import erlaubt
from boerdi.domain.inline_documents import (
    MAX_DOKUMENTE_JE_ZUG,
    ZEIGE_DOKUMENT,
    dokument_aus_argumenten,
)
from boerdi.domain.inline_grouping import (
    MIN_SELECTABLE_CARDS,
    _strip_trailing_option_lines,
    _ui_box_state_footer,
)
from boerdi.domain.inline_grouping import max_selectable_cards as _max_selectable
from boerdi.domain.reasoning_filters import strip_reasoning_markers
from boerdi.domain.skill_precedence import merke_laufende_anleitung
from boerdi.domain.tool_pflicht import fehlende_pflichtwerkzeuge, gerufene_werkzeuge
from boerdi.domain.tool_result_redaction import _redact_search_content_for_llm
from boerdi.domain.untrusted_text import frame_untrusted, frame_wissen
from boerdi.domain.werkzeug_angebot import NICHT_ANGEBOTEN, angebotene_namen
from boerdi.domain.write_confirm import (
    CONFIRM_TOKEN_FIELD,
    confirmed_args,
    extract_confirm_token,
    is_confirmable,
    is_expired,
    redact_confirm_token,
    remember_pending,
    strip_confirm_token,
    token_for,
)
from boerdi.i18n import DEFAULT
from boerdi.i18n.prompt_language import SPRACHE_DER_PERSON
from boerdi.obs.log_inhalt import inhalt
from boerdi.obs.usage import add_usage, extract_usage
from boerdi.obs.zeiten import seit_ms
from boerdi.services import llm
from boerdi.services.agent_tools import verborgene_werkzeuge
from boerdi.services.card_collect import CARD_YIELDING_TOOLS as _CARD_YIELDING_TOOLS
from boerdi.services.card_collect import collect_cards
from boerdi.services.fehlertext import antwort_fehlertext
from boerdi.services.llm_parallel import LlmAusgelastet
from boerdi.services.llm_streaming import _stream_completion
from boerdi.services.mcp.auth import aufrufer_kennung
from boerdi.services.mcp.parsers import skill_registry_note, skill_titel
from boerdi.services.response_tool_selection import _nameable_tools
from boerdi.services.zustimmung_pruefen import zugestimmt

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_logger = logging.getLogger(__name__)


# Die Menge wohnt seit A4c-2a bei der Logik, die sie auswertet
# (``services/card_collect``, mit ihrer Begründung); hier bleibt der Name
# gebunden, weil dieses Modul der angestammte Fundort ist und Tests ihn so lesen.
CARD_YIELDING_TOOLS = _CARD_YIELDING_TOOLS

#: Wo der Musterweg die gelieferten Ergebnis-Boxen ablegt (D3). Diese Schleife
#: kennt kein ``ctx``; ihr Weg nach oben ist der ``session_state``, wie schon
#: bei ``_selected_card_ids`` und ``_write_preview``. Der Merker gehört DIESEM
#: Zug — ``graph/nodes/persist`` holt ihn mit ``pop`` ab.
GELIEFERTE_DOKUMENTE_KEY = "_gelieferte_dokumente"

#: Lokale Werkzeuge, die nur laufen, wenn dieser Zug sie anbietet (Paket 4, A2).
_DARSTELLUNGS_WERKZEUGE = frozenset({"select_top_cards", RESPOND_TO_USER, ZEIGE_DOKUMENT})

_DOKUMENT_FEHLER = (
    "Fehler: Das Dokument war unbrauchbar — ``titel`` und ``markdown`` muessen "
    "nichtleere Zeichenketten sein. Wiederhole den Aufruf mit dem "
    "vollstaendigen Ergebnis, oder antworte in Prosa."
)

_DOKUMENT_DECKEL = (
    "Hinweis: Fuer diesen Zug sind bereits genug Boxen geliefert. Schreibe "
    "jetzt deinen Begleitsatz."
)


def _nimm_dokument_an(roh_args: str, session_state: dict) -> str:
    """Einen ``zeige_dokument``-Aufruf annehmen; Rückgabe ist die Quittung.

    Die Quittung ist keine Höflichkeit: ohne sie wüsste das Modell nicht, ob der
    Inhalt angekommen ist, und schriebe ihn sicherheitshalber noch einmal in die
    Prosa-Antwort — dann stünde er doppelt da.

    Unbrauchbare Argumente sind ein Werkzeugfehler und kein Zug-Ende (B8): das
    Modell soll den Aufruf richtig wiederholen oder in Prosa antworten können.
    """
    try:
        args = json.loads(roh_args or "{}")
    except (json.JSONDecodeError, TypeError):
        return _DOKUMENT_FEHLER
    dokument = dokument_aus_argumenten(args)
    if dokument is None:
        _logger.info("zeige_dokument: unbrauchbare Argumente")
        return _DOKUMENT_FEHLER
    geliefert = session_state.setdefault(GELIEFERTE_DOKUMENTE_KEY, [])
    if len(geliefert) >= MAX_DOKUMENTE_JE_ZUG:
        _logger.info("zeige_dokument: Deckel von %d erreicht", MAX_DOKUMENTE_JE_ZUG)
        return _DOKUMENT_DECKEL
    geliefert.append(dokument)
    # Ohne den Titel: er ist Modell-Ausgabe aus Nutzer-Inhalt und kann bei
    # ``art: zeugnis`` einen Namen tragen. Art und Länge tragen die Diagnose.
    _logger.info("zeige_dokument: Box übernommen (%s, %d Zeichen)",
                 dokument["kind"], len(dokument["content"]))
    return (
        f"Uebernommen: '{dokument['title']}' wird als Box angezeigt. Schreibe "
        "jetzt nur noch einen kurzen Begleitsatz — NICHT den Inhalt noch einmal."
    )


async def _run_tool_loop(
    session: AsyncSession,
    message: str,
    classification: dict[str, Any],
    pattern_output: dict[str, Any],
    pattern_label: str,
    session_state: dict,
    rag_context: str,
    blocked_tools: list[str],
    active_tools: list[dict],
    _inline_qr_enabled: bool,
    _inline_grouping_mode: bool,
    messages: list[dict],
    all_cards: list[dict],
    tools_called: list[str],
    outcomes: list,
    knowledge_prefetched: bool,
    mcp_prefetched: bool,
    always_areas: list[str],
    _RAG_TOP_K: int,
    _RAG_MIN_SCORE: float,
    _RAG_MAX_CHARS_PER_AREA: int,
    usage_acc: dict[str, Any] | None,
    on_token: Any,
    *,
    tool_mode: str | None = None,
    rag_bereiche: frozenset[str] = frozenset(),
    sprache: str = DEFAULT,
) -> tuple[str, list[dict], list[str], list] | None:
    """Tool-Calling-Loop (Phase P15) fuer ``generate_response`` — verbatim port
    of ALT llm_tool_loop.py:565-1158: tool_choice-Gates, Stream-vs-Create,
    Usage-Phase-Label, Tool-Dispatch (select_top_cards / respond_to_user /
    query_knowledge / blocked / Filter-Injektion / call_with_outcome /
    Card-Parse-Merge) und Reflection-Retry (Phase A1).

    NEU-deviations (sanctioned, see the AST fidelity gate): ``session`` is
    prepended for the pg-DI ``get_rag_context`` seam; the LLM round goes
    through ``llm.chat_completion`` / ``_stream_completion`` on SEMANTIC
    kwargs instead of ALT's ``build_chat_kwargs(model=MODEL, ...)`` +
    ``client`` singleton; usage folding uses the ``obs.usage`` names
    (``add_usage``/``extract_usage``); the ALT no-op
    ``resolve_discipline_labels`` call is dropped (lp_fast_path precedent).

    Returns: das finale ``(response_text, wlo_cards, tools_called,
    outcomes)``-Tupel (Final-Answer- oder API-Fehlerpfad) ODER ``None``
    als Fortsetzungs-Marker, wenn max_iterations ohne finale Antwort
    erreicht wurde — der Call-Site faellt dann auf
    ``_max_iterations_fallback`` (P16) durch. ``messages``/``all_cards``/
    ``tools_called``/``outcomes`` werden in-place weitergefuehrt, der
    Fallback sieht also den vollen Loop-Stand.
    """
    max_iterations = 5
    first_iteration = True
    # Phase A1 — Reflection-Loop-Flag: nur EINMAL retryen, sonst Endlosschleife
    _reflection_done = False
    # Verbrauchte Wiederholungen nach einem Aussetzer des Anbieters (s.u.).
    _leerlaeufe = 0
    # Token-Streaming: höchstens EINE gestreamte Antwortrunde je Zug (Review L1).
    _strom_verbraucht = False
    # E1 (2026-08-10): der offene Bestätigungsvorgang, wie er beim EINTRITT in
    # diesen Zug aussah. Genau das macht ihn zur Zeitgrenze: eine Vorschau, die
    # weiter unten in diesem Zug entsteht, landet in ``session_state`` — aber
    # nicht mehr hier. Sie ist damit erst im nächsten Zug bestätigbar, und
    # zwischen zwei Zügen steht der Mensch. ``_run_tool_loop`` wird genau
    # einmal pro Zug betreten (``services/generate.py:153``, einzige
    # Aufrufstelle) — daran hängt diese Eigenschaft.
    # Der Schnappschuss vom Zug-Eintritt. Er wohnt in ``entities``, weil NUR
    # die fünf Spalten aus ``update_session`` einen Zug überdauern; ein
    # Schlüssel auf oberster Ebene von ``session_state`` stirbt mit der
    # Anfrage (``graph/nodes/setup.py`` baut den Zustand jeden Zug neu).
    # Bis 2026-08-11 stand er dort — dadurch war dies immer ``None`` und
    # keine Bestätigung je einlösbar.
    _pending_at_turn_start = (session_state.get("entities") or {}).get("_pending_write")
    # An den MCP geht nur, was im Katalog des Muster-Wegs steht (Audit
    # 2026-09-29, B-M1) — nicht nur, was dieses Muster aufzählt: Muster-Texte
    # verlangen Werkzeuge ausserhalb ihrer ``tools``-Liste (M10
    # ``get_node_details``, M18 ``get_compendium_text``), und gespeicherte
    # Muster ändert kein Seed (Review 2026-10-03). Ohne Zugangsblock fehlen dem
    # Katalog die kuratierenden Werkzeuge. Dazu das Werkzeug des offenen
    # Vorgangs aus dem vorigen Zug, sonst liefe eine Zustimmung über den
    # Fingerabdruck-Weg ins Leere; ob zugestimmt wurde, entscheidet die Wall.
    _angeboten = angebotene_namen(active_tools) | angebotene_namen(_nameable_tools())
    if isinstance(_pending_at_turn_start, dict) and _pending_at_turn_start.get("tool"):
        _angeboten = _angeboten | {str(_pending_at_turn_start["tool"])}
    # Die Erlaubnis der Einbettung gilt auch hier, wie im Agent-Weg (Paket 4,
    # P4-1): ``read-only`` nimmt dem Katalog alles Schreibende, auch das
    # Werkzeug eines offenen Vorgangs. Im Studio Verborgenes fehlt ihm ebenso —
    # hier und nicht in ``blocked_tools`` (Review Paket 9): ein Aufruf gilt dann wie
    # ein Name außerhalb des Katalogs, nicht als Sicherheitssperre mit ``error``.
    _verborgen = verborgene_werkzeuge()
    _angeboten = {name for name in _angeboten
                  if erlaubt(name, tool_mode) and name not in _verborgen}
    # Die Darstellungswerkzeuge laufen nur, wenn dieser Zug sie anbietet
    # (Paket 4, A2): die Auswahl hält sie bewusst zurück, etwa im Rückfrage-
    # Muster oder bei abgeschalteter Karten-Auswahl (``response_tool_selection``).
    _direkt_angeboten = angebotene_namen(active_tools)
    # S4 (2026-08-14): Die Zustimmung steht in der Nachricht des Menschen, nicht
    # in den Argumenten des Modells — siehe ``domain/write_confirm``. Die letzte
    # Nachricht mit ``role: "user"`` IST die dieses Zugs: ``_assemble_messages``
    # haengt sie zuletzt an, und der Loop ergaenzt darunter nur noch
    # ``assistant``/``tool``. Einmal gelesen, bevor der Loop laeuft.
    _nutzernachricht = next(
        (str(m.get("content") or "")
         for m in reversed(messages) if m.get("role") == "user"),
        "",
    )

    for iteration in range(max_iterations):  # noqa: B007 — verbatim ALT (unused index)
        tool_choice: Any = None
        if active_tools:
            # Force tool call on first iteration — but NOT if context is already available
            # (pre-fetched knowledge or prior content cards already provide context)
            has_prior_content = bool(session_state.get("entities", {}).get("_last_contents"))
            # Pattern-Override: Discovery/Listing-Patterns brauchen IMMER den
            # echten Tool-Output (Karten), auch wenn RAG-Kontext da ist —
            # sonst antwortet der LLM mit einer Aufzählung in Text statt mit
            # klickbaren Karten. WLO-MCP-Calls sind günstig, also kann der
            # Extra-Round-Trip sein.
            pattern_forces_tool = bool(pattern_output.get("force_tool_use"))
            # `tools_called` enthält ggf. bereits "query_knowledge (prefetch)"
            # vom RAG-Vorabfetch — das soll force_tool_use NICHT blockieren.
            # Nur ECHTE MCP-Tool-Calls (kein "(prefetch)"-Suffix) zählen als
            # "Tool wurde schon aufgerufen, Force erfüllt".
            real_tools_called = [
                t for t in tools_called
                if not (isinstance(t, str) and "(prefetch)" in t)
            ]
            if pattern_forces_tool and first_iteration and not real_tools_called:
                tool_choice = "required"
                _logger.info(
                    "force_tool_use=true → tool_choice=required (active_tools=%d)",
                    len(active_tools),
                )
            elif (
                first_iteration
                and not tools_called
                and not knowledge_prefetched
                and not mcp_prefetched
                and not has_prior_content
            ):
                tool_choice = "required"
            first_iteration = False

        # Map pattern.length → GPT-5 verbosity. RAG/knowledge-heavy turns get
        # an extra bump so the model actually USES the prefetched context
        # rather than condensing it into a one-liner.
        _length = (pattern_output.get("length") or "mittel").lower()
        _verbosity_map = {"kurz": "low", "mittel": "medium", "lang": "high"}
        _verbosity = _verbosity_map.get(_length, "medium")
        if knowledge_prefetched or (rag_context and len(rag_context) > 500):
            # RAG context present → lift at least one notch (medium → high).
            if _verbosity == "low":
                _verbosity = "medium"
            elif _verbosity == "medium":
                _verbosity = "high"

        kwargs = dict(
            messages=messages,
            tools=active_tools or None,
            tool_choice=tool_choice,
            temperature=0.4,
            verbosity=_verbosity,
        )

        # Gestreamt wird eine Runde nur, wenn die A1-Reflexion ihre Antwort nicht
        # mehr verwerfen kann — sonst stünde verworfener Text schon beim Client
        # (Plan Token-Streaming, T10).
        _strom_runde = on_token is not None and not _strom_verbraucht and (
            _reflection_done or not fehlende_pflichtwerkzeuge(pattern_output, tools_called))
        _t0 = time.perf_counter()
        try:
            if _strom_runde:
                # Phase-2 Streaming — same kwargs but tokens arrive progressively
                # via on_token. The reconstructed _StreamedResponse exposes the
                # same attributes so the tool-loop body below is unchanged.
                resp = await _stream_completion(on_token, **kwargs)
            else:
                resp = await llm.chat_completion(**kwargs)
        except Exception as e:
            if isinstance(e, LlmAusgelastet):
                # Last, kein Fehler: ohne Traceback (``llm_platz_frist`` meldet gedrosselt).
                _logger.info("LLM API: kein Platz frei — Zug ausgelastet")
            else:
                _logger.exception("LLM API error (%s)", type(e).__name__)
            # Der Grund steht im Log, die Person sieht die Fehlerblase des Chats
            # mit der Fehlernummer (Paket 18C/D; bis dahin der Typ, davor „Fehler bei
            # der Verarbeitung: {e}“ mit Interna aus der Anbieter-Meldung).
            # Paket 18F: ohne LLM-Platz die „ausgelastet“-Blase statt einer Fehlernummer —
            # in der Sprache der Person (Review 18F: bis dahin immer DEFAULT).
            text = antwort_fehlertext(sprache, "error.internal", fehler=e)
            return text, all_cards, tools_called, outcomes

        choice = resp.choices[0]
        if _strom_runde and any(tc.function.name == RESPOND_TO_USER
                                for tc in (choice.message.tool_calls or [])):
            # Endet diese Runde nicht (etwa mit unlesbaren Argumenten, B8),
            # hinge die nächste Antwort sichtbar an der ersten — sie läuft
            # deshalb ungestreamt, und ``result`` ersetzt den Text.
            _strom_verbraucht = True
        if usage_acc is not None:
            # A2.1 — Phase-Label je Iteration: tool-Iteration vs final response.
            # Hilft bei der Cache-Hit-Rate-Diagnose: "response"-Calls haben oft
            # keinen Cache-Hit, weil Tool-Output-Messages den Prompt variieren.
            # Eine Runde mit ``respond_to_user`` IST die Antwort (Vorgabe seit
            # 2026-09-30), auch wenn sie als Werkzeugaufruf kommt.
            _phase = (
                "tool_loop"
                if (choice.finish_reason == "tool_calls" and choice.message.tool_calls
                    and not any(tc.function.name == "respond_to_user"
                                for tc in choice.message.tool_calls))
                else "response"
            )
            add_usage(usage_acc, extract_usage(resp), phase=_phase, ms=seit_ms(_t0))

        # Track whether the model used the optional respond_to_user tool —
        # if so, the for-loop's tool-handling falls through and we treat it
        # as the final response instead of a continued tool round-trip.
        _inline_response_text: str | None = None
        _inline_quick_replies: list[str] = []

        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            # Diagnose (2026-07-04): zählt netz-gebundene MCP-Tool-Calls PRO
            # LLM-Runde. Nur bei ≥2 in EINER Runde würde eine Parallelisierung
            # (asyncio.gather statt seriellem await) überhaupt Wall-Clock
            # sparen — diese Zeile liefert die Häufigkeitsdaten für diese
            # Entscheidung. Lokale/virtuelle Tools (Auswahl, Inline-Antwort,
            # RAG) sind kein MCP-Netz-Call und zählen nicht mit. Rein
            # beobachtend, kein Verhaltenseffekt.
            _LOCAL_TOOLS = {"select_top_cards", "respond_to_user", "query_knowledge",
                            ZEIGE_DOKUMENT}
            _mcp_calls_this_round = sum(
                1 for _tc in choice.message.tool_calls
                if _tc.function.name not in _LOCAL_TOOLS
            )
            if _mcp_calls_this_round >= 2:
                _logger.info(  # log-ok: Werkzeugnamen
                    "parallel-mcp-round: %d netz-gebundene MCP-Tool-Calls in einer "
                    "Runde (%s) — Kandidat für gather-Parallelisierung",
                    _mcp_calls_this_round,
                    [tc.function.name for tc in choice.message.tool_calls],
                )
            # Convert message to a dict shape OpenAI accepts on the next call.
            # Non-streaming responses ship a Pydantic ChatCompletionMessage that
            # the SDK can re-serialize; the streaming path produces our own
            # ``_StreamedMessage`` shim, which has the same attributes but
            # isn't auto-serialized — hand it through as a plain dict so both
            # paths work uniformly.
            messages.append({
                "role": getattr(choice.message, "role", "assistant"),
                "content": getattr(choice.message, "content", None),
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    } for tc in choice.message.tool_calls
                ],
            })
            # ── Ergebnis-Dokumente ZUERST (D3) ────────────────────
            # Eine Vorrunde und nicht bloß ein Zweig weiter unten: der
            # ``respond_to_user``-Zweig verlässt die Runde mit ``break``, und
            # stünde die finale Antwort VOR dem Dokument in derselben Runde,
            # ginge ein fertiges Arbeitsergebnis verloren. Genau die
            # Abhängigkeit von der Ausgabe-Reihenfolge des Modells, die dieser
            # Umbau beseitigen soll. Virtuell wie ``select_top_cards``: geht
            # nie an den MCP, zählt daher nicht als Werkzeugaufruf.
            _dokument_calls: set[str] = set()
            for tc in choice.message.tool_calls:
                if tc.function.name != ZEIGE_DOKUMENT:
                    continue
                _dokument_calls.add(tc.id)
                if ZEIGE_DOKUMENT not in _direkt_angeboten:
                    _logger.warning("tool-call %s: nicht angeboten, verworfen", ZEIGE_DOKUMENT)
                    messages.append({
                        "role": "tool", "tool_call_id": tc.id, "content": NICHT_ANGEBOTEN,
                    })
                    continue
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": _nimm_dokument_an(tc.function.arguments, session_state),
                })

            for tc in choice.message.tool_calls:
                if tc.id in _dokument_calls:
                    continue          # in der Vorrunde erledigt und quittiert
                tool_name = tc.function.name
                # B8 (2026-06-10): malformed Tool-Args (Token-Limit-Abbruch,
                # Streaming-Reassembly) warfen vorher den GANZEN Turn auf den
                # generischen Fehlerpfad. Stattdessen: als Tool-Fehler zurück-
                # melden und weiterlaufen — das LLM wiederholt den Call dann
                # mit korrektem JSON oder antwortet ohne Tool.
                try:
                    tool_args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError) as _ja_err:
                    _logger.warning("tool-call %s: malformed arguments (%s)",
                                    tool_name, _ja_err)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": ("Fehler: Die Tool-Argumente waren kein "
                                    "gültiges JSON. Bitte denselben Aufruf "
                                    "mit korrektem JSON wiederholen."),
                    })
                    continue
                # Darstellungswerkzeuge nur mit Angebot (Paket 4, A2, s. o.).
                # ``query_knowledge`` ist bewusst ausgenommen: Die Domänen-Regeln
                # verlangen es musterübergreifend, M10 als Pflicht für Berichte —
                # auch wo es nicht angeboten ist. Eine Sperre änderte diese
                # Antworten und braucht erst einen Golden-Lauf.
                if tool_name in _DARSTELLUNGS_WERKZEUGE and tool_name not in _direkt_angeboten:
                    _logger.warning("tool-call %s: nicht angeboten, verworfen", tool_name)
                    messages.append({
                        "role": "tool", "tool_call_id": tc.id, "content": NICHT_ANGEBOTEN,
                    })
                    continue
                tools_called.append(tool_name)

                # ── Inline-Mode-Curation: select_top_cards ────────────
                # LLM-Auswahl der finalen Treffer-Anzeige (siehe Tool-
                # Definition oben). IDs in session_state stashen — wird im
                # Postprocess (_apply_widget_modes_postprocess) genutzt, um
                # die Cards auf genau diese IDs zu filtern in dieser
                # Reihenfolge.
                if tool_name == "select_top_cards":
                    ids = tool_args.get("card_ids") or []
                    reasoning = (tool_args.get("reasoning") or "").strip()
                    # Sanitize: nur Strings, dedupe, gedeckelt auf das
                    # Auswahl-Budget aus den Studio-Gruppen. Hier stand bis
                    # 2026-08-14 eine harte 5 — quer über ALLE Boxen. Da der
                    # Postprocess die Karten danach auf genau diese IDs
                    # filtert, konnten Einzelinhalte die Plätze belegen und
                    # eine gesuchte Sammlung fiel heraus, obwohl
                    # ``sammlungen_max`` drei erlaubt. Begründung und
                    # Grenzen: ``domain/inline_grouping.max_selectable_cards``.
                    try:
                        from boerdi.services.config_loader import (
                            load_display_rules_config as _ldrc_sel,
                        )
                        _max_sel = _max_selectable(_ldrc_sel() or {})
                    except Exception:
                        # Sichtbar, nicht still: der Rückfall ist genau der
                        # Zustand, den #193 beseitigt hat — eine unlesbare
                        # Config nähme ihn stillschweigend zurück.
                        _logger.warning(
                            "display_rules für den Auswahl-Deckel unlesbar; "
                            "nehme die Untergrenze", exc_info=True)
                        _max_sel = MIN_SELECTABLE_CARDS
                    clean_ids: list[str] = []
                    seen: set[str] = set()
                    for x in ids:
                        # Trim FIRST, then judge: comparing the raw value against
                        # a set of trimmed ones let " abc " slip past "abc".
                        xs = x.strip() if isinstance(x, str) else ""
                        if xs and xs not in seen:
                            clean_ids.append(xs)
                            seen.add(xs)
                        if len(clean_ids) >= _max_sel:
                            break
                    session_state["_selected_card_ids"] = clean_ids
                    session_state["_selected_card_reasoning"] = reasoning
                    _logger.info(
                        "select_top_cards: %d IDs picked — %s",
                        len(clean_ids), inhalt(reasoning),
                    )
                    # Welle E (2026-05-23) — Konsistenz Prompt ↔ Anzeige:
                    # nach der Auswahl bekommt der LLM einen verschärften
                    # Reminder, dass er NUR über diese IDs sprechen darf.
                    # Backend-seitiges Trunken der älteren Tool-Results
                    # wäre noch sauberer (siehe TODO), würde aber den
                    # OpenAI-Tool-Call-Chain brechen.
                    _consistency_tail = ""
                    try:
                        from boerdi.services.config_loader import (
                            load_display_rules_config as _ldrc,
                        )
                        _dr_pak = (_ldrc().get("prompt_anzeige_konsistenz") or {})
                        _pak_excl = set(_dr_pak.get("exclude_patterns") or [])
                        if (
                            _dr_pak.get("enabled", True)
                            and (pattern_output.get("id") or "") not in _pak_excl
                            and clean_ids
                        ):
                            _consistency_tail = (
                                "\n\nWICHTIG: Im nächsten ``respond_to_user``-"
                                "Aufruf darfst du NUR über genau diese "
                                f"{len(clean_ids)} ausgewählten IDs sprechen. "
                                "Material, Sammlungen oder Themenseiten, die "
                                "in vorigen Tool-Results stehen aber NICHT in "
                                "dieser Auswahl, NICHT erwähnen — der User "
                                "sieht im Frontend nur diese gewählten Treffer. "
                                "Wenn du im Text auf Treffer Bezug nimmst: "
                                "ausschließlich auf die gewählten."
                            )
                    except (AttributeError, TypeError) as e:
                        # Paket 18E: der Hinweis fällt weg, die Auswahl gilt trotzdem.
                        _logger.debug("Konsistenz-Hinweis: display-rules unlesbar (%s)",
                                      type(e).__name__)
                        _consistency_tail = ""

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": (
                            (
                                f"OK — Auswahl gespeichert ({len(clean_ids)} IDs). "
                                "Rufe jetzt respond_to_user mit der Prosa-Antwort auf."
                                if _inline_qr_enabled
                                else f"OK — Auswahl gespeichert ({len(clean_ids)} IDs)."
                            ) + _consistency_tail
                        ),
                    })
                    continue

                # ── Combined-output: model emitted FINAL answer + quick_replies ─
                # See ``domain/antwort_werkzeug``. Treat this as the equivalent
                # of a finish_reason == "stop" with the extracted text. Count and
                # length are capped at assembly (``filtere_vorschlaege``), where
                # the pattern's count is known.
                if tool_name == RESPOND_TO_USER:
                    _inline_response_text, _inline_quick_replies = antwort_aus_argumenten(
                        tool_args)
                    # Safety net: the model occasionally ALSO writes the quick-
                    # replies / "Bring mich hin"-link as bold lines at the END of
                    # the answer text. They belong only in quick_replies (rendered
                    # as pills/buttons), not as text in the bubble — strip them.
                    _inline_response_text = _strip_trailing_option_lines(
                        _inline_response_text, _inline_quick_replies
                    )
                    # OpenAI requires every tool call to be followed by a
                    # role=tool message in the chain. Acknowledge briefly.
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": "OK",
                    })
                    # The break below skips every SIBLING call of this same
                    # parallel batch, leaving them without a role=tool answer.
                    # Normally harmless (the chain is discarded), but the
                    # reflection retry further down re-sends exactly this chain
                    # — and OpenAI rejects one in which a tool_call has no tool
                    # message, so the turn degraded to an error bubble although
                    # the model's answer was already in hand (audit 2026-08-12,
                    # F-5). The answer is deliberately NOT "OK": in that retry
                    # it would tell the model a search had run when it had not.
                    _answered = {
                        m.get("tool_call_id") for m in messages
                        if isinstance(m, dict) and m.get("role") == "tool"
                    }
                    for _sibling in choice.message.tool_calls:
                        if _sibling.id in _answered:
                            continue
                        messages.append({
                            "role": "tool",
                            "tool_call_id": _sibling.id,
                            "content": ("Nicht ausgeführt: Die Antwort wurde "
                                        "bereits mit respond_to_user gegeben."),
                        })
                    # Don't process more tool calls — respond_to_user means
                    # we're done.
                    break

                # ── Handle virtual knowledge tool ──────────────
                if tool_name == "query_knowledge":
                    from boerdi.services.rag.retrieval import get_rag_context
                    from boerdi.services.response_tool_selection import wissensbereiche
                    area = tool_args.get("area", "general")
                    query = tool_args.get("query", message)
                    # Paket 9 (V2): gesperrt oder nicht angeboten heißt nicht abgefragt.
                    # Ohne das Werkzeug im Angebot bleibt es rufbar (Paket 4, A2: die
                    # Domänen-Regeln verlangen es musterübergreifend) — dann in den
                    # konfigurierten Bereichen (``rag_bereiche``), nicht in jedem der
                    # Datenbank. Ein eigener Name: ``_angeboten`` ist der
                    # Werkzeug-Katalog des ganzen Zuges (Review Paket 9).
                    _bereiche = wissensbereiche(active_tools) or rag_bereiche
                    if (tool_name in blocked_tools or not isinstance(area, str)
                            or area not in _bereiche):
                        _logger.warning("query_knowledge(%s) abgewiesen (%s)", area,
                                        "gesperrt" if tool_name in blocked_tools
                                        else "nicht angeboten")
                        messages.append({
                            "role": "tool", "tool_call_id": tc.id,
                            "content": (
                                "Tool wurde aus Sicherheitsgruenden blockiert."
                                if tool_name in blocked_tools
                                else f"Bereich '{area}' ist in diesem Zug nicht verfügbar. "
                                     f"Verfügbar: {', '.join(sorted(_bereiche)) or 'keiner'}."),
                        })
                        continue

                    # Track explicitly-queried RAG areas in session_state so the
                    # downstream Guide-QR-injector (chat.py:_attach_guide_qr) can
                    # offer a "Bring mich hin"-link to the area's source URL
                    # (z.B. WissenLebtOnline → https://wissenlebtonline.de/).
                    # Bewusst NUR explizite Calls — die mode:always-Prefetch
                    # läuft immer, das wäre als Guide-Trigger zu breit.
                    used = session_state.setdefault("_rag_areas_used", [])
                    if area and area not in used:
                        used.append(area)

                    # Guard: if this area was already covered by the pre-fetch
                    # and the query is the same, return a short hint instead of
                    # re-querying the database (saves an embedding API call).
                    if knowledge_prefetched and area in always_areas and query == message:
                        _logger.info("query_knowledge(%s): skipped — already pre-fetched", area)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": (
                                f"Bereich '{area}' wurde bereits vorab durchsucht. "
                                "Die Ergebnisse findest du in der vorherigen query_knowledge-Antwort."  # noqa: E501
                            ),
                        })
                        continue

                    _explicit_sources: list[str] = []
                    result_text = await get_rag_context(
                        session, query, areas=[area], top_k=_RAG_TOP_K,
                        min_score=_RAG_MIN_SCORE,
                        max_chars_per_area=_RAG_MAX_CHARS_PER_AREA,
                        out_sources=_explicit_sources,
                    )
                    if _explicit_sources:
                        used_src = session_state.setdefault("_rag_top_sources", [])
                        for s in _explicit_sources:
                            if s not in used_src:
                                used_src.append(s)
                    _logger.info("query_knowledge(%s): %d chars", area, len(result_text))
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        # Paket 9 (V6): ein Treffer ist Text von Dritten — gerahmt.
                        "content": frame_wissen(result_text[:6000]) if result_text else (
                            f"Keine relevanten Informationen im Bereich '{area}' gefunden."),
                    })
                    continue

                # ── Handle MCP tools ──────────────────────────
                # Safety: refuse blocked tools (Triple-Schema T-19)
                if tool_name in blocked_tools:
                    from boerdi.api.schemas import ToolOutcome
                    outcomes.append(ToolOutcome(
                        tool=tool_name, status="error",
                        error="blocked by safety layer",
                    ))
                    messages.append({
                        "role": "tool", "tool_call_id": tc.id,
                        "content": "Tool wurde aus Sicherheitsgruenden blockiert.",
                    })
                    continue
                # Nur Katalog-Werkzeuge gehen an den MCP (B-M1, s. o.): ein
                # fremder Name kommt aus einer Halluzination oder einer
                # Einschleusung im Fremdtext. Kein ``outcomes``-Eintrag: es lief
                # nichts, und ein ``error`` senkte Zuversicht und Zustand
                # (Review 2026-10-03).
                if tool_name not in _angeboten:
                    _logger.warning("tool-call %s: nicht im Katalog, verworfen", tool_name)
                    messages.append({
                        "role": "tool", "tool_call_id": tc.id, "content": NICHT_ANGEBOTEN,
                    })
                    continue

                # Enforce maxResults limit on search/collection tools.
                # (maxItems is a legacy alias accepted by our Pydantic validator.)
                MAX_RESULTS = 5
                if tool_name in ("search_wlo_collections", "search_wlo_content", "get_collection_contents"):  # noqa: E501
                    # Migrate legacy key if the LLM passed the old name.
                    if "maxItems" in tool_args and "maxResults" not in tool_args:
                        tool_args["maxResults"] = tool_args.pop("maxItems")
                    tool_args.setdefault("maxResults", MAX_RESULTS)
                    if tool_args["maxResults"] > MAX_RESULTS:
                        tool_args["maxResults"] = MAX_RESULTS

                # ── Safety net: forward entity-level filters the LLM forgot ──
                # The classifier extracts medientyp / fach / stufe up-front; the
                # LLM is instructed to pass them as learningResourceType /
                # discipline / educationalContext on content searches, but it's
                # not 100% reliable (especially when it chains
                # search_wlo_collections first and then does a "fallback"
                # search_wlo_content). We inject missing filters here so user
                # intent isn't lost. mcp_client's fuzzy label→URI resolver
                # tolerates paraphrased entity values.
                if tool_name == "search_wlo_content":
                    _classif_entities = classification.get("entities", {}) or {}
                    # Migrate any legacy keys the LLM might still send
                    if "resourceType" in tool_args and "learningResourceType" not in tool_args:
                        tool_args["learningResourceType"] = tool_args.pop("resourceType")
                    if "educationalLevel" in tool_args and "educationalContext" not in tool_args:
                        tool_args["educationalContext"] = tool_args.pop("educationalLevel")
                    _medientyp = _classif_entities.get("medientyp")
                    # Paket 18B: mehrere Typen als Liste (``mcp/listen_argumente``).
                    _medientypen = als_liste(_classif_entities.get("medientypen"))
                    if len(_medientypen) > 1:
                        _medientyp = _medientypen
                    if _medientyp and "learningResourceType" not in tool_args:
                        _logger.info(
                            "injecting learningResourceType=%r from entities.medientyp (LLM omitted it)",  # noqa: E501
                            _medientyp,
                        )
                        tool_args["learningResourceType"] = _medientyp
                    _fach = _classif_entities.get("fach")
                    if _fach and "discipline" not in tool_args:
                        tool_args["discipline"] = _fach
                    _stufe = _classif_entities.get("stufe")
                    if _stufe and "educationalContext" not in tool_args:
                        tool_args["educationalContext"] = _stufe
                # Same for search_wlo_collections — collections can't be
                # filtered by learningResourceType, but fach/stufe are valid
                # and worth propagating.
                elif tool_name == "search_wlo_collections":
                    _classif_entities = classification.get("entities", {}) or {}
                    if "educationalLevel" in tool_args and "educationalContext" not in tool_args:
                        tool_args["educationalContext"] = tool_args.pop("educationalLevel")
                    _fach = _classif_entities.get("fach")
                    if _fach and "discipline" not in tool_args:
                        tool_args["discipline"] = _fach
                    _stufe = _classif_entities.get("stufe")
                    if _stufe and "educationalContext" not in tool_args:
                        tool_args["educationalContext"] = _stufe

                # ── E1 (2026-08-10): Bestätigungs-Wall ────────────────
                # Die kuratierenden Werkzeuge sind zweistufig: ohne
                # ``confirmToken`` nur Vorschau, erst der zweite Aufruf mit
                # dem Schlüssel führt aus. Der Server bindet den Schlüssel an
                # die Änderung — aber er kann nicht sehen, ob zwischen beiden
                # Schritten ein MENSCH stand. Bei fünf Iterationen pro Zug
                # stünde dort sonst niemand.
                #
                # Deshalb: das Modell darf keinen Schlüssel setzen, und
                # einsetzen dürfen wir ihn nur für einen Vorgang aus einem
                # FRÜHEREN Zug — ``_pending_at_turn_start`` ist der
                # Schnappschuss vom Zug-Eintritt. Was in diesem Zug entsteht,
                # steht nicht darin und ist in diesem Zug nicht bestätigbar.
                # Der Zugwechsel ist der Mensch.
                if is_confirmable(tool_name):
                    tool_args = strip_confirm_token(tool_name, tool_args)
                    # Die Uhr steht hier und nicht in der Domäne: dort wohnt
                    # die Identität eines Vorhabens, hier die Zeit (E4).
                    _jetzt = time.time()
                    # S4 (2026-08-14): Hat der Mensch zugestimmt, gilt das
                    # ABGENOMMENE Vorhaben — nicht das, was das Modell in
                    # diesem Zug neu zusammenstellt. Nur dieser Weg trägt bei
                    # Vorhaben MIT Nutzlast: eine hochgeladene Datei steht als
                    # Argument im Aufruf (``_ContentFields.content`` /
                    # ``fileBase64``), und die kann kein Modell zeichengleich
                    # wiederholen. Der Fingerabdruck-Weg darunter bleibt für
                    # alles ohne Nutzlast — und als Rückfall, wenn nichts
                    # gemerkt wurde (zu grosse Argumente).
                    _abgenommen = (
                        confirmed_args(_pending_at_turn_start, tool_name, now=_jetzt)
                        if zugestimmt(session_state, _nutzernachricht) else None
                    )
                    _confirm = None if _abgenommen else token_for(
                        _pending_at_turn_start, tool_name, tool_args, now=_jetzt)
                    if _abgenommen is not None:
                        # Weder Argumente noch Schlüssel ins Protokoll — nur,
                        # dass eingelöst wurde.
                        _logger.info(
                            "Abnahme für %s eingelöst; es gelten die gezeigten "
                            "Argumente", tool_name)
                        tool_args = _abgenommen
                        _pending_at_turn_start = None
                        session_state.setdefault("entities", {}).pop("_pending_write", None)
                    elif _confirm:
                        tool_args = {**tool_args, CONFIRM_TOKEN_FIELD: _confirm}
                        _pending_at_turn_start = None
                        session_state.setdefault("entities", {}).pop("_pending_write", None)
                    elif ((_pending_at_turn_start or {}).get("tool") == tool_name
                          and is_expired(_pending_at_turn_start, now=_jetzt)):
                        # E4: derselbe Vorgang, nur zu spät. Ohne diesen Zweig
                        # meldete die Zeile darunter „Argumente weichen ab" —
                        # ein Grund, den es hier nicht gibt. Der Merkposten
                        # bleibt liegen; die gleich folgende neue Vorschau
                        # überschreibt ihn mit einem frischen Zeitpunkt.
                        _logger.info(
                            "offener Vorgang für %s ist abgelaufen — es folgt eine "
                            "neue Vorschau", tool_name)
                    elif (_pending_at_turn_start or {}).get("tool") == tool_name:
                        # Offener Vorgang DESSELBEN Werkzeugs, aber andere
                        # Argumente: es wird nicht bestätigt, sondern neu
                        # vorgeschaut. Von hier aus sind zwei Fälle nicht zu
                        # unterscheiden — der Nutzer hat angepasst (Normalfall),
                        # oder das Modell hat im Bestätigungszug ein Feld mehr
                        # oder weniger genannt (dann sagt der Nutzer „ja" und
                        # wird erneut gefragt). Deshalb INFO statt WARNING:
                        # aufgezeichnet, ohne einen Fehler zu behaupten.
                        # Ohne diese Zeile ist der Rückfall spurlos.
                        #
                        # Nur der Werkzeugname, wie beim Nachbarn unten: weder
                        # Schlüssel noch Argumente gehören ins Protokoll.
                        _logger.info(
                            "offener Vorgang für %s nicht bestätigt — Argumente weichen "
                            "von der Vorschau ab; es folgt eine neue Vorschau",
                            tool_name)

                # Triple-Schema T-23: call with structured outcome
                from boerdi.services.outcome_service import call_with_outcome
                result_text, outcome = await call_with_outcome(tool_name, tool_args)
                outcomes.append(outcome)

                # Welche Anleitung gerade abgearbeitet wird, muss den Zug
                # überdauern: stellt ein Skill eine Rückfrage, kommt die Antwort
                # erst im NÄCHSTEN Zug — und der entschied bisher neu. Gemessen
                # 2026-08-16: „Stunde planen" fragte nach der Dauer, die Antwort
                # „45 min physik sek 1" landete beim Klassifikator in einem
                # fremden Muster, und das Modell holte eine andere Anleitung.
                # Nur bei ECHTEM Ergebnis merken — ein Fehlschlag ist keine
                # laufende Anleitung. Ein MCP-Fehler kommt als gewöhnlicher
                # Text zurück, deshalb zählt der Befund (Review 2026-09-26).
                if tool_name == "get_skill" and result_text and outcome.status == "success":
                    merke_laufende_anleitung(
                        session_state.setdefault("entities", {}),
                        tool_args.get("nodeId"),
                        session_state.get("turn_count"),
                        titel=skill_titel(result_text),
                    )

                # Rückweg des Walls: den frisch geprägten Schlüssel merken und
                # aus dem Text nehmen, BEVOR er irgendwohin weiterfließt
                # (Nachrichtenkette, Karten, Protokoll). Sähe das Modell ihn,
                # könnte es im selben Zug bestätigen.
                if is_confirmable(tool_name):
                    _minted = extract_confirm_token(result_text)
                    # Redigiert wird ZUERST — danach kann kein Pfad mehr den
                    # rohen Text weiterreichen. Seit S1 gibt es einen zweiten
                    # Empfänger (den offenen Vorgang, aus dem die sichtbare
                    # Vorschau-Box gespeist wird); die Reihenfolge macht die
                    # Zusicherung an der Stelle ablesbar, an der sie gilt.
                    # Die Absagen-Unterscheidung unten bleibt unberührt: die
                    # Redaktion ersetzt nur den Schlüssel, ``confirmToken:``
                    # selbst überlebt sie.
                    result_text = redact_confirm_token(result_text)
                    if _minted:
                        # In ``entities``, weil der Merkposten den Zug
                        # überdauern MUSS — siehe Zug-Eintritt oben.
                        session_state.setdefault("entities", {})["_pending_write"] = (
                            remember_pending(tool_name, tool_args, _minted, now=time.time(),
                                             caller=aufrufer_kennung()))
                        # S1: derselbe Text ein zweites Mal — diesmal für den
                        # Menschen. Der Server formuliert die Abnahme bereits
                        # vollständig und auf Deutsch; bisher endete sie in der
                        # Nachrichtenkette des Modells, und der Nutzer las nur
                        # die Nacherzählung.
                        #
                        # Auf oberster Ebene, und das ist genau umgekehrt zum
                        # Merkposten daneben: die Vorschau DARF den Zug nicht
                        # überdauern. Dass dort nichts gespeichert wird, ist
                        # hier die gewünschte Eigenschaft.
                        session_state["_write_preview"] = result_text
                    elif "confirmToken:" in result_text:
                        # Der Server kündigt einen Schlüssel an, wir lesen aber
                        # keinen heraus: dann hat sich sein Vorschautext
                        # geändert. Sichtbar machen statt still hinnehmen —
                        # die Folge wäre, dass sich nichts mehr bestätigen
                        # lässt. Der Wall selbst hält auch dann, denn er trägt
                        # auf dem HINWEG (``strip_confirm_token``): ein
                        # Schlüssel, den das Modell sieht, kann es trotzdem
                        # nicht absetzen.
                        #
                        # Der Doppelpunkt ist der Unterschied und kein Zufall:
                        # die Vorschau sagt „mit confirmToken: <schlüssel>
                        # wiederholen", die drei Absagen (abgelaufen, andere
                        # Änderung, unbekannt) sagen „ohne confirmToken
                        # wiederholen". Ohne ihn schlüge diese Warnung bei
                        # jedem abgelaufenen Schlüssel falsch an.
                        _logger.warning(
                            "Vorschautext von %s nennt confirmToken, enthält aber "
                            "keinen lesbaren Schlüssel — Bestätigung nicht möglich",
                            tool_name)
                # A4c-2a: Parser-Auswahl, Sammlungs-Markierung, Themenseiten-
                # Mischung und Entdopplung wohnen in ``services/card_collect``,
                # seit die Agent-Schleife dieselbe Ernte braucht.
                cards = collect_cards(all_cards, tool_name, result_text)

                # ── Inline-Result-Grouping: search_wlo_content-Redaction ──
                # Im Box-Anzeige-Modus zeigt die UI Einzelinhalte NICHT direkt
                # an — sie tauchen nur indirekt über die "Alle Treffer zur
                # Suche"-CTA auf. Wenn die LLM den vollen Tool-Result-Text mit
                # Titeln/Beschreibungen sieht, paraphrasiert sie diese unter-
                # mauernd ("ein Arbeitsblatt und ein Video für Fläche, Umfang
                # und Konstruktion") — der User sieht aber gar keine
                # Materialien in der UI und ist verwirrt (User-Feedback
                # 2026-05-21). Helper-Funktion ``_redact_search_content_for_llm``
                # ersetzt den Text durch eine kompakte Summary (Anzahl + grobe
                # Typ-Verteilung). Cards selbst bleiben in ``all_cards``, sodass
                # Lernpfad-Generator (separater Flow) und Such-CTA-Count weiter
                # arbeiten.
                # Tool-Result + UI-Box-Status-Footer (Anti-Hallucination):
                # die Footer-Zeile sagt der LLM, was nach diesem Call WIRKLICH
                # in den sichtbaren Boxen landet — sodass sie im Antwort-Text
                # keine Sammlungen/Themenseiten erfinden kann.
                # D4 (2026-08-10): ``frame_untrusted`` kennzeichnet Werkzeuge,
                # deren Nutzlast Langform-Prosa von Dritten ist (Volltext,
                # Kompendium), als Daten statt Anweisung — indirekte
                # Prompt-Einschleusung. Der UI-Box-Status ist UNSERE Anweisung
                # und bleibt deshalb AUSSERHALB des Rahmens; innerhalb wuerde
                # der Rahmen sie mit entwerten.
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": (
                        frame_untrusted(
                            tool_name,
                            _redact_search_content_for_llm(tool_name, result_text, cards, _inline_grouping_mode),  # noqa: E501
                        )
                        + _ui_box_state_footer(all_cards, _inline_grouping_mode)
                        # P1 (2026-08-13): der Freigabe-Katalog, den das
                        # Ergebnis mitbringt. NACH der Redaktion, denn die
                        # ersetzt bei ``get_collection_contents`` im Box-Modus
                        # den ganzen Text — davor eingebaut waere er still weg.
                        # Aufruf mitgegeben (2026-08-15): bringt das Ergebnis
                        # keinen Katalog mit, war der Aufruf aber sammlungs-
                        # bezogen, steht dort der Anstoss — die Sammlungs-ID
                        # dafuer kommt aus unseren eigenen Argumenten.
                        + skill_registry_note(
                            result_text, tool_name=tool_name, args=tool_args)
                    ),
                })

            # If respond_to_user was called among the tool calls, treat THIS
            # iteration as the finish point. Otherwise continue the outer
            # for-loop into the next LLM round-trip.
            if _inline_response_text is None:
                continue
            # Inline final response — set response_text + stash quick_replies
            # and fall through to the Reflection/return path below (which
            # used to be the ``else`` branch only).
            response_text = _inline_response_text
            session_state["_inline_quick_replies"] = _inline_quick_replies
        else:
            response_text = strip_reasoning_markers(choice.message.content or "")

        # ── Final-answer path — runs for BOTH content-only and inline
        #    respond_to_user tool calls. Phase A1 Reflection check gates the
        #    return so a missing-tool retry can still trigger.
        if True:
            # Phase A1 — Reflection-Loop für Tool-Compliance:
            # Wenn das Pattern Tools verlangt (force_tool_use=true) UND keines
            # davon im Tool-Loop tatsächlich gerufen wurde, einmal mit harter
            # Korrektur-Anweisung neu versuchen. Schützt vor LLMs, die einen
            # netten Text-Antwort-Shortcut nehmen, obwohl ihre Pattern-Definition
            # eindeutig MCP-/Service-Calls verlangt.
            #
            # Sicherheits-Conditions (vermeidet Endlos-Loops):
            #   - läuft nur 1× pro Turn (Flag _reflection_done)
            #   - greift nur wenn pattern_output.force_tool_use == True
            #   - greift nur wenn pattern_output.tools eine echte Liste ist
            #   - greift nur wenn keines der erwarteten Tools im tools_called auftaucht
            # B1: requires_all_tools=true → vollständige Coverage; sonst Schnittmenge.
            # Die Bedingung selbst wohnt in ``domain/tool_pflicht`` — der Strom fragt
            # sie vor jeder Runde (Plan Token-Streaming, T10).
            required_tools = list(pattern_output.get("tools") or [])
            requires_all = bool(pattern_output.get("requires_all_tools"))
            actual_bare = gerufene_werkzeuge(tools_called)
            missing_tools = fehlende_pflichtwerkzeuge(pattern_output, tools_called)

            if (not _reflection_done) and missing_tools:
                _logger.info(
                    "Reflection-Loop: Pattern %s verlangt Tools %s (mode=%s), aufgerufen %s, fehlend %s — Retry",  # noqa: E501
                    pattern_label, required_tools,
                    "ALL" if requires_all else "ANY",
                    sorted(actual_bare), missing_tools,
                )
                _reflection_done = True
                # Korrektur-Nachricht in den Loop-Messages-Stack einfügen
                if requires_all:
                    msg = (
                        f"⚠ KORREKTUR: Du hast PAT-{pattern_label} gewählt; dieses Pattern "
                        f"verlangt ALLE diese Tools nacheinander: {', '.join(required_tools)}. "
                        f"Du hast {sorted(actual_bare) or 'keinen davon'} bisher gerufen. "
                        f"Rufe JETZT die fehlenden Tools ({', '.join(missing_tools)}) auf, "
                        f"BEVOR du final antwortest. {SPRACHE_DER_PERSON}"
                    )
                else:
                    msg = (
                        f"⚠ KORREKTUR: Du hast PAT-{pattern_label} gewählt, aber KEINEN der "
                        f"verlangten Tools genutzt: {', '.join(required_tools)}. "
                        f"Rufe JETZT mindestens EINEN dieser Tools auf, BEVOR du final "
                        f"antwortest. Ohne Tool-Aufruf hast du keine echten Daten zur Verfügung — "
                        f"deine Antwort wäre erfunden. {SPRACHE_DER_PERSON}"
                    )
                messages.append({"role": "user", "content": msg})
                # Continue zur nächsten Iteration: Loop wird Tools forcieren
                # weil active_tools immer noch gesetzt ist und der LLM jetzt
                # den expliziten Hinweis hat.
                continue

            # Aussetzer des Anbieters: weder Werkzeug noch Text. Dann ist
            # dieser Zug stumm — die Person sieht eine leere Blase. Wiederholt
            # wird die Kette UNVERAENDERT, ohne Ermahnung: dieselbe Eingabe
            # gelingt beim naechsten Mal, es gibt also nichts richtigzustellen.
            # Der zweite Anlauf ist ein echter — der b-api-Cache-Bust schickt
            # je Aufruf ``clearCache`` bzw. eine frische ``user``-Kennung.
            #
            # ``_inline_response_text is None`` grenzt auf den INHALTS-Pfad ein
            # (dieselbe Weiche wie oben), und das ist der Kern dieses Zweigs:
            # auf dem Inline-Pfad (``respond_to_user``) waere die Wiederholung
            # schaedlich. Der Text ist dort schon zeichenweise beim Client
            # (``_ToolArgTextStreamer`` -> ``on_token``), eine zweite Antwort
            # haengte sich sichtbar dahinter; und die Kette traegt dort bereits
            # Assistenten-Zug und ``role:tool``-Quittungen (F-5, Audit
            # 2026-08-12) — „unveraendert" waere sie also gar nicht. Der
            # Leerfall ist dort ueber ``_strip_trailing_option_lines``
            # erreichbar (Antwort nur aus Optionszeilen) und faellt bewusst an
            # ``graph/nodes/respond``, der den ehrlichen Satz sagt.
            #
            # NACH der A1-Reflexion und nicht davor: greift die, hat sie den
            # spezifischeren Befund (Muster verlangt Werkzeuge, keines lief)
            # und behebt die Stille gleich mit. Dieser Zweig deckt den Rest —
            # etwa M04, das gar keine Werkzeuge verlangt.
            #
            # Er aendert NUR den Ausfall: ein Zug mit Text laeuft Zeile fuer
            # Zeile wie bisher (eigener Test). Live gemessen 2026-08-21 blieb
            # der Muster-Weg in 10 Zuegen ohne Aussetzer, die Agent-Schleife
            # hatte 7 in 20 — hier also Vorsorge, dort ein Befund.
            if (_inline_response_text is None
                    and not (response_text or "").strip()
                    and _leerlaeufe < llm.LEERLAUF_VERSUCHE):
                _leerlaeufe += 1
                _logger.warning(
                    "Tool-Loop: Antwort ohne Werkzeug und ohne Text — "
                    "Anlauf %d von %d", _leerlaeufe, llm.LEERLAUF_VERSUCHE)
                continue
            return response_text, all_cards, tools_called, outcomes
    # Loop erschoepft ohne finale Antwort → Fortsetzungs-Marker fuer den
    # P16-Fallback am Call-Site.
    return None
