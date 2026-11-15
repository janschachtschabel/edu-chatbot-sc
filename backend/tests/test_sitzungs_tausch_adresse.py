"""Anmeldung aus der WLO-Sitzung (Plan 2026-11-15): die Adresse des Tauschs im Widget-Bündel.

Das Backend nennt dem Widget nur, WO der MCP-Server die Sitzung einer Repository-Seite tauscht
(``MCP_SESSION_URL`` → Feld ``mcp_session_url``). Den Tausch selbst macht der Browser auf dem
Host des Repositorys; das Backend sieht davon nichts als später den Block.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from boerdi.domain.mcp_herkunft import sitzungs_adresse
from boerdi.settings import Settings

_GUT = "https://repository.example.org/edu-sharing/services/wlo-mcp/auth/session"


def test_eine_brauchbare_adresse_bleibt_wie_sie_ist():
    assert sitzungs_adresse(_GUT) == _GUT
    assert sitzungs_adresse(f"  {_GUT}  ") == _GUT
    assert sitzungs_adresse("http://localhost:8080/edu-sharing/auth/session") == (
        "http://localhost:8080/edu-sharing/auth/session")
    assert sitzungs_adresse("http://[::1]:8080/edu-sharing/auth/session") == (
        "http://[::1]:8080/edu-sharing/auth/session")


def test_leer_heisst_nicht_angeboten():
    assert sitzungs_adresse("") == ""
    assert sitzungs_adresse("   ") == ""
    assert sitzungs_adresse(None) == ""


@pytest.mark.parametrize("kaputt", [
    "/edu-sharing/services/wlo-mcp/auth/session",                 # ohne Herkunft
    "//repository.example.org/edu-sharing/auth/session",
    "ftp://repository.example.org/edu-sharing/auth/session",
    "https://repository.example.org/auth/session",                # ohne Wurzel des Repositorys
    "https://repository.example.org/edu-sharing/rest/node/v1",    # endet nicht auf /auth/session
    "https://repository.example.org/edu-sharing/auth/session/",
    "https://repository.example.org/edu-sharing/auth/session?x=1",
    "https://repository.example.org/edu-sharing/auth/session#x",
    "https://nutzer:geheim@repository.example.org/edu-sharing/auth/session",
    "https://repository.example.org/edu-sharing/../auth/session",
    "https://repository.example.org/edu-sharing/%2e%2e/auth/session",
    "https://repository.example.org/edu-sharing//auth/session",
    "https://repository.example.org:99999/edu-sharing/auth/session",
    "https://repository.example.org/edu-sharing/auth/session\nX: y",
    # Ein Browser liest diese anders als ``urlparse`` — beide Riegel sollen dasselbe sehen.
    "https://repository.example.org\\x/edu-sharing/auth/session",
    "https://repo sitory.example.org/edu-sharing/auth/session",
    "https://repository.example.org/edu-sharing/au\tth/session",
    "https://repository.example.org:/edu-sharing/auth/session",
    "https://repository_x.example.org/edu-sharing/auth/session",
    "https://repository.example.org/edu-sharing/%61uth/session",
    "https://repository.example.org/edu-sharing/auth/session;x=1",
    "https://repösitory.example.org/edu-sharing/auth/session",
    "https://-repository.example.org/edu-sharing/auth/session",
    "HTTPS://repository.example.org/edu-sharing/auth/session",
])
def test_eine_unbrauchbare_adresse_wird_abgelehnt(kaputt):
    """Dieselbe Regel wie im Widget (``session/session-login.ts``): nur Herkunft und ein
    schlichter Pfad auf ``/auth/session`` — sonst ließe sich das Widget auf einen anderen
    Pfad der Repository-Seite lenken."""
    with pytest.raises(ValueError):
        sitzungs_adresse(kaputt)


def test_eine_kaputte_ipv6_adresse_endet_in_derselben_meldung():
    """``urlparse`` wirft bei ``[…]`` ohne gültige Adresse selbst — mit einem anderen Text."""
    with pytest.raises(ValueError, match="MCP_SESSION_URL"):
        sitzungs_adresse("https://[1.2]/edu-sharing/auth/session")


def test_die_herkunft_einer_kaputten_adresse_ist_leer_statt_eines_wurfs():
    """Dieselbe Funktion liest ``MCP_SERVER_URL`` für das öffentliche Widget-Bündel: ein Wurf
    wäre dort ein 500 am Config-Abruf."""
    from boerdi.domain.mcp_herkunft import mcp_herkunft

    assert mcp_herkunft("https://[1.2]/mcp") == ""


def test_die_einstellung_ist_ohne_vorgabe_leer(monkeypatch):
    monkeypatch.delenv("MCP_SESSION_URL", raising=False)
    assert Settings(_env_file=None).mcp_session_url == ""


def test_die_einstellung_nimmt_eine_brauchbare_adresse(monkeypatch):
    monkeypatch.setenv("MCP_SESSION_URL", f" {_GUT} ")
    assert Settings(_env_file=None).mcp_session_url == _GUT


def test_ein_tippfehler_beendet_den_start_mit_einer_meldung(monkeypatch):
    """SA-11: still abgeschaltet fiele niemandem auf — die Person bliebe einfach unangemeldet."""
    monkeypatch.setenv("MCP_SESSION_URL", "https://repository.example.org/edu-sharing/session")
    with pytest.raises(ValidationError) as fehler:
        Settings(_env_file=None)
    assert "MCP_SESSION_URL" in str(fehler.value)


# ── das Feld im Widget-Bündel ────────────────────────────────────────────────


def _buendel(monkeypatch, *, origin, offen, adresse=_GUT):
    from boerdi.api import config as api_config

    einstellungen = SimpleNamespace(
        mcp_server_url="https://mcp.example.org/mcp", mcp_session_url=adresse,
        cors_allow_all=offen, cors_origin_list=["https://repository.example.org"],
        cors_origin_regex=None)
    monkeypatch.setattr(api_config, "get_settings", lambda: einstellungen)
    monkeypatch.setattr(api_config.cl, "load_guide_mode_config", lambda: {})
    monkeypatch.setattr(api_config.cl, "load_header_nav_config", lambda: {})
    monkeypatch.setattr(api_config.cl, "load_welcome_config", lambda: {})
    anfrage = SimpleNamespace(headers={"origin": origin} if origin else {})
    return asyncio.run(api_config.get_guide_mode(anfrage))


def test_das_buendel_nennt_die_adresse(monkeypatch):
    assert _buendel(monkeypatch, origin=None, offen=True)["mcp_session_url"] == _GUT


def test_ohne_einstellung_ist_das_feld_leer(monkeypatch):
    assert _buendel(monkeypatch, origin=None, offen=True, adresse="")["mcp_session_url"] == ""


def test_eine_geschlossene_anlage_nennt_sie_nur_seiten_die_sie_bedient(monkeypatch):
    """Wie die Anmelde-Adresse (Nutzer-Entscheid 2026-10-15, A-2)."""
    eigen = _buendel(monkeypatch, origin="https://repository.example.org", offen=False)
    fremd = _buendel(monkeypatch, origin="https://fremd.example", offen=False)
    assert eigen["mcp_session_url"] == _GUT
    assert fremd["mcp_session_url"] == ""
    assert fremd["mcp_auth_base"] == ""
