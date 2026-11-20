"""Plan 2026-11-19, A5 (E6, Befund S4): Ebene 2 aus einem Dokument.

Meldet das Modell für Ebene 1 eines Dokuments bei ALLEN Punkten ``unterthemen: 0``, gilt das als
„nicht angegeben“ — jeder Punkt bekommt ``UNTERTHEMEN_OBEN`` als Plan (die Augenoptiker-Läufe
blieben sonst flach). Ein frei erzeugter Entwurf und die Materialien der Person (``aus_inhalten``)
bleiben, wie sie sind.
"""

from __future__ import annotations

from types import SimpleNamespace

from boerdi.domain.dokument_gliederung import gliederung
from boerdi.services import strukturentwurf_dokument as sd
from boerdi.services import strukturentwurf_prompt as prompt
from boerdi.services.ablauf.metadaten import DOKUMENT_FORMAT
from tests.test_strukturentwurf_dienst import Attrappe, _auftrag, _erzeugen, _k
from tests.test_strukturentwurf_dokument import _MD
from tests.test_strukturentwurf_dokument import _erzeugen as _aus_dokument


def _ids() -> dict[str, str]:
    return {a.titel: a.id for a in gliederung(_MD)[0]}


def _kinder_aufrufe(llm: Attrappe) -> list[dict]:
    return [a["auftrag"] for a in llm.aufrufe if "knoten" in a["auftrag"]]


async def test_alle_null_beim_dokument_heisst_nicht_angegeben():
    ids = _ids()
    llm = Attrappe([_k("Mechanik", abschnitte=[ids["1 Mechanik"]]),
                    _k("Optik", abschnitte=[ids["2 Optik"]])],
                   {"Mechanik": [_k("Kraft"), _k("Energie")], "Optik": [_k("Linsen"), _k("Licht")]})
    erzeugt = await _aus_dokument(llm, tiefe=2)
    assert [[c["titel"] for c in k["kinder"]] for k in erzeugt.daten["knoten"]] == [
        ["Kraft", "Energie"], ["Linsen", "Licht"]]
    assert [a["anzahl"] for a in _kinder_aufrufe(llm)] == [prompt.UNTERTHEMEN_OBEN] * 2


async def test_eine_angabe_gilt_null_mit_abschnitten_nicht():
    """Review A, MINOR 5: je Punkt — 0 bei einem Punkt MIT Abschnitten heißt „nicht angegeben“
    (gemessen: der lange Plan Anlagenmechaniker SHK, 6 von 12 Punkten flach); ohne Abschnitte gibt
    es keinen Text, der Punkt bleibt, wie das Modell ihn plant."""
    ids = _ids()
    llm = Attrappe([_k("Mechanik", 2, abschnitte=[ids["1 Mechanik"]]),
                    _k("Optik", abschnitte=[ids["2 Optik"]]), _k("Akustik")],
                   {"Mechanik": [_k("Kraft"), _k("Energie")], "Optik": [_k("Linsen"), _k("L")],
                    "Akustik": [_k("Schall"), _k("Ton")]})
    erzeugt = await _aus_dokument(llm, tiefe=2)
    aufrufe = {k["knoten"]["titel"]: k["anzahl"] for k in _kinder_aufrufe(llm)}
    assert aufrufe == {"Mechanik": prompt.UNTERTHEMEN_OBEN, "Optik": prompt.UNTERTHEMEN_OBEN}
    assert "kinder" not in erzeugt.daten["knoten"][2]


async def test_sechs_von_zwoelf_ohne_angabe_bekommen_ebene_zwei(monkeypatch):
    monkeypatch.setattr(sd, "GANZTEXT_ZEICHEN", 0)              # der lange Weg
    erste = gliederung(_MD)[0][0].id
    oben = [_k(f"P{n}", 3 if n % 2 else 0, abschnitte=[erste]) for n in range(12)]
    llm = Attrappe(oben, {f"P{n}": [_k(f"P{n} a"), _k(f"P{n} b")] for n in range(12)})
    erzeugt = await _aus_dokument(llm, tiefe=2)
    assert len(_kinder_aufrufe(llm)) == 12
    assert all(k.get("kinder") for k in erzeugt.daten["knoten"])


async def test_ohne_dokument_bleibt_alle_null_flach():
    llm = Attrappe([_k("Licht"), _k("Spiegel")], {"Licht": [_k("Quellen"), _k("Schatten")]})
    erzeugt = await _erzeugen(_auftrag(tiefe=2), llm)
    assert _kinder_aufrufe(llm) == [] and erzeugt.grund is None


async def test_die_materialien_der_person_bleiben_wie_sie_sind():
    abschnitte, _ = gliederung("## Video Fotosynthese\nPflanzen.\n## Blatt Zellatmung\nZellen.\n")
    materialien = SimpleNamespace(markdown="", abschnitte=abschnitte, format=DOKUMENT_FORMAT)
    llm = Attrappe([_k("Fotosynthese", abschnitte=[abschnitte[0].id])],
                   {"Fotosynthese": [_k("Licht"), _k("Zucker")]})
    await _aus_dokument(llm, dokument=materialien, tiefe=2)
    assert _kinder_aufrufe(llm) == []
