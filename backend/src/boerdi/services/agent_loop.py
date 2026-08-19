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

from boerdi.domain.config_models.engine import AgentLimits
from boerdi.domain.inline_documents import (
    MAX_DOKUMENTE_JE_ZUG,
    ZEIGE_DOKUMENT,
    dokument_aus_argumenten,
)
from boerdi.domain.pattern_catalog import finde_muster
from boerdi.domain.pattern_engine import PatternDef
from boerdi.domain.reasoning_filters import strip_reasoning_markers
from boerdi.domain.result_delivery import (
    BEREITS_GELIEFERT,
    ERGEBNIS_UEBERNOMMEN,
    ERGEBNIS_UNBRAUCHBAR,
    LIEFERE_ERGEBNIS,
    ergebnis_aus_argumenten,
)
from boerdi.domain.untrusted_text import frame_untrusted
from boerdi.obs.progress import NO_PROGRESS, TurnProgress
from boerdi.obs.usage import new_accumulator
from boerdi.services import llm, outcome_service
from boerdi.services.agent_knowledge import WISSEN_SUCHEN
from boerdi.services.agent_tools import SUBMIT_RESULT, WAEHLE_VORGEHEN
from boerdi.services.agent_write import WriteGate
from boerdi.services.mcp.parsers import skill_registry_note

logger = logging.getLogger(__name__)

#: Der Name, unter dem die Kostenschau (K3) die Züge der Agent-Schleife führt.
USAGE_PHASE = "agent"

_ARGUMENT_FEHLER = (
    "Fehler: Die Argumente dieses Aufrufs waren kein gueltiges JSON. Wiederhole "
    "den Aufruf mit vollstaendigem, gueltigem JSON."
)

#: Der Kopf, unter dem ein gewaehltes Muster in die Kette geht. Er sagt dem
#: Modell, dass dies eine Anweisung ist und kein Fund — anders als bei einem
#: MCP-Ergebnis, das der Fremdtext-Rahmen ausdruecklich als Daten kennzeichnet.
_VORGEHEN_KOPF = (
    "Ab jetzt gilt dieses Vorgehen ({kennung} — {label}). Es ist die "
    "verbindliche Arbeitsanweisung der Redaktion; halte dich daran, bis du ein "
    "anderes waehlst.\n\n"
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


def _unbekanntes_vorgehen(kennung: object) -> str:
    """Antwort auf eine Kennung, die es nicht gibt oder die gesperrt ist.

    Ein Werkzeugfehler, kein Laufende (wie B8 bei unlesbaren Argumenten): das
    Modell soll es richtig wiederholen oder ohne Muster weiterarbeiten koennen.
    Der Text nennt **nicht**, welche Muster gesperrt sind — das ``enum`` fuehrt
    die waehlbaren, und eine Aufzaehlung der verbotenen waere eine Einladung.
    """
    return (
        f"Fehler: '{kennung}' ist kein waehlbares Vorgehen. Nimm eine der "
        "Kennungen aus der Liste des Werkzeugs — oder arbeite ohne Vorgehen "
        "weiter und antworte direkt."
    )


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
    outcomes: list[Any] = field(default_factory=list)
    #: Das zuletzt gewaehlte Muster (H3) — leer, wenn keines gewaehlt wurde.
    #: Es ist das TATSAECHLICH benutzte und damit die ehrlichere Angabe fuer
    #: Qualitaetslogs als eine Vermutung im Voraus.
    muster_id: str = ""
    #: Die vom Modell GELIEFERTEN Ergebnis-Boxen (D2), in Aufrufreihenfolge.
    #: Leer heisst: dieser Zug hat keine geliefert — dann greift weiter die
    #: geratene Box aus ``turn_persist``.
    dokumente: list[dict[str, Any]] = field(default_factory=list)


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
    muster_katalog: list[PatternDef] | None = None,
    werkzeuge_fuer: Callable[[PatternDef], list[dict[str, Any]]] | None = None,
    wissen: Callable[[dict[str, Any]], Awaitable[str]] | None = None,
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

    ``muster_katalog`` (H3) macht aus der Schleife den **Hybrid**: das Modell darf
    über ``waehle_vorgehen`` ein redaktionelles Muster ziehen, dessen Body als
    Anweisung in die Kette geht. Ohne den Katalog gibt es den Sonderfall nicht —
    dann ist der Name ein unbekanntes Werkzeug wie jeder andere.

    ``werkzeuge_fuer`` (H4) liefert die Werkzeugliste **des gewählten Musters**.
    Ohne sie bleibt die mitgegebene Liste stehen; mit ihr wechselt sie im Moment
    der Wahl. Als Rückruf und nicht als Katalog-Parameter, weil nur der Aufrufer
    weiß, was sonst noch in die Liste gehört (Sperren aus Safety/Policy, ob eine
    Anmeldung vorliegt) — diese Schleife soll davon nichts wissen müssen.
    """
    acc = usage_acc if usage_acc is not None else new_accumulator()
    gate = WriteGate(limits.write_mode)
    run = AgentRun()
    # Die Werkzeugliste dieses Augenblicks. Sie beginnt bei der mitgegebenen und
    # wechselt erst, wenn ein Muster gewählt wurde — neu gebaut wird sie also bei
    # der WAHL und nicht in jeder Runde, weil sie sich sonst nicht ändert.
    aktive_tools = tools
    start = clock()
    # Der Nullpunkt des Budgets, nicht der Zählerstand: im Chat-Modus trägt der
    # Zug-Zähler bereits Token früherer Schritte (Safety), und die gehören dem
    # Zug, nicht der Schleife.
    start_tokens = _spent(acc)
    last_call: str | None = None

    for _ in range(limits.max_iterations):
        if clock() - start >= limits.deadline_s:
            logger.info("Agent-Schleife: Frist von %s s erreicht", limits.deadline_s)
            return _ended(run, "deadline")
        if _spent(acc) - start_tokens >= limits.token_budget:
            logger.info("Agent-Schleife: Token-Budget von %s erreicht", limits.token_budget)
            return _ended(run, "token_budget")

        run.iterations += 1
        progress.record("agent_iteration", f"Agent-Schritt {run.iterations}",
                        {"iteration": run.iterations})
        try:
            # Gebucht wird über den Transport (``usage_acc``/``phase``) und
            # nicht mit eigener Hand: das Etikett steht hier im Voraus fest —
            # anders als im Tool-Loop, wo es erst aus ``finish_reason`` folgt
            # und deshalb dort begründet selbst gebucht wird. Eine Buchungs-
            # stelle weniger ist eine Driftquelle weniger.
            resp = await llm.chat_completion(
                messages=messages, tools=aktive_tools, temperature=0.4,
                usage_acc=acc, phase=USAGE_PHASE)
        except Exception as e:
            logger.error("Agent-Schleife: LLM-Fehler — %s", e)
            return _ended(run, "error")

        choice = resp.choices[0]
        calls = getattr(choice.message, "tool_calls", None)
        if not calls:
            run.text = strip_reasoning_markers(choice.message.content or "")
            return _ended(run, "text")

        messages.append(_assistant_turn(choice.message, calls))

        for tc in calls:
            name = tc.function.name
            args, fehler = _arguments(tc.function.arguments)
            if fehler:
                logger.info("Agent-Schleife: unlesbare Argumente für %s", name)
                messages.append(_tool_turn(tc.id, fehler))
                continue

            # Das Abschluss-Werkzeug ist virtuell: es geht nie an den MCP.
            # Weitere Aufrufe derselben Runde fallen weg — wer „fertig" sagt,
            # hat nichts mehr zu tun.
            if name == SUBMIT_RESULT:
                run.text = strip_reasoning_markers(str(args.get("text") or ""))
                run.result = args.get("result")
                return _ended(run, "submit")

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
                return _ended(run, "no_progress")
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

            # Der Musterwechsel ist virtuell wie ``submit_result`` — nur beendet
            # er den Lauf nicht, sondern richtet ihn aus. Er steht NACH der
            # Stillstands-Prüfung, damit zweimal dasselbe Muster als Stillstand
            # zählt und ein Wechsel als Fortschritt; beides fällt damit ohne
            # eigene Logik heraus. Und er steht VOR ``call_with_outcome``, denn
            # es gibt kein Werkzeug dieses Namens am MCP.
            if muster_katalog and name == WAEHLE_VORGEHEN:
                gewaehlt = finde_muster(args.get("muster_id"), muster_katalog)
                if gewaehlt is None:
                    logger.info("Hybrid: Vorgehen %r nicht waehlbar",
                                args.get("muster_id"))
                    messages.append(_tool_turn(
                        tc.id, _unbekanntes_vorgehen(args.get("muster_id"))))
                    continue
                run.muster_id = gewaehlt.id
                if werkzeuge_fuer is not None:
                    aktive_tools = werkzeuge_fuer(gewaehlt)
                logger.info("Hybrid: Vorgehen %s (%s) gewaehlt — %d Werkzeuge",
                            gewaehlt.id, gewaehlt.label, len(aktive_tools))
                progress.record("agent_pattern", f"Vorgehen: {gewaehlt.label}",
                                {"pattern": gewaehlt.id})
                # Ohne Fremdtext-Rahmen, und das ist keine Auslassung: der Body
                # stammt aus dem eigenen Konfigurations-Bestand, nicht vom MCP.
                # Ihn als Fremdtext zu kennzeichnen hieße dem Modell zu sagen,
                # es solle unsere eigene Anweisung als bloße Daten behandeln.
                messages.append(_tool_turn(
                    tc.id,
                    _VORGEHEN_KOPF.format(kennung=gewaehlt.id, label=gewaehlt.label)
                    + gewaehlt.body_md,
                ))
                continue

            # Die Wissensdatenbank (P): virtuell wie die vier davor — sie liegt
            # in der eigenen Datenbank, nicht am MCP. Ginge der Name durch,
            # meldete der Server ein unbekanntes Werkzeug, und das Modell lernte,
            # dass es kein internes Wissen gibt. Die Naht ist eine Rueckrufkarte
            # und keine Datenbank-Sitzung: die Schleife bedient auch den
            # Agent-Endpunkt, und der hat keine.
            if wissen is not None and name == WISSEN_SUCHEN:
                progress.record("agent_tool", f"Werkzeug: {name}", {"tool": name})
                run.tools_called.append(name)
                # Ohne Fremdtext-Rahmen: der Bestand ist redaktionell gepflegt
                # und liegt bei uns — dieselbe Begruendung wie beim Muster-Body.
                messages.append(_tool_turn(tc.id, await wissen(args)))
                continue

            progress.record("agent_tool", f"Werkzeug: {name}", {"tool": name})
            text, outcome = await outcome_service.call_with_outcome(name, args)
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
            # P1: der Freigabe-Katalog, den das Ergebnis mitbringt — ausserhalb
            # des Rahmens, weil er unsere Anweisung ist. Auf ``beobachtet``,
            # nicht auf ``text``: was die Schlüssel-Redaktion entfernt hat, darf
            # auch hier nicht wieder auftauchen.
            messages.append(_tool_turn(
                tc.id,
                frame_untrusted(name, beobachtet)
                + skill_registry_note(beobachtet, tool_name=name, args=args),
            ))

    logger.info("Agent-Schleife: Iterationsdeckel von %s erreicht", limits.max_iterations)
    return _ended(run, "max_iterations")
