"""Wächter über die bewussten Vertragszusätze (K4).

Der OpenAPI-Vertrag ist eingefroren und wird byte-genau verglichen
(`scripts/export_openapi.py --check`). Beim Zusatz der Kosten-Routen ist er
**bewusst** neu erzeugt worden — der Nutzer-Entscheid steht in
`docs/plans/2026-08-11-kostenueberwachung.md` §5.5.

Das Restrisiko dieses Entscheids benennt derselbe Abschnitt: wird „Gate rot →
neu erzeugen" zum Reflex, fängt das Gate irgendwann keine Versehen mehr. Dieser
Wächter ist das Gegenmittel — dieselbe Bauart wie `BEWUSST_EINSPRACHIG`
(i18n), `OHNE_BUCHUNG` (K1f) und `NEUE_BEREICHE` (K3): eine benannte Liste mit
Grund, und ein Test, der **beide** Richtungen prüft.

* Vorwärts: jede in der Liste genannte Operation gibt es wirklich.
* Rückwärts: die Zahl der Operationen im Vertrag ist genau die eingefrorene
  plus die Zahl der begründeten Zusätze. Eine **undokumentierte** Route fällt
  damit auf, auch wenn jemand den Vertrag arglos neu erzeugt hat.

Verhältnis zu ``test_openapi_contract.py``: der ältere Wächter dort vergleicht
das Routen-Inventar der **laufenden App** gegen eine Liste im Test. Dieser hier
zählt gegen den **abgelegten Vertrag** und verlangt die Begründung in einer
ausgelieferten Datei statt in einem Test-Docstring. Beide zusammen decken die
zwei Seiten ab; wer nur einen von beiden pflegt, merkt es an dieser Stelle.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_DOCS = Path(__file__).resolve().parents[2] / "docs" / "api"
_VERTRAG = _DOCS / "openapi-v1.json"
_ZUSAETZE = _DOCS / "bewusste-vertragszusaetze.md"

# Der Stand beim Einfrieren (P0-4), gemessen 2026-08-11 am unveränderten
# Dokument: 86 Pfade, 114 Operationen (61 GET, 26 POST, 13 PUT, 11 DELETE,
# 3 HEAD). Diese Zahlen dürfen NICHT nachgezogen werden, wenn das Gate rot
# wird — genau dann soll der Zusatz stattdessen unten in die Liste.
_EINGEFROREN_PFADE = 86
_EINGEFROREN_OPERATIONEN = 114

_ZEILE = re.compile(
    r"^\|\s*(GET|POST|PUT|PATCH|DELETE|HEAD)\s*\|\s*`([^`]+)`\s*\|(.+)\|\s*$",
    re.M,
)


def _vertrag() -> dict:
    return json.loads(_VERTRAG.read_text(encoding="utf-8"))


def _gelistet() -> list[tuple[str, str, str]]:
    """``[(Methode, Pfad, Grund)]`` aus der Markdown-Tabelle."""
    return [
        (m.group(1).lower(), m.group(2).strip(), m.group(3).strip())
        for m in _ZEILE.finditer(_ZUSAETZE.read_text(encoding="utf-8"))
    ]


def test_die_liste_existiert_und_ist_nicht_leer() -> None:
    assert _ZUSAETZE.is_file(), f"fehlt: {_ZUSAETZE}"
    assert _gelistet(), "keine Tabellenzeile erkannt — Format der Liste geprüft?"


def test_jeder_genannte_zusatz_existiert_wirklich() -> None:
    pfade = _vertrag()["paths"]
    fehlend = [
        f"{methode.upper()} {pfad}"
        for methode, pfad, _ in _gelistet()
        if methode not in pfade.get(pfad, {})
    ]
    assert fehlend == [], f"in der Liste, aber nicht im Vertrag: {fehlend}"


def test_jeder_zusatz_traegt_einen_grund() -> None:
    knapp = [f"{m.upper()} {p}" for m, p, grund in _gelistet() if len(grund) < 40]
    assert knapp == [], f"Grund zu knapp: {knapp}"


def test_der_vertrag_traegt_keine_undokumentierte_route() -> None:
    """Die Gegenrichtung — der eigentliche Zweck dieses Wächters."""
    pfade = _vertrag()["paths"]
    operationen = sum(len(v) for v in pfade.values())
    gelistet = _gelistet()
    neue_pfade = {p for _, p, _ in gelistet}

    assert operationen == _EINGEFROREN_OPERATIONEN + len(gelistet), (
        f"{operationen} Operationen im Vertrag, erwartet "
        f"{_EINGEFROREN_OPERATIONEN} + {len(gelistet)} dokumentierte Zusätze. "
        "Wenn der Zusatz gewollt ist, gehört er nach "
        "docs/api/bewusste-vertragszusaetze.md — nicht in diese Zahl."
    )
    assert len(pfade) == _EINGEFROREN_PFADE + len(neue_pfade)
