"""Paket 18E (N1): Schalter so lesen, wie das Gate sie prüft.

Das Gate prüft einen Bereich mit seinem Pydantic-Modell im Lax-Modus, speichert aber das
ROHDOKUMENT (``api/config_guards.modell_fehler``). ``messages: "false"`` — im Rohtext-Editor
gequotet — passiert das Gate (Pydantic liest ``False``); die Lader machten mit ``bool("false")``
daraus ``True``: Nachrichten wurden trotz „aus“ gespeichert. ``als_schalter`` liest mit derselben
Regel wie das Gate.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any

import pytest

from boerdi.obs import drossel
from boerdi.services import config_loader as cl
from boerdi.services.config_loader.schalter import als_schalter


@pytest.fixture(autouse=True)
def _frisch():
    drossel.zuruecksetzen()
    yield
    drossel.zuruecksetzen()
    cl.bind_store(None)


class _Store:
    def __init__(self, areas: dict[str, dict[str, Any]]) -> None:
        self.areas = areas

    def get_cached(self, area: str) -> dict | None:
        return self.areas.get(area)

    def cached_areas(self) -> list[str]:
        return list(self.areas)


@pytest.mark.parametrize("wert", [True, 1, "1", "true", "True", "TRUE", "yes", "on", "y", "t"])
def test_an_wie_das_gate(wert):
    assert als_schalter(wert, False, name="x") is True


@pytest.mark.parametrize("wert", [False, 0, "0", "false", "False", "no", "off", "n", "f"])
def test_aus_wie_das_gate(wert):
    assert als_schalter(wert, True, name="x") is False


def test_fehlt_der_wert_gilt_die_vorgabe():
    assert als_schalter(None, True, name="x") is True
    assert als_schalter(None, False, name="x") is False


def test_unbrauchbar_vorgabe_und_eine_warnung(caplog):
    with caplog.at_level(logging.WARNING):
        assert als_schalter("vielleicht", True, name="widget.enabled") is True
        assert als_schalter(2, True, name="widget.enabled") is True
    meldungen = [r.getMessage() for r in caplog.records if "widget.enabled" in r.getMessage()]
    assert len(meldungen) == 1
    assert "vielleicht" not in meldungen[0]  # der Wert steht nicht im Log, nur sein Typ


def test_streng_wirft_statt_der_vorgabe():
    with pytest.raises(ValueError, match="privacy"):
        als_schalter("vielleicht", True, name="privacy.logging.messages", streng=True)


def test_datenschutz_schalter_als_text_schaltet_aus():
    cl.bind_store(_Store({"01-base/privacy-config": {
        "logging": {"messages": "false", "memory": "no", "quality": "0"}}}))
    assert cl.load_privacy_config() == {
        "messages": False, "memory": False, "quality": False, "safety": True}


def test_datenschutz_schalter_unbrauchbar_wirft():
    """Ein ausdrückliches „aus“ darf nie an einem kaputten Wert scheitern (F1: fail-closed) —
    der Lader wirft, die Leser speichern dann nichts."""
    cl.bind_store(_Store({"01-base/privacy-config": {"logging": {"messages": "vielleicht"}}}))
    with pytest.raises(ValueError):
        cl.load_privacy_config()


def test_kein_bool_um_einen_rohwert_in_den_ladern():
    """Wächter: in ``services/config_loader`` kein ``bool(… .get(…))`` und kein ``bool(v)`` auf
    einem gespeicherten Wert mehr — dafür ``als_schalter``."""
    wurzel = Path(cl.__file__).parent
    funde = []
    for datei in sorted(wurzel.glob("*.py")):
        for knoten in ast.walk(ast.parse(datei.read_text(encoding="utf-8"))):
            if (isinstance(knoten, ast.Call) and isinstance(knoten.func, ast.Name)
                    and knoten.func.id == "bool" and knoten.args
                    and not isinstance(knoten.args[0], ast.Compare)):
                funde.append(f"{datei.name}:{knoten.lineno}")
    assert funde == []


# ── Review 18E-1 (S1): der Cache normalisiert, was das Modell als ``bool`` führt ─────
# Außerhalb der Lader lesen Stellen gespeicherte Konfiguration roh — ``log_all_turns:
# "false"`` schickte jeden Zug ins Sicherheitsprotokoll, ein Fremdserver mit ``enabled:
# "false"`` blieb im Angebot. Statt jeder Stelle einzeln: einmal beim Füllen des Caches.

from boerdi.domain.config_models import AREA_MODELS  # noqa: E402
from boerdi.domain.config_models.schalter import normalisiere_schalter  # noqa: E402


def test_unterblock_zuordnung_und_liste_werden_normalisiert():
    roh = {
        "logging": {"enabled": "true", "log_all_turns": "false"},
        "escalation": {"downgrade_false_positives": "no"},
        "presets": {"streng": {"prompt_injection": "yes", "double_check": "0"}},
    }
    aus = normalisiere_schalter("01-base/safety-config", roh)
    assert aus["logging"] == {"enabled": True, "log_all_turns": False}
    assert aus["escalation"]["downgrade_false_positives"] is False
    assert aus["presets"]["streng"]["prompt_injection"] is True
    assert aus["presets"]["streng"]["double_check"] is False
    assert roh["logging"]["log_all_turns"] == "false"  # das Original bleibt roh


def test_wurzelmodell_und_liste_von_modellen():
    assert normalisiere_schalter("05-knowledge/rag-config", {"wlo": {"agent": "false"}}) == {
        "wlo": {"agent": False}}
    aus = normalisiere_schalter("05-knowledge/mcp-servers",
                                {"servers": [{"id": "x", "enabled": "false"}]})
    assert aus["servers"][0]["enabled"] is False


def test_optionales_feld_im_muster_kopf():
    aus = normalisiere_schalter("03-patterns/m06", {
        "frontmatter": {"id": "M06", "card_text_link_required": "false"}, "body": "x"})
    assert aus["frontmatter"]["card_text_link_required"] is False


def test_unbrauchbares_und_fremdes_bleibt_wie_es_ist():
    roh = {"logging": {"log_all_turns": "vielleicht", "fremd": "false"}}
    assert normalisiere_schalter("01-base/safety-config", roh) is roh
    assert normalisiere_schalter("99-unbekannt/x", {"a": "false"}) == {"a": "false"}


def test_jedes_bereichsmodell_ueberlebt_seine_vorgaben():
    """Kein Modell mit einer Form, die der Normalisierer nicht kennt — und Vorgaben bleiben."""
    for schluessel, modell in AREA_MODELS.items():
        try:
            vorgabe = modell().model_dump(mode="json")
        except Exception:  # noqa: BLE001 — Modelle mit Pflichtfeldern haben keine Vorgabe
            continue
        if isinstance(vorgabe, dict):
            assert normalisiere_schalter(schluessel, vorgabe) == vorgabe


def test_der_cache_haelt_den_normalisierten_stand():
    from boerdi.services.config_store import ConfigStore

    store = ConfigStore(None, "postgresql://unbenutzt")  # type: ignore[arg-type]
    store._remember("01-base/safety-config", {"logging": {"log_all_turns": "false"}}, 2)
    assert store.get_cached("01-base/safety-config") == {"logging": {"log_all_turns": False}}


# ── Review 18E-1 (K1): ``null`` beim Datenschutz ist kein „an“ ───────────────────────

@pytest.mark.parametrize("logging_block", [
    {"messages": None},
    None,
    [],
    "aus",
], ids=["schalter-null", "block-null", "block-liste", "block-text"])
def test_datenschutz_null_oder_kaputter_block_wirft(logging_block):
    """``bool(None)`` war „aus“; mit der Vorgabe wäre es „an“ geworden — die falsche Richtung
    zu F1. Ein vorhandener, unbrauchbarer Wert wirft, die Leser speichern dann nichts."""
    cl.bind_store(_Store({"01-base/privacy-config": {"logging": logging_block}}))
    with pytest.raises(ValueError):
        cl.load_privacy_config()


def test_datenschutz_fehlender_schluessel_gilt_als_vorgabe():
    cl.bind_store(_Store({"01-base/privacy-config": {"logging": {"messages": False}}}))
    assert cl.load_privacy_config() == {
        "messages": False, "memory": True, "quality": True, "safety": True}


# ── Paket 19 (Audit N-21): ``null`` schaltet einen Datenschutz-/Sicherheitsschalter nicht ein ──

def test_null_heisst_aus_mit_einer_warnung(caplog):
    from boerdi.services.config_loader.schalter import FEHLT

    with caplog.at_level(logging.WARNING):
        assert als_schalter(None, True, name="mcp_servers.enabled", null_heisst=False) is False
        assert als_schalter(None, True, name="mcp_servers.enabled", null_heisst=False) is False
    assert len([r for r in caplog.records if "mcp_servers.enabled" in r.getMessage()]) == 1
    # Fehlt der Schlüssel, gilt weiter die Vorgabe — nur ein gespeichertes ``null`` ist aus.
    assert als_schalter(FEHLT, True, name="mcp_servers.enabled", null_heisst=False) is True
    assert als_schalter("false", True, name="mcp_servers.enabled", null_heisst=False) is False
    assert als_schalter(True, True, name="mcp_servers.enabled", null_heisst=False) is True


def test_harmlose_schalter_behalten_die_vorgabe_bei_null():
    assert als_schalter(None, True, name="website_tour.enabled") is True


def test_ein_abgeschalteter_fremdserver_bleibt_bei_null_aus():
    """Ein Altbestand-``null`` schaltete einen abgeschalteten Fremdserver wieder ein."""
    cl.bind_store(_Store({"05-knowledge/mcp-servers": {"servers": [
        {"id": "fremd-null", "url": "https://fremd.example/mcp", "enabled": None},
        {"id": "fremd-ohne", "url": "https://ohne.example/mcp"},
    ]}}))
    assert [s["id"] for s in cl.get_enabled_mcp_servers()] == ["fremd-ohne"]


def test_das_qualitaetsprotokoll_bleibt_bei_null_aus(monkeypatch):
    from boerdi.services.turn_quality import qualitaetsprotokoll_an

    monkeypatch.setattr("boerdi.services.config_loader.load_quality_log_config",
                        lambda: {"logging": {"enabled": None}})
    monkeypatch.setattr("boerdi.services.config_loader.load_privacy_config",
                        lambda: {"quality": True})
    assert qualitaetsprotokoll_an() is False
    monkeypatch.setattr("boerdi.services.config_loader.load_quality_log_config",
                        lambda: {"logging": {}})
    assert qualitaetsprotokoll_an() is True  # fehlt der Schlüssel: Vorgabe „an“


def test_null_heisst_gilt_auch_fuer_einen_unlesbaren_wert(caplog):
    """Review 19-5 (8): ein kaputter Wert an einem sicherheitsnahen Schalter ist genauso
    wenig ein „an“ wie ein gespeichertes ``null``."""
    with caplog.at_level(logging.WARNING):
        assert als_schalter("vielleicht", True, name="quality_log.logging.enabled",
                            null_heisst=False) is False
    meldungen = [r.getMessage() for r in caplog.records
                 if "quality_log.logging.enabled" in r.getMessage()]
    assert len(meldungen) == 1 and "vielleicht" not in meldungen[0]
