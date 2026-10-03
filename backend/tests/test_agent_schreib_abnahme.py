"""Befund 2026-09-28, behoben in Paket 2 (2026-10-01): im Agent-Modus kam eine
kuratierende Änderung im Chat nie über die Vorschau hinaus — auch nicht nach „ja“.

Die Abnahme im Vorlauf (``graph/nodes/preflight`` → ``services/write_approval``,
S5) ist maschinenunabhängig: sie läuft vor der Engine-Weiche. Einlösen kann sie
ein „ja“ aber nur über den Merkposten ``entities["_pending_write"]``. Den setzte
anfangs allein die Werkzeugschleife der Muster-Maschine (``services/tool_loop``);
die Agent-Schleife (``services/agent_write.WriteGate``) merkte sich in der
Vorgabe ``write_mode: propose`` nichts, und ihr eigener Merkposten starb mit
dem Lauf. Folge: keine Vorschau-Box, kein Zustimmungs-Knopf, und ein „ja“ im
Folgezug erzeugte eine neue Vorschau statt der Ausführung. Seit Paket 2 reicht
die Schleife den offenen Vorgang am Ende hinaus (``on_offene_abnahme`` →
``write_approval.merke_abnahme``).

Gefälscht wird nur, was eine Prozessgrenze überschreitet: das Modell
(``llm.chat_completion``), der MCP-Server (``transport.call_tool``, zweistufig
wie der echte) und die Datenbank. Echt laufen ``preflight`` samt Abnahme,
``respond_agent``, die Agent-Schleife samt Schreib-Wall und der MCP-Client samt
Argumentprüfung. Den Zugwechsel spielt der Test nach: von ``session_state``
überdauert nur ``entities`` (JSONB), alles auf oberster Ebene stirbt mit der
Anfrage (``graph/nodes/setup``).

Die beiden Soll-Tests standen bis zum Umbau als ``xfail(strict=True)``; seit
Paket 2 (2026-10-01, Plan ``2026-09-28-agent-runde-2``, „Nebenbefund außerhalb
dieser Runde“) sind sie grün und tragen keinen Marker mehr. Der dritte Test ist
die Zusicherung, die vorher galt und weiter gelten muss.
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
from boerdi.domain.write_confirm import extract_confirm_token
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import preflight as pf_mod
from boerdi.graph.nodes import respond_agent as agent_mod
from boerdi.graph.nodes.preflight import preflight
from boerdi.graph.nodes.respond_agent import respond_agent
from boerdi.services import agent_deckel, agent_tools, agent_write, llm
from boerdi.services import write_approval as wa_mod
from boerdi.services.mcp import client as mcp_client
from boerdi.services.mcp import transport
from boerdi.services.rate_limits import RateVerdict

_SITZUNG = object()  # Sentinel — jede DB-Grenze ist gepatcht.
_WUNSCH = "Leg mir bitte eine Sammlung Bruchrechnen an"
_WERKZEUG = "wlo_create_collection"
_ARGS = {"title": "Bruchrechnen"}


class _WloServer:
    """Der zweistufige Schreibweg des MCP-Servers, auf das Nötige verkleinert.

    Ohne ``confirmToken`` prägt er einen Schlüssel und liefert die Vorschau; mit
    dem passenden Schlüssel für dieselbe Änderung führt er aus, genau einmal.
    ``ausgefuehrt`` beantwortet damit die Frage des Befunds: ist etwas passiert?
    """

    def __init__(self) -> None:
        self.aufrufe: list[tuple[str, dict, bool]] = []
        self.ausgefuehrt: list[tuple[str, dict]] = []
        self.gepraegt: list[str] = []
        self._offen: dict[str, str] = {}

    async def call_tool(self, tool_name, arguments=None, *, url=None):
        args = dict(arguments or {})
        schluessel = args.pop("confirmToken", None)
        self.aufrufe.append((tool_name, args, schluessel is not None))
        vorhaben = json.dumps([tool_name, args], sort_keys=True)
        titel = args.get("title", "")
        if schluessel is None:
            neu = f"TESTschluessel{len(self.gepraegt):02d}abcdefgh"
            self.gepraegt.append(neu)
            self._offen[neu] = vorhaben
            text = (
                f"Die Sammlung „{titel}“ wird angelegt. Dazu denselben Aufruf "
                f"mit confirmToken: {neu} wiederholen.\n"
                "Der Schlüssel gilt 10 Minuten und nur für genau diese Änderung."
            )
        elif self._offen.pop(schluessel, None) == vorhaben:
            self.ausgefuehrt.append((tool_name, args))
            text = f"Die Sammlung „{titel}“ wurde angelegt."
        else:
            return {"error": {
                "message": "confirmToken unbekannt oder abgelaufen — ohne "
                           "confirmToken wiederholen.",
                "kind": "tool",
            }}
        return {"result": {"content": [{"type": "text", "text": text}]}}


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
    """``llm.chat_completion`` nach Drehbuch; hält jede Kette fest, die es sah."""

    def __init__(self, drehbuch: list) -> None:
        self._rest = list(drehbuch)
        self.ketten: list[str] = []

    async def __call__(self, **kwargs):
        self.ketten.append(json.dumps(kwargs.get("messages"), ensure_ascii=False, default=str))
        return self._rest.pop(0)


@pytest.fixture
def welt(monkeypatch) -> _WloServer:
    """Agent-Modus mit der Vorgabe (``propose``), Schreibwerkzeuge im Katalog,
    keine angemeldete Person; DB-Grenzen ins Leere, MCP-Server gefälscht."""
    server = _WloServer()
    monkeypatch.setattr(transport, "call_tool", server.call_tool)
    monkeypatch.setattr(mcp_client, "_get_server_url_for_tool",
                        lambda _t: "https://mcp.invalid/mcp")

    monkeypatch.setattr(agent_mod, "load_engine",
                        lambda: EngineArea(mode="agent", agent=AgentLimits()))

    async def _keine_gesamtanleitung(_ueberschreibung=None):
        return None

    monkeypatch.setattr(agent_mod.master_skill, "prompt_block", _keine_gesamtanleitung)
    monkeypatch.setattr(agent_tools, "has_auth_token", lambda: True)
    monkeypatch.setattr(agent_write, "has_personal_auth", lambda: False)
    monkeypatch.setattr(agent_deckel, "has_personal_auth", lambda: False)
    monkeypatch.setattr(agent_mod, "has_personal_auth", lambda: False)

    async def _frei(*_a, **_k):
        return RateVerdict(allowed=True)

    async def _nichts(*_a, **_k):
        return None

    monkeypatch.setattr(pf_mod, "check_rate_limit", _frei)
    monkeypatch.setattr(pf_mod, "log_turn_quality", _nichts)
    monkeypatch.setattr(wa_mod, "update_session", _nichts)
    monkeypatch.setattr(wa_mod, "save_message", _nichts)
    return server


@pytest.fixture
def angemeldet(monkeypatch) -> None:
    """Eine angemeldete Person mit WLO-Rechten (Ticket oder persönlicher
    Zugang) — nur dann reicht der Chat-Zug die Abnahme in die Sitzung
    (Nutzer-Entscheid 2026-08-12, ``services/mcp/auth.has_personal_auth``)."""
    for modul in (agent_write, agent_deckel, agent_mod):
        monkeypatch.setattr(modul, "has_personal_auth", lambda: True)


def _zug(nachricht: str, *, entities: dict, verlauf: list | None = None):
    ctx = state_mod.TurnContext(req=ChatRequest(
        session_id="s-agent", message=nachricht,
        environment=Environment(locale="de"),
    ))
    ctx.env = ctx.req.environment.model_dump()
    ctx.history = list(verlauf or [])
    ctx.safety = SafetyDecision(risk_level="low")
    ctx.policy = PolicyDecision()
    ctx.classification = ClassificationResult()
    ctx.session_state = {"persona_id": "P-AND", "entities": entities}
    return ctx


def _zugwechsel(ctx) -> dict:
    """Was ``update_session`` speichert und ``setup`` im nächsten Zug lädt."""
    return json.loads(json.dumps(ctx.session_state.get("entities") or {}))


async def _chat_zug(ctx):
    """Ein Zug, wie der Graph ihn fährt: erst der Vorlauf, und nur ohne frühe
    Antwort die Schleife (``graph/build._after_preflight``)."""
    ctx = await preflight(ctx, _SITZUNG)
    if ctx.early_response is None:
        ctx = await respond_agent(ctx)
    return ctx


def _folgezug(nachricht: str, vorzug) -> object:
    return _zug(nachricht, entities=_zugwechsel(vorzug), verlauf=[
        {"role": "user", "content": _WUNSCH},
        {"role": "assistant", "content": vorzug.response_text},
    ])


def _drehbuch_zug_1() -> list:
    return [
        _werkzeug_antwort(_WERKZEUG, _ARGS, "c1"),
        _text_antwort("Ich kann die Sammlung „Bruchrechnen“ anlegen. Soll ich?"),
    ]


async def test_ja_im_folgezug_fuehrt_die_gezeigte_aenderung_aus(welt, angemeldet, monkeypatch):
    """Der gemeldete Fall, Ende zu Ende über zwei Züge."""
    monkeypatch.setattr(llm, "chat_completion", _Modell([
        *_drehbuch_zug_1(),
        # Zug 2 — nur erreicht, wenn der Vorlauf das „ja“ nicht einlöst: das
        # Modell tut, was es kann, und ruft dasselbe Werkzeug noch einmal.
        _werkzeug_antwort(_WERKZEUG, _ARGS, "c2"),
        _text_antwort("Soll ich die Sammlung „Bruchrechnen“ anlegen?"),
    ]))

    zug1 = await _chat_zug(_zug(_WUNSCH, entities={}))
    # Voraussetzung: die Vorschau ist geholt, geschrieben ist nichts.
    assert welt.aufrufe == [(_WERKZEUG, _ARGS, False)]
    assert welt.ausgefuehrt == []

    zug2 = await _chat_zug(_folgezug("ja", zug1))

    assert welt.ausgefuehrt == [(_WERKZEUG, _ARGS)], (
        "Nach „ja“ wurde nichts ausgeführt. "
        f"Vorlauf hat eingelöst: {zug2.early_response is not None}; "
        f"Server-Aufrufe (Werkzeug, Argumente, mit Schlüssel): {welt.aufrufe}; "
        f"Antwort im Folgezug: {zug2.response_text!r}"
    )


async def test_der_agent_zug_legt_vorschau_box_und_merkposten_an(welt, angemeldet,
                                                                 monkeypatch):
    """Dieselben zwei Stellen, die ``tool_loop`` setzt: ``_write_preview`` speist
    Box und Zustimmungs-Knopf (``turn_persist``), ``_pending_write`` die
    Abnahme im nächsten Zug (``write_approval``)."""
    monkeypatch.setattr(llm, "chat_completion", _Modell(_drehbuch_zug_1()))

    zug1 = await _chat_zug(_zug(_WUNSCH, entities={}))

    vorschau = zug1.session_state.get("_write_preview") or ""
    merkposten = (zug1.session_state.get("entities") or {}).get("_pending_write") or {}
    assert "Die Sammlung „Bruchrechnen“ wird angelegt." in vorschau, (
        f"Keine Vorschau-Box: _write_preview = {vorschau!r}")
    # Die Box sieht ein Mensch, und sie wird gespeichert — der Schlüssel nicht.
    assert extract_confirm_token(vorschau) is None
    assert merkposten.get("tool") == _WERKZEUG, (
        f"Kein Merkposten für den Folgezug: entities = "
        f"{sorted((zug1.session_state.get('entities') or {}).keys())}")
    assert merkposten.get("args") == _ARGS


async def test_ohne_zustimmung_wird_nichts_ausgefuehrt_und_das_modell_sieht_keinen_schluessel(
        welt, monkeypatch):
    """Die Zusicherung, die heute gilt und nach dem Umbau weiter gelten muss:
    ein „nein“ führt nichts aus, und kein geprägter Schlüssel erreicht je die
    Kette des Modells — auch nicht über einen gespeicherten Merkposten."""
    modell = _Modell([
        *_drehbuch_zug_1(),
        _text_antwort("Alles klar, ich lege nichts an."),
    ])
    monkeypatch.setattr(llm, "chat_completion", modell)

    zug1 = await _chat_zug(_zug(_WUNSCH, entities={}))
    await _chat_zug(_folgezug("Nein, doch nicht", zug1))

    assert welt.ausgefuehrt == []
    assert welt.gepraegt, "Voraussetzung: der Server hat einen Schlüssel geprägt"
    alle_ketten = "\n".join(modell.ketten)
    assert not any(s in alle_ketten for s in welt.gepraegt)


async def test_ohne_anmeldung_bleibt_es_bei_der_vorschau(welt, monkeypatch):
    """Review Paket 2, Befund 1: ohne angemeldete Person liefe das „ja“ unter
    dem Dienstkonto der Anlage (Audit B-H3) — gegen den Nutzer-Entscheid
    2026-08-12, dass nur schreibt, wer selbst WLO-Rechte hat. Also weder Box
    noch Merkposten, und ein „ja“ im Folgezug führt nichts aus."""
    monkeypatch.setattr(llm, "chat_completion", _Modell([
        *_drehbuch_zug_1(),
        _werkzeug_antwort(_WERKZEUG, _ARGS, "c2"),
        _text_antwort("Soll ich die Sammlung „Bruchrechnen“ anlegen?"),
    ]))

    zug1 = await _chat_zug(_zug(_WUNSCH, entities={}))
    assert not zug1.session_state.get("_write_preview")
    assert "_pending_write" not in (zug1.session_state.get("entities") or {})

    zug2 = await _chat_zug(_folgezug("ja", zug1))
    assert zug2.early_response is None
    assert welt.ausgefuehrt == []


async def test_ein_ja_ohne_die_anmeldung_des_vorzugs_fuehrt_nichts_aus(
        welt, angemeldet, monkeypatch):
    """Paket 4, A1 (Gegenprüfung des externen Audits, F05): Gemerkt wird nur mit
    Anmeldung — eingelöst wurde aber ohne Blick auf die Identität. Ein „ja“ im
    Folgezug OHNE persönlichen Block lief dann mit dem Dienst-Block und dem
    Schlüssel, den die angemeldete Person ausgelöst hatte. Der Vorgang gehört
    dem Aufrufer, der ihn auslöste."""
    monkeypatch.setattr(llm, "chat_completion", _Modell([
        *_drehbuch_zug_1(),
        _text_antwort("Dafür musst du angemeldet sein."),
    ]))
    monkeypatch.setattr(agent_write, "caller_fingerprint", lambda: "person-a")

    zug1 = await _chat_zug(_zug(_WUNSCH, entities={}))
    assert (zug1.session_state.get("entities") or {}).get("_pending_write"), (
        "Voraussetzung: der angemeldete Zug hat einen Vorgang gemerkt")

    # Zug 2: dieselbe Sitzung, aber ohne die Anmeldung von Zug 1.
    for modul in (agent_write, agent_deckel, agent_mod):
        monkeypatch.setattr(modul, "has_personal_auth", lambda: False)
    monkeypatch.setattr(agent_write, "caller_fingerprint", lambda: "")
    monkeypatch.setattr(wa_mod, "caller_fingerprint", lambda: "")

    zug2 = await _chat_zug(_folgezug("ja", zug1))
    assert zug2.early_response is None
    assert welt.ausgefuehrt == []
