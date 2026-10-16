"""DB-Tore in der CI: scheitern statt still überspringen (Paket 6, B3).

Module mit ``skipif(not pg_utils.dev_db_ready())`` fielen unter Last ganz aus,
ohne Fehler (am 2026-10-08 ``test_guide_mode_endpoint.py`` mit 9 Tests). In der
CI hieße das: grün, obwohl nicht geprüft — dort ist die Datenbank bereitgestellt,
ein Überspringen ist also immer ein Fehler.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests import db_tor, pg_utils


def _bericht(grund: str, *, skipped: bool = True):
    return SimpleNamespace(skipped=skipped, longrepr=("tests/x.py", 1, f"Skipped: {grund}"))


@pytest.mark.parametrize("grund", [pg_utils.SKIP_REASON, pg_utils.DEV_DB_SKIP_REASON])
def test_in_der_ci_ist_ein_db_tor_ein_fehler(grund):
    assert db_tor.ist_verbotener_sprung(_bericht(grund), {"CI": "true"}) is True


def test_ausserhalb_der_ci_bleibt_es_ein_ueberspringen():
    assert db_tor.ist_verbotener_sprung(_bericht(pg_utils.DEV_DB_SKIP_REASON), {}) is False
    assert db_tor.ist_verbotener_sprung(
        _bericht(pg_utils.DEV_DB_SKIP_REASON), {"CI": "false"}) is False


def test_andere_spruenge_bleiben_spruenge():
    assert db_tor.ist_verbotener_sprung(_bericht("nur unter Windows"), {"CI": "true"}) is False
    assert db_tor.ist_verbotener_sprung(
        _bericht(pg_utils.SKIP_REASON, skipped=False), {"CI": "true"}) is False


def test_die_proben_laufen_je_prozess_nur_einmal(monkeypatch):
    # Einmal am Anfang, solange noch keine Last anliegt — nicht je Modul mitten
    # im Lauf, wo eine kurze Frist unter Last ein ganzes Modul kostete.
    assert hasattr(pg_utils.dev_db_ready, "cache_info")
    assert hasattr(pg_utils.pg_available, "cache_info")
    assert pg_utils.PROBE_TIMEOUT_S >= 10
