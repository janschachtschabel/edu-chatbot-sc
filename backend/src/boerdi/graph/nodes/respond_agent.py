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

**Token-Streaming** (Plan 2026-10-01): nur der Text von ``respond_to_user``,
also nur mit ``AGENT_INLINE_QUICK_REPLIES`` und ``CHAT_TOKEN_STREAMING``.
``graph/nodes/respond_strom`` öffnet oder sperrt den Strom, ``run_agent_loop``
streamt höchstens eine Antwortrunde. Sonst trägt der SSE-Strom die
``phase``-Ereignisse und am Ende die ganze Antwort.

Randkonvention wie bei den Nachbarknoten: Nachbarn sind AN DIESEM Modul patchbar.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from boerdi.domain import host_capabilities, host_instruction
from boerdi.domain.answer_notes import append_answer_notes
from boerdi.domain.antwort_werkzeug import antwort_werkzeug, inline_anzahl
from boerdi.domain.history_window import verlaufs_fenster
from boerdi.domain.skill_ansagen import mit_master_ansage
from boerdi.domain.skill_precedence import (
    anleitungs_hinweis,
    merke_laufende_anleitung,
    mit_ladehinweisen,
)
from boerdi.graph.nodes.respond_strom import strom_fuer_agent_zug
from boerdi.graph.state import TurnContext
from boerdi.i18n import resolve_locale
from boerdi.i18n.bot_text import bot_text
from boerdi.obs.progress import NO_PROGRESS, TurnProgress
from boerdi.obs.tasks import cancel_and_drain
from boerdi.services import (
    betriebsschalter,
    master_skill,
    page_context,
    prompt_ablage,
    seitenkontext_prompt,
)
from boerdi.services.agent_abschluss import abschluss_nachholen, antwort_oder_ersatz
from boerdi.services.agent_deckel import fuer_diesen_zug
from boerdi.services.agent_knowledge import WISSENS_REGEL, wissen_werkzeug
from boerdi.services.agent_knowledge import antwort as wissen_antwort
from boerdi.services.agent_kopf import kopf
from boerdi.services.agent_loop import run_agent_loop
from boerdi.services.agent_prefetch import resolve_prefetch, vorab_aufrufe
from boerdi.services.agent_tools import angebotene_mcp_werkzeuge, build_agent_tools
from boerdi.services.agent_trace import spur
from boerdi.services.agent_write import enforce_write_mode
from boerdi.services.agent_zugblock import zuletzt_gezeigt
from boerdi.services.card_collect import collect_cards, juengste_zuerst
from boerdi.services.config_loader import load_engine
from boerdi.services.quick_replies_llm import _max_chars
from boerdi.services.schreibrecht import schreiben_erlaubt
from boerdi.services.write_approval import merke_abnahme

logger = logging.getLogger(__name__)


def _antwort_werkzeug(ctx: TurnContext) -> dict[str, Any] | None:
    """``respond_to_user`` für den Agenten — nur mit den Agent-Schnellantworten
    (Studio ``betrieb.agent_schnellantworten`` oder ``AGENT_INLINE_QUICK_REPLIES``).

    Vorgabe an seit Paket 15 — Token-Streaming im Agent-Modus braucht das Werkzeug.
    Der Master-Skill muss die Mechanik dazu beschreiben (nicht mehr „ein zweiter
    Modellaufruf schreibt die Pillen"); Werkzeug und Anleitung dürfen sich nicht
    widersprechen. ``inline_anzahl`` trägt den globalen Schalter und die
    Anzahl — dieselbe wie im Muster-Weg (Plan 2026-09-30).
    """
    if not betriebsschalter.agent_schnellantworten():
        return None
    anzahl = inline_anzahl(ctx.pattern_output or {})
    return antwort_werkzeug(anzahl, _max_chars()) if anzahl else None

#: Wie viele Züge des Verlaufs mitgehen — dieselbe Zahl wie im Bestandsweg
#: (``tool_loop._assemble_messages``), damit der A/B-Vergleich nicht schon am
#: Gedächtnis auseinanderläuft.
_HISTORY_TURNS = 10

#: Die ZAHL ist dieselbe wie im Bestandsweg, die **Größe** nicht mehr (H8-3):
#: ``verlaufs_fenster`` deckelt zusätzlich die Zeichen. Eine bewusste Abweichung
#: mit zwei Gründen. Erstens zahlt diese Schleife den Verlauf in **jeder** ihrer
#: bis zu 12 Runden, der Bestandsweg in höchstens 5 — dieselben Zeichen kosten
#: hier also mehr als das Doppelte. Zweitens trägt ``tool_loop_messages`` als
#: P12/P14-Port die Zusage „byte-identisch zu ALT für dieselbe Config"; derselbe
#: Deckel dort wäre ein Bruch dieser Zusage. Folge, ausdrücklich: der A/B-Lauf
#: vergleicht ab jetzt zwei Maschinen mit unterschiedlicher Verlaufs-Behandlung.
#:
#: Seit dem Wegfall des ``message``-Deckels (2026-08-18) hat diese Abweichung
#: eine zweite Folge, die hier stehen soll statt entdeckt zu werden: der
#: Bestandsweg — und das ist die VORGABE-Maschine — trägt den Verlauf ohne jede
#: Größenschranke in den Prompt. Bewusst so gelassen: die Zusage der
#: Byte-Gleichheit wiegt schwerer als ein Randfall, den der Gastgeber selbst
#: auslöst und in seinem eigenen Token-Budget bezahlt (dieselbe Abwägung wie in
#: ``domain/host_instruction``). Wer die Entscheidung dreht, fängt hier an.

# Der Rollenblock steht seit AG-3 im Studio (``01-base/engine``, ``agent_rolle``);
# ``services/agent_kopf`` baut daraus den Kopf der Kette.

# Die Wissens-Regel (nur mit ``wissen_suchen`` im Katalog) steht seit ST-8d in
# ``services/agent_knowledge`` — die Prompt-Vorschau des Studios liest sie dort.


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


async def respond_agent(
    ctx: TurnContext, progress: TurnProgress = NO_PROGRESS, session: Any = None,
    on_token: Any = None,
) -> TurnContext:
    """Beantworte den Zug mit der Agent-Schleife. Mutiert ``ctx`` und gibt ihn
    zurück — gleiche Ausgangsfelder wie ``respond``, damit ``assemble`` und
    ``persist`` unverändert weiterlaufen."""
    # Die Frist der Schleife zählt ab hier, mit Vorabruf (Paket 4, B1).
    beginn = time.monotonic()
    await _verwirf_vorabruf(ctx)

    sprache = resolve_locale(ctx.req.environment.locale)
    # ``ctx.env`` und NICHT ``ctx.req.environment``: ``ctx.env`` ist ein
    # ``model_dump()``, das das verschachtelte ``page_context``-Dict KOPIERT
    # (gemessen 2026-08-20). Alles, was der Server selbst einträgt — Seitenart
    # ``editorial`` (Prüftisch), ``home``/``external`` aus der Host-Einordnung,
    # die Textfeld-Normalisierung —, steht nur in dieser Kopie. Der Muster-Weg
    # liest sie längst (``respond.py``: ``env = ctx.env``); hier fehlte sie, und
    # damit kam z.B. die Erschließungs-Regel im Agent-Modus nie an.
    # Rückfall auf das Original, falls ``setup`` nicht lief.
    seite = (ctx.env or {}).get("page_context") or ctx.req.environment.page_context or {}
    # EIN Stand für Rolle und Deckel: ein Speichern im Studio zwischen zwei
    # Aufrufen gäbe dem Zug sonst Rolle und Deckel aus verschiedenen Fassungen.
    einstellung = load_engine()
    messages: list[dict] = [
        {"role": "system", "content": kopf(einstellung.agent_rolle, sprache)},
    ]
    # Paket 13 (A5): die festen Bausteine als Prüfsummen im Merkposten des Zuges.
    prompt_ablage.merke(ctx.usage, "agent.kopf", messages[0]["content"])
    # N3: die redaktionelle Gesamtanleitung — GROSS und zwischen zwei Zuegen
    # unveraendert, deshalb im Systemteil; der eigene Rollen-Block bleibt davor,
    # denn eigene Regeln gehoeren vor fremden Text. Gemessen 2026-09-29
    # (gpt-6-luna, Responses-Weg): OpenAI trifft den Cache nur am Ende des GANZEN
    # Systemteils samt Werkzeugen, nicht an einem Block darin — wechselt einer,
    # ist der ganze Prompt ungecacht. Deshalb steht im Systemteil nur, was nicht
    # von Seite, Verlauf oder Nachricht abhaengt (Plan 2026-09-29, Paket B).
    anleitung = await master_skill.prompt_block(ctx.req.environment.master_skill)
    if anleitung:
        messages.append({"role": "system", "content": anleitung})
        prompt_ablage.merke(ctx.usage, "agent.master_skill", anleitung)
    # Der Beleg fuer den Zusammenbau unten: die Ansage-Zeile entsteht NUR,
    # wenn der Abruf wirklich lief. Das Modell selbst haelt sich nicht
    # zuverlaessig an die Bitte des Dokuments (gemessen ueber drei Zuege:
    # ja / nein / ja) — deshalb setzt der Server sie.
    ctx.master_skill_zeile = master_skill.aktivierungszeile(anleitung)
    # O-C: was DIESE Einbettung anzeigt und erlaubt. Ebenfalls stabil (die
    # Attribute wechseln nicht zwischen zwei Zuegen), deshalb noch im
    # gecachten Praefix — aber hinter der Gesamtanleitung, denn es schraenkt
    # sie ein. Steht alles auf Vorgabe, entsteht kein Block.
    grenzen = host_capabilities.prompt_block(
        inline_result_grouping=ctx.req.environment.inline_result_grouping,
        tool_mode=ctx.req.environment.tool_mode,
    )
    if grenzen:
        messages.append({"role": "system", "content": grenzen})
    # P4: der Seitenkontext. Der Bestandsweg reicht ihn über
    # ``response_prompt_builder`` ein; hier wurde die Kette selbst gebaut und er
    # fiel weg — der Agent fragte nach einer ID, die vor ihm stand (B-2).
    # Seit Paket B in zwei Teilen (``services/seitenkontext_prompt``): hier die
    # festen Regeln, für jede Seite gleich; die Daten gerahmt vor dem Verlauf.
    seiten_daten = seitenkontext_prompt.seiten_daten(ctx.session_state, seite)
    if seiten_daten:
        messages.append({"role": "system", "content": seitenkontext_prompt.SEITEN_REGELN})
        prompt_ablage.merke(ctx.usage, "seitenregeln", seitenkontext_prompt.SEITEN_REGELN)
    # G1: der Auftrag der einbettenden Anwendung — WÖRTLICH derselbe Block wie im
    # Bestandsweg (``domain/host_instruction``). Er steht hinter dem Seitenblock
    # und vor den Anleitungen: die Anwendung rahmt den Zug, die Anleitung sagt,
    # wie eine Aufgabe zu tun ist.
    anweisungs_block = host_instruction.prompt_block(ctx.req.environment.host_instruction)
    if anweisungs_block:
        messages.append({"role": "system", "content": anweisungs_block})
    # Und die Anleitungen, die nur aus dem GESPRÄCH bekannt sind: über die Suche
    # gibt es keinen Seitenkontext, also auch keinen Katalog — der Agent kannte
    # weder die Anleitungen noch die ``collectionId`` für ``get_skill_registry``.
    # Derselbe Entscheid wie im Bestandsweg, eine Ebene tiefer in
    # ``domain/skill_precedence``; auf der Seite schweigt er von selbst.
    anleitungen = anleitungs_hinweis(
        (page_context.get_cached(ctx.session_state) or {}).get("context_facts"),
        (ctx.session_state or {}).get("entities"),
    )
    if anleitungen:
        messages.append({"role": "system", "content": anleitungen})
    _fenster = verlaufs_fenster(ctx.history, max_nachrichten=_HISTORY_TURNS)
    _roh = sum(len(m.get("content") or "") for m in ctx.history[-_HISTORY_TURNS:])
    _im_prompt = sum(len(m["content"]) for m in _fenster)
    if _im_prompt < _roh:
        logger.info("Verlauf gedeckelt: %d von %d Nachrichten, %d von %d Zeichen",
                    len(_fenster), len(ctx.history[-_HISTORY_TURNS:]), _im_prompt, _roh)
    # Paket B: die Seitendaten als erste Nachricht nach dem Systemteil — gemessen
    # bleibt der Block dort im Folgezug gecacht, vor der aktuellen Nachricht nicht.
    if seiten_daten:
        messages.append({"role": "user", "content": seiten_daten})
    # Anleitungen vor Gegenstand — dieselbe Reihenfolge wie im Agent-Endpunkt. E-C
    # (gemessen 2026-10-09, gpt-6-luna): direkt hinter den Seitendaten, VOR dem
    # Verlauf. Hinter dem Verlauf lag der Vorabruf im ersten Zug vor der Frage und
    # danach hinter dem Verlauf — die Ketten trennten sich nach den Seitendaten,
    # und jeder Folgezug auf einer Sammlungsseite zahlte Seitendaten und Katalog
    # ungecacht (≈ 2 900 Token). So verlängert jeder Zug den vorigen — solange keine
    # Antwort im Verlauf über 1 200 Zeichen hat: ``verlaufs_fenster`` kürzt sie, sobald
    # sie nicht mehr die jüngste ist, und ab ihr trennen sich die Ketten (Review B-3,
    # gemessen mit 3 300 Zeichen: ab Zug 3 je Zug ≈ 300 Token mehr ungecacht).
    # Paket 7 (S4, P5-9): schreiben nur mit persönlicher Anmeldung — oder mit dem
    # Block der Anlage, wenn das Studio das Gastkonto erlaubt (``schreibrecht``).
    _darf_schreiben = schreiben_erlaubt()
    _angebot = angebotene_mcp_werkzeuge(
        allow_curation=_darf_schreiben, blocked_tools=ctx.safety.blocked_tools,
        tool_mode=ctx.req.environment.tool_mode)
    await resolve_prefetch(messages, vorab_aufrufe(seite, _angebot), progress=progress)
    messages.extend(_fenster)
    # Paket C: was die Person zuletzt gesehen hat, damit „der erste Treffer“ oder
    # „die Lösungen dazu“ einen Gegenstand haben — gerahmt am ANFANG ihrer
    # Nachricht, nicht als System-Block: den hebt LiteLLM auf dem Responses-Weg in
    # ``instructions`` (Review 2026-09-29), und er enthält Fremdtext.
    gezeigt = zuletzt_gezeigt(ctx.history)
    messages.append({"role": "user",
                     "content": f"{gezeigt}\n\n{ctx.req.message}" if gezeigt else ctx.req.message})

    # Erklärt der Gastgeber ein Schema, bekommt der Lauf seinen Ergebnis-Kanal
    # (2026-08-14, seit J1 ``liefere_ergebnis`` statt ``submit_result``). Nur
    # dann: der Zug kostet 2–9 s und sagt sonst, was die Prosa schon sagt. Und
    # nur dann steht der Satz darüber im Systemprompt — eine Anweisung auf ein
    # Werkzeug, das nicht im Katalog ist, wäre der Widerspruch, den der
    # Modulkopf beschreibt.
    _schema = ctx.req.environment.result_schema or None
    if _schema:
        messages[0]["content"] += (
            "\n\nDer Gastgeber erwartet ein maschinenlesbares Ergebnis. Rufe "
            "``liefere_ergebnis`` genau einmal, sobald du es hast — und nur "
            "dann. Es beendet den Lauf NICHT: schreibe danach deine Antwort "
            "fuer die Person im Chat, und zwar vollstaendig, denn sie sieht das "
            "Ergebnis nicht. Ist die Nachricht bloss Gespraech (Begruessung, "
            "Rueckfrage), antworte gewoehnlich und rufe es NICHT."
        )

    # P: die interne Wissensdatenbank. Bis 2026-08-18 hatte die Agent-Schleife
    # sie GAR NICHT — ``query_knowledge`` wird allein im Muster-Weg gebaut, also
    # lief hier jede Frage nach WLO, OER oder edu-sharing ins Modellgedaechtnis.
    # Ohne Vorabruf und mit allen Bereichen zugleich: siehe Modulkopf von
    # ``services/agent_knowledge``.
    _wissen_tool = wissen_werkzeug(ctx.rag_config or {})

    # Werkzeug im Katalog ⇔ Regel im Prompt — dieselbe Kopplung wie beim
    # ``result_schema`` oben. ``wissen_suchen`` ist virtuell und damit nicht
    # sperrbar: ist es hier gebaut, ist es in JEDER Runde da.
    if _wissen_tool:
        messages[0]["content"] += WISSENS_REGEL

    async def _wissen(args: dict) -> str:
        return await wissen_antwort(session, args, ctx.rag_config or {})

    all_cards: list[dict] = []
    ernten: list[list[dict]] = []
    _antwort_tool = _antwort_werkzeug(ctx)
    # Token-Streaming (Plan 2026-10-01, T22): nur mit ``respond_to_user`` im
    # Angebot — dessen Text ist das Einzige, was hinausgeht (E-S1).
    _strom = strom_fuer_agent_zug(on_token, ctx, antwort_werkzeug=_antwort_tool is not None)
    progress.start("response", "LLM response generation")
    lauf = await run_agent_loop(
        messages=messages,
        tools=build_agent_tools(
            allow_curation=_darf_schreiben,
            blocked_tools=ctx.safety.blocked_tools,
            # ``submit_result`` gehört seit J1 dem Agent-Endpunkt: es beendet
            # den Lauf, und im Chat kostete genau das die Prosa-Antwort.
            include_submit=False, include_ergebnis=bool(_schema),
            result_schema=_schema, include_dokument=True,
            # O-A: die Erlaubnis der Einbettung. Dasselbe Wort, das ueber
            # ``host_capabilities.prompt_block`` im Prompt steht — sonst
            # verspraeche das Modell, was ihm die Liste gleich nimmt.
            tool_mode=ctx.req.environment.tool_mode,
            wissen_tool=_wissen_tool,
            antwort_tool=_antwort_tool),
        # AG-6: ohne angemeldete Person gelten die engeren anonymen Deckel.
        # Die Schreibregel zuletzt: was auch immer davor die Deckel ändert,
        # ``execute`` ohne Person kommt hier nicht durch.
        limits=enforce_write_mode(fuer_diesen_zug(einstellung.agent)),
        usage_acc=ctx.usage,
        progress=progress,
        on_tool_result=lambda name, text: ernten.append(collect_cards(all_cards, name, text)),
        wissen=_wissen if _wissen_tool else None,
        # Paket 2: eine nicht eingelöste Schreib-Vorschau nimmt die Person im
        # nächsten Zug an — Box und Merkposten wie im Muster-Weg. Nur mit
        # Schreibrecht (Nutzer-Entscheid 2026-08-12, Paket 7 S4): sonst liefe das
        # „ja“ unter dem Dienstkonto der Anlage (Audit 2026-09-29, B-H3).
        on_offene_abnahme=(
            (lambda merkposten, vorschau: merke_abnahme(
                ctx.session_state, merkposten, vorschau))
            if _darf_schreiben else None),
        on_token=_strom,
        start=beginn,
    )
    if _strom is not None:
        _strom.schliessen()  # den zurückgehaltenen Rest senden
    logger.info("Agent-Modus: %d Schritte, Ende=%s, %d Werkzeuge, %d Karten",
                lauf.iterations, lauf.stop_reason, len(lauf.tools_called),
                len(all_cards))

    # Die zuletzt geholte Anleitung überdauert den Zug — dieselbe Notiz, die der
    # Bestandsweg seit 2026-08-16 schreibt (``tool_loop``:744). Sie trägt EINEN
    # Faden: stellt ein Skill eine Rückfrage, kommt die Antwort erst im nächsten
    # Zug, und der entschiede sonst neu. Die sichtbare Meldung unten kommt
    # dagegen aus der vollen Liste — sie soll zeigen, was DIESER Zug benutzt hat.
    if lauf.anleitungen:
        _zuletzt = lauf.anleitungen[-1]
        merke_laufende_anleitung(
            (ctx.session_state or {}).setdefault("entities", {}),
            _zuletzt.get("node_id"),
            (ctx.session_state or {}).get("turn_count"),
            titel=_zuletzt.get("titel", ""),
        )

    # Geliefert, aber nicht geantwortet (J1): ein Deckel hat die Prosa
    # verschluckt. Nur dann — ein Lauf ohne jede Lieferung hat auch nichts zu
    # erzählen, und der ehrliche Ersatzsatz ist billiger und richtiger als ein
    # weiterer Zug.
    if not lauf.text.strip() and (lauf.result is not None or lauf.dokumente):
        lauf.text = await abschluss_nachholen(lauf, messages, ctx.usage)

    # Triple-Schema T-25/27 wie im Bestandsweg: die Qualitätslogs lesen beides
    # in beiden Maschinen, sonst misst der A/B-Vergleich eine selbstgebaute Lücke.
    from boerdi.services.outcome_service import adjust_confidence, derive_state_hint
    zustand = derive_state_hint(lauf.outcomes)
    if zustand and zustand != ctx.state_id:
        logger.info("Outcome-based state hint: %s -> %s", ctx.state_id, zustand)
        ctx.state_id = zustand

    _antwort = mit_master_ansage(
        # Aus der LISTE des Laufs, nicht aus der Notiz: die Notiz führt einen
        # Faden (eine Anleitung), die Meldung zeigt den Zug (womöglich zwei).
        # Sie räumt zugleich die Zeilen weg, die das Modell selbst geschrieben
        # hat — live gemessen 2026-08-19 an „Geometrische Optik" standen drei
        # Ansagen übereinander, zwei davon Modell-Ausgabe in zwei Formaten.
        mit_ladehinweisen(
            append_answer_notes(
                antwort_oder_ersatz(lauf, sprache),
                policy=ctx.policy, safety=ctx.safety),
            lauf.anleitungen,
        ),
        ctx.master_skill_zeile,
        # Der Merker reist in ``entities`` — nicht der Zugzaehler. Der waechst
        # allein in ``turn_persist``, und die frueh endenden Zuege (Tour,
        # Kontext-Begruessung, Schreib-Abnahme) kommen dort nie an: nach einem
        # Tour-Zug stand die Ansage ein zweites Mal im Chat (live gemessen
        # 2026-08-19). Begruendung im Kopf von ``domain/skill_ansagen``.
        (ctx.session_state or {}).get("entities"),
    )
    # Das Modell hat NUR die Master-Ansage geschrieben und sonst nichts.
    # ``mit_master_ansage`` entfernt die Modell-Kopie dieser Zeile — richtig so,
    # sonst stünde sie doppelt —, und danach ist die Antwort leer. Denselben
    # Leerfall erzeugt ``mit_ladehinweisen`` mit Fach-Skill-Ansagen; der Zweig
    # fängt beide, deshalb spricht das WARNING von Ansagezeilen.
    #
    # Live gemessen 2026-08-21 (b-api-openai/gpt-5.6-luna, 3 von 12 Zügen):
    # ``AgentRun.text`` war genau die 49 Zeichen der Ansage, ``stop_reason``
    # war ``text``, kein Deckel, kein Fehler. Der Ersatzsatz oben griff deshalb
    # NICHT (er prüft ``lauf.text``, und der war nicht leer), und die Person
    # bekam eine leere Blase — der stille Ausfall, gegen den A4c-2b gebaut ist,
    # nur eine Station später. Geprüft wird darum das ERGEBNIS der Komposition
    # und nicht mehr allein die Eingabe.
    #
    # Keine Wiederholung, sondern der ehrliche Satz: derselbe Fall, dieselbe
    # Antwort wie bei jedem anderen textlosen Zug. Das WARNING macht die
    # Häufigkeit sichtbar — ohne es war der Fall im Betrieb unauffindbar.
    if not _antwort.strip():
        logger.warning(
            "Agent-Modus: Antwort bestand nur aus Ansagezeilen "
            "(%d Zeichen Lauf-Text, Ende=%s) — ehrlicher Ersatzsatz",
            len(lauf.text or ""), lauf.stop_reason)
        _antwort = bot_text(sprache, "agent.failed")
    ctx.response_text = _antwort
    ctx.wlo_cards_raw = juengste_zuerst(all_cards, ernten)
    # D2: Was das Modell als Ergebnis GELIEFERT hat. ``turn_persist`` zieht es
    # der geratenen Box vor; ist die Liste leer, bleibt der Bestandsweg.
    ctx.gelieferte_dokumente = lauf.dokumente
    # Plan 2026-09-30: Schnellantworten aus ``respond_to_user`` — die
    # Zusammenstellung nimmt sie vor dem eigenen Aufruf (und filtert sie gleich).
    if lauf.vorschlaege:
        ctx.session_state["_inline_quick_replies"] = lauf.vorschlaege
    # Ergebnis und Ende-Grund weiterreichen. Der Grund geht MIT, auch wenn kein
    # Ergebnis kam: sonst sähe ein an der Frist abgeschnittener Lauf für die
    # Gastseite aus wie einer, der nichts zu sagen hatte.
    if _schema:
        ctx.result = lauf.result if isinstance(lauf.result, dict) else None
        ctx.result_stop_reason = lauf.stop_reason
    ctx.tools_called = lauf.tools_called
    ctx.debug.outcomes = lauf.outcomes
    # AG-1: Runden, Werkzeuge samt der virtuellen, Token und Ende-Grund —
    # bis hier gingen sie nach dem Log-Satz oben verloren.
    ctx.debug.trace = spur(lauf.runden, lauf.stop_reason)
    ctx.debug.confidence = adjust_confidence(
        ctx.classification.intent_confidence, lauf.outcomes)
    return ctx
