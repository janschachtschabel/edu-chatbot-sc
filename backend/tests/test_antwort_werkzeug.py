"""``respond_to_user`` — Antwort und Schnellantworten in EINEM Aufruf.

Plan ``docs/plans/2026-09-30-muster-kette-zeit.md`` (T1/T2): Der eigene
Schnellantwort-Aufruf nach der Antwort kostete im Median 5,3 s Wartezeit und
lieferte bei Rückfragen Unpassendes. Der Weg im Antwort-Aufruf ist seither
Vorgabe; seine Beschreibung nennt, was die Konfiguration sagt, statt fester
„2-4 Vorschläge / 6-8 Wörter".
"""

from __future__ import annotations

import pytest

from boerdi.domain import antwort_werkzeug as aw


def _beschreibung(werkzeug: dict) -> str:
    return werkzeug["function"]["description"]


def _vorschlags_feld(werkzeug: dict) -> dict:
    return werkzeug["function"]["parameters"]["properties"]["quick_replies"]


# ═══ Die Werkzeugdefinition ════════════════════════════════════════════════

def test_die_beschreibung_nennt_zeichengrenze_und_fragt_eine_ersatzzeile_an():
    """Wie im exakten Aufruf (Paket A, Tor E-5): zu lange Vorschläge werden
    verworfen, nicht gekürzt — ohne Ersatzzeile kostete jeder eine Pille. Bei
    zwei Pillen werden also drei angefragt; gekappt wird im Filter."""
    werkzeug = aw.antwort_werkzeug(anzahl=2, max_zeichen=48)

    assert werkzeug["function"]["name"] == "respond_to_user"
    text = _beschreibung(werkzeug)
    assert "3 kurze nutzerseitige Folgevorschläge" in text
    assert "48 Zeichen" in text
    assert "2-4" not in text and "6-8 Wörter" not in text
    feld = _vorschlags_feld(werkzeug)
    assert "3 kurze Folgevorschläge" in feld["description"]
    assert "48 Zeichen" in feld["description"]


def test_der_lotse_belegt_keinen_der_plaetze():
    """Wie im exakten Aufruf (R-6): der Bring-mich-hin-Eintrag kommt
    ZUSÄTZLICH — sonst bliebe bei ``max_count: 2`` eine Pille statt zwei."""
    feld = _vorschlags_feld(aw.antwort_werkzeug(anzahl=2, max_zeichen=48))

    assert feld["maxItems"] == 4
    assert "Zusätzlich darf EIN Eintrag" in feld["description"]


def test_du_form_und_lotsen_format_bleiben_erhalten():
    text = _beschreibung(aw.antwort_werkzeug(anzahl=2, max_zeichen=48))

    assert "Du-Form ist Pflicht" in text
    assert "``__guide__|<kurzer Anzeigetext>|<vollständige URL>``" in text


# ═══ Wann der Weg aktiv ist ════════════════════════════════════════════════

@pytest.fixture
def politik(monkeypatch):
    """Muster-Politik und globale Anzahl ohne Konfigurationszugriff."""
    je_muster = {"M01": ("none", None), "M03": ("speculative", 3)}
    monkeypatch.setattr(aw, "_qr_policy", lambda pid: je_muster.get(pid, ("exact", None)))
    monkeypatch.setattr(aw, "_qr_default_count", lambda: 2)


def test_der_weg_ist_vorgabe_mit_der_globalen_anzahl(politik):
    assert aw.inline_anzahl({"id": "M04"}) == 2


def test_das_muster_setzt_die_anzahl(politik):
    assert aw.inline_anzahl({"id": "M03"}) == 3


def test_krise_und_bedrohung_bekommen_keine_vorschlaege(politik):
    """M01/M02 tragen ``quick_replies_mode: none``. In der Zusammenstellung
    stehen Inline-Vorschläge VOR ``none`` — ohne diese Sperre bekäme ein
    Krisen-Zug Pillen, sobald der Weg Vorgabe ist."""
    assert aw.inline_anzahl({"id": "M01"}) == 0


def test_ein_muster_ohne_folgeformat_bekommt_keine_vorschlaege(politik):
    assert aw.inline_anzahl({"id": "M04", "format_follow_up": "none"}) == 0


def test_der_betreiber_kann_den_weg_abschalten(politik, monkeypatch):
    monkeypatch.setenv("CHAT_INLINE_QUICK_REPLIES", "0")

    assert aw.inline_anzahl({"id": "M04"}) == 0


def test_die_globale_anzahl_null_schaltet_den_weg_ab(monkeypatch):
    monkeypatch.setattr(aw, "_qr_policy", lambda pid: ("exact", None))
    monkeypatch.setattr(aw, "_qr_default_count", lambda: 0)

    assert aw.inline_anzahl({"id": "M04"}) == 0


# ═══ Das Auslesen — eine Funktion für beide Schleifen ══════════════════════

def test_antwort_aus_argumenten_raeumt_auf():
    text, vorschlaege = aw.antwort_aus_argumenten({
        "text": "  Die Antwort.  ",
        "quick_replies": ["Zeig mir mehr", "", 3, "  Anderes Thema "],
    })

    assert text == "Die Antwort."
    assert vorschlaege == ["Zeig mir mehr", "Anderes Thema"]


def test_antwort_aus_argumenten_vertraegt_fehlende_und_kaputte_felder():
    assert aw.antwort_aus_argumenten({}) == ("", [])
    # Eine Zeichenkette statt einer Liste ergäbe sonst Einzelbuchstaben-Pillen.
    assert aw.antwort_aus_argumenten({"text": None, "quick_replies": "kaputt"}) == ("", [])
