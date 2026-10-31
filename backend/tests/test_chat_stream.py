"""R4f-2: POST /api/chat/stream — the SSE sibling of /api/chat.

Same turn pipeline (``build_turn_graph`` under the per-session lock), but the
response is a Server-Sent-Events stream: a ``connected`` handshake, periodic
keepalives while the turn runs, and a final ``result`` (or ``error``) frame.

Since C9 the stream also carries ``phase`` frames: the graph gets a
``TurnProgress`` bound to a queue, and this generator drains that queue while the
turn runs. The frame byte-format is contract (spec rule 6):
``event: connected\\ndata: <json>\\n\\n`` (the handshake, ``chat_handschlag``),
``event: phase\\ndata: <json>\\n\\n``,
``: keepalive\\n\\n``, ``event: result\\ndata: <json>\\n\\n``,
``event: error\\ndata: <json>\\n\\n``.

Endpoint wiring (content-type, connected + result in the body, error frame) is
exercised through TestClient; the keepalive / disconnect-cancel cost-control
logic is driven directly against ``_stream_turn`` with a fake request, because
TestClient reads the whole stream and never disconnects mid-turn.

``TestClient`` is used WITHOUT a ``with`` block (as in test_chat_endpoint.py):
the lifespan would need a real Postgres; ``get_session`` is overridden instead.
"""

from __future__ import annotations

import asyncio
import json
import logging

import pytest
from fastapi.testclient import TestClient

import boerdi.api.chat as chat_api
import boerdi.api.sse as sse_api
from boerdi.api.deps import get_session_factory
from boerdi.api.schemas import ChatRequest, ChatResponse
from boerdi.main import create_app
from boerdi.obs.progress import TurnProgress
from boerdi.settings import get_settings

#: Paket 19 (N-9): öffentliche Kennungen brauchen mindestens 16 Zeichen.
SID = "bb-0123456789abcdef"

_SESSION = object()  # sentinel: the session the turn opens must reach build_turn_graph

#: Der Handschlag dieses Moduls (Review Paket 7, A-7/C-4). Der echte liest den
#: Verlauf — geprüft in ``test_chat_handschlag.py``; hier fest, damit die
#: Rahmen-Tests nicht an einer Datenbank hängen.
_CONNECTED = 'event: connected\ndata: {"history": true, "after_id": 7}\n\n'


@pytest.fixture(autouse=True)
def _fester_handschlag(monkeypatch):
    async def _fest(session_id, sitzungen):
        return {"history": True, "after_id": 7}

    monkeypatch.setattr(chat_api, "handschlag", _fest)


def _fabrik(log: list | None = None):
    """Stand-in for ``app.state.session_factory`` (Review A-1): the stream turn
    opens its OWN session — the request-scoped one closes when the response ends,
    while the turn may still be finishing (P2)."""
    import contextlib

    @contextlib.asynccontextmanager
    async def _sitzung():
        if log is not None:
            log.append("open")
        try:
            yield _SESSION
        finally:
            if log is not None:
                log.append("close")

    return _sitzung


def _ok(content="X"):
    """A normal-path graph state dict carrying a ChatResponse under ``response``."""
    return {"response": ChatResponse(session_id=SID, content=content)}


def _req():
    """A ChatRequest seeded exactly like the HTTP body in the TestClient tests."""
    return ChatRequest.model_validate(
        {"session_id": SID, "message": "hallo", "environment": {}}
    )


class _FakeGraph:
    """Stand-in compiled graph: ``ainvoke`` returns a preset state dict or raises."""

    def __init__(self, *, result=None, exc=None):
        self._result, self._exc = result, exc

    async def ainvoke(self, state):
        if self._exc is not None:
            raise self._exc
        return self._result


class _Req:
    """Minimal Request stand-in for _stream_turn (peer_ip is patched out)."""

    def __init__(self, *, disconnected=False):
        self._disconnected = disconnected

    async def is_disconnected(self):
        return self._disconnected


async def _passthrough_pp(req, resp, *a, **k):
    return resp


async def _drain(agen):
    return [chunk async for chunk in agen]


def _patch(monkeypatch, *, result=None, exc=None):
    """Fake build_turn_graph / peer_ip / widget-postprocess on the chat module."""
    graph = _FakeGraph(result=result, exc=exc)
    builds: list[dict] = []

    def _fake_build(*, session, peer_ip="", on_token=None, progress=None,
                    engine="pattern"):
        builds.append({
            "session": session, "peer_ip": peer_ip,
            "on_token": on_token, "progress": progress,
        })
        return graph

    monkeypatch.setattr(chat_api, "build_turn_graph", _fake_build)
    monkeypatch.setattr(chat_api, "peer_ip", lambda request: "7.7.7.7")
    monkeypatch.setattr(chat_api, "_postprocess_response_for_widget_modes", _passthrough_pp)
    return graph, builds


def _fake_locks(monkeypatch, *, beschaeftigt: bool = False):
    """Isolate the per-session lock (seit Paket 7, P1, die Naht ``sitzung_sperren``)
    and record acquire/release order — or report the session as busy."""
    import contextlib

    from boerdi.services.sitzungssperre import SitzungBeschaeftigt

    events: list = []

    @contextlib.asynccontextmanager
    async def _fake(request, session_id):
        if beschaeftigt:
            raise SitzungBeschaeftigt(session_id)
        events.append(("acquire", session_id))
        try:
            yield
        finally:
            events.append(("release", session_id))

    monkeypatch.setattr(chat_api, "sitzung_sperren", _fake)
    return events


async def test_eine_beschaeftigte_sitzung_meldet_das_im_strom(monkeypatch):
    """Paket 7 (P1): im Strom steht der HTTP-Status schon fest — die Kennung
    reist im ``error``-Rahmen, das Widget zeigt dazu seinen eigenen Text."""
    _patch(monkeypatch, result=_ok())
    _fake_locks(monkeypatch, beschaeftigt=True)
    frames = await _drain(chat_api._stream_turn(_req(), _Req(), _fabrik()))
    fehler = [f for f in frames if f.startswith("event: error")]
    assert fehler and '"code": "session_busy"' in fehler[0]


async def test_eine_beschaeftigte_sitzung_ist_keine_warnung(monkeypatch, caplog):
    """Paket 9 (Review Paket 7, NIT): ein Doppelversand oder ein Ping während eines
    Zugs ist erwartbar — er steht auf INFO im Log, nicht zwischen echten Fehlern."""
    import logging

    _patch(monkeypatch, result=_ok())
    _fake_locks(monkeypatch, beschaeftigt=True)
    with caplog.at_level(logging.INFO, logger="boerdi.api.sse"):
        await _drain(chat_api._stream_turn(_req(), _Req(), _fabrik()))
    eintraege = [r for r in caplog.records if r.name == "boerdi.api.sse"]
    assert eintraege and all(r.levelno == logging.INFO for r in eintraege)


class _Gespeichert:
    def __init__(self):
        self.calls: list[tuple] = []

    async def __call__(self, session, session_id, role, content, **kw):
        self.calls.append((session_id, role, content, kw))


async def test_ein_gescheiterter_zug_hinterlaesst_die_fehlerblase_im_verlauf(monkeypatch):
    """Review Paket 7 (MINOR 28): rechnete ein Zug nach dem Auflegen weiter und
    scheiterte, stand im Verlauf die Frage ohne Antwort — das Widget fragte bis zur
    Frist nach. Der POST-Weg speichert die Blase seit jeher."""
    _patch(monkeypatch, exc=RuntimeError("boom"))
    _fake_locks(monkeypatch)
    gespeichert = _Gespeichert()
    monkeypatch.setattr(chat_api, "save_message", gespeichert)
    frames = await _drain(chat_api._stream_turn(_req(), _Req(), _fabrik()))
    assert any(f.startswith("event: error") for f in frames)
    assert [(sid, rolle) for sid, rolle, _t, _k in gespeichert.calls] == [(SID, "assistant")]
    assert "boom" not in gespeichert.calls[0][2]      # der Satz, nicht das Innenleben


async def test_ausgelastet_im_strom_ist_dieselbe_blase_wie_im_verlauf(monkeypatch, caplog):
    """Audit N-22: entkam ``LlmAusgelastet`` dem Graphen, stand im Verlauf die „ausgelastet“-
    Blase ohne Nummer, der Strom meldete aber einen Fehler MIT Nummer. Jetzt geht die Blase
    als ``result`` hinaus — samt „Nochmal versuchen“, ohne Traceback im Log."""
    from boerdi.i18n.bot_text import bot_text
    from boerdi.services.llm_parallel import LlmAusgelastet

    _patch(monkeypatch, exc=LlmAusgelastet("kein Platz"))
    _fake_locks(monkeypatch)
    gespeichert = _Gespeichert()
    monkeypatch.setattr(chat_api, "save_message", gespeichert)
    with caplog.at_level(logging.DEBUG):
        frames = await _drain(chat_api._stream_turn(_req(), _Req(), _fabrik()))
    assert not any(f.startswith("event: error") for f in frames)
    ergebnis = next(f for f in frames if f.startswith("event: result"))
    daten = json.loads(ergebnis.split("data: ", 1)[1])
    assert daten["content"] == bot_text("de", "error.llmBusy") == gespeichert.calls[0][2]
    assert daten["quick_replies"] == [bot_text("de", "error.retryChip")]
    # Ohne Traceback (die DEBUG-Zeile zum Rollback der Attrappen-Sitzung zählt nicht).
    assert not any(r.exc_info for r in caplog.records if r.levelno >= logging.INFO)


async def test_ein_hintergrund_ping_hinterlaesst_keine_blase(monkeypatch):
    _patch(monkeypatch, exc=RuntimeError("boom"))
    _fake_locks(monkeypatch)
    gespeichert = _Gespeichert()
    monkeypatch.setattr(chat_api, "save_message", gespeichert)
    req = ChatRequest.model_validate({"session_id": SID, "message": "[context-open]",
                                      "environment": {"page_event": "context_open"}})
    await _drain(chat_api._stream_turn(req, _Req(), _fabrik()))
    assert gespeichert.calls == []


# ── Endpoint via TestClient ─────────────────────────────────────────────────

@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_CHAT", "off")  # deterministic: no limiter interference
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_session_factory] = lambda: _fabrik()
    yield TestClient(app)
    get_settings.cache_clear()


def _post(client):
    body = {"session_id": SID, "message": "hallo", "environment": {}}
    return client.post("/api/chat/stream", json=body)


def test_content_type_is_event_stream(monkeypatch, client):
    _patch(monkeypatch, result=_ok("HI"))
    r = _post(client)
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]


def test_connected_is_first_frame(monkeypatch, client):
    _patch(monkeypatch, result=_ok("HI"))
    r = _post(client)
    assert r.text.startswith(_CONNECTED)


def test_result_frame_carries_the_response(monkeypatch, client):
    _patch(monkeypatch, result=_ok("HI"))
    r = _post(client)
    assert "event: result\n" in r.text
    assert "HI" in r.text


def test_early_response_wins_in_stream(monkeypatch, client):
    _patch(monkeypatch, result={
        "early_response": ChatResponse(session_id=SID, content="EARLY"),
        "response": ChatResponse(session_id=SID, content="NORMAL"),
    })
    r = _post(client)
    assert "EARLY" in r.text
    assert "NORMAL" not in r.text


# ── C5-a: der Zugangsblock gilt auch im Strom ───────────────────────────────
#
# Eigener Pin, weil der Strom einen anderen Weg nimmt als ``/api/chat``: der Zug
# läuft in einer per ``create_task`` erzeugten Task. Die erbt den Kontext beim
# Erzeugen — das ist genau die Eigenschaft, die hier belegt wird.


def test_der_block_gilt_auch_im_gestreamten_zug(monkeypatch, client):
    from pydantic import SecretStr

    from boerdi.services.mcp.http_fabrik import build_http_client_factory

    monkeypatch.setattr(get_settings(), "mcp_auth_token", SecretStr(""),
                        raising=False)
    gesehen: dict[str, str] = {}

    class _Graph:
        async def ainvoke(self, state):
            gesehen["auth"] = build_http_client_factory()().headers.get(
                "authorization", "")
            return _ok("HI")

    monkeypatch.setattr(chat_api, "build_turn_graph", lambda **k: _Graph())
    monkeypatch.setattr(chat_api, "peer_ip", lambda request: "7.7.7.7")
    monkeypatch.setattr(chat_api, "_postprocess_response_for_widget_modes",
                        _passthrough_pp)

    client.post(
        "/api/chat/stream",
        json={"session_id": SID, "message": "hallo", "environment": {}},
        headers={"WLO-Access-Block": "wlo2.person-y"},
    )
    assert gesehen["auth"] == "Bearer wlo2.person-y"


def test_error_frame_on_graph_exception(monkeypatch, client):
    _patch(monkeypatch, exc=RuntimeError("boom"))
    r = _post(client)
    assert r.status_code == 200  # SSE is always 200; failure is an ``error`` frame
    assert "event: error\n" in r.text
    # Audit 2026-09-29 A-M4: kein Innenleben (Typ, Text der Ausnahme) an
    # anonyme Clients — das Widget zeigt ohnehin seinen eigenen Fehlertext.
    assert "RuntimeError" not in r.text
    assert "boom" not in r.text
    assert "event: result" not in r.text


def test_widget_postprocess_is_applied_to_result(monkeypatch, client):
    _patch(monkeypatch, result=_ok("RAW"))

    async def _transform(req, resp, *a, **k):
        return ChatResponse(session_id=resp.session_id, content="POSTPROCESSED")

    monkeypatch.setattr(chat_api, "_postprocess_response_for_widget_modes", _transform)
    r = _post(client)
    assert "POSTPROCESSED" in r.text
    assert "RAW" not in r.text


# ── _stream_turn generator (fakes, no HTTP) ─────────────────────────────────

async def test_stream_binds_session_peer_ip_and_a_token_stream_by_default(monkeypatch):
    from boerdi.services.token_stream import TokenStrom
    monkeypatch.delenv("CHAT_TOKEN_STREAMING", raising=False)
    get_settings.cache_clear()
    _, builds = _patch(monkeypatch, result=_ok())
    _fake_locks(monkeypatch)
    frames = await _drain(chat_api._stream_turn(_req(), _Req(), _fabrik()))
    assert builds[0]["session"] is _SESSION
    assert builds[0]["peer_ip"] == "7.7.7.7"
    # Paket 7 (S2, Nutzer-Entscheid 2026-10-09): Vorgabe an — ohne Umgebung und
    # ohne Studio-Eintrag legt der Endpunkt den Strom an.
    assert isinstance(builds[0]["on_token"], TokenStrom)
    assert frames[0] == _CONNECTED


@pytest.mark.parametrize(("umgebung", "studio"), [(None, False), ("0", True)])
async def test_studio_oder_umgebung_schalten_den_strom_ab(monkeypatch, umgebung, studio):
    """Paket 7 (S2): im Studio abschaltbar (``betrieb.token_streaming``); eine
    gesetzte Umgebung geht vor — auch gegen ein eingeschaltetes Studio."""
    from boerdi.domain.config_models.engine import EngineArea
    from boerdi.services import betriebsschalter
    if umgebung is None:
        monkeypatch.delenv("CHAT_TOKEN_STREAMING", raising=False)
    else:
        monkeypatch.setenv("CHAT_TOKEN_STREAMING", umgebung)
    get_settings.cache_clear()
    monkeypatch.setattr(betriebsschalter, "load_engine", lambda: EngineArea.model_validate(
        {"betrieb": {"token_streaming": studio}}))
    _, builds = _patch(monkeypatch, result=_ok())
    _fake_locks(monkeypatch)
    await _drain(chat_api._stream_turn(_req(), _Req(), _fabrik()))
    get_settings.cache_clear()
    assert builds[0]["on_token"] is None


async def test_mit_schalter_bindet_der_stream_einen_tokenstrom(monkeypatch):
    """Plan Token-Streaming, T12: nur mit ``CHAT_TOKEN_STREAMING`` legt der
    Endpunkt den Strom an — eine Instanz je Anfrage."""
    from boerdi.services.token_stream import TokenStrom
    monkeypatch.setenv("CHAT_TOKEN_STREAMING", "1")
    get_settings.cache_clear()
    _, builds = _patch(monkeypatch, result=_ok())
    _fake_locks(monkeypatch)
    await _drain(chat_api._stream_turn(_req(), _Req(), _fabrik()))
    get_settings.cache_clear()
    assert isinstance(builds[0]["on_token"], TokenStrom)


async def test_der_abschluss_misst_den_strom_gegen_das_ergebnis(monkeypatch, caplog):
    monkeypatch.setenv("CHAT_TOKEN_STREAMING", "1")
    get_settings.cache_clear()
    holder: dict = {}

    class _StreamenderGraph:
        async def ainvoke(self, state):
            strom = holder["on_token"]
            strom.oeffnen(lambda t: t, muster="M04")
            strom("Hallo Welt")
            strom.schliessen()
            return _ok("Hallo Welt — mit Hinweis")

    def _build(**kw):
        holder["on_token"] = kw["on_token"]
        return _StreamenderGraph()

    monkeypatch.setattr(chat_api, "build_turn_graph", _build)
    monkeypatch.setattr(chat_api, "peer_ip", lambda request: "7.7.7.7")
    monkeypatch.setattr(chat_api, "_postprocess_response_for_widget_modes", _passthrough_pp)
    _fake_locks(monkeypatch)
    with caplog.at_level(logging.INFO):
        frames = await _drain(chat_api._stream_turn(_req(), _Req(), _fabrik()))
    get_settings.cache_clear()

    assert [f.split("\n", 1)[0] for f in frames] == [
        "event: connected", "event: text_delta", "event: result"]
    assert "Token-Strom: muster=M04" in caplog.text
    assert "drift=nein" in caplog.text


async def test_session_lock_acquired_and_released(monkeypatch):
    _patch(monkeypatch, result=_ok())
    events = _fake_locks(monkeypatch)
    await _drain(chat_api._stream_turn(_req(), _Req(), _fabrik()))
    assert ("acquire", SID) in events
    assert ("release", SID) in events


class _GatedGraph:
    """Ein Zug, der erst nach ``frei`` fertig wird — und merkt, ob man ihn abbricht."""

    def __init__(self):
        self.frei = asyncio.Event()
        self.abgebrochen = False

    async def ainvoke(self, state):
        try:
            await self.frei.wait()
        except asyncio.CancelledError:
            self.abgebrochen = True
            raise
        return _ok("FERTIG")


async def _bis(bedingung, frist_s: float = 2.0) -> None:
    ende = asyncio.get_running_loop().time() + frist_s
    while not bedingung():
        assert asyncio.get_running_loop().time() < ende, "Bedingung nie erreicht"
        await asyncio.sleep(0.01)


async def test_nach_dem_abbruch_rechnet_der_zug_zu_ende(monkeypatch):
    """Paket 7 (P2, P5-2): schließt jemand den Chat mitten in der Antwort, rechnet
    der Server sauber zu Ende — die Antwort steht dann im Verlauf, und das Widget
    holt sie von dort, statt die Frage ein zweites Mal zu schicken. Die Sperre
    hält bis zum Ende: ein erneutes Senden hört „beschäftigt“ statt doppelt zu
    rechnen. (Bis dahin brach der Abbruch den Zug ab.)"""
    graph = _GatedGraph()
    monkeypatch.setattr(chat_api, "build_turn_graph", lambda **k: graph)
    monkeypatch.setattr(chat_api, "peer_ip", lambda request: "7.7.7.7")
    monkeypatch.setattr(sse_api, "KEEPALIVE_SECONDS", 0.01)
    events = _fake_locks(monkeypatch)

    frames = await _drain(chat_api._stream_turn(_req(), _Req(disconnected=True), _fabrik()))

    assert frames == [_CONNECTED]  # kein result: niemand hört zu
    assert ("release", SID) not in events               # der Zug läuft noch
    graph.frei.set()
    await _bis(lambda: ("release", SID) in events)
    assert not graph.abgebrochen


async def test_auch_ein_geschlossener_strom_laesst_den_zug_zu_ende_rechnen(monkeypatch):
    """Starlette schließt den Generator, wenn das Senden scheitert — derselbe
    Abbruch auf anderem Weg."""
    graph = _GatedGraph()
    monkeypatch.setattr(chat_api, "build_turn_graph", lambda **k: graph)
    monkeypatch.setattr(chat_api, "peer_ip", lambda request: "7.7.7.7")
    monkeypatch.setattr(sse_api, "KEEPALIVE_SECONDS", 0.01)
    events = _fake_locks(monkeypatch)

    agen = chat_api._stream_turn(_req(), _Req(disconnected=False), _fabrik())
    await agen.__anext__()          # connected
    await agen.__anext__()          # keepalive — der Zug läuft
    await agen.aclose()
    assert ("release", SID) not in events
    graph.frei.set()
    await _bis(lambda: ("release", SID) in events)
    assert not graph.abgebrochen



async def test_der_nachlauf_rechnet_auf_einer_eigenen_sitzung_zu_ende(monkeypatch):
    """Review A-1: FastAPI schließt die anfragegebundene Sitzung, sobald die
    Antwort endet — beim Auflegen also mitten im Nachlauf. Der Zug öffnet seine
    Sitzung deshalb selbst und schließt sie erst nach dem letzten Schreiben."""
    graph = _GatedGraph()
    builds: list = []

    def _bau(**k):
        builds.append(k["session"])
        return graph

    monkeypatch.setattr(chat_api, "build_turn_graph", _bau)
    monkeypatch.setattr(chat_api, "peer_ip", lambda request: "7.7.7.7")
    monkeypatch.setattr(sse_api, "KEEPALIVE_SECONDS", 0.01)
    events = _fake_locks(monkeypatch)
    log: list = []

    await _drain(chat_api._stream_turn(_req(), _Req(disconnected=True), _fabrik(log)))

    assert log == ["open"]                       # der Strom ist zu, die Sitzung nicht
    assert builds == [_SESSION]
    graph.frei.set()
    await _bis(lambda: ("release", SID) in events)
    assert log == ["open", "close"]

async def test_im_agent_endpunkt_bricht_der_abbruch_weiter_ab():
    """``/api/agent`` hat keinen Verlauf, aus dem jemand nachlädt — dort spart
    der Abbruch weiter Kosten (Vorgabe von ``sse_turn``)."""
    lauf = _GatedGraph()

    async def _run(progress):
        return await lauf.ainvoke({})

    async def _payload(result):
        return {}

    frames = []
    alt = sse_api.KEEPALIVE_SECONDS
    sse_api.KEEPALIVE_SECONDS = 0.01
    try:
        async for frame in sse_api.sse_turn(_Req(disconnected=True), _run, _payload):
            frames.append(frame)
    finally:
        sse_api.KEEPALIVE_SECONDS = alt
    assert frames == ["event: connected\ndata: {}\n\n"]
    assert lauf.abgebrochen


async def test_im_agent_endpunkt_bricht_auch_ein_geschlossener_strom_ab():
    """Bis Paket 7 lief die Arbeit nach dem Schließen verwaist weiter — für den
    Agent-Endpunkt Kosten für niemanden."""
    lauf = _GatedGraph()

    async def _run(progress):
        return await lauf.ainvoke({})

    async def _payload(result):
        return {}

    alt = sse_api.KEEPALIVE_SECONDS
    sse_api.KEEPALIVE_SECONDS = 0.01
    try:
        agen = sse_api.sse_turn(_Req(disconnected=False), _run, _payload)
        await agen.__anext__()   # connected
        await agen.__anext__()   # keepalive
        await agen.aclose()
    finally:
        sse_api.KEEPALIVE_SECONDS = alt
    await _bis(lambda: lauf.abgebrochen)


# ── C9: phase frames ────────────────────────────────────────────────────────

def _patch_emitting(monkeypatch, steps):
    """Fake a graph that reports ``steps`` through the injected ``TurnProgress``.

    Proves the whole seam end to end: the endpoint builds a progress object, the
    graph writes into it mid-turn, and the generator turns that into SSE frames.
    """
    holder: dict = {}

    class _EmittingGraph:
        async def ainvoke(self, state):
            for step in steps:
                holder["progress"].start(step, f"L-{step}")
            return _ok("DONE")

    def _fake_build(*, session, peer_ip="", on_token=None, progress=None,
                    engine="pattern"):
        holder["progress"] = progress
        return _EmittingGraph()

    monkeypatch.setattr(chat_api, "build_turn_graph", _fake_build)
    monkeypatch.setattr(chat_api, "peer_ip", lambda request: "7.7.7.7")
    monkeypatch.setattr(chat_api, "_postprocess_response_for_widget_modes", _passthrough_pp)
    _fake_locks(monkeypatch)
    return holder


async def test_stream_binds_a_progress_object(monkeypatch):
    """Without a progress seam the graph has no way to report anything — pin that
    the stream always supplies one (POST /api/chat gets a sink-less default)."""
    _, builds = _patch(monkeypatch, result=_ok())
    _fake_locks(monkeypatch)
    await _drain(chat_api._stream_turn(_req(), _Req(), _fabrik()))
    assert isinstance(builds[0]["progress"], TurnProgress)


async def test_phase_frames_are_emitted_in_order_before_the_result(monkeypatch):
    _patch_emitting(monkeypatch, ["safety_classify", "pattern", "response"])
    frames = await _drain(chat_api._stream_turn(_req(), _Req(), _fabrik()))

    kinds = [f.split("\n", 1)[0] for f in frames]
    assert kinds == [
        "event: connected", "event: phase", "event: phase", "event: phase",
        "event: result",
    ]
    steps = [json.loads(f.split("data: ", 1)[1])["step"]
             for f in frames if f.startswith("event: phase")]
    assert steps == ["safety_classify", "pattern", "response"]


async def test_phase_payload_carries_the_four_contract_keys(monkeypatch):
    """``ui/stream/phase-label.ts`` reads ``data.kind`` and ``data.step``; ALT's
    listener shape (``chat.py:405``) is ``{kind, step, label, data}``."""
    _patch_emitting(monkeypatch, ["wlo_search"])
    frames = await _drain(chat_api._stream_turn(_req(), _Req(), _fabrik()))

    phase = next(f for f in frames if f.startswith("event: phase"))
    assert phase.endswith("\n\n")
    payload = json.loads(phase.split("data: ", 1)[1])
    assert payload == {
        "kind": "start", "step": "wlo_search", "label": "L-wlo_search", "data": {},
    }


async def test_umlauts_survive_the_phase_frame(monkeypatch):
    """The labels are German ("Lade Sitzungs-Kontext …") — no \\uXXXX escaping."""
    holder = _patch_emitting(monkeypatch, [])

    class _Umlaut:
        async def ainvoke(self, state):
            holder["progress"].record("context", "Lade Sitzungs-Kontext …")
            return _ok("DONE")

    monkeypatch.setattr(
        chat_api, "build_turn_graph",
        lambda **kw: (holder.__setitem__("progress", kw["progress"]), _Umlaut())[1],
    )
    frames = await _drain(chat_api._stream_turn(_req(), _Req(), _fabrik()))
    phase = next(f for f in frames if f.startswith("event: phase"))
    assert "Lade Sitzungs-Kontext …" in phase



async def test_text_ereignis_wird_text_delta_rahmen(monkeypatch):
    """Plan Token-Streaming, T5: ``TurnProgress.text`` wird zum Rahmen
    ``text_delta`` mit ``{"text", "pos"}`` — Name und ``text`` wie ALT, ``pos``
    neu. Er steht in Reihenfolge zwischen den ``phase``-Rahmen, und Umlaute
    bleiben lesbar."""
    holder = _patch_emitting(monkeypatch, [])

    class _Strom:
        async def ainvoke(self, state):
            holder["progress"].start("response", "Formuliere Antwort")
            holder["progress"].text("Grüße ", 0)
            holder["progress"].text("aus WLO", 6)
            return _ok("DONE")

    monkeypatch.setattr(
        chat_api, "build_turn_graph",
        lambda **kw: (holder.__setitem__("progress", kw["progress"]), _Strom())[1],
    )
    frames = await _drain(chat_api._stream_turn(_req(), _Req(), _fabrik()))

    kinds = [f.split("\n", 1)[0] for f in frames]
    assert kinds == ["event: connected", "event: phase", "event: text_delta",
                     "event: text_delta", "event: result"]
    deltas = [json.loads(f.split("data: ", 1)[1]) for f in frames
              if f.startswith("event: text_delta")]
    assert deltas == [{"text": "Grüße ", "pos": 0}, {"text": "aus WLO", "pos": 6}]
    assert "Grüße" in frames[2]

async def test_a_flooded_queue_drops_events_but_still_finishes_the_turn(monkeypatch):
    """Cost control (ALT ``Queue(maxsize=200)``): a slow client must not let the
    queue grow without bound. Overflow drops progress — never the answer."""
    monkeypatch.setattr(sse_api, "PROGRESS_QUEUE_MAX", 2)
    _patch_emitting(monkeypatch, [f"s{i}" for i in range(50)])
    frames = await _drain(chat_api._stream_turn(_req(), _Req(), _fabrik()))

    phases = [f for f in frames if f.startswith("event: phase")]
    assert 0 < len(phases) <= 2  # capped, not 50
    assert any(f.startswith("event: result\n") for f in frames)  # answer survived


async def test_progress_after_an_exception_still_yields_the_error_frame(monkeypatch):
    """A turn that reports progress and then blows up: the phases already sent
    must not swallow the ``error`` frame."""
    holder: dict = {}

    class _BoomGraph:
        async def ainvoke(self, state):
            holder["progress"].start("pattern", "Pattern selection")
            raise RuntimeError("boom")

    def _fake_build(*, session, peer_ip="", on_token=None, progress=None,
                    engine="pattern"):
        holder["progress"] = progress
        return _BoomGraph()

    monkeypatch.setattr(chat_api, "build_turn_graph", _fake_build)
    monkeypatch.setattr(chat_api, "peer_ip", lambda request: "7.7.7.7")
    _fake_locks(monkeypatch)

    frames = await _drain(chat_api._stream_turn(_req(), _Req(), _fabrik()))
    assert any(f.startswith("event: phase") for f in frames)
    assert any(f.startswith("event: error\n") for f in frames)


async def test_keepalive_emitted_during_slow_turn(monkeypatch):
    release = asyncio.Event()
    resp = ChatResponse(session_id=SID, content="DONE")

    class _GatedGraph:
        async def ainvoke(self, state):
            await release.wait()
            return {"response": resp}

    monkeypatch.setattr(chat_api, "build_turn_graph", lambda **k: _GatedGraph())
    monkeypatch.setattr(chat_api, "peer_ip", lambda request: "7.7.7.7")
    monkeypatch.setattr(chat_api, "_postprocess_response_for_widget_modes", _passthrough_pp)
    monkeypatch.setattr(sse_api, "KEEPALIVE_SECONDS", 0.01)
    _fake_locks(monkeypatch)

    agen = chat_api._stream_turn(_req(), _Req(disconnected=False), _fabrik())
    first = await agen.__anext__()   # connected handshake
    second = await agen.__anext__()  # turn still gated -> keepalive on timeout
    release.set()
    rest = await _drain(agen)        # turn completes -> result frame

    assert first == _CONNECTED
    assert second == ": keepalive\n\n"
    assert any(chunk.startswith("event: result\n") for chunk in rest)


# ── K2b: auch der Streaming-Weg bucht ───────────────────────────────────
# Eigener Test, obwohl der Trichter derselbe ist: die beiden Endpunkte haben
# je eine eigene ainvoke-Stelle, und genau solche Zweitwege sind in diesem
# Plan schon dreimal stumm geblieben.

def test_verbrauch_wird_auch_im_stream_geschrieben(monkeypatch, client):
    acc = {"models": {"m": {"prompt": 10, "completion": 5, "cached": 0,
                            "reasoning": 0, "calls": 1}}}
    _patch(monkeypatch, result={**_ok("HI"), "usage": acc})
    calls: list[tuple] = []

    async def _fake(session, session_id, uebergeben, engine=None):
        calls.append((session, session_id, uebergeben))
        return 1

    monkeypatch.setattr(chat_api, "record_turn_usage", _fake)
    assert _post(client).status_code == 200
    assert len(calls) == 1
    assert calls[0][0] is _SESSION and calls[0][1] == SID
    assert calls[0][2] is acc


def test_der_schluessel_des_proxys_gilt_auch_im_gestreamten_zug(monkeypatch, client):
    """Gesamt-Review Paket 17 (AB3): wie der Zugangsblock erbt die Task des Stroms den
    durchgereichten b-api-Schlüssel — wanderte die Übernahme in den Generator, buchte jeder
    gestreamte Zug still auf den Schlüssel der Anlage."""
    from boerdi.services import llm
    from boerdi.services.llm_router import get_chat_model

    monkeypatch.setenv("LLM_PROVIDER", "b-api-openai")
    monkeypatch.setenv("B_API_KEY", "schluessel-der-anlage")
    get_settings.cache_clear()
    gesehen: dict[str, str] = {}

    class _Graph:
        async def ainvoke(self, state):
            gesehen["schluessel"] = llm.route(get_chat_model())[2]
            return _ok("HI")

    monkeypatch.setattr(chat_api, "build_turn_graph", lambda **k: _Graph())
    monkeypatch.setattr(chat_api, "peer_ip", lambda request: "7.7.7.7")
    monkeypatch.setattr(chat_api, "_postprocess_response_for_widget_modes", _passthrough_pp)
    client.post("/api/chat/stream",
                json={"session_id": SID, "message": "hallo", "environment": {}},
                headers={"Authorization": "Bearer " + "s" * 36})
    assert gesehen["schluessel"] == "s" * 36


def test_auch_im_strom_sieht_die_fehlerblase_trace_id_und_zugakte(monkeypatch, client):
    """Paket 18C/D (1.7, R7): der Strom-Zug läuft als eigene Task — gebunden wird in ihr."""
    from tests.test_chat_endpoint import _kontext_beim_speichern, _scheitert_nach_einem_aufruf

    graph, _ = _patch(monkeypatch)
    _scheitert_nach_einem_aufruf(graph)
    gesehen = _kontext_beim_speichern(monkeypatch)
    r = client.post("/api/chat/stream",
                    json={"session_id": SID, "message": "hallo", "environment": {}},
                    headers={"x-client-trace-id": "zug-4711-abcdef"})
    assert "event: error\n" in r.text
    assert gesehen == [("zug-4711-abcdef", ["search_wlo_content"])]


def _ergebnis(antwort) -> dict:
    rahmen = [z for z in antwort.text.split("\n\n") if z.startswith("event: result")]
    return json.loads(rahmen[0].split("data: ", 1)[1])


def test_das_ergebnis_im_strom_traegt_nur_ui(monkeypatch, client):
    """Paket 18C/D: ``ui`` auch im ``result``-Rahmen; seit Phase 4 ohne Debug-Block."""
    from boerdi.api.schemas import DebugInfo

    _patch(monkeypatch, result={"response": ChatResponse(
        session_id=SID, content="x", debug=DebugInfo(pattern="M04"))})
    nutzlast = _ergebnis(_post(client))
    assert nutzlast["ui"]["pattern"] == "M04" and nutzlast["debug"] is None


def test_mit_studio_schluessel_traegt_der_strom_debug(monkeypatch, client):
    from boerdi.api.schemas import DebugInfo

    monkeypatch.setenv("STUDIO_API_KEY", "schluessel-1")
    get_settings.cache_clear()
    _patch(monkeypatch, result={"response": ChatResponse(
        session_id=SID, content="x", debug=DebugInfo(pattern="M04", persona="P-LEH"))})
    r = client.post("/api/chat/stream", json={"session_id": SID, "message": "hallo"},
                    headers={"X-Studio-Key": "schluessel-1"})
    assert _ergebnis(r)["debug"]["persona"] == "P-LEH"


def test_der_fehlerrahmen_nennt_die_fehlernummer(monkeypatch, client):
    """Review Phase 3: das Widget nutzt den Strom; ohne Nummer im ``error``-Rahmen sähe die
    Person sie erst nach dem Neuladen (in der gespeicherten Blase)."""
    _patch(monkeypatch, exc=RuntimeError("boom"))
    r = client.post("/api/chat/stream",
                    json={"session_id": SID, "message": "hallo", "environment": {}},
                    headers={"x-client-trace-id": "4f2a9c01d3b7e6a8"})
    rahmen = [z for z in r.text.split("\n\n") if z.startswith("event: error")]
    assert json.loads(rahmen[0].split("data: ", 1)[1]) == {
        "message": "internal error", "nummer": "4f2a9c01d3b7"}


async def test_ein_beschaeftigter_strom_braucht_keine_nummer(monkeypatch):
    _fake_locks(monkeypatch, beschaeftigt=True)
    frames = await _drain(chat_api._stream_turn(_req(), _Req(), _fabrik()))
    fehler = [f for f in frames if f.startswith("event: error")]
    assert "nummer" not in fehler[0]
