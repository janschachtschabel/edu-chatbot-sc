"""Der Handschlag des Chat-Stroms (Review Paket 7, A-7 und C-4).

Bricht der Strom nach ``connected`` ab, rechnet der Zug zu Ende und das Widget holt
die Antwort aus dem Verlauf (P2). Der ``connected``-Rahmen sagt ihm dafür,

- ob die Antwort dort überhaupt ankommt (``history``; mit
  ``privacy-config.logging.messages: false`` nie — dann fällt das Widget wie vor
  Paket 7 auf ``POST /api/chat`` zurück, und der Zug bricht beim Auflegen ab), und
- welche Nachrichten-ID die letzte VOR dem Zug war (``after_id``) — sonst hielte es
  eine frühere Antwort auf dieselbe Frage („Ja“) für die neue.
"""

from __future__ import annotations

import asyncio
import contextlib
import json

import boerdi.api.chat as chat_api
import boerdi.api.chat_handschlag as handschlag_mod
import boerdi.api.sse as sse_api
from boerdi.api.schemas import ChatRequest, ChatResponse


def _fabrik(log: list | None = None):
    @contextlib.asynccontextmanager
    async def _sitzung():
        if log is not None:
            log.append("open")
        yield object()

    return _sitzung


def _verlauf(monkeypatch, *, gespeichert: bool = True, letzte=None, fehler=None, log=None):
    """``messages``-Schalter und der Blick auf die letzte Nachricht, ohne DB."""
    monkeypatch.setattr(handschlag_mod, "messages_enabled", lambda: gespeichert)

    async def _letzte(session, session_id):
        if log is not None:
            log.append(("lesen", session_id))
        if fehler is not None:
            raise fehler
        return letzte

    # Paket 9: nur die ID, nicht die ganze letzte Nachricht (``last_message_id``).
    monkeypatch.setattr(handschlag_mod, "last_message_id", _letzte)


async def test_der_handschlag_nennt_die_letzte_id_vor_dem_zug(monkeypatch):
    _verlauf(monkeypatch, letzte=41)
    assert await handschlag_mod.handschlag("bb-1", _fabrik()) == {"history": True, "after_id": 41}


async def test_eine_neue_sitzung_beginnt_bei_null(monkeypatch):
    _verlauf(monkeypatch, letzte=None)
    assert await handschlag_mod.handschlag("bb-1", _fabrik()) == {"history": True, "after_id": 0}


async def test_ohne_gespeicherten_verlauf_meldet_er_das_und_liest_nichts(monkeypatch):
    log: list = []
    _verlauf(monkeypatch, gespeichert=False, log=log)
    daten = await handschlag_mod.handschlag("bb-1", _fabrik(log))
    assert daten == {"history": False, "after_id": None}
    assert log == []                      # keine Sitzung, keine Abfrage


async def test_scheitert_der_blick_bleibt_nur_die_id_offen(monkeypatch):
    """Dann ordnet das Widget wie vor dem Review nur über den Text zu."""
    _verlauf(monkeypatch, fehler=RuntimeError("db weg"))
    assert await handschlag_mod.handschlag("bb-1", _fabrik()) == {"history": True, "after_id": None}


async def test_ein_haengender_blick_haelt_den_handschlag_nicht_auf(monkeypatch):
    _verlauf(monkeypatch, letzte=3)

    async def _haengt(session, session_id):
        await asyncio.sleep(5)

    monkeypatch.setattr(handschlag_mod, "last_message_id", _haengt)
    monkeypatch.setattr(handschlag_mod, "_FRIST_S", 0.05)
    async with asyncio.timeout(1):
        daten = await handschlag_mod.handschlag("bb-1", _fabrik())
    assert daten == {"history": True, "after_id": None}


# ── im Strom ─────────────────────────────────────────────────────────────────

class _Req:
    def __init__(self, *, disconnected=False):
        self._disconnected = disconnected

    async def is_disconnected(self):
        return self._disconnected


class _GatedGraph:
    def __init__(self, log: list | None = None):
        self.frei = asyncio.Event()
        self.abgebrochen = False
        self._log = log

    async def ainvoke(self, state):
        if self._log is not None:
            self._log.append("zug")
        try:
            await self.frei.wait()
        except asyncio.CancelledError:
            self.abgebrochen = True
            raise
        return {"response": ChatResponse(session_id="bb-1", content="FERTIG")}


def _zug(monkeypatch, graph) -> None:
    @contextlib.asynccontextmanager
    async def _sperre(request, session_id):
        yield

    monkeypatch.setattr(chat_api, "sitzung_sperren", _sperre)
    monkeypatch.setattr(chat_api, "build_turn_graph", lambda **k: graph)
    monkeypatch.setattr(chat_api, "peer_ip", lambda request: "7.7.7.7")
    monkeypatch.setattr(sse_api, "KEEPALIVE_SECONDS", 0.01)


def _req():
    return ChatRequest.model_validate({"session_id": "bb-1", "message": "Ja", "environment": {}})


def _daten(frame: str) -> dict:
    kopf, daten = frame.strip().split("\n", 1)
    assert kopf == "event: connected"
    return json.loads(daten.removeprefix("data: "))


async def test_der_connected_rahmen_traegt_den_handschlag(monkeypatch):
    graph = _GatedGraph()
    graph.frei.set()
    _zug(monkeypatch, graph)
    _verlauf(monkeypatch, letzte=12)
    frames = [f async for f in chat_api._stream_turn(_req(), _Req(), _fabrik())]
    assert _daten(frames[0]) == {"history": True, "after_id": 12}


async def test_gelesen_wird_vor_dem_start_des_zuges(monkeypatch):
    """Danach könnte der Zug die Frage schon gespeichert haben — die ID läge dann
    hinter ihr, und das Widget fände sie nie."""
    log: list = []
    graph = _GatedGraph(log)
    graph.frei.set()
    _zug(monkeypatch, graph)
    _verlauf(monkeypatch, letzte=12, log=log)
    [f async for f in chat_api._stream_turn(_req(), _Req(), _fabrik())]
    assert log == [("lesen", "bb-1"), "zug"]


async def test_ohne_verlauf_bricht_das_auflegen_den_zug_ab(monkeypatch):
    """Kein Verlauf, aus dem das Widget nachlädt: es schickt die Frage per POST
    noch einmal. Rechnete der erste Zug weiter, hielte er die Sitzungssperre,
    und der zweite Versand hörte „beschäftigt“."""
    graph = _GatedGraph()
    _zug(monkeypatch, graph)
    _verlauf(monkeypatch, gespeichert=False)
    frames = [f async for f in chat_api._stream_turn(_req(), _Req(disconnected=True), _fabrik())]
    assert [_daten(f) for f in frames] == [{"history": False, "after_id": None}]
    assert graph.abgebrochen


async def test_mit_verlauf_rechnet_der_zug_nach_dem_auflegen_zu_ende(monkeypatch):
    graph = _GatedGraph()
    _zug(monkeypatch, graph)
    _verlauf(monkeypatch, letzte=12)
    frames = [f async for f in chat_api._stream_turn(_req(), _Req(disconnected=True), _fabrik())]
    assert [_daten(f) for f in frames] == [{"history": True, "after_id": 12}]
    assert not graph.abgebrochen
    graph.frei.set()
    async with asyncio.timeout(2):            # den Nachläufer auslaufen lassen
        while sse_api._NACHLAEUFER:
            await asyncio.sleep(0.01)
