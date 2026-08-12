"""Ein Agent-Lauf, von der Anweisung bis zur Antwort (A3a).

Alles, was der Endpunkt (A3b) danach nur noch durchreicht: welche Limits gelten,
was vorab aufgelöst wird, welchen Systemprompt der Agent bekommt. Bewusst ohne
HTTP — dadurch ist der ganze Weg ohne Router prüfbar, und die Vertragsänderung
in A3b steht allein und sichtbar.

**Was hier NICHT ist:** Begrüßung, Muster, Klassifikator, Karten, Quick-Replies,
Sitzungsgedächtnis. Das ist der Chat-Rahmen, und der Gastgeber hat ihn nicht —
er hat eine Maschine, die eine Aufgabe stellt und ein Ergebnis auswertet.

**Vorab aufgelöst wird, was der Aufrufer ausdrücklich mitgegeben hat**, und nur
das: Knoten über ``get_nodes_details``, die Sammlung über ``get_skill_registry``.
Beides landet als *erledigter* Werkzeugaufruf in der Kette — dieselbe Bauart wie
die Prefetch-Injektion in ``_assemble_messages``, weil der Anbieter ein
``role=tool``-Ergebnis ohne den zugehörigen Aufruf ablehnt. Alles andere sucht
sich der Agent selbst; das ist der Sinn der Sache.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from boerdi.api.schemas_agent import AgentRequest, AgentResponse
from boerdi.domain.config_models.engine import AgentLimits
from boerdi.domain.untrusted_text import frame_untrusted
from boerdi.i18n.locale import resolve_locale
from boerdi.i18n.prompt_language import language_name
from boerdi.obs.progress import NO_PROGRESS, TurnProgress
from boerdi.services import outcome_service
from boerdi.services.agent_loop import run_agent_loop
from boerdi.services.agent_tools import build_agent_tools
from boerdi.services.agent_write import enforce_write_mode
from boerdi.services.config_loader import load_engine

logger = logging.getLogger(__name__)

_SYSTEM = (
    "Du bist ein Werkzeug-Agent auf dem Bestand von WirLernenOnline (WLO). Du "
    "arbeitest einen Auftrag ab, der von einem anderen Programm gestellt wurde — "
    "nicht von einem Menschen im Gespraech. Es gibt keine Begruessung und keinen "
    "Smalltalk.\n\n"
    "Arbeitsweise: nutze die Werkzeuge, um dir die Tatsachen zu holen, statt sie "
    "aus dem Gedaechtnis zu behaupten. Steht in einer Sammlung eine Anleitung zu "
    "deiner Aufgabe, halte dich daran. Rufe ``submit_result`` genau einmal, wenn "
    "du fertig bist — vorher endet der Lauf nicht.\n\n"
    "Ehrlichkeit geht vor Vollstaendigkeit: nenne im Text ausdruecklich, was du "
    "NICHT pruefen konntest, statt es zu ueberspielen.\n\n"
    "SPRACHE DER AUSGABE: {sprache}."
)

# Was in die Kette geht, wenn ein Vorab-Abruf scheitert. Ein gelöschter Knoten
# oder ein wackliger MCP darf den Auftrag nicht kippen — der Agent arbeitet
# weiter und sagt selbst, was ihm fehlt.
_VORAB_FEHLER = (
    "Diese Angaben liessen sich nicht abrufen. Arbeite ohne sie weiter und sage "
    "im Ergebnis ausdruecklich, dass sie fehlen."
)


def _limits(vorgabe: AgentLimits, req: AgentRequest) -> AgentLimits:
    """Die Deckel dieses Laufs — Konfiguration, wahlweise vom Aufrufer verschoben.

    Die Schreib-Regel selbst wohnt seit A4c-2b in ``agent_write``, weil der
    Agent-Modus im Chat sie als zweiter Aufrufer braucht; hier bleibt allein die
    Übersetzung „Übersteuerung dieses Endpunkts" → „Wunsch".
    """
    return enforce_write_mode(vorgabe, req.write_mode)


def _vorab_aufrufe(req: AgentRequest) -> list[tuple[str, dict[str, Any]]]:
    """Die Abrufe, die der Aufrufer mit seinen Angaben bestellt hat.

    Anleitungen vor Gegenstand: was der Agent tun soll, bevor er sieht, woran.
    """
    aufrufe: list[tuple[str, dict[str, Any]]] = []
    if req.collection_id:
        aufrufe.append(("get_skill_registry", {"collectionId": req.collection_id}))
    if req.node_ids:
        aufrufe.append(("get_nodes_details", {"nodeIds": list(req.node_ids)}))
    return aufrufe


async def _resolve_prefetch(
    messages: list[dict[str, Any]], req: AgentRequest, progress: TurnProgress
) -> None:
    """Die Vorab-Abrufe ausführen und als erledigte Werkzeugaufrufe anhängen."""
    for i, (name, args) in enumerate(_vorab_aufrufe(req)):
        progress.record("agent_prefetch", f"Hole {name}", {"tool": name})
        try:
            text, _outcome = await outcome_service.call_with_outcome(name, args)
        except Exception:
            logger.warning("Agent-Lauf: Vorab-Abruf %s fehlgeschlagen", name,
                           exc_info=True)
            text = _VORAB_FEHLER
        call_id = f"prefetch-{i}"
        messages.append({
            "role": "assistant", "content": None,
            "tool_calls": [{
                "id": call_id, "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }],
        })
        messages.append({
            "role": "tool", "tool_call_id": call_id,
            # Dritte Naht der Vertrauensgrenze (D4): ``get_skill_registry``
            # liefert die Freigabetexte der Redaktion, also Fremdtext.
            "content": frame_untrusted(name, text),
        })


async def run_agent(
    req: AgentRequest,
    *,
    progress: TurnProgress = NO_PROGRESS,
    usage_acc: dict[str, Any] | None = None,
) -> AgentResponse:
    """Führe einen Agent-Lauf aus und gib sein Ergebnis zurück."""
    engine = load_engine()
    limits = _limits(engine.agent, req)
    sprache = resolve_locale(req.locale)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM.format(sprache=language_name(sprache))},
    ]
    await _resolve_prefetch(messages, req, progress)
    messages.append({"role": "user", "content": req.instruction})

    lauf = await run_agent_loop(
        messages=messages,
        tools=build_agent_tools(
            result_schema=req.result_schema, allow_curation=req.allow_curation),
        limits=limits,
        usage_acc=usage_acc,
        progress=progress,
    )
    return AgentResponse(
        text=lauf.text, result=lauf.result, stop_reason=lauf.stop_reason,
        iterations=lauf.iterations, tools_called=lauf.tools_called,
    )
