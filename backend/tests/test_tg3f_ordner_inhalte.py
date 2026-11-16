"""Plan 2026-11-16, TG-3f: die Ordnerstruktur mit ihren Inhalten — „gemerkt“ (Dateinamen je Ordner,
auch anonym) und „erschlossen“ (node_id nach der Ablage). Der Entwurf aus Ordnern trägt je Punkt
``inhalte: [{i, name, node_id?}]``; an die KI geht nur ihre Zahl."""

from __future__ import annotations

import asyncio

from boerdi.services.ablauf import werkzeuge
from boerdi.ui_module import katalog
from boerdi.ui_module import strukturentwurf as se
from boerdi.ui_module import strukturentwurf_merken as merken
from boerdi.ui_module import strukturentwurf_text as st
from boerdi.ui_module.namen import STRUKTURENTWURF
from boerdi.ui_module.strukturentwurf_ordner import aus_ordnern
from boerdi.ui_module.upload_antwort import ohne_dateien

_NODE = "11111111-2222-3333-4444-555555555555"


def _d(i: int, name: str, rolle: str = "inhalt") -> dict:
    return {"i": i, "name": name, "endung": "pdf", "groesse": 10, "rolle": rolle}


def _o(name: str, *kinder: dict, dateien: list[dict] | None = None) -> dict:
    liste = dateien or []
    return {"name": name, "dateien": len(liste), "alle_dateien": len(liste),
            "kinder": list(kinder), "dateiliste": liste}


_BAUM = _o("Physik 7",
           _o("01_Mechanik", _o("Hebel", dateien=[_d(2, "hebel.pdf")]),
              dateien=[_d(0, "kraft.pdf"), _d(1, "alt.tmp", "ignorieren")]),
           _o("02_Optik", dateien=[_d(3, "linsen.pdf"), _d(4, "Lehrplan.pdf", "struktur")]),
           dateien=[_d(5, "wurzel.pdf")])


def test_jeder_punkt_merkt_die_inhalte_seines_ordners():
    daten = aus_ordnern(_BAUM)
    assert daten is not None
    mechanik, optik = daten["knoten"]
    assert mechanik["inhalte"] == [{"i": 0, "name": "kraft.pdf"}]       # ignorierte nicht
    assert mechanik["kinder"][0]["inhalte"] == [{"i": 2, "name": "hebel.pdf"}]
    assert optik["inhalte"] == [{"i": 3, "name": "linsen.pdf"}]         # Strukturdokument nicht
    assert "wurzel.pdf" not in str(daten)          # die Wurzel hat keinen Punkt
    assert not katalog.daten_fehler(katalog.katalog()[STRUKTURENTWURF], daten)
    assert se.fehler(daten) == []


def test_nach_der_ablage_sind_die_inhalte_erschlossen():
    ablage = {"inhalte": [
        {"index": 0, "i": 3, "stand": "stored", "node_id": _NODE},
        {"index": 1, "i": 0, "stand": "failed"},
        {"index": 2, "stand": "stored", "node_id": _NODE}]}            # ohne ``i``: keine Zuordnung
    daten = aus_ordnern(_BAUM, ablage=ablage)
    mechanik, optik = daten["knoten"]
    assert optik["inhalte"] == [{"i": 3, "name": "linsen.pdf", "node_id": _NODE}]
    assert mechanik["inhalte"] == [{"i": 0, "name": "kraft.pdf"}]
    assert not katalog.daten_fehler(katalog.katalog()[STRUKTURENTWURF], daten)


def test_ohne_dateiliste_wie_vorher_ohne_inhalte():
    daten = aus_ordnern(ohne_dateien(_BAUM))
    assert daten is not None and "inhalte" not in str(daten)


def test_dateien_tieferer_ordner_gehoeren_zum_tiefsten_punkt():
    tief = _o("W", _o("a", _o("b", _o("c", _o("d", dateien=[_d(9, "tief.pdf")]),
                                       dateien=[_d(8, "c.pdf")]))))
    daten = aus_ordnern(tief)
    ebene3 = daten["knoten"][0]["kinder"][0]["kinder"][0]
    assert ebene3["titel"] == "c" and "kinder" not in ebene3
    assert [i["name"] for i in ebene3["inhalte"]] == ["c.pdf", "tief.pdf"]
    assert daten.get("gekuerzt") is True


def test_hoechstens_500_inhalte_im_entwurf():
    viele = _o("W", *[_o(f"o{n}", dateien=[_d(n * 100 + k, f"f{n}-{k}.pdf") for k in range(100)])
                      for n in range(6)])
    daten = aus_ordnern(viele)
    assert sum(se.inhalte_zahl(k) for k, _ in se.alle(daten["knoten"])) == se.HOECHSTENS_INHALTE
    assert daten.get("gekuerzt") is True and se.fehler(daten) == []
    zu_viel = {**daten, "knoten": [{**daten["knoten"][0],
                                    "inhalte": daten["knoten"][0]["inhalte"] * 6}]}
    assert any("Inhalte" in f for f in se.fehler(zu_viel))


def test_die_ki_sieht_nur_die_zahl_nie_einen_dateinamen():
    daten = aus_ordnern(_BAUM)
    kompakt = st.kompakt(daten)
    assert "- Mechanik (1 Datei)" in kompakt and "  - Hebel (1 Datei)" in kompakt
    assert "kraft.pdf" not in kompakt and "linsen.pdf" not in kompakt
    assert "kraft.pdf" not in st.textfassung(daten) and "kraft.pdf" not in st.quittung(daten)


def test_ein_entwurf_ohne_inhalte_gilt_weiter():
    alt = {"titel": "Optik", "quelle": "ki", "knoten": [{"id": "k1", "titel": "Licht"}]}
    assert not katalog.daten_fehler(katalog.katalog()[STRUKTURENTWURF], alt)
    assert se.fehler(alt) == [] and st.kompakt(alt) == "Optik\n- Licht"


def test_namen_der_inhalte_werden_eine_zeile():
    daten = {"titel": "T", "quelle": "ordner", "knoten": [
        {"id": "k1", "titel": "A", "inhalte": [{"i": 0, "name": "a\nb.pdf"}]}]}
    assert se.normalisiert(daten)["knoten"][0]["inhalte"] == [{"i": 0, "name": "a b.pdf"}]


def test_ein_zu_grosser_gemerkter_entwurf_verliert_auch_die_inhalte():
    """Der gemerkte Entwurf (``entities``) bleibt klein — die Namen stehen im Teil ``draft``."""
    daten = aus_ordnern(_o("W", *[_o(f"o{n}" + "x" * 100, dateien=[
        _d(n * 100 + k, f"{'n' * 110}{k}.pdf") for k in range(100)]) for n in range(5)]))
    entities: dict = {}
    merken._merken(entities, daten)
    gemerkt = entities[merken.KEY]["daten"]
    assert gemerkt[merken.OHNE_TEXTE] is True and "inhalte" not in str(gemerkt)


# ── Der Dienst liest den Teil ``struktur``, sonst ``structure`` ───────────────────────────────────

def _dienst(teile: dict, struktur_arg: dict):
    async def lader(name):
        return teile.get(name)

    k = werkzeuge.DienstKontext(teile=lader)
    return asyncio.run(werkzeuge.DIENSTE["strukturentwurf_aus_ordnern"](
        {"struktur": struktur_arg}, k))


def test_der_dienst_nimmt_die_auswahl_mit_dateien_und_die_ablage():
    structure = {"struktur": ohne_dateien(_BAUM), "zahlen": {}}
    ablage = {"block_id": "b0000001",
              "inhalte": [{"index": 0, "i": 0, "stand": "stored", "node_id": _NODE}]}
    auswahl = {"struktur": _BAUM, "block_id": "b0000001"}
    daten = _dienst({"struktur": auswahl, "ablage": ablage}, structure)
    assert daten["knoten"][0]["inhalte"] == [{"i": 0, "name": "kraft.pdf", "node_id": _NODE}]
    # Review TG-3a–c, R3-2: eine Ablage aus einem anderen Upload-Feld verknüpft nichts
    fremd = _dienst({"struktur": auswahl, "ablage": {**ablage, "block_id": "b0000002"}},
                    structure)
    assert fremd["knoten"][0]["inhalte"] == [{"i": 0, "name": "kraft.pdf"}]
    ohne = _dienst({"struktur": {"struktur": _BAUM}, "ablage": ablage}, structure)
    assert ohne["knoten"][0]["inhalte"] == [{"i": 0, "name": "kraft.pdf"}]


def test_eine_andere_auswahl_im_teil_struktur_zaehlt_nicht():
    structure = {"struktur": ohne_dateien(_BAUM), "zahlen": {}}
    andere = _o("Chemie", _o("Säuren", dateien=[_d(0, "s.pdf")]))
    daten = _dienst({"struktur": {"struktur": andere}}, structure)
    assert daten["titel"] == "Physik 7" and "inhalte" not in str(daten)


def test_ohne_kontext_wie_vorher():
    daten = asyncio.run(werkzeuge.DIENSTE["strukturentwurf_aus_ordnern"](
        {"struktur": {"struktur": _BAUM}}))
    assert daten["knoten"][0]["inhalte"] == [{"i": 0, "name": "kraft.pdf"}]
