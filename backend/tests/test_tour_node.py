"""graph.nodes.tour — website-tour router (P4-2c, R2).

Port of ALT ``chat_tour.py::_handle_tour`` — the deterministic, page-stateful
tour state machine that runs BEFORE classify/pattern/LLM. The pure state machine
(``domain/tour``) runs for real; only the config load and the two DB writes
(``update_session``/``save_message``) are patched on the node module. ``session``
is an injected sentinel (like the preflight node); ``tour_state`` is a native
jsonb dict (no json.loads/dumps).
"""

from __future__ import annotations

import asyncio

from boerdi.api.schemas import ChatRequest, Environment
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import tour as tour_mod
from boerdi.graph.nodes.tour import tour

_SESSION = object()

_CFG = {
    "enabled": True,
    "base_host": "https://wlo.test",
    "home_path": "/home/",
    "content_hub": "/bildungsinhalte/",
    "contact_hub": "/mitmachen/",
    "trigger_phrases": ["web-tour", "zeig mir die seite"],
    "groups": [
        {
            "id": "lehrer",
            "label": "Lehrkräfte",
            "synonyms": ["lehrer", "lehrerin"],
            "page": "/fuer-lehrende/",
            "angebote": [{"label": "Material", "path": "/material/"}],
        },
    ],
    "steps": {
        "intro": {"nav_label": "Zur Startseite"},
        "group": {
            "text": "Für wen suchst du?",
            "unsure_text": "Ich hab dich nicht verstanden.",
            "unsure_label": "Weiß nicht",
        },
        "group_page": {"text": "Seite für {group}", "nav_label": "Zur Seite"},
        "content": {"text": "Bildungsinhalte", "nav_label": "Zu den Bildungsinhalten"},
        "solutions": {
            "text": "Lösungen für {group}",
            "nav_label": "Weiter zum Abschluss",
            "angebote_label": "Für dich",
        },
        "contact": {"text": "Mitmachen!", "links_label": "Weiter"},
    },
    "intro": "Willkommen zur Tour!",
    "nudge": "Das ist nicht die richtige Seite.",
    "explore": "Schau dich um.",
    "entry": {"solutions": "Willkommen, {group}!"},
    "contact_links": [{"label": "Kontakt", "path": "/kontakt/"}],
    "content_sublinks": [],
}


class _Spy:
    def __init__(self):
        self.calls = []

    async def __call__(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})


def _patch(monkeypatch):
    upd, save = _Spy(), _Spy()
    monkeypatch.setattr(tour_mod, "load_website_tour_config", lambda: dict(_CFG))
    monkeypatch.setattr(tour_mod, "update_session", upd)
    monkeypatch.setattr(tour_mod, "save_message", save)
    return upd, save


def _ctx(action=None, message="", page="/", tour_state=None) -> state_mod.TurnContext:
    ctx = state_mod.TurnContext(
        req=ChatRequest(
            session_id="bb-1",
            message=message,
            environment=Environment(tour_action=action, page=page),
        )
    )
    ctx.session_state = {"tour_state": tour_state if tour_state is not None else {}}
    return ctx


def _run(ctx):
    return asyncio.run(tour(ctx, _SESSION))


# ── start ───────────────────────────────────────────────────────

def test_start_from_home_enters_group(monkeypatch):
    upd, save = _patch(monkeypatch)
    out = _run(_ctx("start", message="Los geht's", page="/home/"))

    assert out.early_response.debug.pattern == "TOUR:group"
    assert out.early_response.tour == {"active": True, "step": "group", "group": ""}
    assert out.early_response.content == "Für wen suchst du?"
    assert "Lehrkräfte" in out.early_response.quick_replies
    # tour_state persisted as a native dict (jsonb), NOT a json string
    assert isinstance(upd.calls[0]["kwargs"]["tour_state"], dict)
    assert upd.calls[0]["kwargs"]["tour_state"]["step"] == "group"
    # start persists the user turn
    assert any(c["args"][2] == "user" for c in save.calls)


def test_start_on_target_page_enters_solutions_entry(monkeypatch):
    _patch(monkeypatch)
    out = _run(_ctx("start", message="start", page="/fuer-lehrende/"))

    assert out.early_response.debug.pattern == "TOUR:solutions"
    assert out.early_response.tour == {"active": True, "step": "solutions", "group": "lehrer"}
    assert "Willkommen, Lehrkräfte!" in out.early_response.content


def test_typed_trigger_phrase_starts_tour(monkeypatch):
    _patch(monkeypatch)
    out = _run(_ctx(None, message="Kannst du mir die Seite zeigen?", page="/"))
    # message contains trigger "zeig mir die seite"? no — use exact trigger below
    assert out.early_response is None  # this message has no trigger

    out2 = _run(_ctx(None, message="zeig mir die seite bitte", page="/"))
    assert out2.early_response is not None
    assert out2.early_response.debug.pattern == "TOUR:intro"  # page "/" → intro


# ── tick ────────────────────────────────────────────────────────

def test_tick_advances_on_arrival(monkeypatch):
    _patch(monkeypatch)
    state = {"active": True, "step": "intro", "group": "", "misses": 0}
    out = _run(_ctx("tick", page="/home/", tour_state=state))

    assert out.early_response.tour["step"] == "group"  # intro → group on /home arrival
    assert out.early_response.content == "Für wen suchst du?"


def test_tick_nudge_on_wrong_page(monkeypatch):
    _patch(monkeypatch)
    state = {"active": True, "step": "content", "group": "lehrer", "misses": 0}
    out = _run(_ctx("tick", page="/irgendwo/", tour_state=state))

    assert out.early_response.content == "Das ist nicht die richtige Seite."
    assert out.early_response.tour["step"] == "content"  # NOT advanced


def test_stale_tick_returns_inactive(monkeypatch):
    _patch(monkeypatch)
    out = _run(_ctx("tick", page="/home/", tour_state={}))  # no active tour

    assert out.early_response.content == ""
    assert out.early_response.tour == {"active": False, "step": "", "group": ""}
    assert out.early_response.debug.pattern == "TOUR:inactive"


# ── group reply ─────────────────────────────────────────────────

def test_group_reply_matches_group(monkeypatch):
    upd, save = _patch(monkeypatch)
    state = {"active": True, "step": "group", "group": "", "misses": 0}
    out = _run(_ctx(None, message="Lehrer", page="/home/", tour_state=state))

    assert out.early_response.tour == {"active": True, "step": "group_page", "group": "lehrer"}
    assert out.early_response.content == "Seite für Lehrkräfte"
    assert any(c["args"][2] == "user" for c in save.calls)


def test_group_reply_miss_twice_ends_tour(monkeypatch):
    upd, save = _patch(monkeypatch)
    state = {"active": True, "step": "group", "group": "", "misses": 1}
    out = _run(_ctx(None, message="völliger unsinn", page="/home/", tour_state=state))

    assert out.early_response is None  # tour ended → normal flow takes over
    assert upd.calls[-1]["kwargs"]["tour_state"]["active"] is False
    assert save.calls == []  # user message left for the normal flow


# ── fall-through / soft-exit ────────────────────────────────────

def test_soft_exit_active_tour_on_normal_message(monkeypatch):
    upd, save = _patch(monkeypatch)
    state = {"active": True, "step": "solutions", "group": "lehrer", "misses": 0}
    out = _run(_ctx(None, message="was ist photosynthese?", page="/x/", tour_state=state))

    assert out.early_response is None  # not hijacked; falls through
    assert upd.calls[-1]["kwargs"]["tour_state"]["active"] is False  # tour softly ended


def test_not_a_tour_turn_passes_through(monkeypatch):
    upd, save = _patch(monkeypatch)
    out = _run(_ctx(None, message="hallo", page="/", tour_state={}))

    assert out.early_response is None
    assert upd.calls == [] and save.calls == []
