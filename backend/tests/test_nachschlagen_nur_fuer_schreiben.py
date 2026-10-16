"""C-1 (Paket 11 L): ``lookup_wlo_vocabulary`` nur für Schreibvorgänge und Metadaten-Prüfung.

Fach, Bildungsstufe, Inhaltstyp und Zielgruppe gleicht der Client selbst ab
(``arg_resolvers._resolve_filter_uris``: Vokabular-Cache, eindeutiger Teilwort-Treffer,
sonst LLM-Rückfall). Das Nachschlagen davor kostete einen Modell-Umlauf je Suche — im
Muster-Modus in gut der Hälfte der Suchzüge (Golden-Läufe Aug./Sep. 2026). Die Lizenz gleicht
der Client seit Paket 11 L ebenfalls ab (``lizenz_abgleich``). Die Schreibwerkzeuge laufen nicht
durch den Abgleich — dort bleibt das Nachschlagen.

Die Empfehlung stand an fünf Stellen; Code und Konfiguration müssen dasselbe sagen.
"""

from __future__ import annotations

import re
from pathlib import Path

from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS
from boerdi.services.response_prompt_tools_text import render_tools_block

_SEEDS = Path(__file__).resolve().parents[1] / "seeds"
_ABGEGLICHEN = ("discipline", "educationalContext", "userRole", "learningResourceType", "license")
#: Muster, die Metadaten schreiben — dort braucht es echte URIs aus dem Vokabular.
_SCHREIB_MUSTER = {"m18-kuration.md", "m20-erschliessen.md"}


def _def(name: str) -> dict:
    return next(t["function"] for t in TOOL_DEFINITIONS if t["function"]["name"] == name)


def test_suchfilter_empfehlen_kein_nachschlagen():
    funde = [
        f"{t['function']['name']}.{p}"
        for t in TOOL_DEFINITIONS if t["function"]["name"].startswith("search_")
        for p, schema in t["function"]["parameters"].get("properties", {}).items()
        if p in _ABGEGLICHEN and "lookup_wlo_vocabulary" in schema.get("description", "")
    ]
    assert funde == []


def test_nachschlage_werkzeug_nennt_schreiben_und_nicht_die_suche():
    beschreibung = _def("lookup_wlo_vocabulary")["description"]
    assert "Lizenz" in beschreibung  # ausdrücklich: auch sie nicht
    assert "wlo_create_content" in beschreibung
    assert "VOR einer Suche" not in beschreibung


def test_muster_prompt_empfiehlt_kein_nachschlagen_vor_der_suche():
    block = render_tools_block({}, None, None, "de")
    zeilen = [z for z in block.splitlines() if "lookup_wlo_vocabulary" in z]
    assert zeilen, "das Werkzeug soll im Prompt genannt bleiben"
    for zeile in zeilen:
        assert re.search(r"Schreib|Metadaten", zeile), zeile


def test_konfiguration_empfiehlt_kein_nachschlagen_vor_der_suche():
    """Jede Anleitungszeile, die das Werkzeug nennt, nennt auch Schreiben oder Metadaten.

    Ausgenommen: die Werkzeuglisten (``- lookup_wlo_vocabulary``), Kommentare und die
    Schreib-Muster M18/M20.
    """
    dateien = [*(_SEEDS / "01-base").glob("*.md"), *(_SEEDS / "02-domain").glob("*.md"),
               *(_SEEDS / "03-patterns").glob("m*.md")]
    funde = []
    for datei in dateien:
        if datei.name in _SCHREIB_MUSTER:
            continue
        for nr, zeile in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1):
            if "lookup_wlo_vocabulary" not in zeile:
                continue
            werkzeugliste = re.fullmatch(r"\s*- lookup_wlo_vocabulary\s*", zeile)
            if werkzeugliste or zeile.lstrip().startswith("#"):
                continue
            if not re.search(r"Schreib|Metadaten", zeile):
                funde.append(f"{datei.name}:{nr}: {zeile.strip()}")
    assert funde == []


def test_master_skill_vorlagen_empfehlen_bei_suche_und_nulltreffern_kein_nachschlagen():
    """Review 2026-10-16 (#3): der Master-Skill ist die Steuerfläche des Agenten — seine Vorlagen
    sagten bei M05 „erst, wenn ein Begriff nicht greift“ und bei M12 „Filterbegriffe über
    lookup_wlo_vocabulary normalisieren“, gegen Werkzeugbeschreibung und Muster."""
    skills = Path(__file__).resolve().parents[2] / "docs" / "skills"
    funde = []
    for datei in sorted(skills.glob("vorgehen*.md")):
        absaetze = re.split(r"\n\s*\n|\n(?=- \*\*)", datei.read_text(encoding="utf-8"))
        for absatz in absaetze:
            if re.search(r"\((M05|M12)\)", absatz) and "lookup_wlo_vocabulary" in absatz:
                funde.append(f"{datei.name}: {absatz.strip()[:80]}")
    assert funde == []
