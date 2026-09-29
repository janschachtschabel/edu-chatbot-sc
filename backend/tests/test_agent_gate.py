"""AG-4 Teil B — das Safety-Gate des Agent-Endpunkts (Plan 2026-09-26 §8, D-14).

``/api/agent`` lief bis hier ohne Gate (§2.3 Punkt 3). Jetzt prüft derselbe
Weg wie im Chat den Auftrag, bevor irgendetwas geholt oder gerufen wird. Eine
Krise bekommt den Krisentext aus dem Studio (Nutzer, 2026-09-27: frei
konfigurierbar, Vorgabe „an Familie oder Ansprechperson der Einrichtung
wenden"), eine Drohung die Abweisung — beide ohne Schleife.
"""

from __future__ import annotations

import asyncio

from boerdi.api.schemas import SafetyDecision
from boerdi.api.schemas_agent import AgentRequest
from boerdi.domain.config_models.base_governance import (
    KRISENTEXT_VORGABE,
    KRISENTEXT_VORGABE_EN,
    SafetyConfigArea,
)
from boerdi.i18n.bot_text import bot_text
from boerdi.services import agent_gate
from tests.test_agent_run import _lauf

#: So liefern die Stufen es wirklich: das Regex-Gate mit festem M01 und dem Grund,
#: die Moderation mit der Kategorie (``services/safety``).
_KRISE = SafetyDecision(risk_level="high", enforced_pattern="M01",
                        reasons=["crisis_signal_detected"])
_DROHUNG = SafetyDecision(risk_level="high", enforced_pattern="M02",
                          reasons=["threat_signal_detected"])


def _konfig(monkeypatch, **felder) -> None:
    monkeypatch.setattr(agent_gate, "load_safety_config", lambda: dict(felder))


def test_die_vorgabe_verweist_an_familie_und_einrichtung() -> None:
    assert SafetyConfigArea().crisis_message == KRISENTEXT_VORGABE
    assert "Familie" in KRISENTEXT_VORGABE and "Ansprechperson" in KRISENTEXT_VORGABE
    assert "family" in KRISENTEXT_VORGABE_EN


def test_krise_bekommt_den_krisentext_ohne_schleife(monkeypatch) -> None:
    _konfig(monkeypatch)
    # Mit Sammlung und Knoten: ohne Gate liefen dafür zwei Vorabrufe.
    auftrag = AgentRequest(instruction="…", collection_id="c1", node_ids=["n1"])
    loop, out, antwort = _lauf(monkeypatch, auftrag, sicherheit=_KRISE)
    assert (antwort.text, antwort.stop_reason) == (KRISENTEXT_VORGABE, "safety")
    assert (antwort.iterations, antwort.tools_called, antwort.result) == (0, [], None)
    # Weder die Schleife noch ein Vorabruf: das Gate steht vor allem anderen.
    assert loop.kwargs is None and out.calls == []


def test_eine_regex_krise_bleibt_krise_bei_anderem_crisis_pattern(monkeypatch) -> None:
    """Review-Befund 2026-09-27: das Regex-Gate setzt M01 fest, gleich was im
    Studio als ``crisis_pattern`` steht. Die Kennung zu vergleichen gab einer
    Krise dann die Abweisung „verletzt Sicherheitsregeln"."""
    _konfig(monkeypatch, crisis_pattern="M21")
    _loop, _out, antwort = _lauf(monkeypatch, AgentRequest(instruction="…"),
                                 sicherheit=_KRISE)
    assert antwort.text == KRISENTEXT_VORGABE


def test_eine_krise_aus_der_moderation_zaehlt_ueber_die_kategorie(monkeypatch) -> None:
    _konfig(monkeypatch, crisis_pattern="M21")
    moderation = SafetyDecision(risk_level="high", enforced_pattern="M21",
                                flagged_categories=["self_harm/intent"],
                                reasons=["hard_block:self_harm/intent"])
    _loop, _out, antwort = _lauf(monkeypatch, AgentRequest(instruction="…"),
                                 sicherheit=moderation)
    assert antwort.text == KRISENTEXT_VORGABE


def test_andere_harte_kategorien_werden_abgewiesen_nicht_getroestet(monkeypatch) -> None:
    """Review-Befund 2026-09-27: die Moderation schreibt die Krisen-Kennung auch
    für andere harte Kategorien („Rest → M01"). Eine Waffenanfrage bekam so
    „Es tut mir leid, dass es dir gerade nicht gut geht"."""
    _konfig(monkeypatch)
    waffen = SafetyDecision(risk_level="high", enforced_pattern="M01",
                            flagged_categories=["illicit/violent"],
                            reasons=["hard_block:illicit/violent"])
    loop, _out, antwort = _lauf(monkeypatch, AgentRequest(instruction="…"),
                                sicherheit=waffen)
    assert antwort.text == bot_text("de", "error.safetyBlocked")
    assert antwort.stop_reason == "safety" and loop.kwargs is None


def test_der_krisentext_kommt_aus_dem_studio(monkeypatch) -> None:
    _konfig(monkeypatch, crisis_message="Bitte ruf jetzt deine Vertrauenslehrkraft an.")
    _loop, _out, antwort = _lauf(monkeypatch, AgentRequest(instruction="…"),
                                 sicherheit=_KRISE)
    assert antwort.text == "Bitte ruf jetzt deine Vertrauenslehrkraft an."


def test_ein_geleertes_studio_feld_faellt_auf_die_vorgabe_zurueck(monkeypatch) -> None:
    """Nie eine leere Antwort auf eine Krise."""
    _konfig(monkeypatch, crisis_message="   ")
    _loop, _out, antwort = _lauf(monkeypatch, AgentRequest(instruction="…"),
                                 sicherheit=_KRISE)
    assert antwort.text == KRISENTEXT_VORGABE


def test_englisch_nimmt_die_englische_fassung(monkeypatch) -> None:
    _konfig(monkeypatch)
    _loop, _out, antwort = _lauf(monkeypatch, AgentRequest(instruction="…", locale="en"),
                                 sicherheit=_KRISE)
    assert antwort.text == KRISENTEXT_VORGABE_EN


def test_drohung_wird_abgewiesen(monkeypatch) -> None:
    _konfig(monkeypatch)
    loop, _out, antwort = _lauf(monkeypatch, AgentRequest(instruction="…"),
                                sicherheit=_DROHUNG)
    assert (antwort.text, antwort.stop_reason) == (bot_text("de", "error.safetyBlocked"),
                                                   "safety")
    assert loop.kwargs is None


def test_hohes_risiko_ohne_muster_wird_abgewiesen(monkeypatch) -> None:
    _konfig(monkeypatch)
    loop, _out, antwort = _lauf(monkeypatch, AgentRequest(instruction="…"),
                                sicherheit=SafetyDecision(risk_level="high"))
    assert antwort.stop_reason == "safety" and loop.kwargs is None


def test_mittleres_risiko_sperrt_werkzeuge(monkeypatch) -> None:
    _konfig(monkeypatch)
    loop, _out, antwort = _lauf(
        monkeypatch, AgentRequest(instruction="…"),
        sicherheit=SafetyDecision(risk_level="medium", blocked_tools=["search_wlo_content"]))
    namen = [t["function"]["name"] for t in loop.kwargs["tools"]]
    assert "search_wlo_content" not in namen
    assert antwort.stop_reason != "safety"


def test_faellt_die_pruefung_aus_greift_das_regex_gate(monkeypatch) -> None:
    """Wie im Chat (``preflight``): die LLM-Stufen dürfen ausfallen, das
    Regex-Gate ist die harte Rückfallebene."""
    async def kaputt(*_a, **_k):
        raise RuntimeError("Moderation nicht erreichbar")

    monkeypatch.setattr(agent_gate, "assess_safety", kaputt)
    entscheid = asyncio.run(agent_gate.pruefe("Ich will nicht mehr leben", None))
    assert entscheid.enforced_pattern == "M01"
