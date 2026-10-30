"""Gedrosselte Warnungen (Paket 18E): höchstens eine Zeile je Schlüssel und Abstand.

Ein Fehler, der je Zug auftritt, soll sichtbar sein, aber das Log nicht fluten; die nächste
Zeile nach der Pause sagt, wie viele gleiche dazwischen ausgelassen wurden.
"""

from __future__ import annotations

import logging
import math

import pytest

from boerdi.obs import drossel

_LOG = logging.getLogger("test.drossel")


@pytest.fixture(autouse=True)
def _frisch():
    drossel.zuruecksetzen()
    yield
    drossel.zuruecksetzen()


def test_erste_meldung_kommt_weitere_im_abstand_nicht(caplog, monkeypatch):
    jetzt = [100.0]
    monkeypatch.setattr(drossel, "_uhr", lambda: jetzt[0])
    with caplog.at_level(logging.WARNING, logger="test.drossel"):
        assert drossel.gedrosselt(_LOG, logging.WARNING, "k", 60, "Fehler in %s", "x") is True
        jetzt[0] = 130.0
        assert drossel.gedrosselt(_LOG, logging.WARNING, "k", 60, "Fehler in %s", "x") is False
        assert drossel.gedrosselt(_LOG, logging.WARNING, "k", 60, "Fehler in %s", "x") is False
        jetzt[0] = 161.0
        assert drossel.gedrosselt(_LOG, logging.WARNING, "k", 60, "Fehler in %s", "x") is True
    texte = [r.getMessage() for r in caplog.records]
    assert texte == ["Fehler in x", "Fehler in x (2 gleiche Meldungen ausgelassen)"]


def test_schluessel_sind_unabhaengig(caplog):
    with caplog.at_level(logging.WARNING, logger="test.drossel"):
        drossel.gedrosselt(_LOG, logging.WARNING, "a", math.inf, "A")
        drossel.gedrosselt(_LOG, logging.WARNING, "b", math.inf, "B")
        drossel.gedrosselt(_LOG, logging.WARNING, "a", math.inf, "A")
    assert [r.getMessage() for r in caplog.records] == ["A", "B"]


def test_stufe_wird_eingehalten(caplog):
    with caplog.at_level(logging.DEBUG, logger="test.drossel"):
        drossel.gedrosselt(_LOG, logging.ERROR, "e", 60, "schlimm")
    assert caplog.records[0].levelno == logging.ERROR


def test_reicht_den_traceback_durch(caplog):
    """Review 18E-2: eine gedrosselte Warnung kann den Traceback tragen (``exc_info``)."""
    log = logging.getLogger("boerdi.test.drossel.traceback")
    with caplog.at_level(logging.WARNING, logger=log.name):
        try:
            raise RuntimeError("kaputt")
        except RuntimeError:
            drossel.gedrosselt(log, logging.WARNING, "tb", 60.0, "gescheitert", exc_info=True)

    assert len(caplog.records) == 1 and caplog.records[0].exc_info is not None
