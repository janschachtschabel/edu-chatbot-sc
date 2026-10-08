"""graph.nodes.setup — turn-setup base state (P4-2 / R4b).

Port of the base half of ALT ``chat_turn_setup._setup_turn`` (P0-3): the part that
runs unconditionally at the graph entry — reset the per-request MCP query-meta
accumulator, load/create the session, load history (limit 20), parse
``session_state`` from the row, dump ``env``, resolve ``client_ip``. The tour /
page-context / context-greeting early-exits and the user-persist are their own
nodes or later slices — NOT this node.

``session`` and ``peer_ip`` are injected (the graph-build binds the request
session + peer IP, like ``assess``/``preflight``). NEU deviation over ALT:
``get_or_create_session`` already returns ``entities``/``signal_history``/
``tour_state`` as native jsonb (dict/list), so ALT's ``json.loads`` wrappers are
dropped; ``tour_state`` rides along in ``session_state`` because the built tour
node reads ``ctx.session_state['tour_state']``. Tests patch the two DB boundaries
on THIS module; ``session`` is a sentinel. The per-turn accumulators are bound
before the graph (``graph/build.begin_turn``), not here — see the tests below.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from boerdi.api.schemas import ChatRequest, Environment
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import setup as setup_mod
from boerdi.graph.nodes.setup import setup
from boerdi.services import write_approval as wa_mod

_SESSION = object()

# A realistic non-empty session row (what get_or_create_session returns for an
# existing session — jsonb already parsed to dict/list).
_ROW = {
    "session_id": "bb-1",
    "persona_id": "P-LEHR",
    "state_id": "S2",
    "entities": {"thema": "Bruchrechnung"},
    "signal_history": ["sig_a", "sig_b"],
    "turn_count": 3,
    "tour_state": {"active": True, "step": "group"},
    "created_at": None,
    "updated_at": None,
}

_HISTORY = [
    {"id": 1, "role": "user", "content": "hallo", "cards": [], "debug": {}},
    {"id": 2, "role": "assistant", "content": "hi", "cards": [], "debug": {}},
]


class _Spy:
    def __init__(self, ret=None):
        self.calls = []
        self._ret = ret

    async def __call__(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})
        return self._ret


def _patch(monkeypatch, row=None, history=None):
    getsess = _Spy(ret=row if row is not None else dict(_ROW))
    getmsg = _Spy(ret=history if history is not None else list(_HISTORY))
    monkeypatch.setattr(setup_mod, "get_or_create_session", getsess)
    monkeypatch.setattr(setup_mod, "get_messages", getmsg)
    return getsess, getmsg


def _ctx(message="was ist photosynthese?", page="/", page_context=None) -> state_mod.TurnContext:
    return state_mod.TurnContext(
        req=ChatRequest(
            session_id="bb-1",
            message=message,
            environment=Environment(page=page, page_context=page_context or {}),
        )
    )


def _run(ctx, peer_ip=""):
    return asyncio.run(setup(ctx, _SESSION, peer_ip=peer_ip))


# ── session_state parsing ────────────────────────────────────────

def test_loads_session_state_jsonb_native(monkeypatch):
    _patch(monkeypatch)
    out = _run(_ctx())

    ss = out.session_state
    assert ss["persona_id"] == "P-LEHR"
    assert ss["state_id"] == "S2"
    # entities stays a native dict (jsonb) — NOT a json string
    assert ss["entities"] == {"thema": "Bruchrechnung"}
    assert ss["signal_history"] == ["sig_a", "sig_b"]
    assert ss["turn_count"] == 3
    # tour_state rides along so the built tour node can read it
    assert ss["tour_state"] == {"active": True, "step": "group"}


def test_defaults_when_row_fields_falsy(monkeypatch):
    # A fresh session (schema defaults) + defensive nulls: setup coerces to the
    # ALT defaults without crashing.
    _patch(monkeypatch, row={
        "session_id": "bb-1", "persona_id": "", "state_id": "S1",
        "entities": None, "signal_history": None, "turn_count": 0,
        "tour_state": None,
    })
    out = _run(_ctx())

    ss = out.session_state
    assert ss["persona_id"] == ""
    assert ss["state_id"] == "S1"
    assert ss["entities"] == {}
    assert ss["signal_history"] == []
    assert ss["turn_count"] == 0
    assert ss["tour_state"] == {}


# ── history ──────────────────────────────────────────────────────

def test_history_loaded_with_limit_20(monkeypatch):
    _, getmsg = _patch(monkeypatch)
    out = _run(_ctx())

    assert out.history == _HISTORY
    # ALT parity: setup loads the last 20 (NEU get_messages defaults to 50)
    assert getmsg.calls[0]["kwargs"].get("limit") == 20
    # session is threaded as the first positional arg (DI)
    assert getmsg.calls[0]["args"][0] is _SESSION


# ── env ──────────────────────────────────────────────────────────

def test_env_dumped_from_environment(monkeypatch):
    _patch(monkeypatch)
    out = _run(_ctx(page="/fuer-lehrende/", page_context={"node_id": "abc"}))

    assert out.env["page"] == "/fuer-lehrende/"
    assert out.env["page_context"] == {"node_id": "abc"}
    # it is the full model dump (device default present)
    assert out.env["device"] == "desktop"


# ── client_ip resolution ─────────────────────────────────────────

def test_client_ip_prefers_peer_ip(monkeypatch):
    _patch(monkeypatch)
    out = _run(_ctx(page_context={"ip": "9.9.9.9"}), peer_ip="1.2.3.4")
    assert out.client_ip == "1.2.3.4"


def test_client_ip_falls_back_to_page_context_ip(monkeypatch):
    _patch(monkeypatch)
    out = _run(_ctx(page_context={"ip": "9.9.9.9"}), peer_ip="")
    assert out.client_ip == "9.9.9.9"


def test_client_ip_empty_when_neither(monkeypatch):
    _patch(monkeypatch)
    out = _run(_ctx(page_context={}), peer_ip="")
    assert out.client_ip == ""


# ── pass-through ─────────────────────────────────────────────────

def test_returns_same_ctx_no_early_response(monkeypatch):
    _patch(monkeypatch)
    ctx = _ctx()
    out = _run(ctx)
    assert out is ctx
    assert out.early_response is None


# ── offener Schreib-Vorgang (Review Paket 2, Befundliste §1.3) ───────────────
# Bestätigen darf nur die Antwort direkt auf die Vorschau. Tour und Kontext-Gruß
# beenden den Zug aber vor dem Vorlauf — ein dort erst verworfener Vorgang
# überdauerte sie, und ein späteres „ok" führte ihn aus.

def _row_mit_abnahme() -> dict:
    from boerdi.domain.write_confirm import remember_pending
    row = dict(_ROW)
    row["entities"] = {"_pending_write": remember_pending(
        "wlo_create_collection", {"name": "Bruchrechnen"},
        "Ax9-_QmZ2kLpWvRt7NbYcE4s", now=time.time())}
    return row


def test_ein_offener_vorgang_verfaellt_vor_jedem_fruehen_ausgang(monkeypatch):
    _patch(monkeypatch, row=_row_mit_abnahme())
    gespeichert = _Spy()
    monkeypatch.setattr(wa_mod, "update_session", gespeichert)

    out = _run(_ctx(message="Website-Tour starten"))

    assert "_pending_write" not in out.session_state["entities"]
    # Verworfen heißt gespeichert: die Tour schreibt ``entities`` nicht zurück.
    assert len(gespeichert.calls) == 1


def test_eine_glatte_zustimmung_laesst_den_vorgang_stehen(monkeypatch):
    _patch(monkeypatch, row=_row_mit_abnahme())
    monkeypatch.setattr(wa_mod, "update_session", _Spy())

    out = _run(_ctx(message="ja"))

    assert "_pending_write" in out.session_state["entities"]


# ── Hintergrund-Züge des Widgets (Befund 2026-10-08) ─────────────────────────
# Kontext-Ping und Tour-Tick zeigt das Widget nur mit Inhalt. Sie nehmen den
# Vorgang aus dem Zug, schreiben aber nichts: zeigt ihr Weg etwas, schreibt er
# ``entities`` selbst zurück (``test_abnahme_nach_kontext_ping``).

def _hintergrund(message: str, *, tour_aktiv: bool, **umgebung):
    row = _row_mit_abnahme()
    row["tour_state"] = {"active": True, "step": "group"} if tour_aktiv else {}
    return row, state_mod.TurnContext(req=ChatRequest(
        session_id="bb-1", message=message, environment=Environment(**umgebung)))


@pytest.mark.parametrize("message, umgebung", [
    ("[context-open]", {"page_event": "context_open"}),
    ("[context-open]", {"page_event": "context_open_initial"}),
    ("[tour-tick]", {"tour_action": "tick"}),
])
def test_ein_hintergrund_zug_ohne_tour_schreibt_den_verfall_nicht(
        monkeypatch, message, umgebung):
    row, ctx = _hintergrund(message, tour_aktiv=False, **umgebung)
    _patch(monkeypatch, row=row)
    gespeichert = _Spy()
    monkeypatch.setattr(wa_mod, "update_session", gespeichert)

    out = _run(ctx)

    assert "_pending_write" not in out.session_state["entities"]
    assert gespeichert.calls == []


@pytest.mark.parametrize("message, umgebung, tour_aktiv", [
    # Mit laufender Tour antwortet die Tour und zeigt etwas, schreibt aber nur
    # ``tour_state`` zurück — also verfällt der Vorgang wie bisher sofort.
    ("[context-open]", {"page_event": "context_open"}, True),
    ("[tour-tick]", {"tour_action": "tick"}, True),
    # Kein Ping: ein unbekanntes Ereignis läuft als gewöhnlicher Zug weiter.
    ("[context-open]", {"page_event": "irgendwas"}, False),
])
def test_waehrend_einer_tour_oder_ohne_ping_bleibt_der_verfall_sofort(
        monkeypatch, message, umgebung, tour_aktiv):
    row, ctx = _hintergrund(message, tour_aktiv=tour_aktiv, **umgebung)
    _patch(monkeypatch, row=row)
    gespeichert = _Spy()
    monkeypatch.setattr(wa_mod, "update_session", gespeichert)

    out = _run(ctx)

    assert "_pending_write" not in out.session_state["entities"]
    assert len(gespeichert.calls) == 1
