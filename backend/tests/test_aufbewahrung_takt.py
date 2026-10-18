"""Der Takt der Aufbewahrung (Paket 8, A): läuft wiederholt, ein Fehler hält ihn nicht an.

Ohne Datenbank — gezählt werden die Läufe, die Löschung selbst prüft
``test_aufbewahrung.py``.
"""

from __future__ import annotations

import asyncio

from boerdi.services import aufbewahrung


def test_der_takt_laeuft_weiter_auch_nach_einem_fehler(monkeypatch):
    monkeypatch.setattr(aufbewahrung, "ERSTER_LAUF_S", 0)
    monkeypatch.setattr(aufbewahrung, "TAKT_S", 0.005)
    laeufe: list[int] = []

    async def _lauf(engine, sitzungen):
        laeufe.append(1)
        if len(laeufe) == 1:
            raise RuntimeError("DB kurz weg")
        return {"safety_logs": 0, "quality_logs": 0}

    monkeypatch.setattr(aufbewahrung, "lauf", _lauf)

    async def szenario():
        aufgabe = aufbewahrung.starte(object(), object())
        await asyncio.sleep(0.05)
        aufgabe.cancel()
        await asyncio.gather(aufgabe, return_exceptions=True)
        return aufgabe

    aufgabe = asyncio.run(szenario())
    assert len(laeufe) >= 2
    assert aufgabe.cancelled()


def test_die_app_startet_den_takt_und_beendet_ihn(monkeypatch):
    """Im Lebenszyklus der App: gestartet beim Hochfahren, abgebrochen beim Herunterfahren."""
    import boerdi.main as main_mod

    gestartet: list[asyncio.Task] = []
    echt = aufbewahrung.starte

    def _starte(engine, sitzungen):
        aufgabe = echt(engine, sitzungen)
        gestartet.append(aufgabe)
        return aufgabe

    monkeypatch.setattr(aufbewahrung, "starte", _starte)
    monkeypatch.setattr(aufbewahrung, "ERSTER_LAUF_S", 3600)

    from tests import pg_utils

    if not pg_utils.dev_db_ready():
        import pytest
        pytest.skip(pg_utils.DEV_DB_SKIP_REASON)
    from fastapi.testclient import TestClient

    with TestClient(main_mod.create_app()):
        assert len(gestartet) == 1 and not gestartet[0].done()
    assert gestartet[0].done()


def test_eine_negative_frist_weist_das_bereichsmodell_ab():
    """Paket 8 (A): 0 heißt unbegrenzt; eine negative Frist hätte keine Bedeutung —
    das Studio soll sie gar nicht erst speichern können."""
    import pytest
    from pydantic import ValidationError

    from boerdi.domain.config_models.base_governance import (
        PrivacyLoggingBlock,
        QualityLoggingBlock,
        SafetyLoggingBlock,
    )

    for modell in (SafetyLoggingBlock, QualityLoggingBlock, PrivacyLoggingBlock):
        assert modell(retention_days=0).retention_days == 0
        with pytest.raises(ValidationError):
            modell(retention_days=-1)


def test_gespraechsverlaeufe_haben_dreissig_tage_als_vorgabe():
    """Nutzer 2026-10-09: die Standardfrist für Gesprächsverläufe ist 30 Tage, änderbar."""
    from boerdi.domain.config_models.base_governance import PrivacyConfigArea

    assert PrivacyConfigArea().logging.retention_days == 30


def test_die_sperre_liegt_ausserhalb_der_chat_kennungen():
    """Review Paket 7 (MINOR 14): Chat und Löschlauf teilen sich die Sitzungssperre.
    Eine Chat-Anfrage mit der Kennung ``__lauf:aufbewahrung`` blockierte den Lauf —
    seit Paket 9 lässt der Eingang diese Form nicht mehr zu."""
    import re

    from boerdi.api.schemas import SITZUNGSKENNUNG

    assert not re.fullmatch(SITZUNGSKENNUNG, aufbewahrung.SPERRE)


def _fristen_mit(monkeypatch, *, gespraeche=None, sicherheit=None, qualitaet=None) -> dict:
    """Die Fristen je Protokoll bei diesen rohen Werten (``None`` = Feld fehlt)."""
    def _bereich(wert):
        return {"logging": {} if wert is None else {"retention_days": wert}}

    monkeypatch.setattr(aufbewahrung, "area", lambda _key: _bereich(gespraeche))
    monkeypatch.setattr(aufbewahrung, "load_safety_config", lambda: _bereich(sicherheit))
    monkeypatch.setattr(aufbewahrung, "load_quality_log_config", lambda: _bereich(qualitaet))
    return {f.bereich: f.tage for f in aufbewahrung.fristen()}


def test_fehlt_die_frist_gilt_die_vorgabe_des_auslieferungsstands(monkeypatch):
    """Review Paket 7 (MINOR 15): das Modell sagte 30 Tage, der Seed 90 bzw. 180 —
    fehlte das Feld, löschte der Lauf unwiderruflich nach 30 Tagen."""
    assert _fristen_mit(monkeypatch) == {
        "messages": 30, "memory": 30, "session_state": 30, "safety_logs": 90,
        "quality_logs": 180, "quality_text": 30}


def test_die_frist_wird_wie_im_studio_gelesen(monkeypatch):
    """Ein roher Wert ``"30"`` galt als „keine Zahl“; das Modell liest ihn als 30."""
    assert _fristen_mit(monkeypatch, gespraeche="45", sicherheit=60.0)["messages"] == 45
    assert _fristen_mit(monkeypatch, sicherheit=60.0)["safety_logs"] == 60


def test_ein_wahrheitswert_loescht_nichts(monkeypatch):
    """Lax gelesen machte das Modell aus ``true`` eine 1 — ein Tag Aufbewahrung."""
    fristen = _fristen_mit(monkeypatch, gespraeche=True, qualitaet="abc")
    assert fristen["messages"] == 0 and fristen["quality_logs"] == 0
