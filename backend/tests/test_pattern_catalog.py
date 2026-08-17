"""Der Musterkatalog als Werkzeug-Beschreibung (H2).

Im Hybrid-Modus wählt nicht mehr der Klassifikator das Muster, sondern das
Modell — über ein Werkzeug, dessen ``enum`` die wählbaren Kennungen führt und
dessen Beschreibung den Katalog trägt.

**Der wichtigste Test dieser Datei ist die Sperrliste.** M01/M02 werden vom
Sicherheits-Gate erzwungen, M03 ist Klärungs-Mechanik mit Versuchszähler und M15
der Rückfall-Anker. Stünden sie im Katalog, könnte ein Modell die
Krisen-Behandlung *abwählen*. Deshalb wird die Sperre an zwei Stellen geprüft:
im Katalog und im Nachschlagen — eine Kennung, die nicht angeboten wird, darf
auch dann nicht greifen, wenn das Modell sie frei erfindet.
"""

from __future__ import annotations

from boerdi.domain.pattern_catalog import (
    NICHT_WAEHLBAR,
    finde_muster,
    katalog_kurz,
    katalog_text,
    waehlbare_muster,
)
from boerdi.domain.pattern_engine import PatternDef


def _muster(pid: str, **felder) -> PatternDef:
    felder.setdefault("label", f"Muster {pid}")
    return PatternDef(id=pid, **felder)


def _bestand() -> list[PatternDef]:
    return [
        _muster("M01", label="Krisen-Empathie"),
        _muster("M02", label="Bedrohungs-Refusal"),
        _muster("M03", label="Slot-Klärung"),
        _muster("M06", label="Material-Suche Cascade",
                short_purpose="Thema ohne Filter → Kaskade",
                when_to_use=["Thema genannt, keine Filter"],
                when_not_to_use=["Filter sind schon gesetzt"],
                trigger_phrases=["material zu"],
                discriminators=[{"vs": "M05", "rule": "M05 hat Filter",
                                 "example": "Video zu Optik"}]),
        _muster("M12", label="Null-Treffer-Eskalation"),
        _muster("M15", label="Orientierung"),
    ]


def test_die_gesperrten_muster_stehen_nicht_im_katalog() -> None:
    """Ein Modell darf die Krisen-Behandlung nicht abwählen können."""
    kennungen = [p.id for p in waehlbare_muster(_bestand())]
    for gesperrt in ("M01", "M02", "M03", "M15"):
        assert gesperrt in NICHT_WAEHLBAR
        assert gesperrt not in kennungen


def test_die_uebrigen_muster_bleiben_waehlbar() -> None:
    kennungen = [p.id for p in waehlbare_muster(_bestand())]
    assert kennungen == ["M06", "M12"]


def test_finde_muster_greift_die_sperre_ein_zweites_mal_ab() -> None:
    """Verteidigung in der Tiefe: das ``enum`` bietet M01 nicht an — erfindet
    das Modell die Kennung trotzdem, darf sie hier nicht durchkommen."""
    bestand = _bestand()
    assert finde_muster("M06", bestand) is not None
    assert finde_muster("M01", bestand) is None
    assert finde_muster("M03", bestand) is None
    assert finde_muster("gibtsnicht", bestand) is None


def test_der_katalogtext_nennt_kennung_zweck_und_einsatzregeln() -> None:
    text = katalog_text(_bestand())
    assert "### M06 — Material-Suche Cascade" in text
    assert "Thema ohne Filter" in text
    assert "Einsetzen wenn:" in text
    assert "NICHT einsetzen wenn:" in text
    assert "M05 hat Filter" in text


def test_der_katalogtext_verschweigt_die_gesperrten_muster() -> None:
    text = katalog_text(_bestand())
    assert "M01" not in text
    assert "Orientierung" not in text


def test_lange_listen_werden_gedeckelt() -> None:
    """Derselbe Deckel wie im Klassifikator-Block: eine versehentlich groß
    editierte Config darf die Werkzeugbeschreibung nicht sprengen."""
    viel = _muster("M06", when_to_use=[f"Fall {i}" for i in range(9)])
    text = katalog_text([viel])
    assert "Fall 4" in text
    assert "Fall 5" not in text


def test_ein_leerer_bestand_ergibt_einen_leeren_katalog() -> None:
    assert waehlbare_muster([]) == []
    assert katalog_text([]) == ""
    assert finde_muster("M06", []) is None


# ── Kurzform nach der Wahl (H8-2) ────────────────────────────────────────────
# Gemessen: der volle Katalog ist 25 251 von 31 742 Zeichen des Werkzeugsatzes,
# NACHDEM ein Muster gewählt wurde — 80 %, und er geht in jeder weiteren Runde
# mit. Zum Wechseln genügt Kennung, Etikett und Zweck.


def test_der_kurzkatalog_nennt_kennung_etikett_und_zweck() -> None:
    text = katalog_kurz(_bestand())
    assert "M06" in text
    assert "Material-Suche Cascade" in text
    assert "Thema ohne Filter" in text


def test_der_kurzkatalog_laesst_die_einsatzregeln_weg() -> None:
    """Sie sind der teure Teil und beim WECHSELN nicht mehr die Frage — das
    Modell kennt die Lage inzwischen aus seinen eigenen Werkzeug-Ergebnissen."""
    text = katalog_kurz(_bestand())
    assert "Einsetzen wenn" not in text
    assert "Abgrenzung" not in text
    assert "material zu" not in text


def test_der_kurzkatalog_ist_deutlich_kleiner_als_der_volle() -> None:
    assert len(katalog_kurz(_bestand())) < len(katalog_text(_bestand())) / 2


def test_der_kurzkatalog_verschweigt_die_gesperrten_muster_ebenso() -> None:
    text = katalog_kurz(_bestand())
    assert "Krisen-Empathie" not in text
    assert "M01" not in text


def test_ein_muster_ohne_zweck_steht_trotzdem_mit_namen_da() -> None:
    text = katalog_kurz([_muster("M12", label="Null-Treffer-Eskalation")])
    assert "M12" in text
    assert "Null-Treffer-Eskalation" in text


def test_ein_leerer_bestand_ergibt_auch_kurz_einen_leeren_katalog() -> None:
    assert katalog_kurz([]) == ""
