"""Paket U3-1b: Ordnerbaum aus ``ui_upload`` → Strukturentwurf (``quelle: ordner``), ohne LLM."""

from __future__ import annotations

from boerdi.ui_module import katalog
from boerdi.ui_module import strukturentwurf as se
from boerdi.ui_module.namen import STRUKTURENTWURF
from boerdi.ui_module.strukturentwurf_ordner import aus_ordnern, sauberer_name


def _o(name: str, *kinder: dict, dateien: int = 1) -> dict:
    return {"name": name, "dateien": dateien, "alle_dateien": dateien, "kinder": list(kinder)}


def test_ordner_werden_punkte_und_der_wurzelname_der_titel():
    daten = aus_ordnern(_o("Physik 7", _o("01_Mechanik", _o("1.2 Hebel")), _o("02_Optik")))
    assert daten is not None
    assert daten["titel"] == "Physik 7" and daten["quelle"] == "ordner"
    assert [k["titel"] for k in daten["knoten"]] == ["Mechanik", "Optik"]
    assert daten["knoten"][0]["kinder"][0]["titel"] == "Hebel"
    assert not katalog.daten_fehler(katalog.katalog()[STRUKTURENTWURF], daten)
    assert se.fehler(daten) == []


def test_namen_bereinigen():
    assert sauberer_name("01_Mechanik") == "Mechanik"
    assert sauberer_name("1.2 Kräfte_und_Bewegung") == "Kräfte und Bewegung"
    assert sauberer_name("2024") == "2024"                 # nur Ziffern: bleibt
    assert sauberer_name("  A\n  B ") == "A B"
    assert len(sauberer_name("x" * 300)) == se.TITEL_ZEICHEN


def test_tiefer_als_drei_ebenen_wird_weggelassen_und_gemeldet():
    tief = _o("W", _o("a", _o("b", _o("c", _o("d")))))
    daten = aus_ordnern(tief)
    assert daten is not None
    ebene3 = daten["knoten"][0]["kinder"][0]["kinder"][0]
    assert ebene3["titel"] == "c" and "kinder" not in ebene3
    assert daten.get("gekuerzt") is True


def test_deckel_oben_und_insgesamt():
    viele = _o("W", *[_o(f"o{i:03d}", *[_o(f"k{j}") for j in range(20)]) for i in range(40)])
    daten = aus_ordnern(viele)
    assert daten is not None
    assert len(daten["knoten"]) <= se.HOECHSTENS_OBEN
    assert se.anzahl(daten["knoten"]) <= se.HOECHSTENS_KNOTEN
    assert all(len(k.get("kinder", [])) <= se.HOECHSTENS_KINDER for k in daten["knoten"])
    assert daten.get("gekuerzt") is True
    assert se.fehler(daten) == []


def test_ohne_unterordner_kein_entwurf():
    assert aus_ordnern(_o("W")) is None
    assert aus_ordnern({"kaputt": True}) is None


def test_kuenstliche_wurzel_bekommt_den_ersatztitel():
    daten = aus_ordnern(_o("", _o("A")), ersatz_titel="Gliederung aus Ordnern")
    assert daten is not None and daten["titel"] == "Gliederung aus Ordnern"


def test_kennungen_eindeutig_und_stabil():
    baum = _o("W", _o("A", _o("A1"), _o("A2")), _o("B"))
    a, b = aus_ordnern(baum), aus_ordnern(baum)
    assert a == b
    ids = [k["id"] for k, _ in se.alle(a["knoten"])]
    assert len(ids) == len(set(ids))


def test_die_textfassung_nennt_die_herkunft_ordner():
    """Review U3-1, Befund 4: nicht „Entwurf (KI)“."""
    from boerdi.ui_module import strukturentwurf_text as st

    daten = aus_ordnern(_o("Physik", _o("A")))
    assert st.textfassung(daten).startswith("**Entwurf (aus Ordnern)")
