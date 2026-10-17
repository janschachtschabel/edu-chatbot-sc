"""ST-8b: die Werkzeugliste des Agenten mit ihren Sperren, für das Studio.

Die Liste muss aus denselben Quellen kommen wie der Zug — sonst zeigt das Studio
einen Katalog, den der Agent nie sieht. Deshalb vergleicht der erste Test mit
``build_agent_tools`` selbst, und die festen Sperren des Regex-Gates stehen dort
als Konstanten, die das Gate benutzt (zweiter Block).
"""

from __future__ import annotations

import pytest

from boerdi.services import agent_tool_overview as ov
from boerdi.services import agent_tools
from boerdi.services.engine_choice import zug_laeuft_ueber_die_schleife
from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS
from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS
from boerdi.services.safety import regex_gate


@pytest.fixture(autouse=True)
def _quellen(monkeypatch):
    """Ohne Zugang, ohne Policy-Sperren, ohne Wissensbereiche."""
    monkeypatch.setattr(agent_tools, "has_auth_token", lambda: False)
    monkeypatch.setattr(ov, "load_policy_config", lambda: {})
    monkeypatch.setattr(ov, "load_rag_config", lambda: {})


def _zeile(liste: dict, name: str) -> dict:
    return next(t for t in liste["tools"] if t["name"] == name)


def _sperre(zeile: dict, code: str) -> dict | None:
    return next((s for s in zeile["locks"] if s["code"] == code), None)


# ── Welche Werkzeuge, woher ─────────────────────────────────────────────


def test_angeboten_ist_genau_der_katalog_eines_chat_zugs():
    liste = ov.werkzeugliste()
    im_zug = {t["function"]["name"] for t in agent_tools.build_agent_tools(
        include_submit=False, include_dokument=True)}
    assert {t["name"] for t in liste["tools"] if t["offered"]} == im_zug


def test_jedes_werkzeug_steht_einmal_da_mit_art_und_beschreibung():
    liste = ov.werkzeugliste()
    namen = [t["name"] for t in liste["tools"]]
    assert len(namen) == len(set(namen))
    for art, katalog in (("read", TOOL_DEFINITIONS), ("curation", CURATION_TOOL_DEFINITIONS)):
        for definition in katalog:
            zeile = _zeile(liste, definition["function"]["name"])
            assert zeile["kind"] == art
            assert zeile["description"] == definition["function"]["description"]


def test_mit_schreibrecht_kommen_die_kuratierenden_dazu(monkeypatch):
    """Seit Paket 7 (S4) dieselbe Regel wie im Chat-Zug: der Block der Anlage
    allein genügt nicht — erst mit Schreibrecht (``schreibrecht``)."""
    ohne = ov.werkzeugliste()
    assert not _zeile(ohne, "wlo_create_content")["offered"]
    assert _sperre(_zeile(ohne, "wlo_create_content"), "needs_access") is not None

    monkeypatch.setattr(agent_tools, "has_auth_token", lambda: True)
    nur_block = ov.werkzeugliste()
    assert not _zeile(nur_block, "wlo_create_content")["offered"]

    monkeypatch.setattr(ov, "schreiben_erlaubt", lambda: True)
    mit = ov.werkzeugliste()
    assert all(_zeile(mit, d["function"]["name"])["offered"] for d in CURATION_TOOL_DEFINITIONS)


def test_search_skill_ist_von_haus_aus_verborgen():
    """Seit Paket 7 (S5) im Studio je MCP-Server einschaltbar — die Sperre heißt
    deshalb nicht mehr „nie“, sondern „abgeschaltet“ (``hidden``)."""
    zeile = _zeile(ov.werkzeugliste(), "search_skill")
    assert zeile["offered"] is False
    assert zeile["locks"] == [{"code": "hidden"}]


# ── Sperren ─────────────────────────────────────────────────────────────


def test_die_einbettung_nimmt_je_modus_andere_werkzeuge():
    liste = ov.werkzeugliste()
    assert _sperre(_zeile(liste, "wlo_create_content"), "tool_mode") == {
        "code": "tool_mode", "modes": ["read-only"]}
    assert _sperre(_zeile(liste, "get_url_text"), "tool_mode") == {
        "code": "tool_mode", "modes": ["curate"]}
    # Die zwei benannten Ausnahmen tragen das Präfix, ohne zu schreiben.
    assert _sperre(_zeile(liste, "wlo_auth_status"), "tool_mode") is None
    assert _sperre(_zeile(liste, "search_wlo_content"), "tool_mode") is None


def test_persoenliche_daten_nehmen_der_schleife_die_volltextsuche():
    liste = ov.werkzeugliste()
    assert _sperre(_zeile(liste, "search_wlo_content"), "safety_fixed") == {
        "code": "safety_fixed", "signals": ["pii"]}
    assert _sperre(_zeile(liste, "get_skill"), "safety_fixed") is None


def test_das_gate_sperrt_bei_persoenlichen_daten_genau_die_gezeigte_liste():
    """Die Anzeige liest die Konstante; das Gate muss sie auch benutzen."""
    entscheid = regex_gate.regex_gate("mein passwort ist geheim123", [])
    assert entscheid.blocked_tools == list(regex_gate.SPERRE_PERSOENLICH)
    # Kein erzwungenes Muster: die Schleife läuft, nur ohne diese Werkzeuge.
    assert zug_laeuft_ueber_die_schleife("agent", entscheid.enforced_pattern)


@pytest.mark.parametrize("satz", ["ich will mich umbringen", "ich werde dich umbringen"])
def test_krise_und_drohung_sperren_keine_einzelnen_werkzeuge(satz):
    """Review-Befund 2026-09-27: Krise und Drohung erzwingen ein Schutzmuster, und
    dann antwortet nicht die Schleife (SF-1) — es gibt in diesem Zug gar kein
    Agent-Werkzeug. Einzelne Sperren daneben zu nennen hieße, die Schleife liefe
    mit dem Rest weiter. Dasselbe gilt für die harte Sperre der Moderation mit
    ``crisis_blocked_tools``: sie erzwingt immer ein Muster
    (``test_safety_escalation.py``)."""
    entscheid = regex_gate.regex_gate(satz, [])
    assert entscheid.enforced_pattern
    assert not zug_laeuft_ueber_die_schleife("agent", entscheid.enforced_pattern)
    liste = ov.werkzeugliste()
    for name in regex_gate.SPERRE_KRISE:
        assert all(set(s.get("signals", [])) <= {"pii"} for s in _zeile(liste, name)["locks"])
    assert not any(s["code"] == "safety_config" for t in liste["tools"] for s in t["locks"])


def test_policy_regeln_sperren_mit_ihrer_kennung(monkeypatch):
    monkeypatch.setattr(ov, "load_policy_config", lambda: {"rules": [
        {"id": "keine-wikipedia", "effect": {"block_tools": ["get_wikipedia_summary"]}},
        # Ohne Kennung heißt eine Regel wie in ``assess_policy``.
        {"match": {"persona": "P-SUS"}, "effect": {"block_tools": ["get_wikipedia_summary"]}},
        {"id": "nur-hinweis", "effect": {"disclaimer": "Achtung"}},
        {"id": "leer", "effect": None},
    ]})
    liste = ov.werkzeugliste()
    assert _sperre(_zeile(liste, "get_wikipedia_summary"), "policy") == {
        "code": "policy", "rules": ["keine-wikipedia", "policy-rule"]}
    assert _sperre(_zeile(liste, "get_url_text"), "policy") is None


# ── Virtuelle Werkzeuge ─────────────────────────────────────────────────


def test_virtuelle_werkzeuge_sind_nicht_sperrbar(monkeypatch):
    # Selbst wenn eine Policy-Regel sie nennt: ``build_agent_tools`` hängt sie
    # NACH dem Sperrfilter an.
    monkeypatch.setattr(ov, "load_policy_config", lambda: {"rules": [
        {"id": "keine-box", "effect": {"block_tools": ["zeige_dokument"]}}]})
    liste = ov.werkzeugliste()
    dokument = _zeile(liste, "zeige_dokument")
    assert (dokument["kind"], dokument["offered"], dokument["locks"]) == ("virtual", True, [])
    ergebnis = _zeile(liste, "liefere_ergebnis")
    assert (ergebnis["kind"], ergebnis["offered"]) == ("virtual", False)
    assert ergebnis["locks"] == [{"code": "host_schema"}]
    assert "submit_result" not in {t["name"] for t in liste["tools"]}


def test_die_wissenssuche_nur_mit_bereichen(monkeypatch):
    ohne = _zeile(ov.werkzeugliste(), "wissen_suchen")
    assert (ohne["kind"], ohne["offered"]) == ("virtual", False)
    assert ohne["locks"] == [{"code": "knowledge_areas"}]

    monkeypatch.setattr(ov, "load_rag_config", lambda: {
        "Plattformwissen": {"description": "Was WLO ist", "agent": True}})
    mit = _zeile(ov.werkzeugliste(), "wissen_suchen")
    assert mit["offered"] is True
    assert "Plattformwissen" in mit["description"]
