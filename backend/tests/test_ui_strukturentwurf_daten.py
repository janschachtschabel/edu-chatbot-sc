"""Paket U2-b (Plan 2026-11-04, T-3/T-8/T-9): Daten des Strukturentwurfs.

Dokumenttyp ``wlo.sammlungsstruktur@1``.

Deckel, die JSON Schema nicht ausdrücken kann (Gesamtzahl, eindeutige Kennungen), die Bereinigung
eines Knotens aus Modell- oder WLO-Daten, Fach und Bildungsstufe nur, wenn erkannt, sowie die drei
Texte: Textfassung (ältere Widgets), Kompaktfassung (an die KI, gedeckelt) und Quittung (kurz).
"""

from __future__ import annotations

from boerdi.ui_module import strukturentwurf as se
from boerdi.ui_module import strukturentwurf_text as st


def _knoten(kennung: str, titel: str, kinder: list | None = None, **mehr) -> dict:
    k = {"id": kennung, "titel": titel, **mehr}
    if kinder:
        k["kinder"] = kinder
    return k


def _entwurf(knoten: list) -> dict:
    return {"titel": "Optik", "quelle": "ki", "knoten": knoten}


# ── Bildungsstufe und Fach ────────────────────────────────────────────────

def test_bildungsstufe_nur_aus_der_festen_liste():
    assert se.bildungsstufe("Sekundarstufe I") == "Sekundarstufe I"
    assert se.bildungsstufe("sekundarstufe 1") == "Sekundarstufe I"
    assert se.bildungsstufe("Grundschule") == "Primarstufe"
    assert se.bildungsstufe("Sek II") == "Sekundarstufe II"
    assert se.bildungsstufe("Klasse 7 bis Mond") is None
    assert se.bildungsstufe(None) is None and se.bildungsstufe(7) is None


def test_fach_ist_ein_kurzes_label():
    assert se.fach("  Physik ") == "Physik"
    assert se.fach("x" * 61) is None
    assert se.fach("") is None and se.fach(["Physik"]) is None


# ── Ein Knoten aus fremden Daten ──────────────────────────────────────────

def test_ein_knoten_wird_bereinigt_und_gedeckelt():
    roh = {"titel": "  Licht\nund Schatten ", "beschreibung": "b" * 400,
           "keywords": ["Licht", "licht", " ", "Schatten", *[f"k{i}" for i in range(20)], "z" * 50],
           "fach": "Physik", "bildungsstufe": "Grundschule"}
    k = se.knoten_aus(roh, "k1", wurzel={"fach": "Physik"})
    assert k["id"] == "k1" and k["titel"] == "Licht und Schatten"
    assert len(k["beschreibung"]) == se.BESCHREIBUNG_ZEICHEN
    assert k["keywords"][:2] == ["Licht", "Schatten"] and len(k["keywords"]) == se.KEYWORDS
    assert all(len(w) <= se.KEYWORD_ZEICHEN for w in k["keywords"])
    assert "fach" not in k                     # gleich der Wurzel → nicht am Knoten
    assert k["bildungsstufe"] == "Primarstufe"


def test_ohne_titel_ist_es_kein_knoten():
    assert se.knoten_aus({"titel": "  "}, "k1", wurzel={}) is None
    assert se.knoten_aus("Licht", "k1", wurzel={}) is None


# ── Prüfung über das Schema hinaus ────────────────────────────────────────

def test_ein_gueltiger_entwurf_hat_keine_fehler():
    daten = _entwurf([_knoten("a", "A", [_knoten("a1", "A1", [_knoten("a11", "A11")])])])
    assert se.fehler(daten) == []
    assert se.anzahl(daten["knoten"]) == 3


def test_doppelte_kennungen_werden_gemeldet():
    daten = _entwurf([_knoten("a", "A"), _knoten("b", "B", [_knoten("a", "A2")])])
    assert any("doppelt" in f for f in se.fehler(daten))


def test_zu_tief_und_zu_viele_werden_gemeldet():
    tief = _knoten("e5", "E5")
    for i in range(4, 0, -1):
        tief = _knoten(f"e{i}", f"E{i}", [tief])
    assert any("tief" in f for f in se.fehler(_entwurf([tief])))
    viele = [_knoten(f"o{i}", "O", [_knoten(f"o{i}-{j}", "K") for j in range(15)])
             for i in range(16)]                # 16 + 240 = 256 > 250
    assert any("Knoten" in f for f in se.fehler(_entwurf(viele)))


def test_neue_kennungen_folgen_dem_pfad_und_bleiben_eindeutig():
    vergeben = {"k1", "k1-1"}
    assert se.neue_kennung("k1", vergeben) == "k1-2"
    assert "k1-2" in vergeben
    assert se.neue_kennung(None, vergeben) == "k2"


# ── Texte ─────────────────────────────────────────────────────────────────

def test_textfassung_ist_eine_eingerueckte_liste_mit_beschreibung():
    kind = _knoten("a1", "Brechung", beschreibung="Wie Licht…")
    daten = _entwurf([_knoten("a", "Licht", [kind])])
    text = st.textfassung(daten)
    assert text.splitlines()[0] == "**Entwurf (KI): Optik**"
    assert "- Licht" in text and "  - Brechung — Wie Licht…" in text


def test_kompaktfassung_ist_gedeckelt_und_nennt_nur_titel():
    daten = _entwurf([_knoten(f"k{i}", f"Thema {i}", beschreibung="lang " * 50) for i in range(30)])
    text = st.kompakt(daten, deckel=200)
    assert len(text) <= 200 and text.endswith("…")
    assert "lang" not in text and text.startswith("Optik")


def test_kompaktfassung_kennzeichnet_ausstehende():
    daten = _entwurf([_knoten("a", "Licht", ausstehend=True)])
    assert "Licht (Unterthemen fehlen noch)" in st.kompakt(daten)


def test_quittung_nennt_zahlen_und_die_erste_ebene():
    daten = _entwurf([_knoten("a", "Licht", [_knoten("a1", "Brechung")]),
                      _knoten("b", "Farben", ausstehend=True)])
    q = st.quittung(daten)
    assert "2 Themen oben" in q and "3 Punkte" in q and "1 noch ohne Unterthemen" in q
    assert "Licht; Farben" in q
    assert "Brechung" not in q                   # nur die erste Ebene
    assert "endet hier" in q
    # Review U2, Befund 7: der Zug endet mit dem Entwurf — keine Bitte, die niemand mehr liest.
    assert "Begleitsatz" not in q
