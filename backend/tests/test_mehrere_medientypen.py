"""Paket 18B — mehrere Medientypen in einer Anfrage („Arbeitsblatt oder interaktives Material“).

Externes Audit 2026-10 und Prüfung 2026-10-28. Bisher:
- ``learningResourceType`` als Liste → -32602, gerettet nur vom Retry des Modells;
- der Typ-Fokus wählte ``sorted(wanted)[0]``: Label und Such-URL kannten einen Typ;
- der Anti-Halluzinations-Wächter stürzte auf ``list.strip``;
- Stichwörter als Teilzeichenkette: „Protest“ war ein Quiz, „Beispiel“ ein Spiel.
"""

from __future__ import annotations

import pytest

from boerdi.domain.content_types import (
    _extract_wanted_content_types,
    _resolve_wanted_content_types,
    als_liste,
    als_text,
    normalisiere_entitaeten,
)

# ── Stichwörter ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("nachricht", [
    "Material zum Protest der Bauern",
    "Gib mir ein Beispiel für Reibung",
    "Ein Exkurs zur Geschichte",
    "Kannst du das testen?",
    "Schick mir eine Testnachricht",
    "Ein Gegenbeispiel zur Regel",
    "Rechenbeispiele zur Prozentrechnung",
    "Der Diskurs über Medien",
])
def test_ein_wortteil_ist_kein_medientyp(nachricht):
    assert _extract_wanted_content_types(nachricht) == set()


@pytest.mark.parametrize(("nachricht", "erwartet"), [
    ("Hast du einen Test zur Bruchrechnung?", {"quiz"}),
    ("Lernvideos zur Optik", {"video"}),
    ("Übungsblätter zu Brüchen", {"übung"}),
    ("Ein Lernspiel zum Einmaleins", {"spiel"}),
    # Review 18: Komposita, die den Typ meinen, zählen weiter.
    ("Ein Klassentest zu Brüchen", {"quiz"}),
    ("Gibt es einen Onlinekurs zu Python?", {"kurs"}),
    ("Ein Rollenspiel zur Demokratie", {"spiel"}),
    ("Spiele zum Einmaleins", {"spiel"}),
    ("Show me the latest videos on optics", {"video"}),
    ("Arbeitsblatt oder interaktives Material zum Klimawandel", {"arbeitsblatt", "interaktiv"}),
])
def test_ganze_woerter_und_komposita_bleiben_erkannt(nachricht, erwartet):
    assert _extract_wanted_content_types(nachricht) == erwartet


@pytest.mark.parametrize(("wert", "erwartet"), [
    ("Onlinekurs", {"kurs"}), ("Vokabeltest", {"quiz"}), ("Rollenspiel", {"spiel"}),
])
def test_ein_klassifikatorwert_als_kompositum_trifft_seinen_typ(wert, erwartet):
    # Review 18: der Wert IST ein Typwort. Mit der Ganzwort-Regel fiel „Onlinekurs“
    # auf das rohe Wort zurück, und der Kartenfilter warf jede Karte weg.
    assert _resolve_wanted_content_types("", classification_entities={"medientyp": wert}) \
        == erwartet


def test_ein_medientyp_als_liste_ergibt_alle_typen():
    wanted = _resolve_wanted_content_types(
        "", classification_entities={"medientyp": ["Arbeitsblatt", "Interaktives Medium"]})
    assert wanted == {"arbeitsblatt", "interaktiv"}


# ── Werte, die als Liste ankommen ────────────────────────────────────────

@pytest.mark.parametrize(("wert", "text", "liste"), [
    ("Video", "Video", ["Video"]),
    ("  ", "", []),
    (["Arbeitsblatt", "", "Video", "Arbeitsblatt"], "Arbeitsblatt", ["Arbeitsblatt", "Video"]),
    ([], "", []),
    (None, "", []),
    (42, "", []),
])
def test_als_text_und_als_liste(wert, text, liste):
    assert als_text(wert) == text
    assert als_liste(wert) == liste


def test_normalisierung_der_entitaeten():
    roh = {"medientyp": ["Arbeitsblatt", "Interaktives Medium"], "fach": ["Physik", "Chemie"],
           "thema": "Optik", "stufe": []}
    assert normalisiere_entitaeten(roh) == {
        "medientyp": "Arbeitsblatt",
        "medientypen": ["Arbeitsblatt", "Interaktives Medium"],
        "fach": "Physik",
        "thema": "Optik",
    }


def test_ein_einzelner_medientyp_bekommt_keine_liste():
    assert normalisiere_entitaeten({"medientyp": ["Video"]}) == {"medientyp": "Video"}
