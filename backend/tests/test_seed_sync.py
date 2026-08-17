"""Auslieferungsstand aus dem Image gegen den gelebten Stand (S2).

Der Vergleich ist der Kern des neuen Studio-Knopfes: er entscheidet, was der
harmlose Weg („fehlende nachziehen") anfasst und was der verlustbehaftete
(„exakt gleichziehen") überschreibt **und löscht**.

**Der wichtigste Test dieser Datei ist ``nur_in_db``.** Diese Liste ist die
Löschliste. Zählt sie einen Bereich mit, den der Seed doch kennt, löscht der
Knopf gepflegte Konfiguration; zählt sie einen nicht mit, bleibt Altlast liegen
und der Stand ist nach dem Lauf nicht der Auslieferungsstand.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.services.seed_sync import anwenden, seed_pfad, vergleiche


def test_leerer_seed_gegen_leere_datenbank():
    d = vergleiche({}, {})
    assert (d.neu, d.gleich, d.abweichend, d.nur_in_db) == ([], [], [], [])


def test_bereich_nur_im_seed_ist_neu():
    d = vergleiche({"01-base/engine": {"mode": "pattern"}}, {})
    assert d.neu == ["01-base/engine"]
    assert d.abweichend == [] and d.nur_in_db == []


def test_gleicher_inhalt_ist_gleich_und_wird_nicht_geschrieben():
    doc = {"mode": "pattern", "agent": {"max_iterations": 12}}
    d = vergleiche({"01-base/engine": doc}, {"01-base/engine": dict(doc)})
    assert d.gleich == ["01-base/engine"]
    assert d.neu == [] and d.abweichend == []


def test_abweichender_inhalt_ist_abweichend():
    d = vergleiche({"01-base/engine": {"mode": "pattern"}},
                   {"01-base/engine": {"mode": "hybrid"}})
    assert d.abweichend == ["01-base/engine"]


def test_bereich_nur_in_der_datenbank_landet_auf_der_loeschliste():
    """Die einzige Liste dieses Vergleichs, die Daten vernichtet."""
    d = vergleiche({}, {"01-base/eigenbau": {"x": 1}})
    assert d.nur_in_db == ["01-base/eigenbau"]
    assert d.neu == [] and d.abweichend == []


def test_die_reihenfolge_ist_stabil_sortiert():
    """Das Panel zeigt die Namen; eine wechselnde Reihenfolge sähe bei zwei
    Aufrufen nach einer Änderung aus, die es nicht gab."""
    seed = {"c": {}, "a": {}, "b": {}}
    d = vergleiche(seed, {})
    assert d.neu == ["a", "b", "c"]


def test_verschachtelte_gleichheit_zaehlt_nicht_als_abweichung():
    """Der Seed wird über ``seed_io`` gelesen und die Datenbank über jsonb —
    dieselben Daten, zwei Wege. Ein Vergleich, der auf Objekt-Identität oder
    Schlüssel-Reihenfolge hörte, meldete Abweichungen, die es nicht gibt."""
    seed = {"a": {"x": [1, {"y": 2}], "z": {"tief": {"tiefer": True}}}}
    live = {"a": {"z": {"tief": {"tiefer": True}}, "x": [1, {"y": 2}]}}
    d = vergleiche(seed, live)
    assert d.gleich == ["a"] and d.abweichend == []


def test_zu_schreibende_bereiche_je_modus():
    d = vergleiche({"neu": {}, "anders": {"a": 1}, "gleich": {}},
                   {"anders": {"a": 2}, "gleich": {}, "alt": {}})
    assert d.zu_schreiben("missing") == ["neu"]
    assert d.zu_schreiben("exact") == ["anders", "neu"]
    assert d.zu_loeschen("missing") == []
    assert d.zu_loeschen("exact") == ["alt"]


# ── anwenden: was tatsächlich an der Datenbank passiert ────────────────────
# Die beiden Rückrufe machen den Ablauf ohne Datenbank prüfbar und halten
# ``seed_sync`` frei von der Loader-Fassade (dieselbe Naht wie ``import_tree``).

class _Protokoll:
    def __init__(self) -> None:
        self.geschrieben: list[tuple[str, dict]] = []
        self.geloescht: list[str] = []

    async def schreiben(self, area: str, data: dict) -> None:
        self.geschrieben.append((area, data))

    async def loeschen(self, area: str) -> None:
        self.geloescht.append(area)


_SEED = {"neu": {"a": 1}, "anders": {"b": 2}, "gleich": {"c": 3}}
_LIVE = {"anders": {"b": 99}, "gleich": {"c": 3}, "alt": {"d": 4}}


def _lauf(modus):
    p = _Protokoll()
    diff = vergleiche(_SEED, _LIVE)
    bericht = asyncio.run(
        anwenden(diff, _SEED, modus, schreiben=p.schreiben, loeschen=p.loeschen)
    )
    return p, bericht


def test_missing_schreibt_nur_fehlende_und_loescht_nie():
    p, bericht = _lauf("missing")
    assert [a for a, _ in p.geschrieben] == ["neu"]
    assert p.geloescht == []
    assert bericht == {"written": 1, "deleted": 0}


def test_exact_schreibt_neu_und_abweichend_und_loescht_den_rest():
    p, bericht = _lauf("exact")
    assert [a for a, _ in p.geschrieben] == ["anders", "neu"]
    assert p.geloescht == ["alt"]
    assert bericht == {"written": 2, "deleted": 1}


def test_exact_schreibt_den_seed_inhalt_nicht_den_gelebten():
    """Sonst wäre der Lauf wirkungslos und meldete trotzdem Erfolg."""
    p, _ = _lauf("exact")
    assert dict(p.geschrieben)["anders"] == {"b": 2}


def test_erst_schreiben_dann_loeschen():
    """Die Reihenfolge ist die Absicherung gegen einen Abbruch mitten im Lauf:
    bricht der Lösch-Durchgang ab, ist der Stand eine Obermenge des Seeds — es
    fehlt nichts. Umgekehrt stünde die Konfiguration zeitweise unvollständig da,
    und eine Replika, die in genau diesem Moment liest, servierte eine Lücke.
    """
    reihenfolge: list[str] = []

    async def schreiben(area, data):
        reihenfolge.append(f"put:{area}")

    async def loeschen(area):
        reihenfolge.append(f"del:{area}")

    diff = vergleiche(_SEED, _LIVE)
    asyncio.run(anwenden(diff, _SEED, "exact", schreiben=schreiben, loeschen=loeschen))
    assert reihenfolge.index("del:alt") > max(
        reihenfolge.index("put:anders"), reihenfolge.index("put:neu")
    )


def test_kein_bereich_wird_geschrieben_und_geloescht():
    """Die Listen sind disjunkt konstruiert — hier festgenagelt, weil ein
    Überlapp je nach Reihenfolge einen gerade geschriebenen Bereich wieder
    entfernen würde."""
    diff = vergleiche(_SEED, _LIVE)
    assert set(diff.zu_schreiben("exact")) & set(diff.zu_loeschen("exact")) == set()


def test_unbekannter_modus_wird_abgewiesen():
    """Ein Tippfehler im Aufruf darf nicht stillschweigend zum scharfen Weg
    werden — deshalb Fehler statt Rückfall."""
    diff = vergleiche(_SEED, _LIVE)
    with pytest.raises(ValueError, match="Modus"):
        asyncio.run(anwenden(diff, _SEED, "alles", schreiben=None, loeschen=None))


# ── Pfad-Auflösung ────────────────────────────────────────────────────────
def test_seed_pfad_findet_absoluten_ordner(tmp_path):
    assert seed_pfad(str(tmp_path)) == tmp_path


def test_seed_pfad_ohne_treffer_ist_none():
    assert seed_pfad("gibt-es-nicht-42") is None


def test_seed_pfad_ohne_angabe_ist_none():
    """Leeres ``CONFIG_SEED_DIR``: das Panel bleibt aus statt zu raten."""
    assert seed_pfad("") is None


def test_seed_pfad_findet_den_ausgelieferten_baum():
    """Im Bild liegt der Baum unter ``/app/seeds`` (Arbeitsverzeichnis), lokal
    unter ``backend/seeds``. Beide Wege müssen den echten Seed finden."""
    gefunden = seed_pfad("seeds")
    assert gefunden is not None and (gefunden / "01-base").is_dir()
