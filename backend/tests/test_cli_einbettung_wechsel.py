"""``boerdi rag-einbettung-wechseln`` — die Kommandozeile um ``services/rag/einbettung_wechsel``
(Paket 11, D).

Die Datenbank-Seite prüft ``test_rag_einbettung_wechsel_pg.py``; hier nur Optionen, Ausgabe und
Rückgabewert.
"""

from __future__ import annotations

import pytest

from boerdi import cli
from boerdi.services.rag import einbettung_wechsel as ew


class _Motor:
    async def dispose(self) -> None:
        return None


@pytest.fixture
def aufrufe(monkeypatch):
    gesehen: list[dict] = []
    antwort: dict = {"bericht": ew.Bericht(spalte_vorher=1536, dimension=1024, abschnitte=3,
                                           fehlend=0, eingebettet=3)}

    async def wechseln(_engine, **kwargs):
        gesehen.append(kwargs)
        if isinstance(antwort["bericht"], Exception):
            raise antwort["bericht"]
        return antwort["bericht"]

    monkeypatch.setattr(cli, "make_engine", lambda _s, **_k: _Motor())
    monkeypatch.setattr(ew, "wechseln", wechseln)
    return gesehen, antwort


def test_probe_zeigt_und_aendert_nichts(aufrufe, capsys):
    gesehen, antwort = aufrufe
    antwort["bericht"] = ew.Bericht(spalte_vorher=1536, dimension=1024, abschnitte=906, fehlend=0)
    assert cli.main(["rag-einbettung-wechseln", "--probe"]) == 0
    assert gesehen == [{"probe": True, "fortsetzen": False}]
    aus = capsys.readouterr().out
    assert "1536" in aus and "1024" in aus and "906" in aus and "nichts geändert" in aus


def test_ein_voller_lauf_meldet_das_ergebnis(aufrufe, capsys):
    gesehen, _a = aufrufe
    assert cli.main(["rag-einbettung-wechseln"]) == 0
    assert gesehen == [{"probe": False, "fortsetzen": False}]
    assert "3 von 3" in capsys.readouterr().out


def test_fehlende_abschnitte_enden_mit_hinweis_und_code_1(aufrufe, capsys):
    _g, antwort = aufrufe
    antwort["bericht"] = ew.Bericht(spalte_vorher=1536, dimension=1024, abschnitte=3, fehlend=1,
                                    eingebettet=2)
    assert cli.main(["rag-einbettung-wechseln", "--fortsetzen"]) == 1
    assert "--fortsetzen" in capsys.readouterr().err


def test_ein_abbruch_endet_mit_code_2(aufrufe, capsys):
    _g, antwort = aufrufe
    antwort["bericht"] = ew.Abbruch("EMBED_DIM=1024 setzen")
    assert cli.main(["rag-einbettung-wechseln"]) == 2
    assert "EMBED_DIM=1024" in capsys.readouterr().err


def test_probe_und_fortsetzen_schliessen_sich_aus(aufrufe, capsys):
    gesehen, _a = aufrufe
    assert cli.main(["rag-einbettung-wechseln", "--probe", "--fortsetzen"]) == 2
    assert gesehen == []
