"""Paket U1-b2: das Dokument-Werkzeug ist das Modul-Werkzeug ``ui_inhaltsrahmen``.

Beschreibung und Parameter kommen aus dem Manifest des Moduls
(``frontend/projects/ui-module/src/ui-inhaltsrahmen/manifest.json``), die Argumente werden
aufbereitet (kürzen, Art-Rückfall) und dann gegen ``eingabe`` geprüft. Der alte Name
``zeige_dokument`` wird weiter angenommen (gespeicherte Rollen-Vorgaben, live abgelegte
Master-Skills), angeboten wird nur der neue.
"""

from __future__ import annotations

import pytest

from boerdi.domain import inline_documents as idoc
from boerdi.ui_module import katalog, werkzeuge


def _manifest() -> dict:
    return katalog.katalog()["ui_inhaltsrahmen"]


# ── b2-1: Werkzeug aus dem Manifest ───────────────────────────────────────
def test_das_werkzeug_entsteht_aus_dem_manifest():
    f = werkzeuge.werkzeug_aus_manifest(_manifest())["function"]
    assert f["name"] == "ui_inhaltsrahmen"
    assert f["description"].startswith(_manifest()["beschreibung"])
    assert "WANN:" in f["description"] and "NICHT:" in f["description"]
    assert f["parameters"]["required"] == ["titel", "art", "markdown"]


def test_systemarten_und_eigene_schluessel_gehen_nicht_an_die_ki():
    parameter = werkzeuge.werkzeug_aus_manifest(_manifest())["function"]["parameters"]
    art = parameter["properties"]["art"]
    assert "volltext" not in art["enum"] and "schreib_vorschau" not in art["enum"]
    assert set(art["enum"]) == set(idoc.DOKUMENT_ARTEN)
    assert not [k for k in art if k.startswith("x-")]
    # das Manifest selbst bleibt unberührt
    assert "x-nur-system" in _manifest()["eingabe"]["properties"]["art"]


def test_feldnamen_mit_x_bleiben_und_leere_aufzaehlungen_fallen_weg():
    m = {"name": "ui_probe", "beschreibung": "Probe.", "eingabe": {
        "type": "object", "properties": {
            "x-wert": {"type": "string", "description": "heißt nur so"},
            "nur": {"type": "string", "enum": ["a"], "x-nur-system": ["a"]}}}}
    props = werkzeuge.werkzeug_aus_manifest(m)["function"]["parameters"]["properties"]
    assert "x-wert" in props
    assert "enum" not in props["nur"]


def test_das_dokument_werkzeug_ist_das_modul_werkzeug():
    assert idoc.dokument_werkzeug() == werkzeuge.werkzeug_aus_manifest(_manifest())


# ── b2-2: Name und Alias ──────────────────────────────────────────────────
def test_beide_namen_meinen_das_dokument_werkzeug():
    assert idoc.INHALTSRAHMEN == "ui_inhaltsrahmen"
    assert idoc.ist_dokument_werkzeug("ui_inhaltsrahmen")
    assert idoc.ist_dokument_werkzeug("zeige_dokument")
    assert not idoc.ist_dokument_werkzeug("respond_to_user")
    assert not idoc.ist_dokument_werkzeug(None)


# ── b2-1: Annahme mit Prüfung ─────────────────────────────────────────────
def test_ein_brauchbarer_aufruf_wird_zum_dokument():
    dok, fehler = idoc.dokument_annehmen({"titel": "Plan", "art": "lernpfad", "markdown": "x"})
    assert fehler is None
    assert dok == {"kind": "lernpfad", "title": "Plan", "content": "x", "meta": {"source": "tool"}}


@pytest.mark.parametrize("art", ["volltext", "schreib_vorschau", "gibt_es_nicht", 7])
def test_systemarten_und_unbekanntes_vom_modell_fallen_auf_dokument(art):
    dok, fehler = idoc.dokument_annehmen({"titel": "T", "art": art, "markdown": "x"})
    assert fehler is None and dok["kind"] == "dokument"


@pytest.mark.parametrize("args", [
    {"titel": "", "art": "lernpfad", "markdown": "x"},
    {"titel": "T", "art": "lernpfad", "markdown": "   "},
    {"titel": 3, "art": "lernpfad", "markdown": "x"},
    "kein Objekt",
])
def test_unbrauchbares_meldet_einen_fehler(args):
    dok, fehler = idoc.dokument_annehmen(args)
    assert dok is None and fehler.startswith(idoc.DOKUMENT_FEHLER)


@pytest.mark.parametrize("args,fehlt", [
    ({"titel": "", "art": "lernpfad", "markdown": "x"}, "titel"),
    ({"titel": "T", "art": "lernpfad", "markdown": "  "}, "markdown"),
    ({"art": "lernpfad"}, "titel, markdown"),
    ("kein Objekt", "titel, markdown"),
])
def test_der_fehler_nennt_das_fehlende_feld(args, fehlt):
    _dok, fehler = idoc.dokument_annehmen(args)
    assert fehler.endswith(f"Fehlt oder leer: {fehlt}.")


def test_eine_abweichung_vom_manifest_nennt_den_pfad(monkeypatch):
    """Die Manifest-Prüfung ist der Wächter gegen Drift zwischen Aufbereitung und Manifest."""
    import copy

    eng = copy.deepcopy(_manifest())
    eng["eingabe"]["properties"]["markdown"]["maxLength"] = 3
    monkeypatch.setattr(idoc, "_manifest", lambda: eng)
    dok, fehler = idoc.dokument_annehmen({"titel": "T", "art": "lernpfad", "markdown": "zu lang"})
    assert dok is None
    assert "Abweichungen: markdown:" in fehler


def test_zu_langes_wird_gekuerzt_und_besteht_die_pruefung():
    dok, fehler = idoc.dokument_annehmen({
        "titel": "T" * 500, "art": "bericht", "markdown": "m" * (idoc.MAX_MARKDOWN_ZEICHEN + 50)})
    assert fehler is None
    assert len(dok["title"]) <= idoc.MAX_TITEL_ZEICHEN
    assert len(dok["content"]) <= idoc.MAX_MARKDOWN_ZEICHEN


# ── b2-3: Dokument → Block ────────────────────────────────────────────────
def test_aus_einem_dokument_wird_ein_inhaltsrahmen_block():
    b = idoc.als_inhaltsrahmen({"kind": "volltext", "title": "T", "content": "## x", "meta": {}})
    assert (b.modul, b.version, b.art, b.status) == (
        "ui_inhaltsrahmen", 1, "anzeigen", "nur_anzeige")
    assert b.daten == {"titel": "T", "art": "volltext", "markdown": "## x"}
    assert b.text == "## x"


@pytest.mark.parametrize("art", [*idoc.DOKUMENT_ARTEN, "volltext", "schreib_vorschau", "quiz"])
def test_jeder_block_aus_dem_trichter_besteht_die_pruefung(art):
    """Auch System-Boxen (Volltext-Titel kommt ungedeckelt vom MCP) passen zum Manifest."""
    b = idoc.als_inhaltsrahmen({"kind": art, "title": "T" * 400, "content": "x"})
    assert katalog.daten_fehler(_manifest(), b.daten) == []
    assert len(b.daten["titel"]) <= idoc.MAX_TITEL_ZEICHEN


def test_auch_ein_pydantic_dokument_wird_ein_block():
    from boerdi.api.schemas_inline import InlineDocument

    b = idoc.als_inhaltsrahmen(InlineDocument(kind="schreib_vorschau", title="Ä", content="c"))
    assert b.daten == {"titel": "Ä", "art": "schreib_vorschau", "markdown": "c"}


# ── b2-3: Wächter — es gibt nur noch einen Kanal ──────────────────────────
def test_keine_antwort_befuellt_noch_inline_documents():
    """Jede Box reist als Inhaltsrahmen-Block. Wer eine Antwort mit ``inline_documents=``
    baut, umginge den Kanal — das alte Feld steht nur noch als veraltet im Vertrag."""
    import re
    from pathlib import Path

    import boerdi

    wurzel = Path(boerdi.__file__).parent
    treffer = [f"{p.relative_to(wurzel)}:{nr}"
               for p in wurzel.rglob("*.py")
               for nr, zeile in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
               if re.search(r"\binline_documents=(?!=)", zeile)]
    assert treffer == []


def test_die_alten_box_felder_sind_im_vertrag_als_veraltet_markiert():
    """Die Felder bleiben (ihr Wegfall ist ein eigener Entscheid), aber Clients sehen im
    Schema, dass sie nicht mehr gefüllt bzw. nicht mehr gebraucht werden."""
    from boerdi.api.schemas import ChatResponse
    from boerdi.api.schemas_ui import UiInfo

    assert ChatResponse.model_json_schema()["properties"]["inline_documents"]["deprecated"] is True
    assert UiInfo.model_json_schema()["properties"]["dokumente"]["deprecated"] is True
