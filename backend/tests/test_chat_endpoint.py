"""R4f-1: POST /api/chat — the non-streaming endpoint = first-e2e-turn wiring.

The router's job is HTTP translation + turn-orchestration glue: build the
per-request turn graph, run it under the per-session lock, extract
``early_response or response`` from the state dict, apply the widget-modes
postprocess, and convert any unhandled graph error into a graceful chat bubble
(never HTTP 500). The graph and its nodes have their own suites, so these pins
fake ``build_turn_graph`` and patch the collaborators on the chat module —
deterministic and offline. The sentinel session doubles as proof that the DI
session reaches the graph builder.

``TestClient`` is used WITHOUT a ``with`` block on purpose (as in
test_rag_router.py): the context manager would run the lifespan, which needs a
real Postgres. ``get_session`` is overridden, so it is never called.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

import boerdi.api.chat as chat_api
from boerdi.api.deps import get_session
from boerdi.api.schemas import ChatResponse
from boerdi.main import create_app
from boerdi.settings import get_settings

_SESSION = object()  # sentinel: whatever get_session yields must reach build_turn_graph


def _ok(content="X"):
    """A normal-path graph result dict carrying a ChatResponse under ``response``."""
    return {"response": ChatResponse(session_id="bb-1", content=content)}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_CHAT", "off")  # deterministic: no limiter interference
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: _SESSION
    yield TestClient(app)
    get_settings.cache_clear()


class _FakeGraph:
    """Stand-in compiled graph: ``ainvoke`` returns a preset state dict or raises."""

    def __init__(self, *, result=None, exc=None):
        self._result, self._exc = result, exc
        self.invoked_with = None

    async def ainvoke(self, state):
        self.invoked_with = state
        if self._exc is not None:
            raise self._exc
        return self._result


def _patch(monkeypatch, *, result=None, exc=None):
    graph = _FakeGraph(result=result, exc=exc)
    builds: list[dict] = []

    def _fake_build(*, session, peer_ip="", on_token=None, engine="pattern"):
        builds.append({"session": session, "peer_ip": peer_ip, "on_token": on_token})
        return graph

    async def _fake_pp(req, resp, *a, **k):
        return resp

    saves: list[dict] = []

    async def _fake_save(session, session_id, role, content, **k):
        saves.append({"session": session, "session_id": session_id,
                      "role": role, "content": content, "debug": k.get("debug")})

    monkeypatch.setattr(chat_api, "build_turn_graph", _fake_build)
    monkeypatch.setattr(chat_api, "peer_ip", lambda request: "7.7.7.7")
    monkeypatch.setattr(chat_api, "_postprocess_response_for_widget_modes", _fake_pp)
    monkeypatch.setattr(chat_api, "save_message", _fake_save)
    return graph, builds, saves


def _post(client, **over):
    body = {"session_id": "bb-1", "message": "hallo", "environment": {}}
    body.update(over)
    return client.post("/api/chat", json=body)


# ── Response extraction ─────────────────────────────────────────────────────

def test_returns_response_from_graph(monkeypatch, client):
    _patch(monkeypatch, result=_ok("HI"))
    r = _post(client)
    assert r.status_code == 200
    assert r.json()["content"] == "HI"


def test_early_response_takes_precedence_over_response(monkeypatch, client):
    _patch(monkeypatch, result={
        "early_response": ChatResponse(session_id="bb-1", content="EARLY"),
        "response": ChatResponse(session_id="bb-1", content="NORMAL"),
    })
    assert _post(client).json()["content"] == "EARLY"


# ── Seam binding ────────────────────────────────────────────────────────────

def test_passes_di_session_peer_ip_and_no_on_token(monkeypatch, client):
    _, builds, _ = _patch(monkeypatch, result=_ok())
    _post(client)
    assert builds[0]["session"] is _SESSION
    assert builds[0]["peer_ip"] == "7.7.7.7"
    assert builds[0]["on_token"] is None  # non-streaming path


def test_chat_returns_200_under_active_rate_limit(monkeypatch):
    # Regression: /api/chat returns a ChatResponse (a Pydantic model, NOT a
    # Response). slowapi (headers_enabled=True) injects X-RateLimit-* via the
    # endpoint's `response: Response` param; without it the SUCCESS path 500s the
    # moment the limiter is active (V7 default ON). The `client` fixture sets
    # RATE_LIMIT_CHAT=off, which masks this — here the limiter is ON.
    monkeypatch.setenv("RATE_LIMIT_CHAT", "100/minute")
    get_settings.cache_clear()
    _patch(monkeypatch, result=_ok("HI"))
    app = create_app()
    app.dependency_overrides[get_session] = lambda: _SESSION
    limited = TestClient(app, raise_server_exceptions=False)
    r = limited.post("/api/chat", json={"session_id": "bb-1", "message": "hallo"})
    assert r.status_code == 200
    assert r.json()["content"] == "HI"
    assert "x-ratelimit-limit" in {k.lower() for k in r.headers}
    get_settings.cache_clear()


def test_turncontext_seeded_from_request(monkeypatch, client):
    graph, _, _ = _patch(monkeypatch, result=_ok())
    _post(client, message="frage?")
    assert graph.invoked_with.req.message == "frage?"
    assert graph.invoked_with.req.session_id == "bb-1"


def test_widget_postprocess_output_is_returned(monkeypatch, client):
    _patch(monkeypatch, result=_ok("RAW"))

    async def _transform(req, resp, *a, **k):
        return ChatResponse(session_id=resp.session_id, content="POSTPROCESSED")

    monkeypatch.setattr(chat_api, "_postprocess_response_for_widget_modes", _transform)
    assert _post(client).json()["content"] == "POSTPROCESSED"


# ── Error bubble (never HTTP 500) ───────────────────────────────────────────

def test_graph_exception_becomes_graceful_bubble(monkeypatch, client):
    _, _, saves = _patch(monkeypatch, exc=RuntimeError("boom"))
    r = _post(client)
    assert r.status_code == 200  # NOT 500
    body = r.json()
    assert "schiefgelaufen" in body["content"]
    assert "RuntimeError" in body["content"]
    assert body["quick_replies"] == ["Nochmal versuchen"]
    assert body["debug"]["pattern"] == "ERROR: unhandled_chat_exception"
    assert saves and saves[0]["role"] == "assistant"
    assert "unhandled error: RuntimeError" in saves[0]["content"]


def test_error_persist_failure_never_masks_bubble(monkeypatch, client):
    _patch(monkeypatch, exc=RuntimeError("boom"))

    async def _boom_save(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(chat_api, "save_message", _boom_save)
    r = _post(client)  # DB write failing must NOT turn the bubble into a 500
    assert r.status_code == 200
    assert "schiefgelaufen" in r.json()["content"]


# ── Per-session lock ────────────────────────────────────────────────────────

def test_session_lock_acquired_and_released(monkeypatch, client):
    _patch(monkeypatch, result=_ok())
    events: list = []
    lock = asyncio.Lock()

    async def _acq(session_id):
        events.append(("acquire", session_id))
        return lock

    async def _rel(session_id):
        events.append(("release", session_id))

    monkeypatch.setattr(chat_api, "_get_session_lock", _acq)
    monkeypatch.setattr(chat_api, "_release_session_lock", _rel)
    _post(client)
    assert ("acquire", "bb-1") in events
    assert ("release", "bb-1") in events


# ── C1-f2b6b: die Fehler-Blase folgt der Widget-Sprache ─────────────────────

def test_error_bubble_follows_widget_language(monkeypatch, client):
    _patch(monkeypatch, exc=RuntimeError("boom"))
    r = client.post("/api/chat", json={
        "session_id": "bb-1", "message": "hi",
        "environment": {"locale": "en-GB"},
    })
    body = r.json()
    assert body["content"] == (
        "Something went wrong on our side (RuntimeError). Try again — if it "
        "keeps happening, let me know."
    )
    assert body["quick_replies"] == ["Try again"]


# ── C5-a: der Zugangsblock der Person kommt als Kopfzeile ───────────────────
#
# Das Widget holt ihn beim MCP-Server (OAuth) und schickt ihn je Anfrage mit.
# Gepinnt wird, was WÄHREND des Zuges gilt — nicht, ob eine Funktion gerufen
# wurde: der Block muss am MCP-Aufruf ankommen, und der passiert im Graphen.

_BLOCK_HEADER = "WLO-Access-Block"


def _mit_block_beobachter(monkeypatch):
    """Fährt einen Zug und hält fest, welcher Block dabei wirklich gilt."""
    from pydantic import SecretStr

    from boerdi.services.mcp.auth import build_http_client_factory
    from boerdi.settings import get_settings

    # Ohne das hinge der Test an der Entwicklungs-Umgebung: ein gesetztes
    # ``MCP_AUTH_TOKEN`` liesse „ohne Kopfzeile" nicht leer aussehen.
    monkeypatch.setattr(get_settings(), "mcp_auth_token", SecretStr(""),
                        raising=False)

    gesehen: dict[str, str] = {}

    class _Graph:
        async def ainvoke(self, state):
            client = build_http_client_factory()()
            gesehen["auth"] = client.headers.get("authorization", "")
            return _ok()

    async def _fake_pp(req, resp, *a, **k):
        return resp

    monkeypatch.setattr(chat_api, "build_turn_graph", lambda **k: _Graph())
    monkeypatch.setattr(chat_api, "peer_ip", lambda request: "7.7.7.7")
    monkeypatch.setattr(chat_api, "_postprocess_response_for_widget_modes", _fake_pp)
    return gesehen


def _post_mit(client, headers=None):
    return client.post(
        "/api/chat",
        json={"session_id": "bb-1", "message": "hallo", "environment": {}},
        headers=headers or {},
    )


def test_kopfzeile_meldet_die_person_fuer_diesen_zug(monkeypatch, client):
    gesehen = _mit_block_beobachter(monkeypatch)
    r = _post_mit(client, {_BLOCK_HEADER: "wlo2.person-x"})
    assert r.status_code == 200
    assert gesehen["auth"] == "Bearer wlo2.person-x"


def test_ein_zug_ohne_kopfzeile_erbt_nichts_vom_vorigen(monkeypatch, client):
    """Die wichtigste Zusicherung: kein Zug handelt unter fremdem Namen.

    Der ``ContextVar`` überlebt die Task; würde der Endpunkt ihn nur BEI
    vorhandener Kopfzeile setzen, hinge der nächste, anonyme Zug an der
    Anmeldung des vorigen.
    """
    gesehen = _mit_block_beobachter(monkeypatch)
    _post_mit(client, {_BLOCK_HEADER: "wlo2.person-x"})
    assert gesehen["auth"] == "Bearer wlo2.person-x"

    _post_mit(client)  # derselbe Prozess — aber ohne Kopfzeile
    assert gesehen["auth"] == ""


def test_unbrauchbare_kopfzeile_meldet_niemanden_an(monkeypatch, client, caplog):
    """Fremde Zugangsdaten werden nicht weitergereicht — und nicht protokolliert."""
    gesehen = _mit_block_beobachter(monkeypatch)
    with caplog.at_level("WARNING"):
        r = _post_mit(client, {_BLOCK_HEADER: "Basic aGFsbG86d2VsdA=="})
    assert r.status_code == 200
    assert gesehen["auth"] == ""
    assert "aGFsbG86d2VsdA==" not in caplog.text


# ── K2b: der Zug bucht seinen Verbrauch ─────────────────────────────────
# Geschrieben wird am TRICHTER hinter ``ainvoke``, nicht im persist-Knoten:
# Direkt-Aktionen und der Sicherheits-Block beenden den Zug vorher, hätten dort
# also keine Zeile bekommen. Gemessen: nur diese beiden Ausstiege geben
# überhaupt Token aus — Tour und Kontext-Begrüßung rufen kein LLM.

def _spy_usage(monkeypatch):
    calls: list[tuple] = []

    async def _fake(session, session_id, acc):
        calls.append((session, session_id, acc))
        return 1

    monkeypatch.setattr(chat_api, "record_turn_usage", _fake)
    return calls


def test_verbrauch_wird_am_zugende_geschrieben(monkeypatch, client):
    acc = {"models": {"m": {"prompt": 10, "completion": 5, "cached": 0,
                            "reasoning": 0, "calls": 1}}}
    _patch(monkeypatch, result={**_ok("HI"), "usage": acc})
    calls = _spy_usage(monkeypatch)
    assert _post(client).status_code == 200
    assert len(calls) == 1
    session, session_id, uebergeben = calls[0]
    assert session is _SESSION and session_id == "bb-1"
    assert uebergeben is acc  # Identität: derselbe Merkposten, keine Kopie


def test_verbrauch_auch_bei_direkt_aktion_mit_frueh_antwort(monkeypatch, client):
    # Der Fall, den ein Schreiben im persist-Knoten verloren hätte.
    acc = {"models": {"m": {"prompt": 7, "completion": 1, "cached": 0,
                            "reasoning": 0, "calls": 1}}}
    _patch(monkeypatch, result={
        "early_response": ChatResponse(session_id="bb-1", content="EARLY"),
        "usage": acc,
    })
    calls = _spy_usage(monkeypatch)
    assert _post(client).json()["content"] == "EARLY"
    assert len(calls) == 1 and calls[0][2] is acc


def test_schreibfehler_beim_verbrauch_kippt_die_antwort_nicht(monkeypatch, client):
    _patch(monkeypatch, result={**_ok("HI"), "usage": {"models": {"m": {}}}})

    async def _boom(session, session_id, acc):
        raise RuntimeError("DB weg")

    monkeypatch.setattr(chat_api, "record_turn_usage", _boom)
    r = _post(client)
    # Die Buchhaltung ist nachrangig: die Antwort geht trotzdem raus.
    assert r.status_code == 200 and r.json()["content"] == "HI"
