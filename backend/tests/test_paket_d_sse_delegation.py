"""Paket D (Plan 2026-11-17, E4/E6): Auflegen im Delegationsbetrieb und die Sätze dazu.

Seit Paket 7 (P2) rechnet ein Chat-Zug nach dem Auflegen zu Ende und speichert die Antwort im
Verlauf. Das Delegations-Token der b-api gilt aber nur, solange die eingehende Anfrage läuft —
nach dem Auflegen darf **kein** b-api-Aufruf mehr folgen. Der Zug endet dann beim nächsten
b-api-Aufruf (``KeinDelegationsToken``) und hinterlässt im Verlauf, was da ist: die Frage und
die fertige Antwort oder einen Vermerk („Verbindung brach ab“). Ohne Delegation bleibt alles,
wie es war. Eine 401 der b-api mit Delegations-Token heißt: die Anmeldung der Seite ist
abgelaufen — die Person soll neu laden, nicht eine Fehlernummer melden.
"""

from __future__ import annotations

import asyncio
import contextlib

import pytest

import boerdi.api.chat as chat_api
import boerdi.api.sse as sse_api
from boerdi.api.schemas import ChatRequest, ChatResponse
from boerdi.i18n.bot_text import bot_text
from boerdi.services import llm_auth
from boerdi.services.fehlertext import antwort_fehlertext

SID = "bb-0123456789abcdef"
TOKEN = "bdt_" + "t" * 120
SCHLUESSEL = "k" * 36


@pytest.fixture(autouse=True)
def _umgebung(monkeypatch):
    async def _fest(session_id, sitzungen):
        return {"history": True, "after_id": 7}

    monkeypatch.setattr(chat_api, "handschlag", _fest)
    monkeypatch.setattr(chat_api, "peer_ip", lambda request: "7.7.7.7")
    monkeypatch.setattr(sse_api, "KEEPALIVE_SECONDS", 0.01)
    llm_auth.setze_llm_schluessel(None)
    yield
    llm_auth.setze_llm_schluessel(None)


class _Req:
    def __init__(self, *, disconnected: bool) -> None:
        self._disconnected = disconnected

    async def is_disconnected(self) -> bool:
        return self._disconnected


class _Sitzung:
    async def rollback(self) -> None:
        pass


def _fabrik():
    @contextlib.asynccontextmanager
    async def _sitzung():
        yield _Sitzung()

    return _sitzung


def _sperren(monkeypatch) -> list:
    events: list = []

    @contextlib.asynccontextmanager
    async def _fake(request, session_id):
        events.append("acquire")
        try:
            yield
        finally:
            events.append("release")

    monkeypatch.setattr(chat_api, "sitzung_sperren", _fake)
    return events


class _BapiGraph:
    """Ein Zug mit zwei b-api-Aufrufen: einer vor dem Auflegen, einer erst nach ``frei``."""

    def __init__(self) -> None:
        self.frei = asyncio.Event()
        self.aufrufe: list[str] = []

    async def ainvoke(self, state):
        self.aufrufe.append(llm_auth.b_api_schluessel())
        await self.frei.wait()
        self.aufrufe.append(llm_auth.b_api_schluessel())
        return {"response": ChatResponse(session_id=SID, content="FERTIG")}


class _Gespeichert:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def __call__(self, session, session_id, role, content, **kw):
        self.calls.append((session_id, role, content))


async def _bis(bedingung, frist_s: float = 2.0) -> None:
    ende = asyncio.get_running_loop().time() + frist_s
    while not bedingung():
        assert asyncio.get_running_loop().time() < ende, "Bedingung nie erreicht"
        await asyncio.sleep(0.01)


def _req() -> ChatRequest:
    return ChatRequest.model_validate({"session_id": SID, "message": "hallo", "environment": {}})


async def _zug_mit_auflegen(monkeypatch, kopf: str, *, schliessen: bool = False):
    graph = _BapiGraph()
    monkeypatch.setattr(chat_api, "build_turn_graph", lambda **k: graph)
    events = _sperren(monkeypatch)
    gespeichert = _Gespeichert()
    monkeypatch.setattr(chat_api, "save_message", gespeichert)

    async def _keine_entities(session, session_id):
        return {}

    monkeypatch.setattr(chat_api, "sitzung_entities", _keine_entities)
    llm_auth.setze_llm_schluessel(kopf)
    if schliessen:
        # Starlette schließt den Generator, weil das Senden scheitert — derselbe Abbruch
        agen = chat_api._stream_turn(_req(), _Req(disconnected=False), _fabrik())
        await agen.__anext__()          # connected
        await agen.__anext__()          # keepalive — der Zug läuft
        await agen.aclose()
    else:
        _ = [f async for f in chat_api._stream_turn(_req(), _Req(disconnected=True), _fabrik())]
    assert "release" not in events      # der Zug läuft noch (Nachlauf)
    graph.frei.set()
    await _bis(lambda: "release" in events)
    return graph, gespeichert


@pytest.mark.parametrize("schliessen", [False, True], ids=["keepalive", "generator_zu"])
async def test_nach_dem_auflegen_folgt_mit_delegation_kein_b_api_aufruf(monkeypatch, schliessen):
    graph, gespeichert = await _zug_mit_auflegen(monkeypatch, f"Bearer {TOKEN}",
                                                 schliessen=schliessen)
    assert graph.aufrufe == [TOKEN]                    # nur der Aufruf vor dem Auflegen
    # Der Vermerk steht im Verlauf — das Widget findet ihn beim Nachladen
    assert gespeichert.calls == [(SID, "assistant", bot_text("de", "error.connectionLost"))]


async def test_ohne_delegation_rechnet_der_zug_wie_bisher_zu_ende(monkeypatch):
    graph, gespeichert = await _zug_mit_auflegen(monkeypatch, f"Bearer {SCHLUESSEL}")
    assert graph.aufrufe == [SCHLUESSEL, SCHLUESSEL]
    assert gespeichert.calls == []                     # keine Fehlerblase


async def test_ohne_kopf_rechnet_der_zug_wie_bisher_zu_ende(monkeypatch):
    graph, gespeichert = await _zug_mit_auflegen(monkeypatch, "")
    assert len(graph.aufrufe) == 2 and gespeichert.calls == []


async def test_das_auflegen_steht_ohne_token_im_log(monkeypatch, caplog):
    import logging

    with caplog.at_level(logging.INFO):
        await _zug_mit_auflegen(monkeypatch, f"Bearer {TOKEN}")
    assert TOKEN[:30] not in caplog.text
    assert "Delegation" in caplog.text
    # ein erwarteter Ausgang, kein Absturz mit Traceback
    assert not any(r.exc_info for r in caplog.records if r.name == chat_api.logger.name)


# ── D5: die Sätze ─────────────────────────────────────────────────────────────

class _Abgewiesen(Exception):
    status_code = 401


@pytest.mark.parametrize("sprache", ["de", "en"])
def test_eine_401_mit_delegation_bittet_ums_neuladen(sprache):
    llm_auth.setze_llm_schluessel(f"Bearer {TOKEN}")
    text = antwort_fehlertext(sprache, "error.answerFailed", fehler=_Abgewiesen("401"))
    assert text == bot_text(sprache, "error.delegationExpired")


def test_der_satz_zum_neuladen():
    assert bot_text("de", "error.delegationExpired") == (
        "Deine Anmeldung auf der Seite ist abgelaufen. Bitte lade die Seite neu.")
    assert "reload the page" in bot_text("en", "error.delegationExpired")


def test_eine_401_ohne_delegation_bleibt_der_fehler_mit_nummer():
    llm_auth.setze_llm_schluessel(f"Bearer {SCHLUESSEL}")
    text = antwort_fehlertext("de", "error.answerFailed", fehler=_Abgewiesen("401"))
    assert "Fehlernummer" in text


@pytest.mark.parametrize(("grund", "schluessel"), [
    ("beendet", "error.connectionLost"), ("unbrauchbar", "error.delegationExpired"),
])
@pytest.mark.parametrize("sprache", ["de", "en"])
def test_kein_token_ergibt_den_passenden_satz(grund, schluessel, sprache):
    text = antwort_fehlertext(sprache, "error.internal",
                              fehler=llm_auth.KeinDelegationsToken(grund))
    assert text == bot_text(sprache, schluessel)


def test_auch_ein_umhuelltes_ende_ergibt_den_vermerk():
    try:
        try:
            raise llm_auth.KeinDelegationsToken("beendet")
        except llm_auth.KeinDelegationsToken as innen:
            raise RuntimeError("Hülle") from innen
    except RuntimeError as huelle:
        text = antwort_fehlertext("de", "error.answerFailed", fehler=huelle)
    assert text == bot_text("de", "error.connectionLost")


# ── Nachtrag: der Agent-Weg (Koordinator 2026-11-18) ──────────────────────────

def test_der_agent_lauf_merkt_sich_den_llm_fehler(monkeypatch):
    """Die Schleife endet bei einem LLM-Fehler mit ``stop_reason="error"`` — die Ausnahme reist im
    Lauf mit, damit der Abschluss den passenden Satz wählt (nie im ``repr``)."""
    from tests.test_agent_loop import _lauf

    fehler = _Abgewiesen("401")
    _fake, run, _msgs = _lauf(monkeypatch, [], raises=fehler)
    assert run.stop_reason == "error"
    assert run.fehler is fehler
    assert "_Abgewiesen" not in repr(run)


@pytest.mark.parametrize("sprache", ["de", "en"])
def test_der_agent_weg_bittet_bei_401_mit_delegation_ums_neuladen(sprache):
    from boerdi.services.agent_abschluss import antwort_oder_ersatz
    from boerdi.services.agent_loop import AgentRun

    llm_auth.setze_llm_schluessel(f"Bearer {TOKEN}")
    lauf = AgentRun(stop_reason="error", fehler=_Abgewiesen("401"))
    assert antwort_oder_ersatz(lauf, sprache) == bot_text(sprache, "error.delegationExpired")


def test_der_agent_weg_ohne_delegation_behaelt_die_nummer():
    from boerdi.services.agent_abschluss import antwort_oder_ersatz
    from boerdi.services.agent_loop import AgentRun

    llm_auth.setze_llm_schluessel(f"Bearer {SCHLUESSEL}")
    lauf = AgentRun(stop_reason="error", fehler=_Abgewiesen("401"))
    assert "Fehlernummer" in antwort_oder_ersatz(lauf, "de")
