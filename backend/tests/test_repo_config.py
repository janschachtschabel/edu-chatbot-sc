"""Das Repositorium als Angabe in der Konfiguration — und als Zusage.

Nutzer-Vorgabe 2026-08-14: „Der Chatbot muss aktuell auf Staging konfiguriert
sein — dazu sollte er eine Repoangabe in der Konfig haben und diese konsequent
einhalten."

Drei Dinge, die vorher fehlten:

1. **Die Angabe lebt nur in einer Umgebungsvariablen mit Prod als Vorgabe.**
   Nicht gesetzt heisst damit „Produktion" — die stille falsche Antwort. Wer im
   Studio nachsehen will, welches Repositorium gilt, findet nichts.
2. **Der Live-Kartenweg hielt sie nicht konsequent ein.** ``rewrite_repo_host``
   schreibt nur Adressen um, die mit dem Prod-Standardhost beginnen; ein Link
   von einem anderen bekannten Repo-Host blieb stehen. Die Fassung, die alle
   bekannten Hosts kennt (``rewrite_repo_host_v2``), hing an einem Schalter, der
   aus ist.
3. **Nichts sagt im Betrieb, welches Repositorium gilt.** „Ist der Bot auf
   Staging?" war nur durch Lesen der Deploy-Umgebung zu beantworten.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from boerdi.main import create_app
from boerdi.services.config_loader import repo_and_cards as rc
from boerdi.services.mcp.parsers.cards import parse_wlo_cards

_STAGING = "https://repository.staging.openeduhub.net"
_PROD = "https://redaktion.openeduhub.net"
_ZWEITES_PROD = "https://repository.openeduhub.net"


@pytest.fixture(autouse=True)
def _frischer_zwischenspeicher():
    # ``get_repo_base_url`` merkt sich die Quelle fuer die Startzeile; ohne
    # Ruecksetzen faerbte ein Test den naechsten.
    rc.reset_repo_base_url_cache()
    yield
    rc.reset_repo_base_url_cache()


def _mit_konfig(monkeypatch, wert: object) -> None:
    """Die Konfig-Angabe setzen, ohne den ganzen Seed-Baum zu laden."""
    monkeypatch.setattr(
        rc, "area", lambda name: {"card_pipeline": {"repo_base_url": wert}},
    )


def _mit_env(monkeypatch, wert: str) -> None:
    monkeypatch.setattr(rc, "get_settings", lambda: type("S", (), {
        "repo_base_url": wert,
    })())


# ═══ 1. Die Angabe in der Konfiguration ══════════════════════════════════

def test_die_konfig_angabe_gilt_vor_der_umgebungsvariablen(monkeypatch):
    # Der Sinn der Angabe: im Studio steht, welches Repositorium gilt — sonst
    # waere sie Zierde.
    _mit_env(monkeypatch, _PROD)
    _mit_konfig(monkeypatch, _STAGING)
    assert rc.get_repo_base_url() == _STAGING


def test_ohne_konfig_angabe_gilt_die_umgebungsvariable(monkeypatch):
    # Rueckwaertsvertraeglich: Bestands-Deploys setzen REPO_BASE_URL.
    _mit_env(monkeypatch, _STAGING)
    _mit_konfig(monkeypatch, "")
    assert rc.get_repo_base_url() == _STAGING


def test_ein_schraegstrich_am_ende_verschwindet(monkeypatch):
    # Alle Verbraucher haengen ``/edu-sharing/…`` an; ohne Normalisierung
    # entstuende ``…net//edu-sharing``.
    _mit_env(monkeypatch, _PROD)
    _mit_konfig(monkeypatch, _STAGING + "/")
    assert rc.get_repo_base_url() == _STAGING


def test_unsinn_in_der_konfig_faellt_auf_die_umgebungsvariable_zurueck(monkeypatch):
    # Eine kaputte Angabe darf den Zug nicht kippen — sie darf ihn nur nicht
    # heimlich auf ein anderes Repositorium schicken.
    _mit_env(monkeypatch, _STAGING)
    for unsinn in (None, 123, "   ", "kein-schema.example"):
        _mit_konfig(monkeypatch, unsinn)
        rc.reset_repo_base_url_cache()
        assert rc.get_repo_base_url() == _STAGING


def test_eine_unlesbare_konfig_wirft_nicht(monkeypatch):
    def _kaputt(_name):
        raise RuntimeError("Speicher nicht erreichbar")

    monkeypatch.setattr(rc, "area", _kaputt)
    _mit_env(monkeypatch, _STAGING)
    assert rc.get_repo_base_url() == _STAGING


# ═══ 2. Konsequent einhalten ═════════════════════════════════════════════

def _envelope(url: str) -> str:
    import json
    return json.dumps({"total": 1, "count": 1, "results": [
        {"nodeId": "n1", "title": "Optik", "nodeType": "collection", "url": url},
    ]})


def test_ein_link_von_einem_anderen_repo_host_folgt_der_angabe(monkeypatch):
    """Der eigentliche Befund: ``rewrite_repo_host`` kennt nur den Prod-Host.

    Steht die Angabe auf Staging und liefert der Server einen Link vom ZWEITEN
    Produktionshost, blieb er stehen — der Chat zeigte eine Adresse, die zum
    konfigurierten Repositorium nicht passt.
    """
    _mit_env(monkeypatch, _STAGING)
    _mit_konfig(monkeypatch, _STAGING)
    karten = parse_wlo_cards(_envelope(f"{_ZWEITES_PROD}/edu-sharing/components/render/n1"))
    assert karten[0]["url"].startswith(_STAGING)


def test_der_prod_host_wird_weiterhin_umgeschrieben(monkeypatch):
    # Die Richtung, die schon vorher stimmte, bleibt.
    _mit_env(monkeypatch, _STAGING)
    _mit_konfig(monkeypatch, _STAGING)
    karten = parse_wlo_cards(_envelope(f"{_PROD}/edu-sharing/components/render/n1"))
    assert karten[0]["url"].startswith(_STAGING)


def test_ein_fremder_host_bleibt_unangetastet(monkeypatch):
    # Externe Inhalte (YouTube, Geogebra, …) sind keine Repo-Adressen.
    _mit_env(monkeypatch, _STAGING)
    _mit_konfig(monkeypatch, _STAGING)
    karten = parse_wlo_cards(_envelope("https://www.geogebra.org/m/abc"))
    assert karten[0]["url"] == "https://www.geogebra.org/m/abc"


# ═══ 3. Im Betrieb sichtbar ══════════════════════════════════════════════

def test_health_nennt_das_repositorium():
    """Ohne dieses Feld ist „laeuft der Bot gegen Staging?" nur durch Lesen der
    Deploy-Umgebung zu beantworten — und genau diese Frage stand am Anfang."""
    with TestClient(create_app()) as client:
        daten = client.get("/api/health").json()
    assert daten["repo"].startswith("https://")
