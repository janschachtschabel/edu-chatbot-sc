"""``respond_agent`` — der Antwort-Knoten im Agent-Modus (A4c-2b).

Der Gegenentwurf zu ``respond``: statt ``generate_response`` mit gebundenem
Werkzeugsatz und spekulativer Vorab-Suche läuft hier ``run_agent_loop`` über dem
vollen Katalog. ``respond`` reicht früh hierher weiter; sein Rumpf bleibt
unangetastet — der Bestandsweg ist die Zusage des Nutzers.

**Gegenstand dieses Moduls ist nicht die Schleife, sondern was der Agent-Modus
vom Chat-Zug ERBT.** Jedes dieser vier Stücke ginge sonst still verloren:

* die **Werkzeug-Sperre** aus Safety/Policy. ``route`` streicht sie im
  Bestandsweg aus ``pattern_output['tools']``; im Agent-Modus ist dieser
  Schlüssel leer (gemessen), die Sperre hätte also keinen Empfänger mehr — der
  Agent bekäme den vollen Katalog samt gesperrtem Werkzeug.
* die **Schreib-Regel** (``enforce_write_mode``): ``execute`` verlangt eine
  angemeldete Person, auch wenn es aus der Konfiguration kommt.
* die **Hinweise an der Antwort** (``append_answer_notes``): Policy-Disclaimer
  und Medium-Risk-Notiz hängen an ``policy``/``safety``, nicht daran, wer den
  Text erzeugt hat.
* der **spekulative Vorabruf** aus ``merge``: er wird hier nie verbraucht und
  deshalb abgebrochen — sonst laufen die Tasks unbeobachtet weiter. Für die
  Schnellweg-Routen tut ``respond`` genau dasselbe.
* der **Seitenkontext** (P4, 2026-08-13). Der Bestandsweg reicht ihn über
  ``response_prompt_builder`` in den Systemprompt; hier wird die Kette selbst
  gebaut, und er fiel weg. Live gemessen (Befund B-2): auf einer Sammlungsseite
  fragte der Agent „welche Sammlung meinst du?" — die ID stand in
  ``page_context``. Steht dort eine Sammlung, wird ihre Freigabeliste dazu
  **vorab geholt** (``agent_prefetch``), damit der Katalog in der Kette steht,
  bevor der Agent auf die Idee kommen könnte, danach zu fragen.

**``submit_result`` nur auf Ansage.** Ohne erklärtes Schema gibt es das
Abschluss-Werkzeug hier nicht: im Chat liest niemand das strukturierte
``result``, und die Beschreibung des Werkzeugs verlangt einen zusätzlichen
Modellzug (2–9 s gemessen), nur um zu sagen, was die Prosa-Antwort schon sagt.
Der Lauf endet dann über ``stop_reason='text'``.

Erklärt der Gastgeber ein ``environment.result_schema`` (2026-08-14), kehrt sich
das um: das Werkzeug kommt in den Katalog **und** der Systemprompt bekommt den
Satz darüber. Beides zusammen oder gar nicht — eine Anweisung auf ein Werkzeug,
das nicht im Katalog steht, wäre genau der Widerspruch, den C1-f1 gelehrt hat.
Wer die 2–9 s zahlt, hat sie bestellt.

**Kein Streaming.** ``run_agent_loop`` kennt keinen ``on_token``-Haken; der
SSE-Strom trägt im Agent-Modus die ``phase``-Ereignisse und am Ende die ganze
Antwort. Bewusst: ein Streaming-Weg in die Schleife wäre ein zweiter Umbau, und
der A/B-Vergleich misst Inhalt und Dauer, nicht die Tropfgeschwindigkeit.

Randkonvention wie bei den Nachbarknoten: Nachbarn sind AN DIESEM Modul patchbar.
"""

from __future__ import annotations

import logging

from boerdi.domain.answer_notes import append_answer_notes
from boerdi.graph.state import TurnContext
from boerdi.i18n import resolve_locale
from boerdi.i18n.bot_text import bot_text
from boerdi.i18n.prompt_language import language_name
from boerdi.obs.progress import NO_PROGRESS, TurnProgress
from boerdi.obs.tasks import cancel_and_drain
from boerdi.services import page_context
from boerdi.services.agent_loop import AgentRun, run_agent_loop
from boerdi.services.agent_prefetch import resolve_prefetch
from boerdi.services.agent_tools import build_agent_tools
from boerdi.services.agent_write import enforce_write_mode
from boerdi.services.card_collect import collect_cards
from boerdi.services.config_loader import load_engine

logger = logging.getLogger(__name__)

#: Wie viele Züge des Verlaufs mitgehen — dieselbe Zahl wie im Bestandsweg
#: (``tool_loop._assemble_messages``), damit der A/B-Vergleich nicht schon am
#: Gedächtnis auseinanderläuft.
_HISTORY_TURNS = 10

_SYSTEM = (
    "Du bist Boerdi, der Assistent von WirLernenOnline (WLO). Du sprichst mit "
    "einem Menschen im Chat — kurz, freundlich und ohne Floskeln.\n\n"
    "Arbeitsweise: hole dir die Tatsachen mit den Werkzeugen, statt sie aus dem "
    "Gedaechtnis zu behaupten. Steht in einer Sammlung eine Anleitung zu deiner "
    "Aufgabe, halte dich daran. Nenne, worauf du dich stuetzt, und sage "
    "ausdruecklich, was du NICHT pruefen konntest.\n\n"
    "SPRACHE DER AUSGABE: {sprache}. Formatiere mit Markdown."
)


async def _verwirf_vorabruf(ctx: TurnContext) -> None:
    """Den spekulativen Vorabruf aus ``merge`` abbrechen.

    Der Agent sucht sich sein Werkzeug selbst; ein auf die Ersatz-Klassifikation
    gestarteter Vorabruf ist hier bestenfalls geraten. Abbrechen statt einspeisen
    ist zugleich die ehrlichere Messung: ein vorgefüllter Treffer stammte aus der
    Muster-Engine und verfälschte den Vergleich.
    """
    aufgaben = [ctx.spec_task] + [t for _name, t in ctx.extra_spec_tasks]
    verworfen = await cancel_and_drain(aufgaben)
    ctx.extra_spec_tasks = []
    if verworfen:
        logger.info("Agent-Modus: %d spekulative Vorabrufe verworfen", verworfen)


def _vorab_aufrufe(seite: dict) -> list[tuple[str, dict]]:
    """Was der Seitenkontext an Vorabrufen bestellt (P4).

    Nur ``collection_id``: es ist das einzige Feld, aus dem ein
    ``collectionId``-Argument wird. Steht keine Sammlung auf der Seite, gäbe es
    nichts zu übergeben — der Aufruf wäre eine Rundreise ohne Ertrag.
    Themenseiten sind im Bestand Sammlungen und tragen das Feld mit; sie sind
    damit ohne eigene Regel abgedeckt.

    Absichtlich NICHT ``node_ids``: was auf der Seite steht, sagt schon der
    Seitenblock, und ein Detail-Abruf je Zug kostet mehr, als er trägt.
    """
    sammlung = (seite.get("collection_id") or "").strip()
    if not sammlung:
        return []
    return [("get_skill_registry", {"collectionId": sammlung})]


#: Enden, bei denen der Lauf an einen Deckel gestoßen ist statt zu scheitern —
#: der Nutzer kann selbst etwas tun (kleiner schneiden). Alles andere ist ein
#: Fehlschlag und bekommt den Wiederhol-Satz.
_GEDECKELT = frozenset({"deadline", "token_budget", "max_iterations", "no_progress"})


def _antwort_oder_ersatz(lauf: AgentRun, sprache: str) -> str:
    """Der Antworttext — oder ein ehrlicher Satz, wenn es keinen gibt.

    ``AgentRun.text`` ist nur bei ``text`` und ``submit`` gefüllt; die fünf
    übrigen Enden liefern ihn LEER. Ohne diesen Ersatz bekäme der Nutzer eine
    leere Blase, und ein stiller Ausfall ist der schlechtere von beiden. Der
    Bestandsweg degradiert an derselben Stelle freundlich.

    Geprüft wird der TEXT und nicht der Grund: auch ``stop_reason='text'`` kann
    leer sein, wenn das Modell mit leerem Inhalt antwortet.
    """
    if lauf.text.strip():
        return lauf.text
    schluessel = "agent.incomplete" if lauf.stop_reason in _GEDECKELT else "agent.failed"
    logger.info("Agent-Modus: Lauf ohne Text (Ende=%s) — Ersatzsatz %s",
                lauf.stop_reason, schluessel)
    return bot_text(sprache, schluessel)


async def respond_agent(
    ctx: TurnContext, progress: TurnProgress = NO_PROGRESS
) -> TurnContext:
    """Beantworte den Zug mit der Agent-Schleife. Mutiert ``ctx`` und gibt ihn
    zurück — gleiche Ausgangsfelder wie ``respond``, damit ``assemble`` und
    ``persist`` unverändert weiterlaufen."""
    await _verwirf_vorabruf(ctx)

    sprache = resolve_locale(ctx.req.environment.locale)
    seite = ctx.req.environment.page_context or {}
    messages: list[dict] = [
        {"role": "system", "content": _SYSTEM.format(sprache=language_name(sprache))},
    ]
    # P4: der Seitenkontext. Der Bestandsweg reicht ihn über
    # ``response_prompt_builder`` ein; hier wurde die Kette selbst gebaut und er
    # fiel weg — der Agent fragte nach einer ID, die vor ihm stand (B-2).
    seiten_block = page_context.prompt_block(ctx.session_state, seite)
    if seiten_block:
        messages.append({"role": "system", "content": seiten_block})
    messages.extend(ctx.history[-_HISTORY_TURNS:])
    # Anleitungen vor Gegenstand — dieselbe Reihenfolge wie im Agent-Endpunkt.
    await resolve_prefetch(messages, _vorab_aufrufe(seite), progress=progress)
    messages.append({"role": "user", "content": ctx.req.message})

    # Erklärt der Gastgeber ein Schema, bekommt der Lauf sein Abschluss-Werkzeug
    # (2026-08-14). Nur dann: der Zug kostet 2–9 s und sagt sonst, was die Prosa
    # schon sagt. Und nur dann steht der Satz darüber im Systemprompt — eine
    # Anweisung auf ein Werkzeug, das nicht im Katalog ist, wäre der Widerspruch,
    # den der Modulkopf beschreibt.
    _schema = ctx.req.environment.result_schema or None
    if _schema:
        messages[0]["content"] += (
            "\n\nDer Gastgeber erwartet ein maschinenlesbares Ergebnis. Rufe "
            "``submit_result`` genau einmal, sobald du es hast — und nur dann. "
            "Ist die Nachricht bloss Gespraech (Begruessung, Rueckfrage), "
            "antworte gewoehnlich und rufe es NICHT."
        )

    all_cards: list[dict] = []
    progress.start("response", "LLM response generation")
    lauf = await run_agent_loop(
        messages=messages,
        tools=build_agent_tools(
            blocked_tools=ctx.safety.blocked_tools,
            include_submit=bool(_schema), result_schema=_schema),
        limits=enforce_write_mode(load_engine().agent),
        usage_acc=ctx.usage,
        progress=progress,
        on_tool_result=lambda name, text: collect_cards(all_cards, name, text),
    )
    logger.info("Agent-Modus: %d Schritte, Ende=%s, %d Werkzeuge, %d Karten",
                lauf.iterations, lauf.stop_reason, len(lauf.tools_called),
                len(all_cards))

    # Triple-Schema T-25/27 wie im Bestandsweg: die Qualitätslogs lesen beides
    # in beiden Maschinen, sonst misst der A/B-Vergleich eine selbstgebaute Lücke.
    from boerdi.services.outcome_service import adjust_confidence, derive_state_hint
    zustand = derive_state_hint(lauf.outcomes)
    if zustand and zustand != ctx.state_id:
        logger.info("Outcome-based state hint: %s -> %s", ctx.state_id, zustand)
        ctx.state_id = zustand

    ctx.response_text = append_answer_notes(
        _antwort_oder_ersatz(lauf, sprache), policy=ctx.policy, safety=ctx.safety)
    ctx.wlo_cards_raw = all_cards
    # Ergebnis und Ende-Grund weiterreichen. Der Grund geht MIT, auch wenn kein
    # Ergebnis kam: sonst sähe ein an der Frist abgeschnittener Lauf für die
    # Gastseite aus wie einer, der nichts zu sagen hatte.
    if _schema:
        ctx.result = lauf.result if isinstance(lauf.result, dict) else None
        ctx.result_stop_reason = lauf.stop_reason
    ctx.tools_called = lauf.tools_called
    ctx.debug.outcomes = lauf.outcomes
    ctx.debug.confidence = adjust_confidence(
        ctx.classification.intent_confidence, lauf.outcomes)
    return ctx
