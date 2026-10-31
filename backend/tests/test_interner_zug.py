"""Paket 18C/D (3.3): ``ist_interner_zug`` und ``darf_diagnose`` — fragt die Anlage selbst?

``ist_interner_zug``: der Studio-Proxy nach der Anmeldung oder ein gültiger Studio-Schlüssel.
Daran hängt die Buchung auf ``B_API_KEY`` (``B_API_KEY_MODE=forward``). ``darf_diagnose``
(Zugakte im Verlauf, ab Phase 4 der Debug-Block) gilt zusätzlich im reinen Entwicklungsmodus
(``BOERDI_ALLOW_OPEN_ADMIN`` ohne Schlüssel) — dort ist ohnehin alles offen
(``require_studio_key``), sonst verlöre der Lasttest lokal seine Kennzahlen (Plan R4). Die
Buchung bleibt davon unberührt (Review Phase 3): ein falsch eingerichteter Betrieb buchte sonst
jeden anonymen Zug auf den gemeinsamen Schlüssel.
"""

from __future__ import annotations

import pytest
from starlette.requests import Request

from boerdi.api.studio_proxy import _UEBER_STUDIO
from boerdi.api.turn_auth import darf_diagnose, ist_interner_zug
from boerdi.settings import get_settings


def _anfrage(*, proxy: bool = False, schluessel: str | None = None) -> Request:
    koepfe = [(b"x-studio-key", schluessel.encode())] if schluessel is not None else []
    scope = {"type": "http", "method": "GET", "path": "/", "headers": koepfe}
    if proxy:
        scope[_UEBER_STUDIO] = True
    return Request(scope)


@pytest.fixture()
def umgebung(monkeypatch):
    def setzen(*, passwort: str | None, schluessel: str | None, offen: bool) -> None:
        for name, wert in (("STUDIO_PASSWORD", passwort), ("STUDIO_API_KEY", schluessel),
                           ("BOERDI_ALLOW_OPEN_ADMIN", "1" if offen else None)):
            if wert is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, wert)
        get_settings.cache_clear()

    yield setzen
    get_settings.cache_clear()


def test_das_angemeldete_studio_ueber_den_proxy(umgebung):
    umgebung(passwort="pw", schluessel="k", offen=False)
    assert ist_interner_zug(_anfrage(proxy=True)) is True


def test_ein_gueltiger_schluessel(umgebung):
    umgebung(passwort="pw", schluessel="k", offen=False)
    assert ist_interner_zug(_anfrage(schluessel="k")) is True


@pytest.mark.parametrize("schluessel", [None, "falsch", "kä"])
def test_ohne_oder_mit_falschem_schluessel_nicht(umgebung, schluessel):
    umgebung(passwort="pw", schluessel="k", offen=False)
    assert ist_interner_zug(_anfrage(schluessel=schluessel)) is False


def test_offenes_tor_mit_schluessel_ist_keine_freigabe(umgebung):
    umgebung(passwort=None, schluessel="k", offen=True)
    assert ist_interner_zug(_anfrage(proxy=True)) is False


def test_der_reine_entwicklungsmodus_gibt_diagnose_frei_aber_bucht_nicht(umgebung):
    umgebung(passwort=None, schluessel=None, offen=True)
    assert darf_diagnose(_anfrage()) is True
    assert ist_interner_zug(_anfrage()) is False


def test_diagnose_folgt_sonst_dem_internen_zug(umgebung):
    umgebung(passwort="pw", schluessel="k", offen=False)
    assert darf_diagnose(_anfrage(schluessel="k")) is True
    assert darf_diagnose(_anfrage(schluessel="falsch")) is False


def test_ohne_schluessel_und_ohne_entwicklungsmodus_nicht(umgebung):
    umgebung(passwort=None, schluessel=None, offen=False)
    assert ist_interner_zug(_anfrage()) is False
    assert darf_diagnose(_anfrage()) is False



def test_ein_schluessel_ausserhalb_von_ascii_ergibt_kein_500(umgebung):
    """Review 2026-10-30: ``compare_digest`` warf bei einem Nicht-ASCII-Schlüssel — jeder Zug mit
    Kopfzeile wurde zum 500."""
    umgebung(passwort="pw", schluessel="kä", offen=False)
    assert ist_interner_zug(_anfrage(schluessel="k")) is False
    assert darf_diagnose(_anfrage(schluessel="k")) is False


def test_require_studio_key_mit_nicht_ascii_schluessel_sagt_401(umgebung):
    import asyncio

    from fastapi import HTTPException

    from boerdi.api.deps import require_studio_key

    umgebung(passwort="pw", schluessel="kä", offen=False)
    with pytest.raises(HTTPException) as e:
        asyncio.run(require_studio_key(_anfrage(), "k-studio-testkey"))
    assert e.value.status_code == 401


def test_der_entwicklungsmodus_bucht_proxy_zuege_auf_den_eigenen_schluessel(umgebung):
    """Paket 18G (G-E2): festgehalten, damit eine Änderung bewusst geschieht — die Chat-Probe im
    Studio läuft lokal ohne eigenen Schlüssel."""
    umgebung(passwort=None, schluessel=None, offen=True)
    assert ist_interner_zug(_anfrage(proxy=True)) is True



def test_forward_weist_die_studio_probe_im_entwicklungsmodus_nicht_ab(umgebung, monkeypatch):
    """G-E2: die eigentliche Wirkung — kein 401 unter ``forward`` für den Proxy-Zug."""
    from boerdi.api.turn_auth import uebernimm_llm_schluessel

    umgebung(passwort=None, schluessel=None, offen=True)
    monkeypatch.setenv("B_API_KEY_MODE", "forward")
    monkeypatch.setenv("LLM_PROVIDER", "b-api-openai")
    get_settings.cache_clear()
    uebernimm_llm_schluessel(_anfrage(proxy=True))  # wirft nicht
