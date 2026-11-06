"""Paket U3-2a: ein umgewandeltes Dokument bereinigen, gliedern, beschreiben (rein, ohne I/O)."""

from __future__ import annotations

from boerdi.domain.dokument_befund import befund, gescannt, sprache
from boerdi.domain.dokument_gliederung import (
    MAX_ABSCHNITTE,
    abschnitt_text,
    bereinigen,
    gliederung,
    uebersicht,
)


def test_bereinigen_entfernt_eingebettete_bilder_steuerzeichen_und_leerzeilen():
    md, bilder = bereinigen("a\n![x](data:image/png;base64,AAAA)\nb\x07c\n\n\n\n\nd")
    assert bilder == 1
    assert "data:" not in md and "\x07" not in md
    assert "\n\n\n" not in md and md.startswith("a")


def test_atx_ueberschriften_ergeben_die_gliederung():
    md = "# Ziele\nText\n## Teilziel\nMehr\n# Inhalte\nNoch"
    abschnitte, art = gliederung(md)
    assert art == "ueberschriften"
    assert [(a.ebene, a.titel) for a in abschnitte] == [
        (1, "Ziele"), (2, "Teilziel"), (1, "Inhalte")]
    # lückenlos: jeder Abschnitt endet, wo der nächste beginnt
    assert abschnitte[0].ende == abschnitte[1].start and abschnitte[-1].ende == len(md)
    assert [a.id for a in abschnitte] == ["a1", "a2", "a3"]


def test_nummerierte_zeilen_mit_inhaltsverzeichnis_zaehlen_beim_letzten_vorkommen():
    md = ("Inhalt\n1 Ziele des Faches ........ 3\n2 Kompetenzen ..... 5\n2.1 Erkenntnis ... 6\n\n"
          "1 Ziele des Faches\nDie Schüler lernen viel.\n2 Kompetenzen\nText\n"
          "2.1 Erkenntnis\nText\n"
          "3. Die Schüler arbeiten.\n")
    abschnitte, art = gliederung(md)
    assert art == "nummeriert"
    assert [(a.ebene, a.titel) for a in abschnitte] == [
        (1, "Ziele des Faches"), (2 - 1, "Kompetenzen"), (2, "Erkenntnis")]
    assert md[abschnitte[0].start:abschnitte[0].ende].startswith("1 Ziele des Faches\nDie Schüler")


def test_ohne_struktur_entstehen_teile_mit_warnung():
    md = "\n\n".join(f"Absatz {i} " + "wort " * 120 for i in range(20))
    abschnitte, art = gliederung(md)
    assert art == "teile"
    assert 3 <= len(abschnitte) <= 8
    assert abschnitte[0].titel.startswith("Teil 1: Absatz 0")


def test_hoechstens_400_abschnitte():
    md = "\n".join(f"# T{i}\nx" for i in range(700))
    abschnitte, _ = gliederung(md)
    assert len(abschnitte) == MAX_ABSCHNITTE


def test_uebersicht_kuerzt_mit_marke():
    abschnitte, _ = gliederung("\n".join(f"# Titel Nummer {i}\nx" for i in range(100)))
    text, gekuerzt = uebersicht(abschnitte, 200)
    assert gekuerzt is True and len(text) <= 200 and text.endswith("…(gekürzt)")


def test_abschnitt_text_liefert_die_gewaehlten_abschnitte_gedeckelt():
    md = "# A\n" + "a" * 500 + "\n# B\n" + "b" * 500 + "\n# C\nc"
    abschnitte, _ = gliederung(md)
    text = abschnitt_text(md, abschnitte, ["a1", "a3"], 300)
    assert "# A" in text and "# C" in text and "# B" not in text
    assert len(text) <= 300


def test_sprache_und_gescannt():
    de = "Die Schüler und die Lehrer arbeiten mit dem Material, das wir haben. "
    en = "The students and the teachers work with the material that we have. "
    assert sprache(de * 5) == "de"
    assert sprache(en * 5) == "en"
    assert sprache("1 2 3") == "unbekannt"
    assert gescannt("x" * 50, seiten=10) is True
    assert gescannt("x" * 5000, seiten=10) is False
    assert gescannt("", seiten=None) is True


def test_befund_zaehlt_und_warnt():
    md = "# A\n# B\n# C\n" + "wort " * 100     # Überschriften zählen ab drei Treffern
    abschnitte, art = gliederung(md)
    b = befund(md, seiten=3, gekuerzt=False, bilder=2, abschnitte=abschnitte,
               gliederung_art=art)
    assert b["seiten"] == 3 and b["woerter"] == 103 and b["abschnitte"] == 3
    assert "bilder_entfernt" in b["warnungen"] and "wenig_text" in b["warnungen"]
    assert b["gliederung_art"] == "ueberschriften"


# ── Review U3-2, Befund 1: keine quadratische Laufzeit bei bösartiger Eingabe ──

def test_lange_leerzeichenzeile_und_offene_data_bilder_in_linearer_zeit():
    import time

    from boerdi.domain.dokument_gliederung import bereinigen

    boese = ["# a" + " " * 1_000_000 + "x\n", "![a](data:" * 100_000, "](data:" * 100_000]
    for md in boese:
        t0 = time.perf_counter()
        bereinigen(md)
        gliederung(md)
        assert time.perf_counter() - t0 < 2.0


def test_atx_schneidet_schluss_rauten_ab_und_data_bilder_verschwinden():
    from boerdi.domain.dokument_gliederung import bereinigen

    md, bilder = bereinigen("# Titel ##\n![x](data:image/png;base64,AAA) Text\n## B\n"
                            "### C\n![y](data:")
    assert bilder == 1 and "base64" not in md and md.endswith("![y](data:")
    assert [a.titel for a in gliederung(md)[0]] == ["Titel", "B", "C"]
