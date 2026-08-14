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

    async def _loop(*, messages, tools, limits, usage_acc=None, progress=None,
                    clock=None, on_tool_result=None):
        seen["run_agent_loop"] = {
            "messages": messages, "tools": tools, "limits": limits,
            "usage_acc": usage_acc, "progress": progress,
            "on_tool_result": on_tool_result,
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


# ── Die Weiche in ``respond`` ──────────────────────────────────────
@pytest.mark.anyio
async def test_respond_reicht_im_agent_modus_frueh_weiter(monkeypatch):
    """Der Rumpf von ``respond`` bleibt unangetastet — er darf im Agent-Modus
    gar nicht erst anlaufen."""
    seen: dict = {}

    async def _agent(ctx, progress=None):
        seen["respond_agent"] = {"progress": progress}
        ctx.response_text = "vom Agenten"
        return ctx

    def _generate(*a, **k):                      # pragma: no cover — darf nie laufen
        seen["generate_response"] = True
        raise AssertionError("generate_response im Agent-Modus gerufen")

    monkeypatch.setattr(respond_mod, "respond_agent", _agent)
    monkeypatch.setattr(respond_mod, "generate_response", _generate)
    ctx = await respond(_ctx(), session=object(), engine="agent")
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
    assert "search_skill" in systeme   # der Weg zum Volltext steht dabei


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
