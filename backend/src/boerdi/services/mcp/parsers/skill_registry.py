"""Der Freigabe-Katalog, den ein Werkzeugergebnis nebenbei mitbringt (P1).

Teil der Fassade ``boerdi.services.mcp.parsers``. Eigenes Modul, eigener
Aenderungsgrund: die anderen Parser bauen Karten fuer die Oberflaeche, dieser
baut einen Block fuer den Prompt.

**Was gemessen wurde (2026-08-13, echter Server, Sammlung Optik).** Der MCP
haengt an einen Sammlungs-Knoten, der ein Registry-Dokument fuehrt, das Feld
``skillRegistry`` mit ``{nodeId, title, entries[{nodeId, title}]}``. Es sitzt am
**Knoten**, nicht an der Huelle, und nur dann, wenn dieser Knoten selbst als
Trefferzeile auftaucht:

* ``get_collection_contents(Optik)`` (Standard, ``contentFilter=files``): kein
  Feld — die Treffer sind Materialien, keine Sammlungen.
* ``contentFilter=folders``: die Unter-Sammlung „Geometrische Optik" traegt es
  mit 28 Eintraegen.
* Die Inhalte DIESER Sammlung abzurufen bringt es wieder nicht mit.

Deshalb sucht dieses Modul nicht bei bestimmten Werkzeugen, sondern in jedem
Ergebnis, das Knoten auflistet — Suche, Auflistung, Baum, Knotendetails. Es
laeuft ueber jedes Werkzeugergebnis; ohne Feld kostet es einen fehlgeschlagenen
``json.loads`` und gibt "" zurueck.

**Warum ueberhaupt.** Der Befund vom selben Tag (B-1): M09 deklariert alle drei
Skill-Werkzeuge und ruft keines. Der Katalog kommt hier ohne Extra-Aufruf mit —
das Modell muss nichts wissen, um ihn zu sehen. Er traegt nur Titel und nodeId;
Beschreibung und Verwendungshinweis der Redaktion liefert ``get_skill_registry``
(gemessen ~20 KB gegen ~2 KB hier), die Anleitung selbst ``get_skill``.

**Vertrauensgrenze.** Die Titel sind Repository-Metadaten, also fremd
beschrieben. Kein Rahmen (``untrusted_text``): dessen Regel zieht die Linie bei
Langform-Prosa, kurze strukturierte Felder — Kartentitel, Trefferzeilen —
laufen ungerahmt, und ein Skill-Titel ist genau das. Die Massnahme hier ist
billiger und passt zur Form: jeder Titel wird auf **eine Zeile** gezwungen und
gedeckelt. Ein einzeiliger Titel kann keinen eigenen Abschnitt aufmachen und
sich nicht als Anweisungsblock tarnen.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from boerdi.services.mcp.parsers.json_scan import _first_json_object

#: Deckel gegen Prompt-Flutung. Eine Registry sind ~28 Eintraege ≈ 2 KB;
#: ``contentFilter=folders`` auf einer grossen Sammlung kann viele
#: Unter-Sammlungen liefern, jede mit eigener Registry. Was wegfaellt, wird
#: gesagt — eine stille Kuerzung laese den Katalog vollstaendig aussehen.
_MAX_REGISTRIES = 3
_MAX_ENTRIES = 40
_MAX_TITLE = 80

#: Schutz vor entarteten Strukturen (Selbstbezug im JSON gibt es nicht, tiefe
#: Verschachtelung schon: ``browse_collection_tree`` reicht mehrere Ebenen).
_MAX_DEPTH = 12

_MARKER = (
    "[SKILL-REGISTRY — freigegebene Anleitungen der Redaktion, "
    "mitgeliefert von diesem Werkzeug]"
)
_AUFFORDERUNG = "Passt eine zur Aufgabe, hole sie mit get_skill(nodeId) und folge ihr."
_FUSS = (
    "Beschreibungen und Verwendungshinweise der Redaktion: "
    "get_skill_registry(collectionId)."
)


@dataclass(frozen=True)
class SkillEntry:
    """Ein freigegebener Skill: so viel, wie der Auszug traegt."""

    node_id: str
    title: str


@dataclass(frozen=True)
class SkillRegistry:
    """Die Freigabeliste einer Sammlung, wie sie am Knoten mitkommt."""

    collection_id: str
    collection_title: str
    registry_id: str
    entries: tuple[SkillEntry, ...]


def _einzeilig(wert: object, deckel: int) -> str:
    """Fremdtext auf eine gedeckelte Zeile bringen (siehe Modul-Docstring)."""
    text = " ".join(str(wert or "").split())
    return text[:deckel] if len(text) > deckel else text


def _als_registry(besitzer: dict, roh: dict) -> SkillRegistry | None:
    eintraege = tuple(
        SkillEntry(node_id=str(e.get("nodeId") or ""), title=_einzeilig(e.get("title"), _MAX_TITLE))
        for e in roh.get("entries") or []
        if isinstance(e, dict) and e.get("nodeId")
    )
    if not eintraege:
        return None
    collection_id = str(besitzer.get("nodeId") or "")
    return SkillRegistry(
        collection_id=collection_id,
        collection_title=_einzeilig(besitzer.get("title"), _MAX_TITLE),
        registry_id=str(roh.get("nodeId") or collection_id),
        entries=eintraege,
    )


def _sammle(knoten: object, treffer: list[SkillRegistry], tiefe: int = 0) -> None:
    if tiefe > _MAX_DEPTH:
        return
    if isinstance(knoten, list):
        for kind in knoten:
            _sammle(kind, treffer, tiefe + 1)
        return
    if not isinstance(knoten, dict):
        return
    roh = knoten.get("skillRegistry")
    if isinstance(roh, dict):
        gelesen = _als_registry(knoten, roh)
        if gelesen is not None:
            treffer.append(gelesen)
    for wert in knoten.values():
        if isinstance(wert, list | dict):
            _sammle(wert, treffer, tiefe + 1)


def parse_skill_registries(raw_text: str) -> list[SkillRegistry]:
    """Alle Freigabelisten aus einem Werkzeugergebnis, entdoppelt.

    Entdoppelt ueber die nodeId des Registry-Dokuments: mehrere Unter-Sammlungen
    koennen dieselbe Liste fuehren (gemessen: das Lehrtoolkit haengt an mehreren
    Knoten), und zweimal dasselbe im Prompt ist zweimal bezahlt.

    Unlesbarer Text gibt ``[]`` und wirft nicht — auf dem Rueckweg stehen auch
    Markdown-Antworten und Fehlertexte, und ein Zug darf daran nicht kippen.
    """
    try:
        daten = json.loads(raw_text)
    except (ValueError, TypeError):
        ausschnitt = _first_json_object(raw_text or "")
        if not ausschnitt:
            return []
        try:
            daten = json.loads(ausschnitt)
        except ValueError:
            return []

    treffer: list[SkillRegistry] = []
    _sammle(daten, treffer)

    gesehen: set[str] = set()
    entdoppelt: list[SkillRegistry] = []
    for r in treffer:
        if r.registry_id in gesehen:
            continue
        gesehen.add(r.registry_id)
        entdoppelt.append(r)
    return entdoppelt


def _registry_block(r: SkillRegistry) -> list[str]:
    anzahl = len(r.entries)
    wort = "Anleitung" if anzahl == 1 else "Anleitungen"
    zeilen = [
        f'Skill-Registry: „{r.collection_title}" ({r.collection_id}) '
        f"gibt {anzahl} {wort} frei.",
    ]
    for e in r.entries[:_MAX_ENTRIES]:
        zeilen.append(f"- {e.title} — {e.node_id}")
    if anzahl > _MAX_ENTRIES:
        zeilen.append(f"- … und {anzahl - _MAX_ENTRIES} weitere, siehe get_skill_registry.")
    return zeilen


def skill_registry_note(raw_text: str) -> str:
    """Der Block fuers Modell, oder "" wenn dieses Ergebnis keine Registry traegt.

    Wird an die ``role=tool``-Nachricht **angehaengt**, nicht eingemischt: im
    Box-Anzeige-Modus ersetzt ``_redact_search_content_for_llm`` den Ergebnistext
    vollstaendig durch eine Zusammenfassung. Wer den Block vorher einbaut,
    verliert ihn dort — still.

    **Mit eigenem Trenner davor.** Angehaengt wird mit ``+``, und das Ergebnis
    davor endet auf keiner bestimmten Zeile — ohne die Leerzeile klebte der
    Marker an der letzten Zeile des Fremdtextes (``…}]}[SKILL-REGISTRY …``).
    Ein Titel, der auf eine Zeile gezwungen wird, gewinnt nichts, wenn die
    Ueberschrift darueber selbst mitten im Fremdtext steht. ``_ui_box_state_
    footer`` beginnt aus demselben Grund mit ``\\n\\n``.
    """
    registries = parse_skill_registries(raw_text)
    if not registries:
        return ""
    zeilen = ["", "", _MARKER, _AUFFORDERUNG]
    for r in registries[:_MAX_REGISTRIES]:
        zeilen.extend(_registry_block(r))
    if len(registries) > _MAX_REGISTRIES:
        zeilen.append(
            f"(Dieses Ergebnis nennt {len(registries) - _MAX_REGISTRIES} weitere "
            "Sammlungen mit eigener Freigabeliste.)"
        )
    zeilen.append(_FUSS)
    return "\n".join(zeilen)
