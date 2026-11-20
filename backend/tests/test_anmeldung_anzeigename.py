"""Plan 2026-11-19, Paket B4: der Anzeigename aus ``/auth/status`` für das Kürzel im Widget.

Bisher kannte nur die Anmeldung aus der Sitzung der Seite einen Namen; von Hand und per Ticket
zeigte der Kreis ein Symbol. ``/auth/status`` nennt ``displayName`` — das Backend reicht ihn
**nur** in der Antwort des Zuges an dieselbe Person zurück (``auth_display_name``):

* gesäubert (getrimmt, ohne Steuer- und Formatzeichen, höchstens 120 Zeichen), nur für eine
  bestätigte Person (``mode: user``), nie für das geteilte Dienstkonto;
* nicht nach einer Abweisung des Blocks;
* nie in Debug, Spur, Verlauf, Log oder an das Modell — gelesen wird er nur an einer Stelle
  (``api/chat._anmeldestand``), nach dem Zug, wenn er schon gespeichert ist. Den Durchlauf durch
  einen echten Zug mit Datenbank prüft ``test_anmeldung_anzeigename_ende.py``.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

import pytest
from pydantic import SecretStr

from boerdi.api import chat
from boerdi.api.schemas import ChatResponse, DebugInfo
from boerdi.services.mcp import anmelde_endpunkte, anmeldung, auth

_BLOCK = "wlo2.persoenlich-anzeigename"
_NAME = "Jan Schachtschabel"
_SRC = Path(__file__).resolve().parents[1] / "src" / "boerdi"
_ECHT_FRAGEN = anmeldung._fragen   # conftest ersetzt ``_fragen`` durch „immer Person“


@pytest.fixture(autouse=True)
def _sauber(monkeypatch):
    from boerdi.settings import get_settings

    monkeypatch.setattr(anmeldung, "_fragen", _ECHT_FRAGEN)
    monkeypatch.setattr(get_settings(), "mcp_auth_token", SecretStr(""), raising=False)
    anmeldung._cache.clear()
    anmeldung._pause.clear()
    auth.set_turn_auth_block(None)
    yield
    anmeldung._cache.clear()
    anmeldung._pause.clear()
    auth.set_turn_auth_block(None)


def _stand(**extra) -> dict:
    return {"mode": "user", "authenticated": True, "authority": "jan", "credential": "ticket",
            "upstream": "ok", **extra}


def _mcp_sagt(monkeypatch, stand: dict, art: str = "ok") -> None:
    async def _status(_block, _frist):
        return art, stand
    monkeypatch.setattr(anmelde_endpunkte, "status_abfragen", _status)


def _zug(block: str | None = _BLOCK) -> str:
    async def lauf() -> str:
        auth.set_turn_auth_block(block)
        await anmeldung.bestaetige_anmeldung()
        return auth.zug_anzeigename()
    return asyncio.run(lauf())


# ── Was aus ``/auth/status`` übernommen wird ─────────────────────────────────
def test_eine_bestaetigte_person_bringt_ihren_namen_mit():
    assert anmeldung._aus_stand(_stand(displayName=_NAME)).anzeigename == _NAME


@pytest.mark.parametrize(("roh", "erwartet"), [
    ("  Jan   Schachtschabel  ", "Jan Schachtschabel"),
    ("Jan\u202eSchacht\u200b", "JanSchacht"),          # Richtungs- und Nullbreitenzeichen raus
    ("Jan\nSchacht\x00schabel", "Jan Schachtschabel"),  # Steuerzeichen: Zeilenumbruch → Leerraum
    ("x" * 300, "x" * 120),
    (7, ""),
    (None, ""),
    ("\u200b \t", ""),
    # Review B (5): ein einzelnes Surrogat ließ das Kodieren der Antwort scheitern (500 je
    # Zug); private, nicht vergebene und Tag-Zeichen fallen ebenso weg.
    ("Jan \ud800", "Jan"),
    ("Jan\ue000\U000e0001 Schachtschabel", "Jan Schachtschabel"),
    ("Jan\U0010ffff", "Jan"),
])
def test_der_name_wird_gesaeubert(roh, erwartet):
    assert anmeldung._aus_stand(_stand(displayName=roh)).anzeigename == erwartet


@pytest.mark.parametrize("stand", [
    {"mode": "service", "authenticated": True, "authority": None, "displayName": _NAME},
    {"mode": "user", "authenticated": False, "authority": "jan", "displayName": _NAME,
     "upstream": "ok"},
    {"mode": "anonymous", "authenticated": False, "authority": "esguest",
     "displayName": "ES Guest", "upstream": "ok"},
])
def test_ohne_bestaetigte_person_kein_name(stand):
    assert anmeldung._aus_stand(stand).anzeigename == ""


# ── Der Zug trägt ihn — und nur solange der Block gilt ───────────────────────
def test_der_zug_kennt_den_namen(monkeypatch):
    _mcp_sagt(monkeypatch, _stand(displayName=_NAME))
    assert _zug() == _NAME


def test_aus_dem_speicher_kommt_derselbe_name(monkeypatch):
    _mcp_sagt(monkeypatch, _stand(displayName=_NAME))
    _zug()
    _mcp_sagt(monkeypatch, {}, art="unklar")    # nicht neu gefragt: aus dem Speicher
    assert _zug() == _NAME


def test_ein_neuer_zug_beginnt_ohne_namen(monkeypatch):
    _mcp_sagt(monkeypatch, _stand(displayName=_NAME))
    _zug()
    assert _zug(None) == ""


def test_nach_der_abweisung_kein_name(monkeypatch):
    _mcp_sagt(monkeypatch, {}, art="abgelehnt")
    assert _zug() == ""

    async def lauf() -> str:
        _mcp_sagt(monkeypatch, _stand(displayName=_NAME))
        anmeldung._cache.clear()
        auth.set_turn_auth_block(_BLOCK)
        await anmeldung.bestaetige_anmeldung()
        auth.verwirf_zug_block()                  # später im Zug: 401 an einem Werkzeug
        return auth.zug_anzeigename()
    assert asyncio.run(lauf()) == ""


# ── Die Antwort des Zuges ────────────────────────────────────────────────────
def _antwort_nach_dem_zug(monkeypatch, stand: dict, art: str = "ok") -> ChatResponse:
    _mcp_sagt(monkeypatch, stand, art)

    async def lauf() -> ChatResponse:
        auth.set_turn_auth_block(_BLOCK)
        await anmeldung.bestaetige_anmeldung()
        return chat._anmeldestand(ChatResponse(session_id="bb-x", content="Hallo"))
    return asyncio.run(lauf())


def test_die_antwort_traegt_den_namen(monkeypatch):
    antwort = _antwort_nach_dem_zug(monkeypatch, _stand(displayName=_NAME))
    assert antwort.auth_display_name == _NAME


def test_ohne_namen_bleibt_das_feld_leer(monkeypatch):
    assert _antwort_nach_dem_zug(monkeypatch, _stand()).auth_display_name is None
    anmeldung._cache.clear()
    abgewiesen = _antwort_nach_dem_zug(monkeypatch, {}, art="abgelehnt")
    assert abgewiesen.auth_display_name is None and abgewiesen.auth_invalid


# ── Datenschutz: wo der Name hin darf ────────────────────────────────────────
def test_der_name_steht_nicht_im_log(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    _mcp_sagt(monkeypatch, _stand(displayName=_NAME))
    _zug()
    _mcp_sagt(monkeypatch, {}, art="unklar")      # Gnadenfrist schreibt eine Zeile
    anmeldung._cache[auth.fingerabdruck(_BLOCK)] = (0.0, anmeldung._cache[
        auth.fingerabdruck(_BLOCK)][1])
    assert _zug() == _NAME
    assert "Jan" not in caplog.text and "Schachtschabel" not in caplog.text


def test_debug_kennt_kein_feld_fuer_den_namen():
    assert not [f for f in DebugInfo.model_fields if "name" in f.lower() and "display" in f.lower()]


def test_nur_vier_module_fassen_den_namen_an():
    """Gelesen wird er nur in ``api/chat._anmeldestand`` — nach dem Zug, also nach dem Speichern
    (``graph/nodes/persist``), nie in einem Knoten, einer Aufforderung, der Spur oder dem Log."""
    muster = re.compile(r"zug_anzeigename|auth_display_name|merke_anzeigename|\.anzeigename\b")
    fundorte = sorted(str(p.relative_to(_SRC)).replace("\\", "/")
                      for p in _SRC.rglob("*.py") if muster.search(p.read_text(encoding="utf-8")))
    assert fundorte == ["api/chat.py", "api/schemas.py", "services/mcp/anmeldung.py",
                        "services/mcp/auth.py"]
    lesend = [z for z in (_SRC / "api" / "chat.py").read_text(encoding="utf-8").splitlines()
              if "zug_anzeigename" in z and "import" not in z]
    assert len(lesend) == 1 and "auth_display_name" in lesend[0]
