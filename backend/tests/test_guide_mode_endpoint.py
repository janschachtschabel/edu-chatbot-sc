"""P2-8: public GET /api/config/guide-mode — bundles guide-mode config +
header_nav buttons + welcome (ALT config_areas.py:176-198). Contract test:
response shape identical to ALT; live key-set diff when ALT runs on :8000.
"""

import httpx
import pytest
from fastapi.testclient import TestClient

from boerdi.main import create_app
from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_ALT_URL = "http://localhost:8000/api/config/guide-mode"


def _neu_bundle() -> dict:
    with TestClient(create_app()) as client:
        resp = client.get("/api/config/guide-mode")
        assert resp.status_code == 200
        return resp.json()


def test_guide_mode_bundle_shape() -> None:
    body = _neu_bundle()
    assert set(body) >= {
        "default_enabled", "allowed_hosts", "url_fields_priority",
        "max_guide_targets_per_turn", "max_guide_quick_replies",
        "trusted_domains", "repo_base_url", "header_nav", "welcome",
    }
    assert isinstance(body["header_nav"], list)
    # C1-g1a: die englische Fassung reist als eigenes Feld MIT — nicht statt.
    # Das Widget waehlt je Schluessel, weil es die Sprache zur Laufzeit
    # umschalten kann; der Server darf sie deshalb nicht vorab aufloesen.
    assert set(body["welcome"]) == {
        "greeting", "quick_replies", "tour_reply",
        "greeting_en", "quick_replies_en", "tour_reply_en",
    }
    assert body["welcome"]["greeting"]  # dev DB seeded => real content
    assert isinstance(body["trusted_domains"], list)
    for button in body["header_nav"]:
        assert "label_en" in button


def test_guide_mode_is_public_no_auth() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/api/config/guide-mode").status_code == 200


# ── C5-c2: die Herkunft des MCP-Servers für die Anmeldung ──────────────
# Ohne sie weiss das Widget nicht, wohin es das Anmeldefenster schicken soll.
# Sie steht in diesem Bündel, weil das Widget genau eine öffentliche
# Konfigurationsanfrage kennt — eine zweite Route wäre ein neuer Pfad im
# eingefrorenen Vertrag; ein Feld in einem ``-> dict`` ist keiner.


def test_die_herkunft_des_mcp_servers_steht_im_buendel() -> None:
    body = _neu_bundle()
    assert "mcp_auth_base" in body


def test_nur_die_herkunft_kein_pfad(monkeypatch) -> None:
    """Der Werkzeug-Pfad ``/mcp`` gehört nicht dazu — die Entdeckungs-Dokumente
    liegen an der Wurzel, und was nicht gebraucht wird, wird nicht veröffentlicht."""
    from boerdi.api import config as api_config

    monkeypatch.setattr(
        api_config, "get_settings",
        lambda: type("S", (), {"mcp_server_url": "https://mcp.example.org:8443/mcp?x=1"})(),
    )
    assert api_config._mcp_auth_base() == "https://mcp.example.org:8443"


@pytest.mark.parametrize("kaputt", ["", "   ", "nicht-mal-eine-url", "ftp://host/x", "//host/x"])
def test_unbrauchbare_angaben_ergeben_leer(monkeypatch, kaputt) -> None:
    """Leer heisst dem Widget „keine Anmeldung angeboten" — besser als ein
    halbes Ziel, auf das der Browser dann ein Fenster schickt."""
    from boerdi.api import config as api_config

    monkeypatch.setattr(
        api_config, "get_settings",
        lambda: type("S", (), {"mcp_server_url": kaputt})(),
    )
    assert api_config._mcp_auth_base() == ""


def _alt_available() -> bool:
    try:
        return httpx.get(_ALT_URL, timeout=3).status_code == 200
    except Exception:
        return False


@pytest.mark.skipif(not _alt_available(), reason="ALT-Backend nicht erreichbar (:8000)")
def test_key_set_matches_live_alt() -> None:
    alt = httpx.get(_ALT_URL, timeout=5).json()
    neu = _neu_bundle()
    assert set(neu) == set(alt), (
        f"nur NEU: {set(neu) - set(alt)}; nur ALT: {set(alt) - set(neu)}"
    )
    assert set(neu["welcome"]) == set(alt["welcome"])
