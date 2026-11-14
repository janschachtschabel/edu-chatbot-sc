"""Ketten kürzen (2026-11-13): die Werkzeugbeschreibungen sagen, was der MCP beim Schreiben wirklich
tut — sonst liest das Modell vor jeder Änderung den Datensatz und schlägt jedes Vokabular nach.

Belegt am MCP-Quelltext (Stand 13.11.): die Schreibwerkzeuge nehmen Bezeichnungen und gleichen
sie ab, bei Fach, Stufe und Zielgruppe auch über Teilwörter (``services/write/fields.ts``,
``vocabs.ts``); der Vorschautext zeigt alt → neu, Titel und Kennung setzt der Client aus dem
strukturierten Teil davor (``domain/write_anzeige.ziel_zeile``); nur Schlagwörter werden
ergänzt (``change-set.ts``, ``MERGED_PROPERTIES``) — Fach, Stufe, Typ und Zielgruppe ersetzt.
Eine falsche Aussage hier führt zu falschen Änderungen im Bestand, deshalb stehen die
Kernsätze fest.
"""
from __future__ import annotations

from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS
from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS


def _werkzeug(katalog: list[dict], name: str) -> dict:
    return next(w["function"] for w in katalog if w["function"]["name"] == name)


def test_aendern_sagt_was_ersetzt_und_was_ergaenzt_wird():
    text = _werkzeug(CURATION_TOOL_DEFINITIONS, "wlo_update_content")["description"]
    assert "Schlagworte werden ergaenzt" in text
    assert "Zielgruppe werden ERSETZT: alle bisherigen Werte fallen weg" in text
    # „Fach ergänzen“ geht mit diesem Werkzeug nicht — und soll keine Ersetzen-Vorschau öffnen.
    assert "Soll ein Wert HINZUKOMMEN, dieses Werkzeug dafuer nicht aufrufen" in text


def test_aendern_nennt_die_grenzen_der_vorschau():
    """Review 2026-11-13 (M1, M2): ein Wert der Vorschau kann vom genannten abweichen (Alias; der
    Server vor dem 14.11. auch über Teilwörter); den Datensatz nennt die Vorschau, weil der Client
    ihn davorsetzt (``test_vorschau_nennt_datensatz``)."""
    text = _werkzeug(CURATION_TOOL_DEFINITIONS, "wlo_update_content")["description"]
    assert "Die Vorschau nennt den Datensatz und zeigt je Feld alt und neu" in text
    assert "Weicht ein Wert der Vorschau vom genannten ab" in text
    assert "get_node_details davor nur, wenn die nodeId nicht aus dem Gespraech stammt" in text


def test_vokabularfelder_nehmen_die_bezeichnung():
    felder = _werkzeug(CURATION_TOOL_DEFINITIONS, "wlo_update_content")["parameters"]["properties"]
    for feld in ("discipline", "educationalContext", "contentType", "userRole"):
        assert "Bezeichnung" in felder[feld]["description"], feld
    assert "ergaenzt" in felder["keywords"]["description"]
    # Seit dem MCP-Stand vom 14.11. rät der Server beim Schreiben nicht mehr: er nennt Kandidaten.
    assert "nennt Kandidaten" in felder["discipline"]["description"]
    assert "Teilwoerter" not in felder["discipline"]["description"]
    # Der Schreibpfad prüft den Typ gegen ein feineres Vokabular: „Video“ lehnt er ab.
    assert "Video" not in felder["contentType"]["description"]
    assert "Vorschlag aus seiner Ablehnung" in felder["contentType"]["description"]
    # Zwei Bedeutungen (der Server verlangt dann die URI) oder kein Vorschlag: die Person fragen.
    assert "die Person fragen" in felder["contentType"]["description"]


def test_nachschlagen_ist_keine_pflicht_vor_dem_schreiben():
    text = _werkzeug(TOOL_DEFINITIONS, "lookup_wlo_vocabulary")["description"]
    assert "brauchen die echten URIs" not in text
    assert "abgelehnt" in text          # der Anlass: der Server hat eine Bezeichnung abgelehnt
    assert "Den Inhaltstyp fuers Schreiben NICHT hier nachschlagen" in text
    assert "SUCHE NICHT" in text        # die alte Grenze zur Suche bleibt


def test_dublettenpruefung_bleibt_beim_anlegen():
    """``find_content_by_url`` findet auch bereinigte Schreibweisen; die Vorschau des Anlegens nur
    die genaue Adresse (``duplicates.ts``) — die Prüfung davor darf nicht entfallen."""
    anlegen = _werkzeug(CURATION_TOOL_DEFINITIONS, "wlo_create_content")["description"]
    assert "find_content_by_url" in anlegen
    finden = _werkzeug(TOOL_DEFINITIONS, "find_content_by_url")["description"]
    assert "gleichzeitig mit get_url_text" in finden
