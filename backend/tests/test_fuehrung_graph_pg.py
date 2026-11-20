"""Review G2 (MINOR 4): die Führung als Ablauf Ende zu Ende durch den echten Zug-Graphen.

Tour aus, Führung an, echtes Postgres (Sitzung, Nachrichten, Vorgang): der Tour-Chip der Begrüßung
(``Web-Tour starten`` mit ``tour_action: start``) startet die Führung, der Seiten-Ping auf der
Startseite bringt die Gruppenwahl, ein Seitenwechsel zeigt sie erneut (G2d), der Chip „Bin mir
nicht sicher“ zählt wie getippt (G2a). Kein Modell: die Sicherheitsprüfung nur mit dem Regex-Gate.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from boerdi.api.schemas import ChatRequest, Environment, SafetyDecision
from boerdi.graph.state import TurnContext
from tests import pg_utils
from tests.test_fuehrung_wie_tour import CFG, ROH

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_g2_fuehrung_graph"
_SID = "bb-g2fuehrung0123456"


@pytest.fixture(scope="module")
def db_url():
    pg_utils.create_migrated_db(_DB)
    yield pg_utils.sqlalchemy_url(_DB)
    pg_utils.drop_db(_DB)


@pytest.fixture
def fuehrung_an(monkeypatch):
    from boerdi.graph.nodes import preflight as preflight_mod
    from boerdi.graph.nodes import tour as tour_mod
    from boerdi.services.ablauf import ausloeser
    from boerdi.services.rate_limits import RateVerdict
    from boerdi.services.safety.regex_gate import regex_gate

    async def frei(*_a, **_k):
        return RateVerdict(allowed=True)

    async def regex(text, signals, **_k):
        return SafetyDecision(risk_level="high" if regex_gate(text, signals or []).enforced_pattern
                              else "low")

    monkeypatch.setattr(tour_mod, "load_website_tour_config", lambda: {**CFG, "enabled": False})
    monkeypatch.setattr(ausloeser, "_roh_liste", lambda: [{**ROH, "aktiv": True}])
    monkeypatch.setattr(preflight_mod, "check_rate_limit", frei)
    monkeypatch.setattr(preflight_mod, "assess_safety", regex)


def _zuege(url: str, anfragen: list[ChatRequest]):
    from boerdi.db.session import make_engine, make_session_factory
    from boerdi.graph.build import build_turn_graph, run_turn
    from boerdi.settings import Settings

    async def ablauf():
        engine = make_engine(Settings(_env_file=None, database_url=url,
                                      db_pool_size=2, db_max_overflow=0))
        antworten = []
        try:
            for req in anfragen:
                async with make_session_factory(engine)() as session:
                    state = await run_turn(build_turn_graph(session=session),
                                           TurnContext(req=req))
                    antworten.append(state.get("early_response") or state.get("response"))
        finally:
            await engine.dispose()
        return antworten

    return asyncio.run(ablauf())


def _req(message: str, seite: str, **mehr) -> ChatRequest:
    env = {"page": seite, "locale": "de", **mehr.pop("env", {})}
    return ChatRequest(session_id=_SID, message=message, environment=Environment(**env), **mehr)


def test_tour_chip_ping_und_text_chip_durch_den_ganzen_zug(db_url, fuehrung_an):
    from boerdi.domain import tour

    start, ping = _zuege(db_url, [
        _req("Web-Tour starten", "/impressum/", env={"tour_action": "start"}),
        _req("[ablauf-seite]", "/home/", env={"page_event": "ablauf_seite"})])
    intro = tour.render("intro", CFG)
    assert start.content == intro["text"]
    assert start.quick_replies == ["__fuehrung__|Zur Startseite|/home/"]
    gruppe = tour.render("group", CFG)
    assert ping.content == gruppe["text"]
    assert [q.split("|")[1] for q in ping.quick_replies] == gruppe["quick_replies"]

    [erneut] = _zuege(db_url, [_req("[ablauf-seite]", "/impressum/",
                                    env={"page_event": "ablauf_seite"})])
    assert erneut.content == gruppe["text"]                       # G2d

    _, _label, aktion, params = ping.quick_replies[-1].split("|", 3)
    [hinweis] = _zuges_chip(db_url, aktion, json.loads(params))
    assert hinweis.content == tour.render("group", CFG, kind="unsure")["text"]   # G2a


def _zuges_chip(url, aktion, params):
    return _zuege(url, [_req("Bin mir nicht sicher", "/home/", action=aktion,
                             action_params=params)])
