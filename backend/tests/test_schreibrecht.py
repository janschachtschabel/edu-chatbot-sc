"""Schreiben nur mit eigenem WLO-Konto (Paket 7, S4 — P5-9, Nutzer-Entscheid 2026-10-09).

Bis Paket 7 genügte im Muster-Modus der Dienst-Block der Anlage
(``MCP_AUTH_TOKEN``): der Bot nahm Inhalte in Sammlungen auf, ohne dass eine
Person angemeldet war (Audit 2026-09-29, B-H3). Jetzt gilt in beiden Modi die
Regel des Agent-Modus — außer das Studio erlaubt das Gastkonto ausdrücklich
(``01-base/engine`` → ``betrieb.gastkonto_schreibt``, Vorgabe aus).
"""

from __future__ import annotations

import pytest

from boerdi.domain.config_models.engine import EngineArea
from boerdi.services import betriebsschalter, schreibrecht


def _lage(monkeypatch, *, person: bool, block: bool, gast: bool) -> None:
    monkeypatch.setattr(schreibrecht, "has_personal_auth", lambda: person)
    monkeypatch.setattr(schreibrecht, "handelt_mit_dem_block_der_anlage", lambda: block)
    monkeypatch.setattr(betriebsschalter, "load_engine", lambda: EngineArea.model_validate(
        {"betrieb": {"gastkonto_schreibt": gast}}))


@pytest.mark.parametrize(("person", "block", "gast", "erwartet"), [
    (True, False, False, True),    # angemeldete Person: immer
    (False, True, False, False),   # nur der Dienst-Block: nicht mehr (B-H3)
    (False, True, True, True),     # … außer das Studio erlaubt das Gastkonto
    (False, False, True, False),   # ohne jeden Block hilft auch der Schalter nicht
])
def test_wer_schreiben_darf(monkeypatch, person, block, gast, erwartet):
    _lage(monkeypatch, person=person, block=block, gast=gast)
    assert schreibrecht.schreiben_erlaubt() is erwartet


def test_der_gastschalter_ist_von_haus_aus_aus():
    assert EngineArea().betrieb.gastkonto_schreibt is False


@pytest.mark.parametrize(("zug_block", "erwartet"), [
    ("", True),                    # kein eigener Block: es gilt der der Anlage
    ("wlo-anon.v1", False),        # anonymer Zug-Block geht vor — der Server lehnte ab
    ("wlo2.abc-def_123", True),    # persönlicher Block: die Person schreibt
])
def test_das_gastkonto_schreibt_nur_mit_dem_block_der_anlage(monkeypatch, zug_block, erwartet):
    """Review Paket 7 (MINOR 27): ``has_auth_token`` zählte auch einen anonymen
    Zug-Block. Der geht dem Block der Anlage vor — geschrieben hätte der Bot unter
    der anonymen Kennung, und der MCP-Server hätte abgelehnt."""
    from boerdi.settings import get_settings
    from tests.helfer_anmeldung import als_person

    monkeypatch.setenv("MCP_AUTH_TOKEN", "wlo2.dienstkonto")
    get_settings.cache_clear()
    monkeypatch.setattr(betriebsschalter, "load_engine", lambda: EngineArea.model_validate(
        {"betrieb": {"gastkonto_schreibt": True}}))
    try:
        als_person(zug_block)
        assert schreibrecht.schreiben_erlaubt() is erwartet
    finally:
        als_person("")
        get_settings.cache_clear()
