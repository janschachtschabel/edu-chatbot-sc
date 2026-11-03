"""Paket U1-a (a4): der Katalog der UI-Module im Backend.

Quelle der Manifeste ist der Modul-Ordner im Frontend (``frontend/projects/ui-module/src/<name>/
manifest.json``); ``npm run module:register`` legt sie gesammelt im Backend-Paket ab. Der Katalog
prüft jedes Manifest gegen das Vertrags-Schema und jedes Beispiel gegen die Eingabe (und Antwort)
des Moduls — ein Modul, dessen Beispiele nicht zu seiner eigenen Beschreibung passen, würde der
KI eine falsche Struktur beibringen.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boerdi.ui_module import katalog

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "projects" / "ui-module" / "src"


def _manifest(**mehr) -> dict:
    m = {
        "name": "ui_probe", "version": 1, "art": "anzeigen",
        "titel": {"de": "Probe"}, "beschreibung": "Zeigt eine Probe für die Tests an.",
        "eingabe": {"type": "object", "required": ["text"],
                    "properties": {"text": {"type": "string", "description": "Der Text."}}},
        "textfassung": {"vorlage": "markdown", "feld": "text"},
        "beispiele": [{"titel": "Kurz", "daten": {"text": "Hallo"}}],
    }
    m.update(mehr)
    return m


def _schreibe(tmp_path: Path, *manifeste: dict) -> Path:
    p = tmp_path / "manifeste.json"
    p.write_text(json.dumps(list(manifeste)), encoding="utf-8")
    return p


def test_ein_gueltiges_manifest_steht_im_katalog(tmp_path):
    kat = katalog.lade(_schreibe(tmp_path, _manifest()))
    assert list(kat) == ["ui_probe"] and kat["ui_probe"]["art"] == "anzeigen"


def test_ohne_datei_ist_der_katalog_leer(tmp_path):
    assert katalog.lade(tmp_path / "fehlt.json") == {}


@pytest.mark.parametrize("aenderung,pfad", [
    ({"name": "Probe"}, "name"),
    ({"art": "fragen"}, "art"),
    ({"art": "abfragen"}, ""),                    # abfragend ohne antwort-Schema
    ({"beispiele": []}, "beispiele"),
    ({"unbekannt": 1}, ""),
])
def test_ein_ungueltiges_manifest_wird_mit_pfad_abgewiesen(tmp_path, aenderung, pfad):
    with pytest.raises(katalog.KatalogFehler) as fehler:
        katalog.lade(_schreibe(tmp_path, _manifest(**aenderung)))
    assert "ui_probe" in str(fehler.value) or "Probe" in str(fehler.value)
    assert pfad in str(fehler.value)


def test_ein_beispiel_muss_zur_eingabe_passen(tmp_path):
    falsch = _manifest(beispiele=[{"titel": "Falsch", "daten": {"text": 3}}])
    with pytest.raises(katalog.KatalogFehler, match="Falsch"):
        katalog.lade(_schreibe(tmp_path, falsch))


def test_eine_beispiel_antwort_muss_zur_antwort_passen(tmp_path):
    frage = _manifest(
        art="abfragen",
        antwort={"type": "object", "required": ["gewaehlt"],
                 "properties": {"gewaehlt": {"type": "array", "items": {"type": "string"}}}},
        beispiele=[{"titel": "Antwort falsch", "daten": {"text": "?"}, "antwort": {"gewaehlt": 1}}],
    )
    with pytest.raises(katalog.KatalogFehler, match="Antwort falsch"):
        katalog.lade(_schreibe(tmp_path, frage))


def test_doppelte_namen_werden_abgewiesen(tmp_path):
    with pytest.raises(katalog.KatalogFehler, match="doppelt"):
        katalog.lade(_schreibe(tmp_path, _manifest(), _manifest()))


def test_daten_eines_blocks_pruefen(tmp_path):
    kat = katalog.lade(_schreibe(tmp_path, _manifest()))
    assert katalog.daten_fehler(kat["ui_probe"], {"text": "ok"}) == []
    assert katalog.daten_fehler(kat["ui_probe"], {}) != []


def test_das_vertrags_schema_im_backend_ist_die_kopie_aus_dem_frontend():
    """Drift-Wächter: ``npm run module:register`` kopiert das Schema; von Hand geändert wäre
    es eine zweite Wahrheit."""
    datei = FRONTEND / "_vertrag" / "manifest.schema.json"
    quelle = json.loads(datei.read_text(encoding="utf-8"))
    assert katalog.vertrags_schema() == quelle


def test_der_ausgelieferte_katalog_ist_gueltig_und_aktuell():
    """Die abgelegten Manifeste sind gültig und entsprechen den Modul-Ordnern im Frontend."""
    kat = katalog.lade()
    # Ordner in Angular-Schreibweise (ui-inhaltsrahmen), Name mit Unterstrich (ui_inhaltsrahmen).
    ordner = sorted(p.parent.name.replace("-", "_") for p in FRONTEND.glob("ui-*/manifest.json"))
    assert sorted(kat) == ordner


@pytest.mark.parametrize("feld,schema", [
    ("eingabe", {"type": "object", "properties": {"text": {"type": "zeichenkette"}}}),
    ("antwort", {"type": "object", "properties": {"wahl": {"minLength": "drei"}}}),
])
def test_ein_selbst_ungueltiges_daten_schema_wird_abgewiesen(tmp_path, feld, schema):
    mehr = {feld: schema}
    if feld == "antwort":
        mehr |= {"art": "abfragen",
                 "beispiele": [{"titel": "Kurz", "daten": {"text": "Hallo"}, "antwort": {}}]}
    with pytest.raises(katalog.KatalogFehler) as fehler:
        katalog.lade(_schreibe(tmp_path, _manifest(**mehr)))
    assert feld in str(fehler.value)


def test_das_feld_der_textfassung_muss_ein_feld_der_eingabe_sein(tmp_path):
    """Sonst bliebe die Textfassung (Fallback für alte Widgets) stets leer."""
    with pytest.raises(katalog.KatalogFehler, match="textfassung"):
        katalog.lade(_schreibe(tmp_path, _manifest(
            textfassung={"vorlage": "markdown", "feld": "inhalt"})))


def test_der_inhaltsrahmen_steht_im_ausgelieferten_katalog():
    """U1-b1: das erste echte Modul — Titel, Art, Markdown wie das alte Dokument-Werkzeug."""
    katalog.katalog.cache_clear()
    m = katalog.katalog()["ui_inhaltsrahmen"]
    assert m["art"] == "anzeigen" and m["agent"] is True
    assert m["eingabe"]["required"] == ["titel", "art", "markdown"]
    assert {"drucken", "herunterladen"} <= set(m["faehigkeiten"])
    assert m["textfassung"] == {"vorlage": "markdown", "feld": "markdown"}


def test_der_inhaltsrahmen_passt_zum_dokument_werkzeug_des_backends():
    """Drift-Wächter (Review U1-b1): Arten und Titel-Deckel stehen im Manifest und in
    ``domain/inline_documents.py``; was das Backend aufbereitet, muss die Prüfung bestehen."""
    from boerdi.domain import inline_documents as idoc

    katalog.katalog.cache_clear()
    m = katalog.katalog()["ui_inhaltsrahmen"]
    art = m["eingabe"]["properties"]["art"]
    assert set(art["enum"]) == set(idoc.DOKUMENT_ARTEN) | set(art["x-nur-system"])
    assert set(art["x-nur-system"]) == {"volltext", "schreib_vorschau"}
    assert m["eingabe"]["properties"]["titel"]["maxLength"] == idoc.MAX_TITEL_ZEICHEN
    doc = idoc.dokument_aus_argumenten(
        {"titel": "x" * 400, "art": "lernpfad", "markdown": "y" * (idoc.MAX_MARKDOWN_ZEICHEN + 9)})
    assert katalog.daten_fehler(m, {"titel": doc["title"], "art": doc["kind"],
                                    "markdown": doc["content"]}) == []


@pytest.mark.parametrize("platz,ok", [("oben", True), ("unten", True), ("mitte", False)])
def test_darstellung_kennt_den_platz(tmp_path, platz, ok):
    """U1-c1: ``oben`` vor den Trefferboxen (Vorgabe), ``unten`` danach (Linkbox, Trefferliste)."""
    datei = _schreibe(tmp_path, _manifest(darstellung={"breit": False, "platz": platz}))
    if ok:
        assert katalog.lade(datei)["ui_probe"]["darstellung"]["platz"] == platz
    else:
        with pytest.raises(katalog.KatalogFehler):
            katalog.lade(datei)
