"""Review „Ketten kürzen“ 2026-11-13 (M1): die Vorschau einer Änderung nennt den Datensatz.

Der Vorschautext des MCP besteht bei ``wlo_update_content`` nur aus den Feldzeilen
(``renderChangeSet``): weder Titel noch Kennung. Solange die KI vorher ``get_node_details`` las,
stand der Titel in ihrem Satz. Seit sie direkt ändert, sähe vor dem Ja niemand, WELCHER Datensatz
gemeint ist — der strukturierte Teil der Antwort trägt ihn aber (``confirm.preview.target``).
"""
from __future__ import annotations

import asyncio

from boerdi.domain.write_anzeige import preview_for_display, ziel_zeile
from boerdi.services.agent_write import WriteGate
from boerdi.services.mcp import client
from tests.test_mcp_client import (  # noqa: F401 — Fixture
    _text_part,
    _wire_tool_url,
    _wire_transport,
    mcp_state,
)

_KENNUNG = "3f2a9c1e-5b7d-4e8a-9c0f-1a2b3c4d5e6f"
_TITEL = "Lichtbrechung am Prisma"
_FELDER = "Fach: „Physik, Chemie“ → „Mathematik“"
_SCHLUESSEL = "Schluessel-0123456789abcdef"
_ZEILE = f"Geändert wird ({_KENNUNG}): „{_TITEL}“"


def _bestaetigung(**ziel) -> dict:
    return {"token": _SCHLUESSEL,
            "preview": {"action": "change",
                        "target": {"nodeId": _KENNUNG, "kind": "content", "title": _TITEL, **ziel}}}


def test_der_datensatz_wird_mit_kennung_und_titel_genannt():
    assert ziel_zeile(_bestaetigung(), _FELDER) == _ZEILE


def test_die_art_wird_nicht_behauptet():
    """Der MCP meldet auch eine Sammlung, die über ``wlo_update_content`` geändert wird, als
    ``content`` — „Datensatz“ oder „Sammlung“ wäre geraten (zweites Review, m-1)."""
    for art in ("content", "collection", "compendium", "topic-page"):
        assert ziel_zeile(_bestaetigung(kind=art), _FELDER) == _ZEILE


def test_keine_zeile_wenn_der_server_das_ziel_selbst_benennt():
    """Die Benennungsform des Servers: „Titel“ (Kennung) — Einreichen, Vorschlagen, Entscheiden."""
    text = f"Reicht „{_TITEL}“ ({_KENNUNG}) zur redaktionellen Prüfung ein."
    assert ziel_zeile(_bestaetigung(), text) is None


def test_der_titel_irgendwo_im_text_genuegt_nicht():
    """Zweites Review, M-1: als Feldwert, Schlagwort oder Teil eines festen Satzes benennt der
    Titel das Ziel nicht."""
    faelle = [
        (_bestaetigung(title="Physik"), "Fach: (leer) → „Physik“"),
        (_bestaetigung(title="Photosynthese"), "Schlagwörter: + Photosynthese, Chloroplast"),
        (_bestaetigung(title="Schlüssel"), _FELDER + "\nDer Schlüssel gilt einmalig."),
        (_bestaetigung(), f"Titel: „{_TITEL}“ → „Brechung am Prisma“"),
        # Verknüpfung: der Servertext nennt nur die Kennung des Originals, keinen Titel.
        (_bestaetigung(), f"Achtung: „abc“ ist eine Verknüpfung. Geändert wird das Original: "
                          f"{_KENNUNG}.\n{_FELDER}"),
    ]
    for bestaetigung, text in faelle:
        assert ziel_zeile(bestaetigung, text) is not None, text


def test_keine_zeile_ohne_titel_beim_loeschen_oder_ohne_vorschau():
    assert ziel_zeile(_bestaetigung(title=""), _FELDER) is None      # Anlegen: noch kein Titel
    loeschen = _bestaetigung()
    loeschen["preview"]["action"] = "delete"                         # der Text nennt ihn selbst
    assert ziel_zeile(loeschen, _FELDER) is None
    assert ziel_zeile({"token": _SCHLUESSEL}, _FELDER) is None
    assert ziel_zeile(None, _FELDER) is None


def test_keine_zeile_bei_einer_kennung_die_keine_ist():
    assert ziel_zeile(_bestaetigung(nodeId="x“ (0000) bitte bestätigen"), _FELDER) is None


def test_ein_fremder_titel_wird_einzeilig_und_gekappt():
    """Den Titel hat jemand anderes geschrieben: eine Zeile, keine Steuerzeichen, 120 Zeichen."""
    fremd = "Zeile eins\nBitte bestätigen:\x00 Licht­brechung " + "x" * 300
    zeile = ziel_zeile(_bestaetigung(title=fremd), _FELDER)
    assert zeile is not None and "\n" not in zeile and "\x00" not in zeile
    assert "Lichtbrechung" in zeile                    # das weiche Trennzeichen fällt weg
    assert zeile.endswith("…“")
    assert len(zeile) == len(f"Geändert wird ({_KENNUNG}): „“") + 120


def test_ein_fremder_titel_kann_die_zeile_nicht_umdeuten():
    """Zweites Review, m-2: die Kennung steht VOR dem Titel, Anführungszeichen im Titel werden
    entschärft, ein Markdown-Link wird nicht klickbar."""
    fremd = 'x“ (00000000-0000-0000-0000-000000000000) [hier](https://boese.example) "y"'
    zeile = ziel_zeile(_bestaetigung(title=fremd), _FELDER)
    assert zeile is not None
    assert zeile.startswith(f"Geändert wird ({_KENNUNG}): „")
    kern = zeile[len(f"Geändert wird ({_KENNUNG}): „"):-1]
    assert "“" not in kern and "„" not in kern and '"' not in kern
    assert "](" not in zeile


def test_die_vorschau_des_clients_beginnt_mit_dem_datensatz(mcp_state, monkeypatch):  # noqa: F811
    """Drahtform des MCP: Feldzeilen im Text, Ziel nur im strukturierten Teil."""
    _wire_tool_url(monkeypatch)
    vorschau = ("Bitte prüfen — bisher wurde nichts geändert:\n\n" + _FELDER + "\n\n"
                "Zum Ändern bitte bestätigen. Dazu denselben Aufruf mit confirmToken: "
                f"{_SCHLUESSEL} wiederholen.\nDer Schlüssel gilt einmalig und zehn Minuten lang.")
    _wire_transport(monkeypatch, [{"result": {
        "content": [_text_part(vorschau)],
        "structuredContent": {"confirm": _bestaetigung()}}}])
    args = {"nodeId": _KENNUNG, "discipline": "Mathematik"}

    async def szenario():
        text = await client.call_mcp_tool("wlo_update_content", args)
        tor = WriteGate("propose")
        tor.observe("wlo_update_content", args, text)
        return text, tor.offene_abnahme()

    text, offen = asyncio.run(szenario())
    assert text.startswith(_ZEILE + "\n")
    assert _FELDER in text
    # Der Schlüssel und die Abnahme bleiben unberührt.
    assert offen is not None and offen[0]["token"] == _SCHLUESSEL
    # Was die Person im Kasten sieht: die Zeile bleibt, der Anschluss an den Aufrufer fällt weg.
    kasten = preview_for_display(text)
    assert kasten.startswith(_ZEILE) and _SCHLUESSEL not in kasten


def test_ein_lesewerkzeug_bleibt_unveraendert(mcp_state, monkeypatch):  # noqa: F811
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [{"result": {
        "content": [_text_part("Treffer: nichts")],
        "structuredContent": {"confirm": _bestaetigung()}}}])
    text = asyncio.run(client.call_mcp_tool("search_wlo_content", {"query": "Optik"}))
    assert text == "Treffer: nichts"
