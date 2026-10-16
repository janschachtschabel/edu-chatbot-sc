"""Befund 2026-10-08 (Nutzer, Staging, Agent-Modus): die Aufnahme in eine
Sammlung kommt nie über die Vorschau hinaus.

Ablauf laut Verlauf: angemeldet, Material erschlossen, „dann füge den Inhalt der
Sammlung hinzu“ → Vorschau zu ``wlo_add_to_collection``; die Antwort „Zum
Aufnehmen bestätigen“ → wieder nur eine Vorschau. Die Seite lief mit
Seitenkontext (die Knoten-ID kam „aus dem Seitenkontext“).

Zwischen Vorschau und Zustimmung kann ein Zug liegen, den die Person nie sieht:
der Kontext-Ping des Widgets (``[context-open]``). Er geht bei jeder Änderung der
Gastseite hinaus (URL-Wächter, ``replaceContext`` der Browser-Erweiterung) und
läuft wie jeder Zug durch ``setup``. Ist die Seite schon begrüßt, bleibt seine
Antwort leer, und das Widget zeigt nichts. Dasselbe gilt für den Tour-Tick ohne
laufende Tour (``[tour-tick]``, bei jedem Seitenaufruf über einen ``?bsid=``-Link).

Die Gegenrichtung bleibt Regel (Audit 2026-09-29): zeigt ein solcher Zug etwas,
etwa die Begrüßung einer neuen Seite, ist die nächste Antwort nicht mehr die auf
die Vorschau, und der Vorgang verfällt.

Gefälscht wird nur, was eine Prozessgrenze überschreitet: Modell, MCP-Server
(zweistufig, mit dem Vorschautext des echten Servers) und die Sitzungszeile.
Echt laufen ``setup``, ``tour``, ``context_greeting``, ``preflight`` samt
Abnahme, ``respond_agent`` mit Schreib-Wall und die Anmeldung über den
Zugangsblock.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

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
from boerdi.graph.build import build_turn_graph, run_turn
from boerdi.graph.nodes import context_greeting as greeting_mod
from boerdi.graph.nodes import page_context_enrich as enrich_mod
from boerdi.graph.nodes import preflight as pf_mod
from boerdi.graph.nodes import respond_agent as agent_mod
from boerdi.graph.nodes import setup as setup_mod
from boerdi.graph.nodes import tour as tour_mod
from boerdi.graph.nodes.context_greeting import context_greeting
from boerdi.graph.nodes.preflight import preflight
from boerdi.graph.nodes.respond_agent import respond_agent
from boerdi.graph.nodes.setup import setup
from boerdi.graph.nodes.tour import tour
from boerdi.services import llm
from boerdi.services import write_approval as wa_mod
from boerdi.services.mcp import client as mcp_client
from boerdi.services.mcp import transport
from boerdi.services.rate_limits import RateVerdict
from tests.helfer_anmeldung import als_person

_SITZUNG = object()  # Sentinel — jede DB-Grenze ist gefälscht.
_SID = "s-kontext-ping"
_BLOCK = "wlo2.TESTblockPersonA"
_WERKZEUG = "wlo_add_to_collection"
_ARGS = {"collectionId": "c-optik", "nodeId": "f5410fbd-e143-445b-810f-bde143945b5b"}
_SEITE = {
    "page_kind": "external",
    "page_host": "de.wikipedia.org",
    "page_url": "https://de.wikipedia.org/wiki/Optische_Abbildung",
}
_NEUE_SEITE = {**_SEITE, "page_url": "https://de.wikipedia.org/wiki/Linse_(Optik)"}


class _WloServer:
    """``wlo_add_to_collection`` wie der echte Server (``referenceHandler`` +
    ``previewReply``): ohne Schlüssel die Vorschau, mit dem passenden genau
    einmal die Ausführung."""

    def __init__(self) -> None:
        self.aufrufe: list[tuple[str, dict, bool]] = []
        self.ausgefuehrt: list[tuple[str, dict]] = []
        self._offen: dict[str, str] = {}

    async def call_tool(self, tool_name, arguments=None, *, url=None):
        args = dict(arguments or {})
        schluessel = args.pop("confirmToken", None)
        self.aufrufe.append((tool_name, args, schluessel is not None))
        vorhaben = json.dumps([tool_name, args], sort_keys=True)
        if schluessel is None:
            neu = f"TESTschluessel{len(self._offen):02d}abcdefgh"
            self._offen[neu] = vorhaben
            text = (
                "Bitte prüfen — bisher wurde nichts geändert:\n\n"
                "Nimmt „Optische Abbildung“ in die Sammlung „Optik“ auf "
                f"({_ARGS['collectionId']} / {_ARGS['nodeId']}). "
                "Das Material selbst wird dabei nicht verändert.\n\n"
                "Zum Aufnehmen bitte bestätigen. Dazu denselben Aufruf mit "
                f"confirmToken: {neu} wiederholen.\n"
                "Der Schlüssel gilt einmalig und zehn Minuten lang."
            )
        elif self._offen.pop(schluessel, None) == vorhaben:
            self.ausgefuehrt.append((tool_name, args))
            text = "„Optische Abbildung“ ist jetzt in „Optik“."
        else:
            return {"error": {"message": "confirmToken unbekannt", "kind": "tool"}}
        return {"result": {"content": [{"type": "text", "text": text}]}}


class _Ablage:
    """Die Sitzungszeile, soweit sie hier zählt: ``entities`` (JSONB) und der
    Verlauf. Gelesen wird eine Kopie, wie aus der Datenbank."""

    def __init__(self) -> None:
        self.entities: dict = {}
        self.verlauf: list[dict] = []
        self.schreibvorgaenge = 0

    async def get_or_create_session(self, _session, _sid):
        return {"persona_id": "P-AND", "entities": json.loads(json.dumps(self.entities))}

    async def get_messages(self, _session, _sid, limit=20):
        return list(self.verlauf[-limit:])

    async def update_session(self, _session, _sid, **felder):
        self.schreibvorgaenge += 1
        if "entities" in felder:
            self.entities = json.loads(json.dumps(felder["entities"]))

    async def save_message(self, _session, _sid, role, content, **_kw):
        self.verlauf.append({"role": role, "content": content})


def _werkzeug_antwort(name: str, args: dict, call_id: str):
    tc = SimpleNamespace(id=call_id, type="function",
                         function=SimpleNamespace(name=name, arguments=json.dumps(args)))
    msg = SimpleNamespace(role="assistant", content=None, tool_calls=[tc])
    return SimpleNamespace(
        choices=[SimpleNamespace(message=msg, finish_reason="tool_calls")],
        usage=None, model="gpt-x")


def _text_antwort(text: str):
    msg = SimpleNamespace(role="assistant", content=text, tool_calls=None)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=msg, finish_reason="stop")],
        usage=None, model="gpt-x")


class _Modell:
    """``llm.chat_completion`` nach Drehbuch."""

    def __init__(self, drehbuch: list) -> None:
        self._rest = list(drehbuch)

    async def __call__(self, **_kwargs):
        return self._rest.pop(0)


@pytest.fixture
def welt(monkeypatch) -> tuple[_WloServer, _Ablage]:
    """Agent-Modus mit der Vorgabe ``propose``; MCP-Server und Sitzungszeile
    gefälscht. Die Anmeldung setzt jeder Test selbst (``_angemeldet``)."""
    server = _WloServer()
    ablage = _Ablage()
    monkeypatch.setattr(transport, "call_tool", server.call_tool)
    monkeypatch.setattr(mcp_client, "_get_server_url_for_tool",
                        lambda _t: "https://mcp.invalid/mcp")
    monkeypatch.setattr(agent_mod, "load_engine",
                        lambda: EngineArea(mode="agent", agent=AgentLimits()))

    async def _keine_gesamtanleitung(_ueberschreibung=None):
        return None

    async def _frei(*_a, **_k):
        return RateVerdict(allowed=True)

    async def _nichts(*_a, **_k):
        return None

    async def _keine_dublette(_url, _title):
        return None

    monkeypatch.setattr(agent_mod.master_skill, "prompt_block", _keine_gesamtanleitung)
    monkeypatch.setattr(pf_mod, "check_rate_limit", _frei)
    monkeypatch.setattr(pf_mod, "log_turn_quality", _nichts)
    monkeypatch.setattr(setup_mod, "get_or_create_session", ablage.get_or_create_session)
    monkeypatch.setattr(setup_mod, "get_messages", ablage.get_messages)
    monkeypatch.setattr(wa_mod, "update_session", ablage.update_session)
    monkeypatch.setattr(wa_mod, "save_message", ablage.save_message)
    monkeypatch.setattr(greeting_mod, "update_session", ablage.update_session)
    monkeypatch.setattr(greeting_mod, "save_message", ablage.save_message)
    monkeypatch.setattr(greeting_mod, "find_existing_by_url", _keine_dublette)
    monkeypatch.setattr(tour_mod, "update_session", ablage.update_session)
    monkeypatch.setattr(tour_mod, "save_message", ablage.save_message)
    return server, ablage


def _angemeldet() -> None:
    """Die Anmeldung, wie ``api/turn_auth`` sie je Anfrage übernimmt und der Server
    sie bestätigt — echt, damit Kennzeichen und ``has_personal_auth`` aus derselben
    Quelle kommen. Im Test-Task gesetzt; der Kontext endet mit dem Test."""
    assert als_person(_BLOCK)


async def _zug(ablage: _Ablage, nachricht: str, *, seite: dict = _SEITE,
              **umgebung) -> state_mod.TurnContext:
    """Ein Zug in der Reihenfolge des Graphen (``graph/build``): ``setup`` →
    ``tour`` → ``context_greeting`` → ``preflight`` → Schleife → ``persist``.
    Seiten-Anreicherung und Sicherheitsstufe tragen hier nichts bei und fehlen."""
    ctx = state_mod.TurnContext(req=ChatRequest(
        session_id=_SID, message=nachricht,
        environment=Environment(locale="de", page_context=dict(seite), **umgebung),
    ))
    ctx = await setup(ctx, _SITZUNG)
    for fruehe_antwort in (tour, context_greeting):
        ctx = await fruehe_antwort(ctx, _SITZUNG)
        if ctx.early_response is not None:
            return ctx
    ctx.safety = SafetyDecision(risk_level="low")
    ctx.policy = PolicyDecision()
    ctx.classification = ClassificationResult()
    ctx = await preflight(ctx, _SITZUNG)
    if ctx.early_response is None:
        ctx = await respond_agent(ctx)
        # Der Knoten ``persist``: ``entities`` gehen in die Zeile, beide
        # Nachrichten in den Verlauf.
        await ablage.update_session(_SITZUNG, _SID, entities=ctx.session_state["entities"])
        ablage.verlauf += [{"role": "user", "content": nachricht},
                           {"role": "assistant", "content": ctx.response_text}]
    return ctx


def _ping(ablage: _Ablage, ereignis: str = "context_open", seite: dict = _SEITE):
    """Der Kontext-Ping des Widgets (``context-greeting.controller.ts``)."""
    return _zug(ablage, "[context-open]", seite=seite, page_event=ereignis)


def _drehbuch() -> list:
    return [
        _werkzeug_antwort(_WERKZEUG, _ARGS, "c1"),
        _text_antwort("Die Aufnahme ist vorbereitet. Bitte bestätigen Sie mit "
                      "„Zum Aufnehmen bestätigen“."),
        # Nur erreicht, wenn der Vorlauf die Zustimmung nicht einlöst: das
        # Modell tut, was es kann, und ruft dasselbe Werkzeug noch einmal.
        _werkzeug_antwort(_WERKZEUG, _ARGS, "c2"),
        _text_antwort("Das Werkzeug hat erneut nur eine Vorschau erzeugt."),
    ]


async def test_ohne_ping_fuehrt_die_zustimmung_aus(welt, monkeypatch):
    """Die Gegenprobe: derselbe Ablauf ohne Ping zwischen Vorschau und Antwort."""
    server, ablage = welt
    monkeypatch.setattr(llm, "chat_completion", _Modell(_drehbuch()))
    _angemeldet()

    await _zug(ablage, "dann füge den Inhalt der Sammlung Optik hinzu")
    assert server.ausgefuehrt == []

    await _zug(ablage, "Zum Aufnehmen bestätigen")
    assert server.ausgefuehrt == [(_WERKZEUG, _ARGS)]


async def test_ein_unsichtbarer_kontext_ping_kostet_die_abnahme_nicht(welt, monkeypatch):
    """Der gemeldete Fall: die Seite ist begrüßt, der Ping bleibt unsichtbar —
    für die Person ist „Zum Aufnehmen bestätigen“ die Antwort direkt auf die
    Vorschau."""
    server, ablage = welt
    monkeypatch.setattr(llm, "chat_completion", _Modell(_drehbuch()))
    _angemeldet()

    begruessung = await _ping(ablage, "context_open_initial")
    assert begruessung.early_response.content, "Vorbedingung: die Seite wird begrüßt"

    await _zug(ablage, "dann füge den Inhalt der Sammlung Optik hinzu")
    assert ablage.entities.get("_pending_write"), "Vorbedingung: Vorgang gemerkt"

    ping = await _ping(ablage)
    assert ping.early_response.content == "", "Vorbedingung: der Ping bleibt unsichtbar"

    await _zug(ablage, "Zum Aufnehmen bestätigen")
    assert server.ausgefuehrt == [(_WERKZEUG, _ARGS)], (
        "Nach „Zum Aufnehmen bestätigen“ wurde nichts ausgeführt. "
        f"Server-Aufrufe (Werkzeug, Argumente, mit Schlüssel): {server.aufrufe}")


async def test_ein_tour_tick_ohne_tour_kostet_die_abnahme_nicht(welt, monkeypatch):
    """Dieselbe Lücke beim zweiten Hintergrund-Zug: nach einem Seitenaufruf über
    einen ``?bsid=``-Link schickt das Widget statt des Kontext-Pings einen
    Tour-Tick, und ohne laufende Tour bleibt dessen Antwort leer."""
    server, ablage = welt
    monkeypatch.setattr(llm, "chat_completion", _Modell(_drehbuch()))
    _angemeldet()

    await _zug(ablage, "dann füge den Inhalt der Sammlung Optik hinzu")
    assert ablage.entities.get("_pending_write"), "Vorbedingung: Vorgang gemerkt"

    tick = await _zug(ablage, "[tour-tick]", tour_action="tick")
    assert tick.early_response.content == "", "Vorbedingung: der Tick bleibt unsichtbar"

    await _zug(ablage, "Zum Aufnehmen bestätigen")
    assert server.ausgefuehrt == [(_WERKZEUG, _ARGS)], (
        f"Server-Aufrufe (Werkzeug, Argumente, mit Schlüssel): {server.aufrufe}")


async def test_eine_sichtbare_begruessung_laesst_den_vorgang_verfallen(welt, monkeypatch):
    """Die Regel, die bleibt: begrüßt der Ping eine NEUE Seite, steht zwischen
    Vorschau und Antwort eine Nachricht samt Knöpfen. Ein „ja“ danach kann ihr
    gelten — ausgeführt wird nichts, und der Verfall steht in der Zeile."""
    server, ablage = welt
    monkeypatch.setattr(llm, "chat_completion", _Modell(_drehbuch()))
    _angemeldet()

    await _ping(ablage, "context_open_initial")
    await _zug(ablage, "dann füge den Inhalt der Sammlung Optik hinzu")
    assert ablage.entities.get("_pending_write"), "Vorbedingung: Vorgang gemerkt"

    gruss = await _ping(ablage, seite=_NEUE_SEITE)
    assert gruss.early_response.content, "Vorbedingung: die neue Seite wird begrüßt"
    assert "_pending_write" not in ablage.entities

    await _zug(ablage, "Zum Aufnehmen bestätigen", seite=_NEUE_SEITE)
    assert server.ausgefuehrt == []


# ── Über den echten Graphen (Review 2026-10-08, Befund 2) ────────────────────
# Der Fix hängt an einer Eigenschaft des GANZEN Graphen: ein Hintergrund-Zug,
# der stumm endet, schreibt ``entities`` nicht — und einer, der etwas zeigt,
# schreibt sie. Hier läuft der kompilierte Graph samt ``page_context_enrich``
# (Auflösung gegen den MCP ausgeschaltet) und Weiche nach der Begrüßung.

async def _graph_ping(monkeypatch, ablage: _Ablage, seite: dict = _SEITE):
    async def _ohne_aufloesung(_page_ctx, _session_state):
        return None

    monkeypatch.setattr(enrich_mod, "resolve_page_context", _ohne_aufloesung)
    graph = build_turn_graph(session=_SITZUNG, engine="agent")
    zustand = await run_turn(graph, state_mod.TurnContext(req=ChatRequest(
        session_id=_SID, message="[context-open]",
        environment=Environment(locale="de", page_context=dict(seite),
                                page_event="context_open"),
    )))
    return zustand.get("early_response")


async def _vorschau_steht(ablage: _Ablage) -> None:
    await _ping(ablage, "context_open_initial")
    await _zug(ablage, "dann füge den Inhalt der Sammlung Optik hinzu")
    assert ablage.entities.get("_pending_write"), "Vorbedingung: Vorgang gemerkt"


async def test_der_graph_schreibt_beim_stummen_ping_nichts(welt, monkeypatch):
    server, ablage = welt
    monkeypatch.setattr(llm, "chat_completion", _Modell(_drehbuch()))
    _angemeldet()
    await _vorschau_steht(ablage)
    vorher = ablage.schreibvorgaenge

    antwort = await _graph_ping(monkeypatch, ablage)

    assert antwort is not None and antwort.content == ""
    assert ablage.schreibvorgaenge == vorher
    assert ablage.entities.get("_pending_write")

    await _zug(ablage, "Zum Aufnehmen bestätigen")
    assert server.ausgefuehrt == [(_WERKZEUG, _ARGS)]


async def test_der_graph_schreibt_den_verfall_bei_sichtbarer_begruessung(welt, monkeypatch):
    server, ablage = welt
    monkeypatch.setattr(llm, "chat_completion", _Modell(_drehbuch()))
    _angemeldet()
    await _vorschau_steht(ablage)

    antwort = await _graph_ping(monkeypatch, ablage, seite=_NEUE_SEITE)

    assert antwort is not None and antwort.content
    assert "_pending_write" not in ablage.entities
