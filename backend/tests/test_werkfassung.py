"""Paket 12, W2: Status eines Bereichs gegenüber seiner Werksfassung (rein, ohne Datenbank).

Ein Bereich gilt nur dann als unberührt, wenn sein Inhalt genau der Werksfassung gleicht, auf der er
stand. Was sich nicht sicher zuordnen lässt, gilt als eigen — der Werksabgleich überschreibt nie
etwas, das jemand angepasst haben könnte.
"""

from __future__ import annotations

from boerdi.services.werkfassung import (
    EIGEN,
    EIGEN_NEUES_WERK,
    NUR_EIGEN,
    WERK,
    WERK_ENTFERNT,
    WERK_FEHLT,
    WERK_VERALTET,
    pruefsumme,
    status,
)

ALT = {"frontmatter": {"id": "M05"}, "body": "alt"}
NEU = {"frontmatter": {"id": "M05"}, "body": "neu"}
EIGENES = {"frontmatter": {"id": "M05"}, "body": "eigen"}


def test_pruefsumme_haengt_nicht_an_der_schluessel_reihenfolge():
    assert pruefsumme({"a": 1, "b": [1, 2]}) == pruefsumme({"b": [1, 2], "a": 1})
    assert pruefsumme({"a": 1}) != pruefsumme({"a": 2})


def test_gleich_der_werksfassung_ist_werk():
    assert status(data=NEU, werk_hash=None, werk=NEU, entfernt=False) == WERK


def test_unberuehrt_auf_alter_werksfassung_ist_veraltet():
    assert status(data=ALT, werk_hash=pruefsumme(ALT), werk=NEU, entfernt=False) == WERK_VERALTET


def test_angepasst_auf_aktueller_werksfassung_ist_eigen():
    assert status(data=EIGENES, werk_hash=pruefsumme(NEU), werk=NEU, entfernt=False) == EIGEN


def test_angepasst_auf_alter_oder_unbekannter_basis_meldet_neues_werk():
    assert status(data=EIGENES, werk_hash=pruefsumme(ALT), werk=NEU,
                  entfernt=False) == EIGEN_NEUES_WERK
    # Bestand vor Paket 12: Basis unbekannt — nie als unberührt behandeln.
    assert status(data=ALT, werk_hash=None, werk=NEU, entfernt=False) == EIGEN_NEUES_WERK


def test_ohne_werksbereich_ist_nur_eigen():
    assert status(data=EIGENES, werk_hash=None, werk=None, entfernt=False) == NUR_EIGEN


def test_geloeschte_und_fehlende_werksbereiche():
    assert status(data=None, werk_hash=None, werk=NEU, entfernt=True) == WERK_ENTFERNT
    assert status(data=None, werk_hash=None, werk=NEU, entfernt=False) == WERK_FEHLT


def test_bestand_aus_einem_import_gilt_als_unberuehrt():
    """Erster Rollout: Bestand ohne Basis, dessen aktuelle Fassung ein Import schrieb
    (``updated_by``) — seither nachweislich unberührt, also darf der Abgleich ihn anheben."""
    for schreiber in ("import", "seed-apply", "seed-apply-cli"):
        assert status(data=ALT, werk_hash=None, werk=NEU, entfernt=False,
                      updated_by=schreiber) == WERK_VERALTET
    assert status(data=ALT, werk_hash=None, werk=NEU, entfernt=False,
                  updated_by="studio") == EIGEN_NEUES_WERK
    # Mit gemerkter Basis zählt nur die Prüfsumme, nicht der Schreiber.
    assert status(data=EIGENES, werk_hash=pruefsumme(NEU), werk=NEU, entfernt=False,
                  updated_by="import") == EIGEN


def _zeile(data, werk_hash=None, updated_by="studio"):
    return {"data": data, "werk_hash": werk_hash, "updated_by": updated_by}


def test_werksabgleich_plant_nur_unberuehrtes_und_fehlendes():
    from boerdi.services.werkfassung import plane_werksabgleich

    seed = {"a/neu": NEU, "a/veraltet": NEU, "a/eigen": NEU, "a/gleich": NEU,
            "a/entfernt": NEU}
    zeilen = {
        "a/veraltet": _zeile(ALT, pruefsumme(ALT)),
        "a/eigen": _zeile(EIGENES, pruefsumme(ALT)),
        "a/gleich": _zeile(NEU, None),           # Bestand, gleicht schon: nur zuordnen
        "a/nur-eigen": _zeile(EIGENES),
    }
    plan = plane_werksabgleich(seed, zeilen, entfernt={"a/entfernt"})
    assert sorted(plan.schreiben) == ["a/neu", "a/veraltet"]
    assert plan.schreiben["a/veraltet"] == NEU
    assert plan.zuordnen == {"a/gleich": pruefsumme(NEU)}
    assert plan.neues_werk == ["a/eigen"]
    assert plan.bericht() == {"neu": 1, "aktualisiert": 1, "zugeordnet": 1, "neues_werk": 1}


# ── Umschalten (Review Paket 12, #1/#8): nie eine Fassung verlieren ──────────────────────
def test_auf_werk_legt_die_eigene_fassung_mit_ihrer_basis_still():
    from boerdi.services.werkfassung import Fassung, umschalten

    neu = umschalten("werk", Fassung(data=EIGENES, werk_hash="h-alt", eigene=None,
                                     eigene_basis=None), werk=NEU)
    assert neu == Fassung(data=NEU, werk_hash=pruefsumme(NEU), eigene=EIGENES,
                          eigene_basis="h-alt")


def test_veraltetes_werk_wird_nicht_als_eigene_fassung_stillgelegt():
    from boerdi.services.werkfassung import Fassung, umschalten

    vorher = Fassung(data=ALT, werk_hash=pruefsumme(ALT), eigene=EIGENES, eigene_basis="hb")
    neu = umschalten("werk", vorher, werk=NEU)
    assert neu.eigene == EIGENES and neu.eigene_basis == "hb"  # die echte bleibt


def test_auf_werk_verweigert_wenn_sonst_eine_eigene_fassung_verloren_ginge():
    import pytest

    from boerdi.services.werkfassung import Fassung, UmschaltEinwand, umschalten

    weiter_bearbeitet = {"frontmatter": {"id": "M05"}, "body": "nach dem Umschalten bearbeitet"}
    with pytest.raises(UmschaltEinwand) as e:
        umschalten("werk", Fassung(data=weiter_bearbeitet, werk_hash=pruefsumme(NEU),
                                   eigene=EIGENES, eigene_basis="hb"), werk=NEU)
    assert e.value.meldung == "fassung.zweiEigene"


def test_auf_eigen_tauscht_statt_zu_verwerfen():
    from boerdi.services.werkfassung import Fassung, umschalten

    weiter_bearbeitet = {"frontmatter": {"id": "M05"}, "body": "nach dem Umschalten bearbeitet"}
    neu = umschalten("eigen", Fassung(data=weiter_bearbeitet, werk_hash=pruefsumme(NEU),
                                      eigene=EIGENES, eigene_basis="hb"), werk=NEU)
    assert neu == Fassung(data=EIGENES, werk_hash="hb", eigene=weiter_bearbeitet,
                          eigene_basis=pruefsumme(NEU))


def test_auf_eigen_vom_werk_aus_gibt_die_stillgelegte_mit_ihrer_basis_zurueck():
    """#8: die Basis der stillgelegten Fassung kommt mit — „neue Werksfassung“ bleibt sichtbar."""
    from boerdi.services.werkfassung import Fassung, umschalten

    neu = umschalten("eigen", Fassung(data=NEU, werk_hash=pruefsumme(NEU), eigene=EIGENES,
                                      eigene_basis=pruefsumme(ALT)), werk=NEU)
    assert neu == Fassung(data=EIGENES, werk_hash=pruefsumme(ALT), eigene=None, eigene_basis=None)
    assert status(data=neu.data, werk_hash=neu.werk_hash, werk=NEU,
                  entfernt=False) == EIGEN_NEUES_WERK


def test_umschalten_ohne_grundlage_wird_abgewiesen():
    import pytest

    from boerdi.services.werkfassung import Fassung, UmschaltEinwand, umschalten

    with pytest.raises(UmschaltEinwand) as e:
        umschalten("eigen", Fassung(data=NEU, werk_hash=None, eigene=None, eigene_basis=None),
                   werk=NEU)
    assert e.value.meldung == "fassung.keineEigene"
    with pytest.raises(UmschaltEinwand) as e:
        umschalten("werk", Fassung(data=EIGENES, werk_hash=None, eigene=None, eigene_basis=None),
                   werk=None)
    assert e.value.meldung == "fassung.keinWerk"


def test_als_geprueft_markieren_behaelt_die_fassung_und_merkt_das_werk():
    """Review 2 #5: Bestand ohne Basis stand sonst für immer auf „neue Werksfassung“."""
    import pytest

    from boerdi.services.werkfassung import Fassung, UmschaltEinwand, umschalten

    vorher = Fassung(data=EIGENES, werk_hash=None, eigene=None, eigene_basis=None)
    neu = umschalten("geprueft", vorher, werk=NEU)
    assert neu == Fassung(data=EIGENES, werk_hash=pruefsumme(NEU), eigene=None, eigene_basis=None)
    assert status(data=neu.data, werk_hash=neu.werk_hash, werk=NEU, entfernt=False) == EIGEN
    with pytest.raises(UmschaltEinwand):
        umschalten("geprueft", Fassung(NEU, pruefsumme(NEU), None, None), werk=NEU)
