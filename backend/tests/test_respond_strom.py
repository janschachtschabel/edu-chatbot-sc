"""Token-Streaming im Muster-Zug (Plan ``2026-10-01-token-streaming``, T11):
``respond`` öffnet den Strom oder sperrt ihn mit Grund, und die Umformung der
Vorschau folgt der Endverarbeitung (Ansage-Zeile, Links → Label)."""

from __future__ import annotations

import pytest

from boerdi.api.schemas import ChatRequest, Environment, SafetyDecision
from boerdi.domain.skill_precedence import merke_laufende_anleitung
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import respond_strom as rs_mod
from boerdi.graph.nodes.respond_strom import strom_fuer_agent_zug, strom_fuer_muster_zug
from boerdi.obs.progress import TurnProgress
from boerdi.services.token_stream import TokenStrom
from boerdi.settings import get_settings


@pytest.fixture
def an(monkeypatch):
    monkeypatch.setenv("CHAT_TOKEN_STREAMING", "1")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def aus(monkeypatch):
    """Seit Paket 7 (S2) ist die Vorgabe an — aus heißt jetzt ausdrücklich aus."""
    monkeypatch.setenv("CHAT_TOKEN_STREAMING", "0")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def antwort_werkzeug(monkeypatch):
    """``inline_anzahl`` liest Konfiguration — hier die Grenze, die der Test setzt."""
    anzahl = {"wert": 3}
    monkeypatch.setattr(rs_mod, "inline_anzahl", lambda _po: anzahl["wert"])
    return anzahl


def _ctx(winner_id: str = "M04", risiko: str = "low", entities: dict | None = None,
         umgebung: Environment | None = None):
    ctx = state_mod.TurnContext(
        req=ChatRequest(session_id="bb-1", message="x", environment=umgebung or Environment()))
    ctx.winner_id = winner_id
    ctx.safety = SafetyDecision(risk_level=risiko)
    ctx.session_state = {"entities": entities if entities is not None else {}, "turn_count": 3}
    return ctx


def _strom() -> tuple[TokenStrom, list[dict]]:
    ereignisse: list[dict] = []
    return TokenStrom(TurnProgress(ereignisse.append)), ereignisse


def _gesendet(ereignisse: list[dict]) -> str:
    return "".join(e["data"]["text"] for e in ereignisse if e["kind"] == "text")


def test_ohne_strom_bleibt_alles_wie_heute(an, antwort_werkzeug):
    assert strom_fuer_muster_zug(None, _ctx(), {}) is None


def test_ein_wissenszug_oeffnet_den_strom(an, antwort_werkzeug):
    strom, ereignisse = _strom()
    offen = strom_fuer_muster_zug(strom, _ctx("M04"), {})
    assert offen is strom
    offen("Hallo")
    assert _gesendet(ereignisse) == "Hallo"


def test_ein_suchzug_wird_mit_grund_gesperrt(an, antwort_werkzeug):
    strom, ereignisse = _strom()
    assert strom_fuer_muster_zug(strom, _ctx("M05"), {}) is None
    strom("Hallo")
    assert ereignisse == []
    assert strom.abschluss("egal") == {"gesperrt": "suchmuster", "muster": "M05"}


def test_ohne_antwort_werkzeug_gesperrt(an, antwort_werkzeug):
    antwort_werkzeug["wert"] = 0
    strom, _e = _strom()
    assert strom_fuer_muster_zug(strom, _ctx("M04"), {}) is None
    assert strom.abschluss("egal")["gesperrt"] == "ohne_antwort_werkzeug"


def test_schalter_aus_sperrt(aus, antwort_werkzeug):
    strom, _e = _strom()
    assert strom_fuer_muster_zug(strom, _ctx("M04"), {}) is None
    assert strom.abschluss("egal")["gesperrt"] == "aus"


def test_umformen_setzt_die_ansage_voran_und_macht_links_zu_labels(an, antwort_werkzeug):
    entities: dict = {}
    merke_laufende_anleitung(entities, "node-1", 3, "Stunde planen")
    strom, ereignisse = _strom()
    offen = strom_fuer_muster_zug(strom, _ctx("M04", entities=entities), {})
    offen("Siehe [WLO](https://wlo.de).")
    offen.schliessen()
    gesendet = _gesendet(ereignisse)
    erste_zeile, _, rest = gesendet.partition("\n")
    assert "Stunde planen" in erste_zeile
    assert rest.strip() == "Siehe WLO."


# ── Agent-Zug (T22) ─────────────────────────────────────────────────────────

def test_der_agent_strom_oeffnet_nur_mit_antwort_werkzeug(an):
    strom, _e = _strom()
    assert strom_fuer_agent_zug(strom, _ctx("AGENT"), antwort_werkzeug=False) is None
    assert strom.abschluss("x")["gesperrt"] == "ohne_antwort_werkzeug"
    offen, _e2 = _strom()
    assert strom_fuer_agent_zug(offen, _ctx("AGENT"), antwort_werkzeug=True) is offen


def test_die_agent_vorschau_setzt_die_master_ansage_voran_ohne_sie_zu_verbrauchen(an):
    """``mit_master_ansage`` merkt sich in ``entities``, dass angesagt wurde. Die
    Vorschau darf das der Endverarbeitung nicht vorwegnehmen — sonst fehlte die
    Zeile in der fertigen Antwort."""
    entities: dict = {}
    ctx = _ctx("AGENT", entities=entities)
    ctx.master_skill_zeile = "[ edu-sharing Skill ] Chatbot Masterskill - aktiv"
    strom, ereignisse = _strom()
    offen = strom_fuer_agent_zug(strom, ctx, antwort_werkzeug=True)
    offen("Siehe [WLO](https://wlo.de).")
    offen.schliessen()

    gesendet = _gesendet(ereignisse)
    assert gesendet.startswith("[ edu-sharing Skill ] Chatbot Masterskill - aktiv")
    assert gesendet.rstrip().endswith("Siehe WLO.")
    assert entities == {}


# ── Review M2: kein Stau, wenn die Endverarbeitung ganze Zeilen entfernt ─────

@pytest.mark.parametrize("roh", [
    "Hier sind Quellen:\n- [WLO FAQ](https://wlo.de/faq)\n- [OER-Info](https://oer.de)"
    "\n\nViel Erfolg beim Lernen!",
    "Quellen:\n1. [WLO FAQ](https://wlo.de/faq)\n2. [OER](https://oer.de)\n\nViel Erfolg!",
    "\N{BLACK RIGHT-POINTING SMALL TRIANGLE} stunde-planen aktiv \N{EM DASH} Verlaufsplan\n"
    "Hier ist dein Plan für die Stunde.",
])
def test_was_die_endverarbeitung_entfernt_staut_den_strom_nicht(an, antwort_werkzeug, roh):
    strom, ereignisse = _strom()
    offen = strom_fuer_muster_zug(strom, _ctx("M04"), {})
    for i in range(0, len(roh), 3):
        offen(roh[i:i + 3])
    offen.schliessen()
    assert offen._vorschau.rueckschritte == 0
    assert _gesendet(ereignisse) == offen._vorschau._umformen(roh)


def test_ohne_ergebnis_gruppen_bleiben_links_links(an, antwort_werkzeug):
    """Review L3: Links werden nur zu Labels, wo die Endverarbeitung das auch
    tut — mit ``inline_result_grouping=false`` bleiben sie im Text
    (``services/turn_links``, ``_grouping_on_impl``)."""
    strom, ereignisse = _strom()
    ctx = _ctx("M04", umgebung=Environment(inline_result_grouping=False))
    offen = strom_fuer_muster_zug(strom, ctx, {})
    offen("Siehe [WLO](https://wlo.de).")
    offen.schliessen()
    assert _gesendet(ereignisse) == "Siehe [WLO](https://wlo.de)."
