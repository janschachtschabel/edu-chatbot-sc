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
from typing import Any

from boerdi.domain import host_capabilities, host_instruction
from boerdi.domain.answer_notes import append_answer_notes
from boerdi.domain.history_window import verlaufs_fenster
from boerdi.domain.pattern_catalog import finde_muster
from boerdi.domain.pattern_engine import PatternDef, get_patterns, phase3_modulate
from boerdi.domain.skill_ansagen import mit_master_ansage
from boerdi.domain.skill_precedence import (
    anleitungs_hinweis,
    merke_laufende_anleitung,
    mit_ladehinweisen,
)
from boerdi.graph.state import TurnContext
from boerdi.i18n import resolve_locale
from boerdi.i18n.bot_text import bot_text
from boerdi.i18n.prompt_language import language_name
from boerdi.obs.progress import NO_PROGRESS, TurnProgress
from boerdi.obs.tasks import cancel_and_drain
from boerdi.services import llm, master_skill, page_context
from boerdi.services.agent_knowledge import antwort as wissen_antwort
from boerdi.services.agent_knowledge import wissen_werkzeug
from boerdi.services.agent_loop import AgentRun, run_agent_loop
from boerdi.services.agent_prefetch import resolve_prefetch
from boerdi.services.agent_tools import VIRTUELLE_WERKZEUGE, build_agent_tools
from boerdi.services.agent_write import enforce_write_mode
from boerdi.services.card_collect import collect_cards
from boerdi.services.config_loader import load_engine
from boerdi.services.engine_choice import AGENT, HYBRID

logger = logging.getLogger(__name__)

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

_SYSTEM = (
    "Du bist Boerdi, der Assistent von WirLernenOnline (WLO). Du sprichst mit "
    "einem Menschen im Chat — kurz, freundlich und ohne Floskeln.\n\n"
    "Arbeitsweise: hole dir die Tatsachen mit den Werkzeugen, statt sie aus dem "
    "Gedaechtnis zu behaupten. Steht in einer Sammlung ein Skill zu deiner "
    "Aufgabe, halte dich daran. Nenne, worauf du dich stuetzt, und sage "
    "ausdruecklich, was du NICHT pruefen konntest.\n\n"
    "SPRACHE DER AUSGABE: {sprache}. Formatiere mit Markdown."
)

#: Die Wissens-Regel — nur wenn ``wissen_suchen`` auch im Katalog steht.
#:
#: **Warum sie noetig ist.** Der Muster-Weg holt die ``mode: always``-Bereiche
#: VOR dem ersten Modellzug und legt sie als erledigten Werkzeug-Aufruf in die
#: Kette (``tool_loop_messages``): dort ist internes Wissen keine Entscheidung,
#: sondern eine Zusage. Hier entscheidet das Modell — und traf 2026-08-19 in
#: 2 von 3 gemessenen Zuegen richtig. Der dritte beantwortete „Was ist
#: WissenLebtOnline?" aus dem Gedaechtnis.
#:
#: **Warum kein Vorabruf.** ``services/agent_knowledge`` begruendet den
#: Verzicht: diese Schleife beantwortet auch „hallo", und eine Einbettung ohne
#: WLO-Bezug zahlte fuer Wissen, das niemand braucht. Der Entscheid bleibt —
#: verschaerft wird die Regel, nicht die Mechanik. Die Formulierung nimmt die
#: Beispiel-Bauart des Muster-Wegs auf (``response_prompt_tools_text``), aber
#: kurz: dieser Block sitzt im gecachten Praefix und wird JEDE Runde gezahlt.
#:
#: **Die Abgrenzung ist Teil der Regel, nicht Beiwerk** (Durchsicht 2026-08-19).
#: Ohne sie liegt die Materialsuche gefaehrlich nah an „Fragen zu WLO" — und
#: genau dort steht der Agent heute BESSER da als der Muster-Weg: bei „Ich
#: suche Inhalte zu einem Thema" fragt er ohne einen einzigen Werkzeug-Aufruf
#: zurueck (gemessen 2026-08-19). Eine zu breit gelesene Regel machte daraus
#: eine ueberfluessige Wissenssuche und verschlechterte den einen Fall, in dem
#: die Schleife vorn liegt. Deshalb nennt der Text beide Ausnahmen beim Namen.
_WISSENS_REGEL = (
    "\n\nWISSEN VOR GEDAECHTNIS: Fragen zu WLO und seinem Umfeld — was die "
    "Plattform oder ein Projekt ist, wie die Webseite aufgebaut ist, OER, "
    "Metadaten, Lizenzen, Qualitaet, Prozesse, Mitmachen — beantwortest du "
    "NICHT aus dem Gedaechtnis. Rufe zuerst ``wissen_suchen``, auch wenn du "
    "die Antwort zu kennen meinst. Findet es nichts, sage das.\n"
    "Nicht gemeint ist die Suche nach Lernmaterial zu einem Unterrichtsthema — "
    "die geht in den Bestand, nicht in die Wissensdatenbank. Und eine "
    "Rueckfrage, weil dir eine Angabe fehlt, braucht ueberhaupt kein Werkzeug."
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
    if lauf.dokumente or lauf.result is not None:
        # Ein Lauf, der ein Ergebnis GELIEFERT hat, ist nicht gescheitert — ihm
        # fehlt nur der Begleitsatz. Der Deckel-Satz („zu umfangreich, stell sie
        # kleiner geschnitten noch einmal") stünde direkt über einer
        # vollständigen Stundenplanung und würde von ihr widerlegt.
        #
        # ``lauf.result`` zählt seit J1 mit: seit ``liefere_ergebnis`` den Lauf
        # nicht mehr beendet, kann ein Zug das Ergebnis abliefern und DANACH an
        # der Frist enden. Ohne diese Zeile bekäme der Gastgeber ein tadelloses
        # JSON und die Person daneben die Auskunft, es sei nichts geworden.
        logger.info("Agent-Modus: Lieferung ohne Begleitsatz (%d Box(en), "
                    "Ergebnis=%s, Ende=%s)",
                    len(lauf.dokumente), lauf.result is not None, lauf.stop_reason)
        return bot_text(sprache, "agent.delivered")
    schluessel = "agent.incomplete" if lauf.stop_reason in _GEDECKELT else "agent.failed"
    logger.info("Agent-Modus: Lauf ohne Text (Ende=%s) — Ersatzsatz %s",
                lauf.stop_reason, schluessel)
    return bot_text(sprache, schluessel)


_ABSCHLUSS_BITTE = (
    "Schreibe jetzt deine Antwort fuer die Person im Chat — ohne weitere "
    "Werkzeug-Aufrufe. Sie hat weder dein Ergebnis noch deine Zwischenschritte "
    "gesehen: sag ihr vollstaendig, was du herausgefunden hast."
)


async def _abschluss_nachholen(
    lauf: AgentRun, messages: list[dict], usage_acc: dict | None,
) -> str:
    """EIN Abschluss-Aufruf, wenn ein Deckel die Antwort verschluckt hat.

    Seit J1 ist die Prosa ein eigener Zug — und damit deckelbar. Live gemessen
    am selben Tag (Hybrid, Sammlung „Optik"): das Ergebnis kam vollstaendig, der
    Lauf riss danach das Token-Budget, und im Chat standen 22 Zeichen. Vorher
    konnte das nicht passieren, weil ``submit_result`` den Text mittrug.

    Die Deckel sind gegen weglaufende **Arbeit** gebaut, nicht gegen die
    Antwort. Genau diese Unterscheidung trifft der Bestandsweg seit P16
    (``tool_loop_fallback``), und dies ist dieselbe Naht: ein Aufruf, keine
    Werkzeuge, eigene Phase in der Kostenschau — ihr Auftauchen meldet den
    gerissenen Deckel und soll in der normalen Antwort nicht untergehen.

    Scheitert er, gibt es ``""`` zurueck: dann greift der ehrliche Ersatzsatz.
    """
    try:
        antwort = await llm.chat_completion(
            messages=[*messages, {"role": "user", "content": _ABSCHLUSS_BITTE}],
            temperature=0.4, usage_acc=usage_acc, phase="fallback_summary")
        text = (antwort.choices[0].message.content or "").strip()
    except Exception as e:                       # pragma: no cover - Transportfehler
        logger.warning("Agent-Modus: Abschluss-Aufruf fehlgeschlagen — %s", e)
        return ""
    logger.info("Agent-Modus: Antwort nach Deckel %s nachgeholt (%d Zeichen)",
                lauf.stop_reason, len(text))
    return text


def _muster_werkzeuge(ctx: TurnContext, muster: PatternDef) -> list[str]:
    """Die Werkzeugliste eines Musters — durch die **echte** ``phase3_modulate``.

    Nicht ``muster.tools`` roh: die Modulation hängt die Helfer an, ohne die eine
    Suche halb ist (``lookup_wlo_vocabulary``, ``get_node_details``), und sie tut
    es nach derselben Regel wie im Bestandsweg. Eine eigene Fassung liefe beim
    nächsten Studio-Feld auseinander — und der A/B-Vergleich maße dann einen
    Unterschied, den er selbst gebaut hat.
    """
    ss = ctx.session_state or {}
    output = phase3_modulate(
        muster,
        list(ctx.classification.signals or []),
        ctx.env.get("device", "desktop"),
        ss.get("entities") or {},
        ss.get("persona_id") or "P-AND",
    )
    return list(output.get("tools") or [])


def _werkzeuge_des_musters(
    alle: list[dict], erlaubt: list[str]
) -> list[dict]:
    """``alle`` auf die Werkzeuge des Musters eingeschränkt.

    Die virtuellen bleiben immer drin (siehe :data:`VIRTUELLE_WERKZEUGE`). Eine
    **leere** Erlaubnisliste heißt „dieses Muster arbeitet ohne Werkzeuge" (M04,
    M11, M13, M14) — dann bleiben nur die virtuellen, und das Modell kann
    zurückwechseln oder antworten, aber nicht suchen. Genau die Zusage, die
    ``sources: [llm]`` im Bestandsweg gibt.
    """
    gewuenscht = set(erlaubt)
    return [t for t in alle
            if t["function"]["name"] in VIRTUELLE_WERKZEUGE
            or t["function"]["name"] in gewuenscht]


async def respond_agent(
    ctx: TurnContext, progress: TurnProgress = NO_PROGRESS, engine: str = AGENT,
    session: Any = None,
) -> TurnContext:
    """Beantworte den Zug mit der Agent-Schleife. Mutiert ``ctx`` und gibt ihn
    zurück — gleiche Ausgangsfelder wie ``respond``, damit ``assemble`` und
    ``persist`` unverändert weiterlaufen."""
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
    messages: list[dict] = [
        {"role": "system", "content": _SYSTEM.format(sprache=language_name(sprache))},
    ]
    # N3: die redaktionelle Gesamtanleitung — GROSS und zwischen zwei Zuegen
    # unveraendert, deshalb so weit vorn wie moeglich: Anbieter mit
    # Praefix-Caching berechnen sie dann nur einmal. Eine Abweichung von
    # „ganz am Anfang" ist gewollt: der eigene Rollen-Block bleibt davor. Er
    # ist ebenso stabil, kostet also keinen Cache-Treffer, und die eigenen
    # Regeln gehoeren vor fremden Text. Alles Wechselnde (Seite, Rahmen,
    # Verlauf) folgt dahinter — sonst zerfiele das Praefix.
    anleitung = await master_skill.prompt_block(ctx.req.environment.master_skill)
    if anleitung:
        messages.append({"role": "system", "content": anleitung})
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
    seiten_block = page_context.prompt_block(ctx.session_state, seite)
    if seiten_block:
        messages.append({"role": "system", "content": seiten_block})
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
    messages.extend(_fenster)
    # Anleitungen vor Gegenstand — dieselbe Reihenfolge wie im Agent-Endpunkt.
    await resolve_prefetch(messages, _vorab_aufrufe(seite), progress=progress)
    messages.append({"role": "user", "content": ctx.req.message})

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

    # H6: Der Musterkatalog liegt nur im Hybrid in der Werkzeugliste — und auch
    # dort NICHT, wenn das Sicherheits-Gate ein Muster erzwungen hat. Über M01
    # und M02 entscheidet nicht das Modell; ein Katalog daneben machte die
    # Krisen-Behandlung zu einem Angebot.
    _katalog: list[PatternDef] | None = None
    if engine == HYBRID:
        if ctx.safety.enforced_pattern:
            logger.info(
                "Hybrid: %s ist vom Sicherheits-Gate erzwungen — der "
                "Musterkatalog bleibt aus dem Werkzeugsatz.",
                ctx.safety.enforced_pattern)
        else:
            _katalog = get_patterns()

    # P: die interne Wissensdatenbank. Bis 2026-08-18 hatte die Agent-Schleife
    # sie GAR NICHT — ``query_knowledge`` wird allein im Muster-Weg gebaut, also
    # lief hier jede Frage nach WLO, OER oder edu-sharing ins Modellgedaechtnis.
    # Ohne Vorabruf und mit allen Bereichen zugleich: siehe Modulkopf von
    # ``services/agent_knowledge``.
    _wissen_tool = wissen_werkzeug(ctx.rag_config or {})

    # Werkzeug im Katalog ⇔ Regel im Prompt — dieselbe Kopplung wie beim
    # ``result_schema`` oben. ``wissen_suchen`` steht in ``VIRTUELLE_WERKZEUGE``
    # und ist damit weder sperrbar noch von der Muster-Einschraenkung des
    # Hybrids betroffen: ist es hier gebaut, ist es in JEDER Runde da.
    if _wissen_tool:
        messages[0]["content"] += _WISSENS_REGEL

    async def _wissen(args: dict) -> str:
        return await wissen_antwort(session, args, ctx.rag_config or {})

    def _voller_satz(*, kurz: bool = False) -> list[dict]:
        """Der Werkzeugsatz. ``kurz`` schaltet den Musterkatalog auf eine Zeile
        je Muster (H8-2) — richtig für jede Liste, die NACH einer Wahl entsteht:
        dort ist nur noch das Wechseln offen, und die Einsatzregeln kosteten
        gemessen 25 251 der 31 742 Zeichen dieses Satzes."""
        return build_agent_tools(
            blocked_tools=ctx.safety.blocked_tools,
            # ``submit_result`` gehört seit J1 dem Agent-Endpunkt: es beendet
            # den Lauf, und im Chat kostete genau das die Prosa-Antwort.
            include_submit=False, include_ergebnis=bool(_schema),
            result_schema=_schema,
            muster_katalog=_katalog, include_dokument=True,
            katalog_kurz=kurz,
            # O-A: die Erlaubnis der Einbettung. Dasselbe Wort, das ueber
            # ``host_capabilities.prompt_block`` im Prompt steht — sonst
            # verspraeche das Modell, was ihm die Liste gleich nimmt.
            tool_mode=ctx.req.environment.tool_mode,
            wissen_tool=_wissen_tool)

    all_cards: list[dict] = []
    progress.start("response", "LLM response generation")
    lauf = await run_agent_loop(
        messages=messages,
        tools=_voller_satz(),
        limits=enforce_write_mode(load_engine().agent),
        usage_acc=ctx.usage,
        progress=progress,
        on_tool_result=lambda name, text: collect_cards(all_cards, name, text),
        muster_katalog=_katalog,
        werkzeuge_fuer=(
            lambda muster: _werkzeuge_des_musters(
                _voller_satz(kurz=True), _muster_werkzeuge(ctx, muster))
        ) if _katalog else None,
        wissen=_wissen if _wissen_tool else None,
    )
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
        lauf.text = await _abschluss_nachholen(lauf, messages, ctx.usage)

    # Triple-Schema T-25/27 wie im Bestandsweg: die Qualitätslogs lesen beides
    # in beiden Maschinen, sonst misst der A/B-Vergleich eine selbstgebaute Lücke.
    from boerdi.services.outcome_service import adjust_confidence, derive_state_hint
    zustand = derive_state_hint(lauf.outcomes)
    if zustand and zustand != ctx.state_id:
        logger.info("Outcome-based state hint: %s -> %s", ctx.state_id, zustand)
        ctx.state_id = zustand

    ctx.response_text = mit_master_ansage(
        # Aus der LISTE des Laufs, nicht aus der Notiz: die Notiz führt einen
        # Faden (eine Anleitung), die Meldung zeigt den Zug (womöglich zwei).
        # Sie räumt zugleich die Zeilen weg, die das Modell selbst geschrieben
        # hat — live gemessen 2026-08-19 an „Geometrische Optik" standen drei
        # Ansagen übereinander, zwei davon Modell-Ausgabe in zwei Formaten.
        mit_ladehinweisen(
            append_answer_notes(
                _antwort_oder_ersatz(lauf, sprache),
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
    ctx.wlo_cards_raw = all_cards
    # D2: Was das Modell als Ergebnis GELIEFERT hat. ``turn_persist`` zieht es
    # der geratenen Box vor; ist die Liste leer, bleibt der Bestandsweg.
    ctx.gelieferte_dokumente = lauf.dokumente
    # Ergebnis und Ende-Grund weiterreichen. Der Grund geht MIT, auch wenn kein
    # Ergebnis kam: sonst sähe ein an der Frist abgeschnittener Lauf für die
    # Gastseite aus wie einer, der nichts zu sagen hatte.
    if _schema:
        ctx.result = lauf.result if isinstance(lauf.result, dict) else None
        ctx.result_stop_reason = lauf.stop_reason
    # H6/H7: Was das Modell WIRKLICH benutzt hat, überschreibt den synthetischen
    # Anfangszustand. ``effective_pattern_id`` trägt genau diese Bedeutung schon
    # („engine=X → executed=Y", ``route_tail.reconcile_effective_pattern``), und
    # daran hängen drei Dinge, die sonst still ausfielen: die Inline-Kachel für
    # M09/M10/M11 (``turn_persist``), ``_last_pattern`` für die Nachbearbeitung
    # im Folgezug, und die Muster-Spalte der Qualitätslogs.
    if lauf.muster_id and (_gewaehlt := finde_muster(lauf.muster_id, _katalog or [])):
        logger.info("Hybrid: ausgefuehrtes Muster %s (%s) statt %s",
                    _gewaehlt.id, _gewaehlt.label, ctx.effective_pattern_id)
        ctx.effective_pattern_id = _gewaehlt.id
        ctx.effective_pattern_label = _gewaehlt.label
    ctx.tools_called = lauf.tools_called
    ctx.debug.outcomes = lauf.outcomes
    ctx.debug.confidence = adjust_confidence(
        ctx.classification.intent_confidence, lauf.outcomes)
    return ctx
