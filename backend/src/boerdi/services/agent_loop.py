"""Die Agent-Schleife (A2) — Nachrichten, Werkzeuge, wiederholen, bis Schluss.

Der Gegenentwurf zur Muster-Engine: kein Klassifikator, kein Muster, keine
gebundene Werkzeugliste. Das Modell bekommt den Systemprompt des Gastgebers und
den vollen Katalog (``services/agent_tools.py``) und entscheidet selbst, was es
ruft und wann es fertig ist.

**Warum nicht ``_run_tool_loop`` nachnutzen.** Die Bestandsschleife hat 22
Parameter, einen festen Deckel von 5 Iterationen und ist an ``pattern_output``,
``classification``, Karten, RAG und den Inline-Modus gebunden — sie ist die
Muster-Engine, nicht eine Schleife darin. Sie bleibt unangetastet (Fidelity-Gate);
diese hier sitzt auf denselben Bausteinen darunter (``llm.chat_completion``,
``outcome_service.call_with_outcome``, ``domain/write_confirm``,
``domain/untrusted_text``).

**Sechs Gründe, den Lauf zu beenden.** Vier sind Deckel — Iterationen, Frist,
Token-Budget, Stillstand —, zwei sind Ziellinien: ``submit_result`` (das Modell
sagt selbst, dass es fertig ist) und ``text`` (es antwortet in Prosa ohne
Werkzeug). Der zweite ist kein Zierrat: ohne ihn liefe die Schleife gegen
dieselbe Nachrichtenkette weiter, bis ein Deckel greift.

**Die Frist wird hereingereicht**, nicht aus dem Modul gelesen. Ein Lauf hat
seine eigene Uhr; ein Test, der ``time.monotonic`` global verbiegt, verböge sie
für alles im selben Prozess.

**``messages`` wird an Ort und Stelle fortgeschrieben** — Hausbrauch aus
``_run_tool_loop``. Der Aufrufer behält damit die volle Kette samt aller
Werkzeug-Ergebnisse und kann daraus lesen, was er braucht (Karten etwa), ohne
dass diese Schleife davon wissen muss.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from boerdi.api.schemas import ToolOutcome
from boerdi.domain.antwort_werkzeug import RESPOND_TO_USER, antwort_aus_argumenten
from boerdi.domain.config_models.engine import AgentLimits
from boerdi.domain.ergebnis_schema import argument_fehler, ergebnis_ungueltig
from boerdi.domain.inline_documents import (
    MAX_DOKUMENTE_JE_ZUG,
    ZEIGE_DOKUMENT,
    dokument_aus_argumenten,
)
from boerdi.domain.reasoning_filters import strip_reasoning_markers
from boerdi.domain.result_delivery import (
    BEREITS_GELIEFERT,
    ERGEBNIS_UEBERNOMMEN,
    ERGEBNIS_UNBRAUCHBAR,
    LIEFERE_ERGEBNIS,
    ergebnis_aus_argumenten,
)
from boerdi.domain.tool_result_redaction import redigiere_strukturell
from boerdi.domain.untrusted_text import frame_untrusted
from boerdi.domain.werkzeug_angebot import (
    NICHT_ANGEBOTEN,
    angebotene_namen,
    angebotene_parameter,
)
from boerdi.domain.write_confirm import CONFIRM_TOKEN_FIELD, is_confirmable
from boerdi.obs.progress import NO_PROGRESS, TurnProgress
from boerdi.obs.usage import add_usage, extract_usage, new_accumulator
from boerdi.obs.zeiten import seit_ms
from boerdi.services import llm, outcome_service
from boerdi.services.agent_frist import (
    ABGEBROCHEN_FRIST,
    NICHT_AUSGEFUEHRT_FRIST,
    NICHT_AUSGEFUEHRT_STILLSTAND,
    FristAbgelaufen,
    frist_ende,
    innerhalb,
)
from boerdi.services.agent_knowledge import WISSEN_SUCHEN
from boerdi.services.agent_tools import SUBMIT_RESULT
from boerdi.services.agent_trace import Rundenbuch
from boerdi.services.agent_write import WriteGate
from boerdi.services.llm_ereignisse import ist_voruebergehend, melde_voruebergehend
from boerdi.services.llm_parallel import LlmAusgelastet
from boerdi.services.llm_streaming import _stream_completion
from boerdi.services.mcp.parsers import skill_registry_note, skill_titel

logger = logging.getLogger(__name__)

#: Der Name, unter dem die Kostenschau (K3) die Züge der Agent-Schleife führt.
USAGE_PHASE = "agent"


_ARGUMENT_FEHLER = (
    "Fehler: Die Argumente dieses Aufrufs waren kein gueltiges JSON. Wiederhole "
    "den Aufruf mit vollstaendigem, gueltigem JSON."
)

_DOKUMENT_FEHLER = (
    "Fehler: Das Dokument war unbrauchbar — ``titel`` und ``markdown`` muessen "
    "nichtleere Zeichenketten sein. Wiederhole den Aufruf mit dem "
    "vollstaendigen Ergebnis, oder antworte in Prosa."
)

_DOKUMENT_DECKEL = (
    "Hinweis: Fuer diesen Zug sind bereits genug Boxen geliefert. Schreibe "
    "jetzt deinen Begleitsatz."
)

# Ehrlich statt „OK": ein Werkzeug NACH der Antwort ist nicht gelaufen. Die
# Kette endet hier zwar, aber jeder Aufruf braucht seine Werkzeug-Nachricht.
_NACH_DER_ANTWORT = "Nicht ausgeführt: Die Antwort wurde bereits mit respond_to_user gegeben."


@dataclass(slots=True)
class AgentRun:
    """Das Ergebnis eines Laufs.

    ``result`` ist bewusst untypisiert: die Form gibt der Aufrufer über sein
    ``result_schema`` vor, und wer sie auswertet, kennt sie — diese Schleife
    nicht. ``stop_reason`` gehört zur Antwort und nicht ins Protokoll: ein Lauf,
    der an der Frist abgeschnitten wurde, sieht von außen sonst aus wie einer,
    der fertig geworden ist.
    """

    text: str = ""
    result: Any = None
    stop_reason: str = ""
    iterations: int = 0
    tools_called: list[str] = field(default_factory=list)
    #: Der Lauf endete, weil das Modell keinen Platz bekam (Paket 18F) — die Antwort ist
    #: dann „ausgelastet“, nicht der Fehler mit Nummer (Review 2026-10-30).
    ausgelastet: bool = False
    outcomes: list[Any] = field(default_factory=list)
    #: Die vom Modell GELIEFERTEN Ergebnis-Boxen (D2), in Aufrufreihenfolge.
    #: Leer heisst: dieser Zug hat keine geliefert — dann greift weiter die
    #: geratene Box aus ``turn_persist``.
    dokumente: list[dict[str, Any]] = field(default_factory=list)
    #: Die in DIESEM Zug geholten Anleitungen — je ``{"node_id", "titel"}``, in
    #: Aufrufreihenfolge. Der Aufrufer setzt daraus die sichtbare Meldung
    #: (Nutzer-Vorgabe 2026-08-19: „Meldungen ueber Skill-Aufrufe sind gewollt,
    #: um zu verdeutlichen, was die KI nutzt — am besten hartcodiert").
    #:
    #: **Warum ueber den Lauf und nicht direkt in die Sitzung.** Der Bestandsweg
    #: schreibt an derselben Stelle in ``entities`` (``tool_loop``:744); diese
    #: Schleife bedient auch den Agent-Endpunkt, der keine Sitzung hat. Die
    #: Schleife berichtet, der Aufrufer verbucht.
    anleitungen: list[dict[str, str]] = field(default_factory=list)
    #: AG-1: je Runde ein Eintrag — Nummer, Dauer, Werkzeuge SAMT der
    #: virtuellen (je Aufruf nur die Argument-Namen) und die Token der Runde.
    #: Geführt von ``agent_trace.Rundenbuch``; ``tools_called`` bleibt davon
    #: unberührt die Liste der echten Werkzeuge.
    runden: list[dict[str, Any]] = field(default_factory=list)
    #: Die Schnellantworten aus ``respond_to_user`` (Plan 2026-09-30) — leer,
    #: wenn der Lauf in Prosa endete; dann schreibt sie der eigene Aufruf.
    vorschlaege: list[str] = field(default_factory=list)


def _spent(acc: dict[str, Any]) -> int:
    """Verbrauchte Token. ``cached``/``reasoning`` sind „davon"-Zahlen und
    zählen nicht zusätzlich (``obs/usage.extract_usage``)."""
    return int(acc.get("prompt_tokens", 0)) + int(acc.get("completion_tokens", 0))


def _call_key(tool_name: str, args: dict[str, Any]) -> str:
    """Identität eines Aufrufs für die Stillstands-Erkennung.

    Sortiert, damit die Reihenfolge der Argumente nicht zur Eigenschaft wird.
    Anders als ``write_confirm.change_fingerprint`` bleibt ein ``confirmToken``
    hier **drin**, und das trägt einen Fall: eine Bestätigung wiederholt den
    Aufruf der Vorschau wortgleich bis auf den Schlüssel. Zählte er nicht mit,
    hielte die Stillstands-Erkennung genau die Einlösung für Stillstand.
    """
    return json.dumps([tool_name, args], sort_keys=True, ensure_ascii=False, default=str)


def _arguments(raw: str) -> tuple[dict[str, Any], str]:
    """Die Argumente eines Werkzeugaufrufs, oder ein Fehlertext für das Modell.

    Abgeschnittenes JSON (Token-Limit, Streaming-Reassembly) ist ein
    Werkzeugfehler und kein Laufende — dieselbe Entscheidung wie im Bestand
    (B8): zurückmelden und weiterlaufen lassen, damit das Modell den Aufruf
    richtig wiederholen kann.
    """
    try:
        geparst = json.loads(raw or "{}")
    except (ValueError, TypeError):
        return {}, _ARGUMENT_FEHLER
    if not isinstance(geparst, dict):
        return {}, _ARGUMENT_FEHLER
    return geparst, ""


def _assistant_turn(message: Any, calls: list[Any]) -> dict[str, Any]:
    """Die Assistenten-Nachricht als reines Dict.

    Wie im Bestand: der nicht-streamende Pfad liefert ein Pydantic-Objekt, der
    streamende eine eigene Attrappe — als Dict funktionieren beide gleich.
    """
    return {
        "role": getattr(message, "role", "assistant"),
        "content": getattr(message, "content", None),
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            } for tc in calls
        ],
    }


def _tool_turn(call_id: str, content: str) -> dict[str, Any]:
    return {"role": "tool", "tool_call_id": call_id, "content": content}


def _ended(run: AgentRun, reason: str) -> AgentRun:
    run.stop_reason = reason
    return run


async def run_agent_loop(
    *,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    limits: AgentLimits,
    usage_acc: dict[str, Any] | None = None,
    progress: TurnProgress = NO_PROGRESS,
    clock: Callable[[], float] = time.monotonic,
    on_tool_result: Callable[[str, str], None] | None = None,
    wissen: Callable[[dict[str, Any]], Awaitable[str]] | None = None,
    on_offene_abnahme: Callable[[dict[str, Any], str], None] | None = None,
    on_token: Callable[[str], None] | None = None,
    start: float | None = None,
) -> AgentRun:
    """Fahre die Schleife, bis ein Grund sie beendet.

    ``messages`` wird an Ort und Stelle fortgeschrieben (Assistenten-Züge und
    Werkzeug-Ergebnisse). Fehlt ``usage_acc``, führt die Schleife einen eigenen
    Zähler — sonst wäre das Token-Budget still abgeschaltet, und ein
    abgeschalteter Deckel ist schlimmer als keiner.

    ``on_tool_result`` (A4c-2a) sieht jedes echte Werkzeug-Ergebnis als
    ``(name, text)``. Der Chat-Zug erntet daraus seine Karten; der
    Agent-Endpunkt reicht nichts herein und zahlt entsprechend nichts. Der Text
    ist **redigiert, aber ungerahmt**: ein Bestätigungs-Schlüssel darf diese
    Naht nicht passieren, der Fremdtext-Rahmen ist dagegen eine Anweisung ans
    Modell und für einen Parser nur Störung.

    ``on_offene_abnahme`` (Paket 2) bekommt beim Laufende höchstens einmal den
    nicht eingelösten Schreib-Vorgang als ``(merkposten, vorschau)``. Es ist die
    einzige Naht, über die ein Schlüssel die Schleife verlässt — in die Sitzung
    des Chat-Zugs, nie zum Modell. Der Agent-Endpunkt reicht nichts herein.

    ``on_token`` (Token-Streaming, Plan 2026-10-01) macht die Runden zu
    gestreamten Aufrufen. Hinaus geht allein der Text von ``respond_to_user``
    (E-S1). Eine Runde mit dieser Antwort beendet den Lauf in aller Regel; tut
    sie es nicht (unlesbare Argumente, Stillstand), läuft jede weitere Runde
    ungestreamt, und ``result`` ersetzt den Text (Review L1). Der Chat-Zug
    reicht den Strom nur herein, wenn das Werkzeug im Angebot ist.

    ``start`` (Paket 4, B1) ist der Beginn des Zugs auf derselben Uhr wie
    ``clock``: Gate und Vorabruf laufen vor der Schleife und zählen zur Frist.
    Ohne ihn beginnt die Uhr hier. Die Frist gilt auch IN laufenden Modell- und
    Werkzeugaufrufen (``services/agent_frist``), nicht nur am Rundenanfang.
    """
    acc = usage_acc if usage_acc is not None else new_accumulator()
    strom_verbraucht = False
    angeboten = angebotene_namen(tools)
    gate = WriteGate(limits.write_mode)
    run = AgentRun()
    jetzt0 = clock()
    start = jetzt0 if start is None else start
    ende = frist_ende(limits.deadline_s, jetzt0 - start)
    # Der Nullpunkt des Budgets, nicht der Zählerstand: im Chat-Modus trägt der
    # Zug-Zähler bereits Token früherer Schritte (Safety), und die gehören dem
    # Zug, nicht der Schleife.
    start_tokens = _spent(acc)
    last_call: str | None = None
    # Verbrauchte Wiederholungen nach einem Aussetzer (siehe unten). Am Lauf
    # und nicht global — wie ``_reflection_done`` im Muster-Weg (``tool_loop``,
    # Phase A1), nur als Zaehler, weil hier mehr als ein Anlauf erlaubt ist.
    _leerlaeufe = 0
    buch = Rundenbuch(run.runden, acc)

    def schluss(reason: str) -> AgentRun:
        # Jeder Ausgang geht hier durch: die Runde, in der der Lauf endet, hat
        # keine naechste, die sie schliessen koennte (AG-1).
        buch.schliessen(clock())
        if on_offene_abnahme is not None and (offen := gate.offene_abnahme()) is not None:
            on_offene_abnahme(*offen)
        return _ended(run, reason)

    def quittiere(offen: list[Any], text: str) -> None:
        # Endet der Lauf mitten in einer Runde, bekommt jeder ihrer Aufrufe eine
        # Antwort. Sonst wiese der Anbieter die Kette ab — etwa beim Abschluss-
        # Aufruf, den ``respond_agent`` nach einem Deckel noch macht.
        for rest in offen:
            messages.append(_tool_turn(rest.id, text))

    def ueber_budget_gemeldet() -> None:
        # P4-2: Eine fertige Antwort wird geliefert, auch wenn ihr Aufruf das
        # Budget gerissen hat — sie ist bezahlt. Unbemerkt bleibt das nicht.
        verbraucht = _spent(acc) - start_tokens
        if verbraucht > limits.token_budget:
            logger.warning("Agent-Schleife: Token-Budget von %s überschritten (%s) "
                           "— die fertige Antwort wird geliefert",
                           limits.token_budget, verbraucht)
            # Ohne Zahlen (Review 2026-10-30): der Phasen-Rahmen geht auch an anonyme Clients;
            # Budget und Verbrauch stehen in der Logzeile darüber und im Debug-Block.
            progress.record("agent_budget", "Token-Budget überschritten")

    for _ in range(limits.max_iterations):
        # EIN Uhrwert je Runde: Frist-Pruefung, Ende der vorigen und Beginn
        # dieser Runde zugleich.
        jetzt = clock()
        buch.schliessen(jetzt)
        if jetzt - start >= limits.deadline_s:
            logger.info("Agent-Schleife: Frist von %s s erreicht", limits.deadline_s)
            return schluss("deadline")
        if _spent(acc) - start_tokens >= limits.token_budget:
            logger.info("Agent-Schleife: Token-Budget von %s erreicht", limits.token_budget)
            return schluss("token_budget")

        run.iterations += 1
        buch.beginnen(run.iterations, jetzt)
        progress.record("agent_iteration", f"Agent-Schritt {run.iterations}",
                        {"iteration": run.iterations})
        try:
            # Gebucht wird über den Transport (``usage_acc``/``phase``) und
            # nicht mit eigener Hand: das Etikett steht hier im Voraus fest —
            # anders als im Tool-Loop, wo es erst aus ``finish_reason`` folgt
            # und deshalb dort begründet selbst gebucht wird. Eine Buchungs-
            # stelle weniger ist eine Driftquelle weniger. Der Strom hat keinen
            # Transport, der bucht — dort dieselbe Buchung von Hand.
            strom_runde = on_token is not None and not strom_verbraucht
            if strom_runde:
                _t0 = time.perf_counter()
                resp = await innerhalb(ende, _stream_completion(
                    on_token, messages=messages, tools=tools, temperature=0.4))
                add_usage(acc, extract_usage(resp), USAGE_PHASE, ms=seit_ms(_t0))
            else:
                resp = await innerhalb(ende, llm.chat_completion(
                    messages=messages, tools=tools, temperature=0.4,
                    usage_acc=acc, phase=USAGE_PHASE))
        except FristAbgelaufen:
            logger.info("Agent-Schleife: Frist von %s s im Modellaufruf erreicht",
                        limits.deadline_s)
            return schluss("deadline")
        except Exception as e:
            if isinstance(e, LlmAusgelastet):
                logger.info("Agent-Schleife: kein LLM-Platz frei — Zug ausgelastet")
                run.ausgelastet = True
            elif ist_voruebergehend(e):
                # Paket 19 (N-16): Frist, 429, Verbindung — ohne Traceback, gedrosselt.
                melde_voruebergehend(logger, "Agent-Schleife", e)
            else:
                logger.exception("Agent-Schleife: LLM-Fehler (%s)", type(e).__name__)
            return schluss("error")

        choice = resp.choices[0]
        calls = getattr(choice.message, "tool_calls", None)
        if strom_runde and any(tc.function.name == RESPOND_TO_USER for tc in calls or []):
            # Höchstens EINE gestreamte Antwortrunde je Zug (Review L1): endet
            # sie nicht — unlesbare Argumente, Stillstand —, liefe eine zweite
            # Antwort sichtbar hinter der ersten her.
            strom_verbraucht = True
        if not calls:
            _prosa = strip_reasoning_markers(choice.message.content or "")
            if _prosa.strip():
                run.text = _prosa
                ueber_budget_gemeldet()
                return schluss("text")
            # Weder Werkzeug noch Text — das ist KEINE Ziellinie, sondern ein
            # Aussetzer des Anbieters. Live gemessen 2026-08-21 an derselben
            # Volltext-Frage: 3 von 8 Zuegen kamen so zurueck, auffaellig
            # schnell (6-8 s statt 9-19 s), und der Zug endete stumm. Bis hier
            # galt der Fall als ``text`` und damit als fertige Antwort.
            #
            # Wiederholt wird die Kette UNVERAENDERT, ohne Ermahnung: die
            # Messung zeigt dieselbe Eingabe mal leer, mal vollstaendig — es
            # ist nichts richtigzustellen. Eine Ermahnung waere eine Diagnose,
            # die die Belege nicht hergeben, und veraenderte den Prompt. Der
            # zweite Anlauf ist auch wirklich einer: der Cache-Bust (B4)
            # schickt je Aufruf ``clearCache``/eine frische ``user``-Kennung,
            # der Anbieter kann die leere Antwort also nicht bloss wiederholen.
            #
            # Der Aussetzer kostet eine Iteration und wird gebucht — beides
            # ist ehrlich: der Aufruf ist passiert. Frist und Token-Budget
            # pruefen oben, die Wiederholung laeuft also nicht an ihnen vorbei.
            if _leerlaeufe < llm.LEERLAUF_VERSUCHE:
                _leerlaeufe += 1
                logger.warning(
                    "Agent-Schleife: Antwort ohne Werkzeug und ohne Text "
                    "(Iteration %d) — Anlauf %d von %d",
                    run.iterations, _leerlaeufe, llm.LEERLAUF_VERSUCHE)
                continue
            # Eigener Abbruchgrund statt ``text``: ``text`` hiesse „hat
            # geantwortet" und machte den stummen Zug in den Qualitaetslogs
            # unsichtbar. ``empty`` faellt in ``respond_agent`` nicht unter
            # ``agent_abschluss.GEDECKELT`` und bekommt damit den richtigen Satz („Ich konnte
            # gerade keine Antwort erzeugen"), nicht den Deckel-Satz.
            logger.warning(
                "Agent-Schleife: auch nach %d Anlaeufen weder Werkzeug noch "
                "Text — Lauf endet leer", llm.LEERLAUF_VERSUCHE)
            return schluss("empty")

        messages.append(_assistant_turn(choice.message, calls))

        def frist_mitten_in_der_runde(laufend: int, calls: list[Any] = calls) -> AgentRun:
            # Der laufende Aufruf ist abgebrochen, die übrigen der Runde haben
            # nicht begonnen — beides sagt die Antwort ans Modell ehrlich.
            logger.info("Agent-Schleife: Frist von %s s im Werkzeugaufruf erreicht",
                        limits.deadline_s)
            quittiere(calls[laufend:laufend + 1], ABGEBROCHEN_FRIST)
            quittiere(calls[laufend + 1:], NICHT_AUSGEFUEHRT_FRIST)
            return schluss("deadline")

        antwort: dict[str, Any] | None = None
        for i, tc in enumerate(calls):
            name = tc.function.name
            args, fehler = _arguments(tc.function.arguments)
            buch.aufruf(name, args)
            if fehler:
                logger.info("Agent-Schleife: unlesbare Argumente für %s", name)
                messages.append(_tool_turn(tc.id, fehler))
                continue

            # Nur Angebotenes läuft (Audit 2026-09-29, B-M1), und zwar VOR allem
            # anderen: vor der Wall, die bei einem Schreibwerkzeug womöglich
            # einen Schlüssel einsetzt, und vor den virtuellen Werkzeugen unten.
            # Die stehen bei legitimer Nutzung im Angebot (``agent_tools``);
            # ungeprüft beendete ``submit_result`` sonst den Lauf mit einem
            # Ergebnis, das niemand verlangt hatte (Paket 4, A2). Der Stillstand
            # zählt auch hier: ein zweites gleiches Abgewiesenes beendet den Lauf.
            if name not in angeboten:
                key = _call_key(name, args)
                if key == last_call:
                    logger.info("Agent-Schleife: %s zweimal abgewiesen — Stillstand", name)
                    quittiere(calls[i:], NICHT_AUSGEFUEHRT_STILLSTAND)
                    return schluss("no_progress")
                last_call = key
                logger.warning("Agent-Schleife: nicht angebotenes Werkzeug %s verworfen", name)
                messages.append(_tool_turn(tc.id, NICHT_ANGEBOTEN))
                continue

            # Die Antwort samt Schnellantworten (Plan 2026-09-30): virtuell, eine
            # Ziellinie wie Prosa — ausgewertet erst am Ende der Runde, damit ein
            # Dokument oder Ergebnis DERSELBEN Runde noch ankommt. Echte
            # Werkzeuge danach laufen nicht mehr: wer antwortet, ist fertig.
            if name == RESPOND_TO_USER:
                antwort = args
                messages.append(_tool_turn(tc.id, "OK"))
                continue
            if antwort is not None and name not in (ZEIGE_DOKUMENT, LIEFERE_ERGEBNIS):
                messages.append(_tool_turn(tc.id, _NACH_DER_ANTWORT))
                continue

            # Das Abschluss-Werkzeug ist virtuell: es geht nie an den MCP.
            # Weitere Aufrufe derselben Runde fallen weg — wer „fertig" sagt,
            # hat nichts mehr zu tun.
            #
            # Vorher die Form (Paket 4, A3): Das Schema des Gastgebers erzwingt
            # der Anbieter nicht (``domain/ergebnis_schema``). Passt das Ergebnis
            # nicht, geht die Abweichung ans Modell zurück, und der Lauf geht
            # weiter; dasselbe Ungültige zweimal ist Stillstand.
            if name == SUBMIT_RESULT:
                abweichungen = argument_fehler(angebotene_parameter(tools, name), args)
                if abweichungen:
                    key = _call_key(name, args)
                    if key == last_call:
                        logger.info("Agent-Schleife: dasselbe ungültige Ergebnis zweimal "
                                    "— Stillstand")
                        quittiere(calls[i:], NICHT_AUSGEFUEHRT_STILLSTAND)
                        return schluss("no_progress")
                    last_call = key
                    logger.info("Agent-Schleife: Ergebnis passt nicht zum Schema "
                                "(%d Abweichungen)", len(abweichungen))
                    messages.append(_tool_turn(tc.id, ergebnis_ungueltig(abweichungen)))
                    continue
                run.text = strip_reasoning_markers(str(args.get("text") or ""))
                run.result = args.get("result")
                ueber_budget_gemeldet()
                return schluss("submit")

            # Das Ergebnis als eigener Kanal (J1): virtuell wie ``submit_result``
            # — aber es beendet den Lauf NICHT. Die Antwort für die Person
            # entsteht danach als gewöhnlicher Zug, und genau diese Trennung ist
            # der Zweck (live gemessen, solange beides in EINEM Aufruf steckte:
            # 196 Zeichen Chat gegen 1932 Zeichen Ergebnis).
            #
            # Es steht VOR der Stillstands-Prüfung, anders als das Dokument: ein
            # zweiter Aufruf mit denselben Argumenten ist hier keine Sackgasse,
            # sondern ein überlesener Hinweis. Ihn als Stillstand zu werten,
            # beendete den Lauf ohne Prosa — mit genau dem Schaden also, gegen
            # den dieser Kanal gebaut ist.
            if name == LIEFERE_ERGEBNIS:
                if run.result is not None:
                    logger.info("Ergebnis-Werkzeug: zweiter Aufruf verworfen")
                    messages.append(_tool_turn(tc.id, BEREITS_GELIEFERT))
                    continue
                ergebnis = ergebnis_aus_argumenten(args)
                if ergebnis is None:
                    logger.info("Ergebnis-Werkzeug: unbrauchbare Argumente")
                    messages.append(_tool_turn(tc.id, ERGEBNIS_UNBRAUCHBAR))
                    continue
                abweichungen = argument_fehler(angebotene_parameter(tools, name), args)
                if abweichungen:
                    logger.info("Ergebnis-Werkzeug: Ergebnis passt nicht zum Schema "
                                "(%d Abweichungen)", len(abweichungen))
                    messages.append(_tool_turn(tc.id, ergebnis_ungueltig(abweichungen)))
                    continue
                run.result = ergebnis
                # Nur die Zahl der Felder: der Inhalt ist Modell-Ausgabe aus
                # Nutzer-Inhalt, und das Server-Log unterliegt keiner
                # Datenschutz-Schranke — dieselbe Linie wie beim Dokument-Titel.
                logger.info("Ergebnis geliefert (%d Felder)", len(ergebnis))
                progress.record("agent_result", "Ergebnis an die Anwendung übergeben",
                                {"felder": len(ergebnis)})
                messages.append(_tool_turn(tc.id, ERGEBNIS_UEBERNOMMEN))
                continue

            # Die Wall zuerst: sie kann einen Schlüssel einsetzen, und der
            # gehört zur Identität des Aufrufs (siehe ``_call_key``).
            args = gate.prepare(name, args)
            key = _call_key(name, args)
            if key == last_call:
                logger.info(
                    "Agent-Schleife: %s zweimal hintereinander mit denselben "
                    "Argumenten — Stillstand", name)
                quittiere(calls[i:], NICHT_AUSGEFUEHRT_STILLSTAND)
                return schluss("no_progress")
            last_call = key

            # Das Ergebnis-Dokument (D2): virtuell wie die beiden anderen, und
            # es beendet den Lauf NICHT — das Modell darf danach noch seinen
            # Begleitsatz schreiben oder ein zweites Dokument liefern. Steht
            # nach der Stillstands-Pruefung, damit zweimal dasselbe Dokument
            # als Stillstand zaehlt.
            if name == ZEIGE_DOKUMENT:
                dokument = dokument_aus_argumenten(args)
                if dokument is None:
                    logger.info("Dokument-Werkzeug: unbrauchbare Argumente")
                    messages.append(_tool_turn(tc.id, _DOKUMENT_FEHLER))
                    continue
                if len(run.dokumente) >= MAX_DOKUMENTE_JE_ZUG:
                    logger.info("Dokument-Werkzeug: Deckel von %d erreicht",
                                MAX_DOKUMENTE_JE_ZUG)
                    messages.append(_tool_turn(tc.id, _DOKUMENT_DECKEL))
                    continue
                run.dokumente.append(dokument)
                # Ohne den Titel: er ist Modell-Ausgabe aus Nutzer-Inhalt und
                # kann bei ``art: zeugnis`` einen Namen tragen. Das Server-Log
                # unterliegt keiner Datenschutz-Schranke; Art und Länge tragen
                # die Diagnose ebenso.
                logger.info("Dokument geliefert (%s, %d Zeichen)",
                            dokument["kind"], len(dokument["content"]))
                progress.record("agent_document", f"Ergebnis: {dokument['title']}",
                                {"kind": dokument["kind"]})
                # Die Bestaetigung ist keine Hoeflichkeit: ohne sie wuesste das
                # Modell nicht, ob der Inhalt angekommen ist, und schriebe ihn
                # sicherheitshalber noch einmal in die Prosa-Antwort.
                messages.append(_tool_turn(
                    tc.id,
                    f"Uebernommen: '{dokument['title']}' wird als Box "
                    f"angezeigt. Schreibe jetzt nur noch einen kurzen "
                    f"Begleitsatz — NICHT den Inhalt noch einmal."))
                continue

            # Die Wissensdatenbank (P): virtuell wie die drei davor — sie liegt
            # in der eigenen Datenbank, nicht am MCP. Ginge der Name durch,
            # meldete der Server ein unbekanntes Werkzeug, und das Modell lernte,
            # dass es kein internes Wissen gibt. Die Naht ist eine Rueckrufkarte
            # und keine Datenbank-Sitzung: die Schleife bedient auch den
            # Agent-Endpunkt, und der hat keine.
            if wissen is not None and name == WISSEN_SUCHEN:
                progress.record("agent_tool", f"Werkzeug: {name}", {"tool": name})
                run.tools_called.append(name)
                # Ohne Fremdtext-Rahmen: der Bestand ist redaktionell gepflegt
                # und liegt bei uns. Ihn als Fremdtext zu kennzeichnen hiesse,
                # die eigene Redaktion als blosse Daten zu behandeln.
                try:
                    wissen_text = await innerhalb(ende, wissen(args))
                except FristAbgelaufen:
                    return frist_mitten_in_der_runde(i)
                messages.append(_tool_turn(tc.id, wissen_text))
                continue

            progress.record("agent_tool", f"Werkzeug: {name}", {"tool": name})
            # Ein bestätigter Schreibaufruf läuft zu Ende, gedeckelt durch
            # ``MCP_CALL_TIMEOUT_S`` (B2): mitten im Flug abgeschnitten wüsste
            # niemand, ob er geschrieben hat, und ein neuer Versuch schriebe
            # doppelt (Prüfer 2026-10-04).
            aufruf = outcome_service.call_with_outcome(name, args)
            bestaetigt = is_confirmable(name) and CONFIRM_TOKEN_FIELD in args
            try:
                text, outcome = await (aufruf if bestaetigt else innerhalb(ende, aufruf))
            except FristAbgelaufen:
                # Auch abgebrochen gehört er ins Protokoll — sonst sähen
                # Gastgeber und Qualitätslog nicht, dass er lief.
                run.tools_called.append(name)
                run.outcomes.append(ToolOutcome(tool=name, status="timeout",
                                                error="Frist abgelaufen"))
                return frist_mitten_in_der_runde(i)
            run.tools_called.append(name)
            run.outcomes.append(outcome)
            # Rückweg: erst den Schlüssel aus dem Text nehmen, dann Fremdtext
            # als Daten kennzeichnen (D4). Beides, bevor irgendetwas davon in
            # die Nachrichtenkette geht.
            beobachtet = gate.observe(name, args, text)
            # Die Ernte-Naht sitzt ZWISCHEN beiden Schritten: nach der
            # Redaktion (kein Schlüssel darf hier heraus), vor dem Rahmen (der
            # ist eine Anweisung ans Modell, für einen Parser nur Störung).
            if on_tool_result is not None:
                on_tool_result(name, beobachtet)
            # Nur bei ECHTEM Ergebnis — ein Fehlschlag ist keine geholte
            # Anleitung, und eine Meldung darueber waere eine Behauptung statt
            # eines Belegs. Dieselbe Bedingung wie im Bestandsweg. Ein
            # MCP-Fehler kommt als gewoehnlicher Text zurueck, deshalb zaehlt
            # der Befund und nicht nur ein nichtleerer Text (Review 2026-09-26).
            if name == "get_skill" and beobachtet and outcome.status == "success":
                run.anleitungen.append({
                    "node_id": str(args.get("nodeId") or ""),
                    "titel": skill_titel(beobachtet),
                })
            # P1: der Freigabe-Katalog, den das Ergebnis mitbringt — ausserhalb
            # des Rahmens, weil er unsere Anweisung ist. Auf ``beobachtet``,
            # nicht auf ``text``: was die Schlüssel-Redaktion entfernt hat, darf
            # auch hier nicht wieder auftauchen.
            # Die Prompt-Sicht wird strukturell redigiert (2026-08-20): die
            # Sammlungs-Suche trug live ~30 KB nachladbaren Kompendiumstext im
            # ersten Treffer, und diese Kette zahlt jede Runde erneut. NUR die
            # Kette — Ernte und Registry-Hinweis lesen weiter ``beobachtet``,
            # und Langform-Werkzeuge (get_skill!) kommen unverändert durch.
            messages.append(_tool_turn(
                tc.id,
                frame_untrusted(name, redigiere_strukturell(name, beobachtet))
                + skill_registry_note(beobachtet, tool_name=name, args=args),
            ))

        if antwort is not None:
            run.text, run.vorschlaege = antwort_aus_argumenten(antwort)
            ueber_budget_gemeldet()
            # Ohne Text ist es keine Antwort — ``empty`` bekommt in
            # ``respond_agent`` den ehrlichen Satz statt einer leeren Blase.
            return schluss("text" if run.text else "empty")

    logger.info("Agent-Schleife: Iterationsdeckel von %s erreicht", limits.max_iterations)
    return schluss("max_iterations")
