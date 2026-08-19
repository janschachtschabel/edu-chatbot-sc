"""A4c-2b — der Antwort-Knoten im Agent-Modus (``graph/nodes/respond_agent.py``).

Im Agent-Modus antwortet nicht ``generate_response``, sondern die Agent-Schleife:
kein Muster, kein gebundener Werkzeugsatz, keine spekulative Vorab-Suche. Diese
Datei hält fest, was der Modus dabei **erbt** — und das ist der eigentliche
Gegenstand der Scheibe, denn jedes dieser vier Stücke ginge sonst *still*
verloren:

* die **Werkzeug-Sperre** aus Safety/Policy. Der Bestandsweg filtert sie in
  ``route`` aus ``pattern_output['tools']``; im Agent-Modus ist dieser Schlüssel
  leer (gemessen), die Sperre hätte also keinen Empfänger mehr — der Agent bekäme
  den vollen Katalog samt gesperrtem Werkzeug.
* die **Schreib-Regel**: ``execute`` verlangt eine angemeldete Person. Diese
  Prüfung saß bis A4c-2b allein im Agent-Endpunkt; eine im Studio auf ``execute``
  gestellte Anlage schriebe im Chat sonst ohne Person.
* die **Hinweise an der Antwort** (Policy-Disclaimer, Medium-Risk-Notiz).
* der **spekulative Vorabruf** aus ``merge``: er wird hier nie verbraucht und muss
  deshalb abgebrochen werden, sonst laufen die Tasks unbeobachtet weiter.

Randkonvention wie bei den Nachbarknoten: Nachbarn werden AN DIESEM Modul
gepatcht. ``build_agent_tools``, ``collect_cards`` und ``append_answer_notes``
laufen dagegen **echt** — bei ihnen ist das Ergebnis die Zusicherung, nicht der
Aufruf. Nur so belegt der Sperr-Test, dass das Werkzeug wirklich fehlt, statt
dass ein Argument gereicht wurde.
"""

from __future__ import annotations

import asyncio
import json
import logging

import pytest

from boerdi.api.schemas import (
    ChatRequest,
    ClassificationResult,
    Environment,
    PolicyDecision,
    SafetyDecision,
)
from boerdi.domain.config_models.engine import AgentLimits, EngineArea
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import respond as respond_mod
from boerdi.graph.nodes import respond_agent as agent_mod
from boerdi.graph.nodes.respond import respond
from boerdi.graph.nodes.respond_agent import respond_agent
from boerdi.services import agent_write
from boerdi.services.agent_loop import AgentRun

_KARTE = json.dumps({"results": [
    {"nodeId": "n-1", "title": "Photosynthese erklaert", "wwwUrl": "https://x/1"},
]})


def _ctx(*, message="frage", history=None, safety=None, policy=None,
         page_context=None, page_meta=None):
    """``page_context`` = was das Widget mitschickt, ``page_meta`` = was der
    ``page_context_enrich``-Knoten daraus aufgelöst und zwischengelegt hat."""
    ctx = state_mod.TurnContext(req=ChatRequest(
        session_id="s1", message=message,
        environment=Environment(page_context=page_context or {}),
    ))
    ctx.history = history if history is not None else []
    ctx.safety = safety or SafetyDecision(risk_level="low")
    ctx.policy = policy or PolicyDecision()
    ctx.classification = ClassificationResult()
    entities = {"_page_metadata": page_meta} if page_meta else {}
    ctx.session_state = {"persona_id": "P-AND", "entities": entities}
    return ctx


def _patch(monkeypatch, seen, *, lauf=None, limits=None, personal=False,
           ruft_werkzeug=None):
    """Die Schleife und die Konfiguration abfangen; ``seen`` ist die Beweislage.

    ``ruft_werkzeug`` lässt die Attrappe die Ernte-Naht bedienen — so läuft
    ``collect_cards`` echt über einen echten MCP-Umschlag.
    """

    # H6: ``muster_katalog``/``werkzeuge_fuer`` gehören zur ECHTEN Signatur —
    # dieselbe A4b-Regel wie unten bei ``load_engine``. Eine Attrappe, die sie
    # nicht kennt, verdeckt genau den Zweig, den der Hybrid neu betritt.
    async def _loop(*, messages, tools, limits, usage_acc=None, progress=None,
                    clock=None, on_tool_result=None, muster_katalog=None,
                    werkzeuge_fuer=None, wissen=None):
        seen["run_agent_loop"] = {
            "messages": messages, "tools": tools, "limits": limits,
            "usage_acc": usage_acc, "progress": progress,
            "on_tool_result": on_tool_result,
            "muster_katalog": muster_katalog, "werkzeuge_fuer": werkzeuge_fuer,
            "wissen": wissen,
        }
        if ruft_werkzeug is not None and on_tool_result is not None:
            on_tool_result(*ruft_werkzeug)
        return lauf if lauf is not None else AgentRun(
            text="Antwort des Agenten", stop_reason="text", iterations=1,
            tools_called=["search_wlo_all"],
        )

    # ``load_engine`` ist SYNCHRON (A4b-Fund: eine Attrappe wird nach der echten
    # Signatur gebaut, nicht nach dem eigenen Aufruf).
    def _engine():
        return EngineArea(mode="agent", agent=limits or AgentLimits())

    # Die Gesamtanleitung bleibt AUS, solange ein Test sie nicht ausdruecklich
    # will. Befund 2026-08-19: diese Tests zaehlen Nachrichten in der Kette und
    # hingen damit still an ``MASTER_SKILL_ENABLED`` aus der lokalen ``.env``.
    # Wurde der Schalter dort gesetzt, kam ein System-Block dazu und drei Tests
    # wurden rot — ohne dass sich am Produkt etwas geaendert haette. Ein Test
    # muss seine Eingaben besitzen.
    async def _keine_gesamtanleitung(_ueberschreibung=None):
        return None

    monkeypatch.setattr(agent_mod.master_skill, "prompt_block", _keine_gesamtanleitung)
    monkeypatch.setattr(agent_mod, "run_agent_loop", _loop)
    monkeypatch.setattr(agent_mod, "load_engine", _engine)
    monkeypatch.setattr(agent_write, "has_personal_auth", lambda: personal)


def _namen(tools):
    return [t["function"]["name"] for t in tools]


# ── Der Kern: die Schleife antwortet ───────────────────────────────
@pytest.mark.anyio
async def test_die_schleife_antwortet_statt_generate_response(monkeypatch):
    seen: dict = {}
    _patch(monkeypatch, seen)
    ctx = _ctx()
    out = await respond_agent(ctx)
    assert out is ctx
    assert ctx.response_text == "Antwort des Agenten"
    assert ctx.tools_called == ["search_wlo_all"]


@pytest.mark.anyio
async def test_verlauf_und_nachricht_stehen_in_der_kette(monkeypatch):
    """Systemprompt, die letzten zehn Züge, dann die Nachricht — dieselbe
    Reihenfolge wie im Bestandsweg (``tool_loop._assemble_messages``)."""
    seen: dict = {}
    _patch(monkeypatch, seen)
    verlauf = [{"role": "user", "content": f"z{i}"} for i in range(12)]
    await respond_agent(_ctx(message="Was ist OER?", history=verlauf))
    messages = seen["run_agent_loop"]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1]["content"] == "z2"          # nur die letzten zehn
    assert len(messages) == 1 + 10 + 1
    assert messages[-1] == {"role": "user", "content": "Was ist OER?"}


@pytest.mark.anyio
async def test_die_karten_kommen_ueber_die_ernte_naht(monkeypatch):
    """A4c-2a hat die Naht gebaut; hier wird sie bedient. ``collect_cards`` läuft
    echt — die Zusicherung ist die geerntete Karte, nicht der Rückruf."""
    seen: dict = {}
    _patch(monkeypatch, seen, ruft_werkzeug=("search_wlo_content", _KARTE))
    ctx = await respond_agent(_ctx())
    assert [c["node_id"] for c in ctx.wlo_cards_raw] == ["n-1"]
    assert ctx.wlo_cards_raw[0]["title"] == "Photosynthese erklaert"


# ── Was der Agent-Modus erbt ───────────────────────────────────────
@pytest.mark.anyio
async def test_gesperrte_werkzeuge_erreichen_die_schleife_nicht(monkeypatch):
    """Der Bestandsweg streicht die Sperre aus ``pattern_output['tools']`` — im
    Agent-Modus ist der Schlüssel leer, also braucht die Sperre hier ihren
    eigenen Empfänger. ``build_agent_tools`` läuft echt."""
    seen: dict = {}
    _patch(monkeypatch, seen)
    safety = SafetyDecision(risk_level="low",
                            blocked_tools=["search_wlo_content", "get_url_text"])
    await respond_agent(_ctx(safety=safety))
    namen = _namen(seen["run_agent_loop"]["tools"])
    assert "search_wlo_content" not in namen
    assert "get_url_text" not in namen
    assert "search_wlo_all" in namen          # der Rest des Katalogs bleibt


@pytest.mark.anyio
async def test_im_chat_gibt_es_kein_abschluss_werkzeug(monkeypatch):
    """``submit_result`` trägt das maschinenlesbare Ergebnis — im Chat liest das
    niemand, und seine Beschreibung verlangt einen zusätzlichen Modellzug (2–9 s
    gemessen), nur um zu sagen, was die Prosa-Antwort schon sagt. Der Lauf endet
    hier über ``stop_reason='text'``; deshalb schweigt auch der Systemprompt
    dazu — zwei einander widersprechende Anweisungen wären schlechter als keine.
    """
    seen: dict = {}
    _patch(monkeypatch, seen)
    await respond_agent(_ctx())
    aufruf = seen["run_agent_loop"]
    assert "submit_result" not in _namen(aufruf["tools"])
    assert "submit_result" not in aufruf["messages"][0]["content"]


@pytest.mark.anyio
async def test_execute_ohne_angemeldete_person_faellt_auf_propose(monkeypatch):
    """Dieselbe Regel wie im Agent-Endpunkt (A3a): geprüft wird das ERGEBNIS,
    nicht die Übersteuerung — ein redaktionell gesetztes ``execute`` kommt sonst
    ungeprüft durch."""
    seen: dict = {}
    _patch(monkeypatch, seen, limits=AgentLimits(write_mode="execute"),
           personal=False)
    await respond_agent(_ctx())
    assert seen["run_agent_loop"]["limits"].write_mode == "propose"


@pytest.mark.anyio
async def test_execute_mit_angemeldeter_person_bleibt_execute(monkeypatch):
    seen: dict = {}
    _patch(monkeypatch, seen, limits=AgentLimits(write_mode="execute"),
           personal=True)
    await respond_agent(_ctx())
    assert seen["run_agent_loop"]["limits"].write_mode == "execute"


@pytest.mark.anyio
async def test_die_hinweise_haengen_auch_an_der_agent_antwort(monkeypatch):
    """``assess_policy`` und das Sicherheits-Gate laufen im Agent-Modus
    unverändert — ihre Ergebnisse müssen auch dort an einer Antwort ankommen.
    ``append_answer_notes`` läuft echt."""
    seen: dict = {}
    _patch(monkeypatch, seen)
    ctx = await respond_agent(_ctx(
        policy=PolicyDecision(required_disclaimers=["Keine Rechtsberatung."]),
        safety=SafetyDecision(risk_level="medium", legal_flags=["datenschutz"]),
    ))
    assert ctx.response_text.startswith("Antwort des Agenten")
    assert "_Keine Rechtsberatung._" in ctx.response_text
    assert "datenschutzbezogene" in ctx.response_text


@pytest.mark.anyio
async def test_der_spekulative_vorabruf_wird_abgebrochen(monkeypatch):
    """``merge`` startet ihn für jeden Zug; der Agent sucht sich sein Werkzeug
    selbst und verbraucht ihn nie. Unabgebrochen liefe er unbeobachtet weiter."""
    seen: dict = {}
    _patch(monkeypatch, seen)

    async def _schlaeft():
        await asyncio.sleep(30)
        return "zu spaet"

    haupt = asyncio.create_task(_schlaeft())
    extra = asyncio.create_task(_schlaeft())
    ctx = _ctx()
    ctx.spec_task = haupt
    ctx.spec_tool_name = "search_wlo_all"
    ctx.extra_spec_tasks = [("search_wlo_topic_pages", extra)]
    await respond_agent(ctx)
    assert haupt.cancelled() and extra.cancelled()
    assert ctx.extra_spec_tasks == []


@pytest.mark.anyio
async def test_die_werkzeug_ergebnisse_werden_zu_outcomes_und_zustand(monkeypatch):
    """Die Qualitätslogs (``persist``) lesen ``debug.outcomes``/``confidence`` in
    beiden Maschinen — sonst misst der A/B-Vergleich eine Lücke, die er selbst
    gebaut hat."""
    from boerdi.services.outcome_service import ToolOutcome
    seen: dict = {}
    ergebnis = ToolOutcome(tool="search_wlo_all", status="empty", detail="")
    _patch(monkeypatch, seen, lauf=AgentRun(
        text="nichts gefunden", stop_reason="text", iterations=2,
        tools_called=["search_wlo_all"], outcomes=[ergebnis]))
    ctx = await respond_agent(_ctx())
    assert ctx.debug.outcomes == [ergebnis]
    assert ctx.debug.confidence is not None


@pytest.mark.parametrize(
    "grund", ["deadline", "token_budget", "max_iterations", "no_progress", "error"])
@pytest.mark.anyio
async def test_ein_abgebrochener_lauf_sagt_es_statt_stumm_zu_bleiben(
        monkeypatch, grund):
    """Nur ``text`` und ``submit`` setzen ``AgentRun.text``. Bei allen fünf
    übrigen Enden bleibt er LEER — der Nutzer bekäme eine leere Antwort, und das
    ist der schlechtere von beiden Ausfällen. Der Bestandsweg degradiert an
    derselben Stelle freundlich (``respond``, Fehler von ``generate_response``).
    """
    seen: dict = {}
    _patch(monkeypatch, seen, lauf=AgentRun(
        text="", stop_reason=grund, iterations=12, tools_called=[]))
    ctx = await respond_agent(_ctx())
    assert ctx.response_text.strip()
    assert "Boerdi" not in ctx.response_text     # kein Rohtext, kein Prompt-Rest


@pytest.mark.anyio
async def test_eine_leere_antwort_zaehlt_wie_ein_abbruch(monkeypatch):
    """Auch ``stop_reason='text'`` kann leer sein — das Modell antwortet mit
    leerem Inhalt. Die Regel hängt deshalb am Text, nicht am Grund."""
    seen: dict = {}
    _patch(monkeypatch, seen, lauf=AgentRun(
        text="   ", stop_reason="text", iterations=1, tools_called=[]))
    ctx = await respond_agent(_ctx())
    assert ctx.response_text.strip()


@pytest.mark.parametrize("grund", ["deadline", "token_budget", "no_progress"])
@pytest.mark.anyio
async def test_eine_gelieferte_box_bekommt_keinen_abbruch_satz(monkeypatch, grund):
    """Ein Lauf, der ein Ergebnis GELIEFERT hat, ist nicht gescheitert — ihm
    fehlt nur der Begleitsatz.

    Der Deckel-Satz („die Anfrage war zu umfangreich, stell sie kleiner
    geschnitten noch einmal") stünde direkt über einer vollständigen
    Stundenplanung und würde von ihr widerlegt.
    """
    seen: dict = {}
    _patch(monkeypatch, seen, lauf=AgentRun(
        text="", stop_reason=grund, iterations=12, tools_called=[],
        dokumente=[{"kind": "stundenplanung", "title": "T", "content": "C",
                    "meta": {"source": "tool"}}]))
    ctx = await respond_agent(_ctx())
    assert ctx.response_text.strip()
    assert "umfangreich" not in ctx.response_text
    assert "noch einmal" not in ctx.response_text


# ── Die Weiche in ``respond`` ──────────────────────────────────────
@pytest.mark.anyio
async def test_respond_reicht_im_agent_modus_frueh_weiter(monkeypatch):
    """Der Rumpf von ``respond`` bleibt unangetastet — er darf im Agent-Modus
    gar nicht erst anlaufen."""
    seen: dict = {}

    async def _agent(ctx, progress=None, engine="agent", session=None):
        seen["respond_agent"] = {"progress": progress, "engine": engine,
                                 "session": session}
        ctx.response_text = "vom Agenten"
        return ctx

    def _generate(*a, **k):                      # pragma: no cover — darf nie laufen
        seen["generate_response"] = True
        raise AssertionError("generate_response im Agent-Modus gerufen")

    monkeypatch.setattr(respond_mod, "respond_agent", _agent)
    monkeypatch.setattr(respond_mod, "generate_response", _generate)
    _sitzung = object()
    ctx = await respond(_ctx(), session=_sitzung, engine="agent")
    # P: die Wissensdatenbank braucht sie — ohne diese Naht liefe der
    # Agent-Modus wieder ohne internes Wissen, und zwar still.
    assert seen["respond_agent"]["session"] is _sitzung
    assert "generate_response" not in seen
    assert ctx.response_text == "vom Agenten"


@pytest.mark.anyio
async def test_gegenrichtung_ohne_angabe_laeuft_der_bestandsweg(monkeypatch):
    """Die Zusage des Nutzers als Wächter: ohne ``engine`` wird der Agent-Knoten
    nie betreten."""
    seen: dict = {}

    async def _agent(ctx, progress=None):        # pragma: no cover — darf nie laufen
        seen["respond_agent"] = True
        return ctx

    async def _generate(*a, **k):
        seen["generate_response"] = True
        return ("Bestandsantwort", [], ["search_wlo_all"], [])

    monkeypatch.setattr(respond_mod, "respond_agent", _agent)
    monkeypatch.setattr(respond_mod, "generate_response", _generate)
    ctx = await respond(_ctx(), session=object())
    assert "respond_agent" not in seen
    assert seen["generate_response"] is True
    assert ctx.response_text == "Bestandsantwort"


@pytest.mark.anyio
async def test_ein_schema_ohne_agent_maschine_wird_angesagt(monkeypatch, caplog):
    """Ein ``result_schema`` wirkt NUR in der Agent-Schleife — die Vorgabe der
    Anlage ist aber ``pattern``. Wer das Attribut setzt und die Maschine
    vergisst, bekäme sonst stumm nie ein Ergebnis und wartete auf ein Ereignis,
    das nie kommt.

    Eine Warnzeile und kein Fehler: der Zug selbst ist in Ordnung, nur die
    Erwartung des Gastgebers nicht. Ihn abzuweisen hieße, eine gültige Frage
    wegen einer wirkungslosen Beifügung zu verlieren.
    """
    async def _generate(*a, **k):
        return ("Bestandsantwort", [], [], [])

    monkeypatch.setattr(respond_mod, "generate_response", _generate)
    ctx = _ctx()
    ctx.req.environment.result_schema = {"type": "object"}
    with caplog.at_level(logging.WARNING, logger=respond_mod.__name__):
        await respond(ctx, session=object())
    assert any("result_schema" in r.message for r in caplog.records)


@pytest.mark.anyio
async def test_ohne_schema_bleibt_der_bestandsweg_stumm(monkeypatch, caplog):
    """Die Gegenprobe: der Normalfall darf nicht bei jedem Zug warnen."""
    async def _generate(*a, **k):
        return ("Bestandsantwort", [], [], [])

    monkeypatch.setattr(respond_mod, "generate_response", _generate)
    with caplog.at_level(logging.WARNING, logger=respond_mod.__name__):
        await respond(_ctx(), session=object())
    assert not [r for r in caplog.records if "result_schema" in r.message]


# ── P4: der Seitenkontext, den der Agent bisher nicht sah ──────────
# Befund B-2 (live gemessen 2026-08-13): auf einer Sammlungsseite fragte der
# Agent „welche Sammlung meinst du?" — die ID stand in ``page_context``. Der
# Bestandsweg reicht den Block über ``response_prompt_builder`` ein; der
# Agent-Modus baut seine Kette selbst und ließ ihn schlicht weg.

_OPTIK_ID = "f35c17d1-a29e-4b26-9d22-802682fad43d"
_SAMMLUNG = {"page_kind": "collection", "collection_id": _OPTIK_ID}
_AUFGELOEST = {"title": "Geometrische Optik", "node_id": _OPTIK_ID}


class _VorabFake:
    """``outcome_service.call_with_outcome`` — hält fest, was vorab lief."""

    def __init__(self, result_map=None, raises=False):
        self.calls: list[tuple[str, dict]] = []
        self._map = result_map or {}
        self._raises = raises

    async def __call__(self, tool_name, tool_args):
        from boerdi.api.schemas import ToolOutcome
        self.calls.append((tool_name, dict(tool_args)))
        if self._raises:
            raise RuntimeError("MCP weg")
        return self._map.get(tool_name, f"result:{tool_name}"), ToolOutcome(
            tool=tool_name, status="success", item_count=1)


def _vorab(monkeypatch, **kw):
    from boerdi.services import outcome_service
    fake = _VorabFake(**kw)
    monkeypatch.setattr(outcome_service, "call_with_outcome", fake)
    return fake


@pytest.mark.anyio
async def test_der_seitenkontext_steht_in_der_kette(monkeypatch):
    seen: dict = {}
    _patch(monkeypatch, seen)
    _vorab(monkeypatch)
    await respond_agent(_ctx(page_context=_SAMMLUNG, page_meta=_AUFGELOEST))
    systeme = [m["content"] for m in seen["run_agent_loop"]["messages"]
               if m.get("role") == "system"]
    assert any("Geometrische Optik" in s for s in systeme)


@pytest.mark.anyio
async def test_der_auftrag_der_gastanwendung_steht_in_der_kette(monkeypatch):
    """G1: ``host_instruction`` erreicht die Schleife — also ``agent`` UND
    ``hybrid``.

    Beide teilen sich diesen Knoten (``respond.py`` verzweigt über
    ``laeuft_ueber_die_schleife``), ein Test deckt hier deshalb zwei Maschinen.
    Die dritte hängt am selben Block-Bauer und wird in
    ``test_response_prompt_builder`` geprüft.
    """
    seen: dict = {}
    _patch(monkeypatch, seen)
    _vorab(monkeypatch)
    ctx = _ctx()
    ctx.req.environment.host_instruction = "Du bist in der Redaktionsumgebung."
    await respond_agent(ctx)
    systeme = [m["content"] for m in seen["run_agent_loop"]["messages"]
               if m.get("role") == "system"]
    assert any("Du bist in der Redaktionsumgebung." in s for s in systeme)
    # Ohne die Rangfolge wäre der Block eine Blankovollmacht.
    assert any("gilt die Regel" in s for s in systeme)


@pytest.mark.anyio
async def test_der_master_skill_steht_im_stabilen_praefix(monkeypatch):
    """N3: die redaktionelle Gesamtanleitung als zweiter System-Block.

    Die Position IST die Zusage: das Caching-Argument traegt nur, wenn der Block
    vor allem Wechselnden steht. Zweiter statt erster Block ist eine bewusste
    Abweichung — der eigene Rollen-Block bleibt davor (er ist ebenso stabil,
    kostet also keinen Cache-Treffer, und eigene Regeln gehoeren vor fremden
    Text). Steht davor irgendwann etwas Wechselndes, fällt dieser Test.
    """
    from boerdi.services import master_skill

    seen: dict = {}
    _patch(monkeypatch, seen)
    _vorab(monkeypatch)
    monkeypatch.setattr(master_skill, "prompt_block",
                        lambda ueberschreibung=None: _fertig("## Gesamtanleitung — Inhalt."))
    ctx = _ctx()
    ctx.req.environment.page_context = {"title": "Optik"}
    await respond_agent(ctx)
    kette = seen["run_agent_loop"]["messages"]
    assert kette[1]["role"] == "system"
    fehler = f"Position 1 ist {kette[1]['content'][:60]!r}"
    assert "Gesamtanleitung" in kette[1]["content"], fehler


async def _fertig(wert):
    return wert


@pytest.mark.anyio
async def test_ohne_master_skill_bleibt_die_kette_wie_bisher(monkeypatch):
    """Vorgabe ist AUS — dann darf kein zusaetzlicher Block auftauchen."""
    from boerdi.services import master_skill

    seen: dict = {}
    _patch(monkeypatch, seen)
    _vorab(monkeypatch)
    monkeypatch.setattr(master_skill, "prompt_block",
                        lambda ueberschreibung=None: _fertig(None))
    await respond_agent(_ctx())
    systeme = [m["content"] for m in seen["run_agent_loop"]["messages"]
               if m.get("role") == "system"]
    assert not any("Gesamtanleitung" in s for s in systeme)


@pytest.mark.anyio
async def test_bestand_und_skillkatalog_stehen_in_der_agent_kette(monkeypatch):
    """Nutzer-Vorgabe 2026-08-14: „inhaltsanzahl und Skillregistry muss man in
    beiden modi aktiv rein geben — pattern und agent loop".

    Dies ist die Agent-Seite. Die Muster-Seite hängt am selben Renderer
    (``page_context.render_for_prompt``) und hat ihren eigenen Wächter in
    ``test_response_prompt_builder``; laufen die beiden auseinander, fällt es
    dort auf und nicht erst live.
    """
    seen: dict = {}
    _patch(monkeypatch, seen)
    _vorab(monkeypatch)
    meta = {**_AUFGELOEST, "context_facts": {
        "materials": 35, "sub_collections": 4, "skills": 28,
        "skill_titles": ["Stunde planen"],
    }}
    await respond_agent(_ctx(page_context=_SAMMLUNG, page_meta=meta))
    systeme = "\n".join(m["content"] for m in seen["run_agent_loop"]["messages"]
                        if m.get("role") == "system")
    assert "35 Materialien" in systeme
    assert "28" in systeme
    assert "Stunde planen" in systeme
    assert "get_skill_registry" in systeme   # der Weg zum Volltext steht dabei


@pytest.mark.anyio
async def test_anleitungen_aus_dem_gespraech_stehen_in_der_agent_kette(monkeypatch):
    """Der Sucheinstieg hat keinen Seitenkontext — und damit bis 2026-08-16 auch
    keinen Skill-Hinweis: ``prompt_block`` liefert ohne Metadaten nichts, und die
    Notiz aus ``merke_skill_sammlung`` las nur das Routing. Der Agent wusste also
    weder von den Anleitungen noch von der ``collectionId`` für Stufe 1.

    Gegenstück auf der Muster-Seite:
    ``test_response_prompt_builder.test_anleitungen_aus_dem_gespraech_stehen_im_prompt``.
    """
    seen: dict = {}
    _patch(monkeypatch, seen)
    _vorab(monkeypatch)
    ctx = _ctx()
    ctx.session_state["entities"]["_skill_bestand"] = {
        "anzahl": 28, "titel": "Geometrische Optik", "node_id": "f35c17d1"}
    await respond_agent(ctx)
    systeme = "\n".join(m["content"] for m in seen["run_agent_loop"]["messages"]
                        if m.get("role") == "system")
    # Zeilenweise: der Seitenblock heißt ``### … dieser Sammlung`` und enthält
    # die kürzere Überschrift als Zeichenfolge.
    assert "## Freigegebene Skills" in systeme.splitlines()
    assert 'collectionId="f35c17d1"' in systeme


@pytest.mark.anyio
async def test_auf_der_sammlungsseite_bleibt_es_beim_seitenblock(monkeypatch):
    """Gegenrichtung: steht der Bestand auf der Seite, trägt ihn der Seitenblock
    — ein zweiter Hinweis daneben wären zwei Stimmen zur selben Sache."""
    seen: dict = {}
    _patch(monkeypatch, seen)
    _vorab(monkeypatch)
    meta = {**_AUFGELOEST, "context_facts": {"materials": 35, "skills": 28}}
    ctx = _ctx(page_context=_SAMMLUNG, page_meta=meta)
    ctx.session_state["entities"]["_skill_bestand"] = {
        "anzahl": 28, "titel": "Geometrische Optik", "node_id": "f35c17d1"}
    await respond_agent(ctx)
    systeme = "\n".join(m["content"] for m in seen["run_agent_loop"]["messages"]
                        if m.get("role") == "system")
    assert "## Freigegebene Skills" not in systeme.splitlines()
    assert "### Freigegebene Skills dieser Sammlung" in systeme


@pytest.mark.anyio
async def test_die_ladezeile_steht_vor_der_agent_antwort(monkeypatch):
    """Nutzer-Vorgabe 2026-08-16: eine hartcodierte Zeile, sobald ``get_skill``
    eine Anleitung geladen hat — statt der Ansage aus dem Ergebnis, die das
    Modell gemessen umformulierte.

    Gegenstück auf der Muster-Seite:
    ``test_respond_node.test_die_ladezeile_steht_vor_der_antwort``.
    """
    seen: dict = {}
    _patch(monkeypatch, seen)
    _vorab(monkeypatch)
    ctx = _ctx()
    ctx.session_state["turn_count"] = 4
    ctx.session_state["entities"]["_skill_lauf"] = {
        "node_id": "5b29f470", "zug": 4, "titel": "Stunde planen"}
    await respond_agent(ctx)
    assert ctx.response_text.splitlines()[0] == (
        "[ edu-sharing Skill ] Stunde planen - wird geladen")


@pytest.mark.anyio
async def test_ohne_geladene_anleitung_bleibt_die_agent_antwort_nackt(monkeypatch):
    seen: dict = {}
    _patch(monkeypatch, seen)
    _vorab(monkeypatch)
    ctx = _ctx()
    await respond_agent(ctx)
    assert "edu-sharing Skill" not in ctx.response_text


@pytest.mark.anyio
async def test_ohne_seitenkontext_bleibt_die_kette_wie_bisher(monkeypatch):
    # Gegenprobe zu ``test_verlauf_und_nachricht_stehen_in_der_kette``: ohne
    # Seite darf kein leerer Block und kein Vorabruf dazukommen.
    seen: dict = {}
    _patch(monkeypatch, seen)
    fake = _vorab(monkeypatch)
    await respond_agent(_ctx())
    assert len(seen["run_agent_loop"]["messages"]) == 2
    assert fake.calls == []


@pytest.mark.anyio
async def test_eine_sammlung_im_kontext_holt_die_freigabeliste_vorab(monkeypatch):
    """Der Kern von P4: der Katalog steht in der Kette, BEVOR der Agent
    überhaupt auf die Idee kommen könnte, danach zu fragen."""
    seen: dict = {}
    _patch(monkeypatch, seen)
    fake = _vorab(monkeypatch, result_map={"get_skill_registry": "Skill: Stunde planen"})
    await respond_agent(_ctx(page_context=_SAMMLUNG, page_meta=_AUFGELOEST))
    assert fake.calls == [("get_skill_registry", {"collectionId": _OPTIK_ID})]
    messages = seen["run_agent_loop"]["messages"]
    ergebnis = [m for m in messages if m.get("role") == "tool"]
    assert len(ergebnis) == 1
    assert "Stunde planen" in ergebnis[0]["content"]
    # Anleitungen vor Gegenstand — die Nutzerfrage bleibt das letzte Wort.
    assert messages[-1] == {"role": "user", "content": "frage"}


@pytest.mark.anyio
async def test_ohne_sammlung_wird_nichts_vorab_geholt(monkeypatch):
    # Eine Einzelinhalt-Seite trägt keine ``collection_id`` — ein Vorabruf
    # hätte hier kein Argument und wäre ein Aufruf ins Leere.
    seen: dict = {}
    _patch(monkeypatch, seen)
    fake = _vorab(monkeypatch)
    await respond_agent(_ctx(
        page_context={"page_kind": "content", "node_id": "n-1"},
        page_meta={"title": "Stationsarbeit zur Optik", "node_id": "n-1"}))
    assert fake.calls == []
    systeme = [m["content"] for m in seen["run_agent_loop"]["messages"]
               if m.get("role") == "system"]
    assert any("Stationsarbeit" in s for s in systeme), "Block fehlt — Test prüft nichts"


@pytest.mark.anyio
async def test_ein_gescheiterter_vorabruf_kippt_den_zug_nicht(monkeypatch):
    seen: dict = {}
    _patch(monkeypatch, seen)
    _vorab(monkeypatch, raises=True)
    ctx = await respond_agent(_ctx(page_context=_SAMMLUNG, page_meta=_AUFGELOEST))
    assert ctx.response_text == "Antwort des Agenten"
    ergebnis = [m for m in seen["run_agent_loop"]["messages"] if m.get("role") == "tool"]
    assert "nicht abrufen" in ergebnis[0]["content"]


# ── Strukturiertes Ergebnis aus dem Chat (Nutzer-Entscheid 2026-08-14) ──
# Ein Gastgeber, der ein `result_schema` erklärt, will maschinenlesbar
# zurückbekommen, was das Gespräch ergeben hat. Ohne Schema bleibt alles wie
# bisher: der Abschluss-Zug kostet 2–9 s (gemessen) und sagt sonst nur, was die
# Prosa schon sagt — deshalb ist er opt-in und nicht die Vorgabe.
#
# **Umgestellt am 2026-08-17 (J1, Nutzer-Entscheid).** Bis dahin trug
# ``submit_result`` Prosa UND Ergebnis in EINEM Aufruf und beendete den Lauf
# dabei. Live gemessen an der Sammlung „Optik": 196 Zeichen im Chat gegen 1932
# im Ergebnis — die Substanz landete dort, wo die Person im Chat sie nie sieht.
# Der Chat-Zug nimmt jetzt ``liefere_ergebnis``: es notiert und läuft WEITER,
# die Antwort entsteht danach als gewöhnlicher Zug. ``submit_result`` gehört ab
# hier ``/api/agent``, wo es keinen Chat gibt und ``text`` die Lieferung IST.

_SCHEMA = {
    "type": "object",
    "properties": {"taxon_id": {"type": "string"}},
    "required": ["taxon_id"],
}


@pytest.mark.anyio
async def test_ohne_schema_bleibt_das_ergebnis_werkzeug_weg(monkeypatch):
    seen: dict = {}
    _patch(monkeypatch, seen)
    ctx = await respond_agent(_ctx())
    assert "liefere_ergebnis" not in _namen(seen["run_agent_loop"]["tools"])
    assert ctx.result is None
    assert ctx.result_stop_reason == ""
    systeme = [m["content"] for m in seen["run_agent_loop"]["messages"]
               if m.get("role") == "system"]
    # Kein Wort über ein Werkzeug, das es nicht gibt: zwei Anweisungen, die
    # einander widersprechen, wären schlechter als keine.
    assert not any("liefere_ergebnis" in s for s in systeme)


@pytest.mark.anyio
async def test_mit_schema_kommt_das_ergebnis_werkzeug_dazu(monkeypatch):
    seen: dict = {}
    _patch(monkeypatch, seen, lauf=AgentRun(
        text="Das Fach ist Physik — und zwar in der Sekundarstufe I.",
        result={"taxon_id": "…/discipline/460"},
        stop_reason="text", iterations=3, tools_called=[],
    ))
    ctx = _ctx()
    ctx.req.environment.result_schema = _SCHEMA
    ctx = await respond_agent(ctx)

    tools = seen["run_agent_loop"]["tools"]
    assert "liefere_ergebnis" in _namen(tools)
    # ``submit_result`` gehört seit J1 dem Agent-Endpunkt. Stünde es hier
    # daneben, hätte das Modell zwei Ziellinien — und die eine, die den Lauf
    # sofort beendet, nähme der Prosa wieder ihren Zug.
    assert "submit_result" not in _namen(tools)
    # Das Schema reist WÖRTLICH als ``result``-Eigenschaft: der Gastgeber
    # bestimmt die Form, unser Code muss sie nicht kennen. Und daneben steht
    # KEIN ``text`` — genau diese Nachbarschaft war die gemessene Ursache.
    werkzeug = next(t for t in tools if t["function"]["name"] == "liefere_ergebnis")
    params = werkzeug["function"]["parameters"]
    assert params["properties"]["result"] == _SCHEMA
    assert set(params["properties"]) == {"result"}
    assert params["required"] == ["result"]
    assert ctx.result == {"taxon_id": "…/discipline/460"}
    # Der Lauf endet jetzt über die Prosa, nicht am Werkzeug.
    assert ctx.result_stop_reason == "text"
    systeme = [m["content"] for m in seen["run_agent_loop"]["messages"]
               if m.get("role") == "system"]
    assert any("liefere_ergebnis" in s for s in systeme), "Anweisung fehlt"


@pytest.mark.anyio
async def test_ein_geliefertes_ergebnis_ohne_prosa_gilt_nicht_als_gescheitert(monkeypatch):
    """Der Deckel-Satz („zu umfangreich, stell sie kleiner geschnitten noch
    einmal") stünde sonst über einem vollständig gelieferten Ergebnis und würde
    von ihm widerlegt — dieselbe Entscheidung wie bei den Dokument-Boxen."""
    seen: dict = {}
    _patch(monkeypatch, seen, lauf=AgentRun(
        text="", result={"taxon_id": "…/discipline/460"},
        stop_reason="max_iterations", iterations=9, tools_called=[],
    ))
    ctx = _ctx()
    ctx.req.environment.result_schema = _SCHEMA
    ctx = await respond_agent(ctx)
    assert "kleiner geschnitten" not in ctx.response_text
    assert ctx.result == {"taxon_id": "…/discipline/460"}


@pytest.mark.anyio
async def test_ein_zug_ohne_ergebnis_meldet_das_ende_trotzdem(monkeypatch):
    # „Hallo" ergibt kein taxonid. Die Gastseite muss `null` aushalten — und
    # am Ende erkennen, warum: ohne `stop_reason` sähe ein an der Frist
    # abgeschnittener Lauf aus wie einer, der fertig geworden ist.
    seen: dict = {}
    _patch(monkeypatch, seen, lauf=AgentRun(
        text="Hallo!", stop_reason="text", iterations=1, tools_called=[]))
    ctx = _ctx()
    ctx.req.environment.result_schema = _SCHEMA
    ctx = await respond_agent(ctx)
    assert ctx.result is None
    assert ctx.result_stop_reason == "text"


# ── Der Hybrid: Musterkatalog im Werkzeugsatz (H6) ──────────────────────────

def _drei_muster():
    from boerdi.domain.pattern_engine import PatternDef
    return [
        PatternDef(id="M01", label="Krisen-Empathie"),
        PatternDef(id="M06", label="Material-Suche Cascade",
                   tools=["search_wlo_all"]),
        PatternDef(id="M10", label="KI-Inhalt-Generierung", sources=["llm"]),
    ]


@pytest.mark.anyio
async def test_der_agent_modus_bekommt_keinen_musterkatalog(monkeypatch):
    """Die Zusage aus H1: ``agent`` bleibt die Maschine ohne Muster."""
    seen: dict = {}
    _patch(monkeypatch, seen)
    await respond_agent(_ctx(), engine="agent")
    assert seen["run_agent_loop"]["muster_katalog"] is None
    assert "waehle_vorgehen" not in _namen(seen["run_agent_loop"]["tools"])


@pytest.mark.anyio
async def test_der_hybrid_bekommt_den_musterkatalog(monkeypatch):
    seen: dict = {}
    _patch(monkeypatch, seen)
    monkeypatch.setattr(agent_mod, "get_patterns", _drei_muster)
    await respond_agent(_ctx(), engine="hybrid")
    namen = _namen(seen["run_agent_loop"]["tools"])
    assert namen[0] == "waehle_vorgehen"
    assert seen["run_agent_loop"]["werkzeuge_fuer"] is not None


@pytest.mark.anyio
async def test_ein_erzwungenes_muster_nimmt_den_katalog_weg(monkeypatch):
    """Über M01/M02 entscheidet das Sicherheits-Gate, nicht das Modell. Läge der
    Katalog daneben, wäre die Krisen-Behandlung ein Angebot."""
    seen: dict = {}
    _patch(monkeypatch, seen)
    monkeypatch.setattr(agent_mod, "get_patterns", _drei_muster)
    safety = SafetyDecision(risk_level="high", enforced_pattern="M01")
    await respond_agent(_ctx(safety=safety), engine="hybrid")
    assert seen["run_agent_loop"]["muster_katalog"] is None
    assert "waehle_vorgehen" not in _namen(seen["run_agent_loop"]["tools"])


@pytest.mark.anyio
async def test_das_gewaehlte_muster_wird_das_ausgefuehrte(monkeypatch):
    """H6/H7: an ``effective_pattern_id`` hängen die Inline-Kachel, der
    ``_last_pattern``-Merker des Folgezugs und die Muster-Spalte der Logs."""
    seen: dict = {}
    _patch(monkeypatch, seen, lauf=AgentRun(
        text="fertig", stop_reason="text", iterations=2, muster_id="M10"))
    monkeypatch.setattr(agent_mod, "get_patterns", _drei_muster)
    ctx = _ctx()
    ctx.effective_pattern_id = "HYBRID"
    await respond_agent(ctx, engine="hybrid")
    assert ctx.effective_pattern_id == "M10"
    assert ctx.effective_pattern_label == "KI-Inhalt-Generierung"


@pytest.mark.anyio
async def test_ohne_muster_bleibt_der_anfangszustand_stehen(monkeypatch):
    """Wählt das Modell nichts, wird auch nichts überschrieben — sonst stünde in
    den Logs ein Muster, das nie gelaufen ist."""
    seen: dict = {}
    _patch(monkeypatch, seen, lauf=AgentRun(
        text="fertig", stop_reason="text", iterations=1))
    monkeypatch.setattr(agent_mod, "get_patterns", _drei_muster)
    ctx = _ctx()
    ctx.effective_pattern_id = "HYBRID"
    await respond_agent(ctx, engine="hybrid")
    assert ctx.effective_pattern_id == "HYBRID"


@pytest.mark.anyio
async def test_das_muster_schnuert_die_werkzeugliste_zusammen(monkeypatch):
    """M10 arbeitet aus dem Modell (``sources: [llm]``, keine ``tools``) — dann
    bleiben nur die virtuellen Werkzeuge übrig. M06 gibt die Suche wieder frei."""
    seen: dict = {}
    _patch(monkeypatch, seen)
    monkeypatch.setattr(agent_mod, "get_patterns", _drei_muster)
    await respond_agent(_ctx(), engine="hybrid")
    fuer = seen["run_agent_loop"]["werkzeuge_fuer"]
    muster = {m.id: m for m in _drei_muster()}

    # M10 arbeitet ohne Suchwerkzeuge — aber es ERZEUGT etwas, muss also eine
    # Box liefern koennen (D2). Beide virtuellen Werkzeuge bleiben deshalb.
    nur_llm = _namen(fuer(muster["M10"]))
    assert sorted(nur_llm) == ["waehle_vorgehen", "zeige_dokument"]

    mit_suche = _namen(fuer(muster["M06"]))
    assert "search_wlo_all" in mit_suche
    assert "waehle_vorgehen" in mit_suche
    assert "wlo_delete_content" not in mit_suche


@pytest.mark.anyio
async def test_die_erste_runde_bekommt_den_vollen_katalog(monkeypatch):
    """Wer noch nicht gewaehlt hat, braucht die Einsatzregeln — sie sind die
    Grundlage der Wahl."""
    seen: dict = {}
    _patch(monkeypatch, seen)
    monkeypatch.setattr(agent_mod, "get_patterns", _drei_muster)
    await respond_agent(_ctx(), engine="hybrid")
    beschreibung = seen["run_agent_loop"]["tools"][0]["function"]["description"]
    assert "###" in beschreibung


@pytest.mark.anyio
async def test_nach_der_wahl_traegt_der_katalog_nur_noch_eine_zeile_je_muster(monkeypatch):
    """H8-2: ``waehle_vorgehen`` bleibt in jeder eingeschraenkten Liste und
    schleppte bisher seinen vollen Katalog durch alle Runden — gemessen 25 251
    von 31 742 Zeichen des Werkzeugsatzes nach der Wahl."""
    seen: dict = {}
    _patch(monkeypatch, seen)
    monkeypatch.setattr(agent_mod, "get_patterns", _drei_muster)
    await respond_agent(_ctx(), engine="hybrid")

    rueckruf = seen["run_agent_loop"]["werkzeuge_fuer"]
    danach = rueckruf(_drei_muster()[0])
    vorgehen = next(t for t in danach if t["function"]["name"] == "waehle_vorgehen")
    vorher = seen["run_agent_loop"]["tools"][0]["function"]["description"]
    assert len(vorgehen["function"]["description"]) < len(vorher)
    assert "###" not in vorgehen["function"]["description"]
    # Die Auswahl bleibt vollstaendig — gespart wird an der Beschreibung.
    assert (vorgehen["function"]["parameters"]["properties"]["muster_id"]["enum"]
            == seen["run_agent_loop"]["tools"][0]["function"]["parameters"]
               ["properties"]["muster_id"]["enum"])


@pytest.mark.anyio
async def test_der_ergebnis_kanal_ueberlebt_die_musterwahl(monkeypatch):
    """H4 baut die Werkzeugliste beim Musterwechsel neu — auf die Werkzeuge des
    Musters plus die virtuellen. Fehlte ``liefere_ergebnis`` in dieser Menge,
    wäre der Ergebnis-Kanal im Hybrid weg, sobald das Modell ein Muster zieht:
    der Gastgeber bekäme genau in den Fällen kein JSON, in denen gearbeitet
    wurde. Dieselbe Falle, die der Kommentar an ``VIRTUELLE_WERKZEUGE`` für
    ``waehle_vorgehen`` beschreibt."""
    from boerdi.domain.pattern_engine import PatternDef
    from boerdi.graph.nodes.respond_agent import _werkzeuge_des_musters
    from boerdi.services.agent_tools import build_agent_tools

    alle = build_agent_tools(include_submit=False, include_ergebnis=True,
                             result_schema=_SCHEMA, include_dokument=True,
                             muster_katalog=[PatternDef(id="M06", label="Suche")])
    # M10 arbeitet ohne MCP (``sources: [llm]``) — die härteste Einschränkung.
    uebrig = _namen(_werkzeuge_des_musters(alle, []))
    assert "liefere_ergebnis" in uebrig
    assert "zeige_dokument" in uebrig
    assert "waehle_vorgehen" in uebrig


@pytest.mark.anyio
async def test_ein_gedeckelter_lauf_holt_die_antwort_nach(monkeypatch):
    """Live gemessen (2026-08-17, hybrid, Sammlung „Optik"): der Lauf lieferte
    das Ergebnis und riss DANACH das Token-Budget — die Person bekam 22 Zeichen.
    Seit ``liefere_ergebnis`` den Lauf nicht mehr beendet, ist die Prosa ein
    eigener Zug und damit deckelbar; vorher trug ``submit_result`` sie mit, und
    diese Lücke konnte es gar nicht geben.

    Der Bestandsweg kennt die Antwort darauf seit P16
    (``tool_loop_fallback._max_iterations_fallback``): EIN Abschluss-Aufruf ohne
    Werkzeuge. Die Deckel sollen weglaufende ARBEIT stoppen, nicht die Antwort.
    """
    gesehen: dict = {}

    async def _abschluss(*, messages, temperature=0.4, usage_acc=None, phase=None,
                         tools=None, **rest):
        gesehen["phase"] = phase
        gesehen["tools"] = tools
        gesehen["letzte"] = messages[-1]["content"]

        class _M:
            content = "Die Sammlung deckt Optik gut ab; es fehlt Wellenoptik."

        class _C:
            message = _M()

        class _R:
            choices = [_C()]

        return _R()

    seen: dict = {}
    _patch(monkeypatch, seen, lauf=AgentRun(
        text="", result={"titel": "x", "befund": "y"},
        stop_reason="token_budget", iterations=7, tools_called=[],
    ))
    monkeypatch.setattr(agent_mod.llm, "chat_completion", _abschluss)
    ctx = _ctx()
    ctx.req.environment.result_schema = _SCHEMA
    ctx = await respond_agent(ctx)

    assert "Wellenoptik" in ctx.response_text
    # Ohne Werkzeuge: der Zug soll antworten, nicht weiterarbeiten.
    assert not gesehen["tools"]
    # Eigene Phase in der Kostenschau — ihr Auftauchen meldet den gerissenen
    # Deckel, und das soll in der normalen Antwort nicht untergehen (K1f).
    assert gesehen["phase"] == "fallback_summary"


@pytest.mark.anyio
async def test_ohne_lieferung_kein_abschluss_aufruf(monkeypatch):
    """Ein Lauf, der NICHTS geliefert hat, hat auch nichts zu erzählen — der
    ehrliche Ersatzsatz ist billiger und richtiger als ein weiterer Zug."""
    gerufen: list = []

    async def _nie(**kw):
        gerufen.append(kw)
        raise AssertionError("kein Abschluss-Aufruf erwartet")

    seen: dict = {}
    _patch(monkeypatch, seen, lauf=AgentRun(
        text="", stop_reason="deadline", iterations=9, tools_called=[]))
    monkeypatch.setattr(agent_mod.llm, "chat_completion", _nie)
    ctx = await respond_agent(_ctx())
    assert gerufen == []
    assert ctx.response_text


@pytest.mark.anyio
async def test_die_grenzen_der_einbettung_stehen_hinter_dem_master_skill(monkeypatch):
    """O-C: was die Anwendung anzeigt und erlaubt, erfaehrt das Modell.

    Die Position ist Teil der Zusage: hinter dem Master-Skill (beide stabil,
    also im gecachten Praefix), aber VOR dem Seitenkontext — der wechselt je
    Zug und darf das Praefix nicht spalten.
    """
    from boerdi.services import master_skill

    seen: dict = {}
    _patch(monkeypatch, seen)
    _vorab(monkeypatch)
    monkeypatch.setattr(master_skill, "prompt_block",
                        lambda ueberschreibung=None: _fertig("## Gesamtanleitung — Inhalt."))
    ctx = _ctx(page_context={"title": "Optik"})
    ctx.req.environment.inline_result_grouping = False
    ctx.req.environment.tool_mode = "read-only"
    await respond_agent(ctx)
    kette = seen["run_agent_loop"]["messages"]
    assert "Gesamtanleitung" in kette[1]["content"]
    grenzen = kette[2]["content"]
    assert grenzen.startswith("## Diese Anwendung"), grenzen[:60]
    assert "gruppiert" in grenzen.lower()
    assert "NICHTS aendern" in grenzen


@pytest.mark.anyio
async def test_ohne_abweichung_kein_grenz_block(monkeypatch):
    """Vorgabe = heutiges Verhalten: kein Satz, kein Token."""
    seen: dict = {}
    _patch(monkeypatch, seen)
    _vorab(monkeypatch)
    await respond_agent(_ctx())
    systeme = [m["content"] for m in seen["run_agent_loop"]["messages"]
               if m.get("role") == "system"]
    assert not any("## Diese Anwendung" in s for s in systeme)


@pytest.mark.anyio
async def test_read_only_nimmt_dem_zug_die_schreibenden_werkzeuge(monkeypatch):
    """O-A: der Gastgeber entscheidet, was in SEINER Anwendung moeglich ist.

    Gegenprobe zum Prompt-Block: das Modell erfaehrt die Grenze nicht nur, es
    kann sie auch nicht umgehen — das Werkzeug ist gar nicht da.
    """
    from boerdi.services.mcp.auth import set_turn_auth_block

    seen: dict = {}
    _patch(monkeypatch, seen)
    _vorab(monkeypatch)
    assert set_turn_auth_block("wlo2.abc-def_123")
    try:
        ctx = _ctx()
        ctx.req.environment.tool_mode = "read-only"
        await respond_agent(ctx)
    finally:
        set_turn_auth_block(None)
    namen = _namen(seen["run_agent_loop"]["tools"])
    # Geprueft wird gegen den KURATIER-Katalog, nicht gegen das Praefix: seit
    # der Durchsicht am 18.08.2026 ueberleben `wlo_auth_status` und
    # `wlo_health_check` den read-only-Modus — sie tragen das Praefix, aendern
    # aber nichts. Das Praefix abzufragen hiesse, die Faustregel zu pruefen
    # statt die Zusage.
    from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS
    schreibend = {t["function"]["name"] for t in CURATION_TOOL_DEFINITIONS}
    assert not (set(namen) & schreibend), sorted(set(namen) & schreibend)
    assert "search_wlo_all" in namen


# ── P: die Wissensdatenbank in der Agent-Schleife ───────────────────


@pytest.mark.anyio
async def test_die_wissensbereiche_stehen_im_werkzeugsatz(monkeypatch):
    """Befund 2026-08-18: der Agent-Modus hatte GAR KEIN internes Wissen —
    ``query_knowledge`` gibt es nur im Muster-Weg. Vorgabe des Nutzers: hier
    immer alle Bereiche, ausser man nennt oder schliesst einzelne aus."""
    seen: dict = {}
    _patch(monkeypatch, seen)
    _vorab(monkeypatch)
    ctx = _ctx()
    ctx.rag_config = {"WirLernenOnline": {"description": "Die Plattform."}}
    await respond_agent(ctx)
    werkzeuge = seen["run_agent_loop"]["tools"]
    assert "wissen_suchen" in _namen(werkzeuge)
    wissen = next(t for t in werkzeuge if t["function"]["name"] == "wissen_suchen")
    assert "Die Plattform." in wissen["function"]["description"]
    assert seen["run_agent_loop"].get("wissen") is not None


@pytest.mark.anyio
async def test_ohne_gepflegte_bereiche_kein_werkzeug(monkeypatch):
    seen: dict = {}
    _patch(monkeypatch, seen)
    _vorab(monkeypatch)
    ctx = _ctx()
    ctx.rag_config = {}
    await respond_agent(ctx)
    assert "wissen_suchen" not in _namen(seen["run_agent_loop"]["tools"])
    assert seen["run_agent_loop"].get("wissen") is None
