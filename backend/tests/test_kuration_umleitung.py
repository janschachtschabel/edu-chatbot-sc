"""Ein Kurations-Auftrag landet im Muster mit den Schreibwerkzeugen (Paket 10, S-7).

Kurzaudit 2026-10-10, S-7: Schreibende Werkzeuge bietet die Muster-Maschine nur in M18
(Kuration) und M20 (Erschließen) an. Wählte der Klassifikator für „Nimm das in meine
Sammlung auf“ M05/M08, fehlten sie — und das Modell erklärte oft, man müsse sich
anmelden, obwohl die Person angemeldet war. Die Regel hier ist das Netz unter dem
Klassifikator: Auftragsverb + Gegenstand im Bestand, keine Wie-Frage → M18, mit
Webadresse M20. Die Wortlisten stehen in ``classify-overrides.yaml`` (Studio).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from boerdi.domain.kuration_umleitung import umleitung

_SEED = Path(__file__).resolve().parents[1] / "seeds" / "01-base" / "classify-overrides.yaml"
REGEL = yaml.safe_load(_SEED.read_text(encoding="utf-8"))["curation_reroute"]


@pytest.mark.parametrize(("satz", "hinweis", "ziel"), [
    ("Nimm das in meine Sammlung auf", "M06", "M18"),
    ("Füge den ersten Treffer zu meiner Sammlung hinzu", "M05", "M18"),
    ("Übernimm das Video in meine Sammlung", "M06", "M18"),
    ("Pack das Arbeitsblatt in die Sammlung Optik", "M08", "M18"),
    ("Kopiere den zweiten Treffer in die Sammlung Licht", "M05", "M18"),
    ("Verlinke das Video in der Sammlung Optik", "M08", "M18"),
    ("Bitte das Arbeitsblatt in WLO hochladen", "M10", "M18"),
    ("Veröffentliche das Arbeitsblatt in WLO", "M11", "M18"),
    ("Benenne die Sammlung Optik in Licht und Farbe um", "M08", "M18"),
    ("Ändere die Metadaten des Datensatzes zu Linsen", "M04", "M18"),
    ("Aktualisiere den Redaktionstext der Sammlung Optik", "M08", "M18"),
    ("Speicher das in WLO", "M04", "M18"),
    ("Kannst du das Video in meine Sammlung Optik aufnehmen?", "M08", "M18"),
    ("Bitte das Arbeitsblatt in die Sammlung Bruchrechnen einsortieren", None, "M18"),
    ("Lösch den Datensatz zu Hebelgesetz", "M17", "M18"),
    ("Nimm https://de.wikipedia.org/wiki/Optik in die Sammlung Optik auf", "M04", "M20"),
    ("Erschließe die Seite https://example.org/linsen für WLO", "M04", "M20"),
])
def test_kurationsauftraege_werden_umgeleitet(satz, hinweis, ziel):
    assert umleitung(satz, hinweis, REGEL) == ziel


@pytest.mark.parametrize(("satz", "hinweis"), [
    ("Wie füge ich etwas zu meiner Sammlung hinzu?", "M13"),
    ("Wie kann ich Material in WLO aufnehmen lassen", "M13"),
    ("Zeig mir die Sammlung Optik", "M08"),
    ("Ich suche Material für meine Sammlung", "M06"),
    ("Erstell mir ein Quiz zu Photosynthese", "M10"),
    ("Was ist eine Sammlung in WLO?", "M04"),
    # Ein Filterwunsch an die Trefferliste ist keine Kuration.
    ("Nimm die Videos aus den Treffern raus", "M05"),
    # Fragen nach Recht und Konto beantwortet M04/M13, nicht der Schreibweg.
    ("Darf ich fremde Videos in WLO hochladen?", "M04"),
    ("Muss ich angemeldet sein, um in meiner Sammlung zu speichern?", "M13"),
    ("Wohin speichere ich Material in WLO?", "M13"),
])
def test_anderes_bleibt_beim_klassifikator(satz, hinweis):
    assert umleitung(satz, hinweis, REGEL) is None


@pytest.mark.parametrize("hinweis", ["M18", "M20"])
def test_ein_schreibendes_muster_bleibt_stehen(hinweis):
    assert umleitung("Nimm das in meine Sammlung auf", hinweis, REGEL) is None


def test_abgeschaltet_oder_leer_leitet_nichts_um():
    assert umleitung("Nimm das in meine Sammlung auf", "M06", {**REGEL, "enabled": False}) is None
    assert umleitung("Nimm das in meine Sammlung auf", "M06", {}) is None
    assert umleitung("Nimm das in meine Sammlung auf", "M06", None) is None
