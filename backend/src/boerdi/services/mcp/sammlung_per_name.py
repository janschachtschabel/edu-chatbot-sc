"""Eine Sammlung über ihren Titel ansprechen (Plan 2026-11-14, N3).

Der MCP-Server nimmt an fünf lesenden Werkzeugen statt der Kennung den Titel der Sammlung
(``collection``), dazu das Fach, das gleichnamige Sammlungen unterscheidet. Er rät nie: Trägt
keine oder mehr als eine Sammlung den Titel, kommen Kandidaten statt eines Ergebnisses
(``ambiguous_collection``). Für das Modell entfällt damit der Zug „erst suchen, dann die Kennung
übergeben“, wenn der Titel eindeutig ist.

Dieses Modul sagt, **was das Modell angeboten bekommt** (Parameter und Beschreibung — nur, wenn
der bereitgestellte Server sie kennt, :mod:`faehigkeiten`) und **was es über die Wahl des Servers
erfährt**: die gewählte Sammlung und die Kandidaten, jeweils aus dem strukturierten Teil der
Antwort gebaut und entschärft. Die Argument-Modelle (``api/schemas_mcp``) nehmen die Parameter
immer an.

**Titel und Pfade sind Fremdtext** (Review N3, Befund 1): Wer eine Sammlung benennen darf, könnte
im Titel eine Kennung, einen Pfad oder eine zweite Zeile vortäuschen. Deshalb steht die Kennung
immer vorn und kommt aus ihrem eigenen Feld, Titel und Pfad stehen in „…“ und verlieren alles,
was diese Fassung brechen oder eine Kennung nachahmen könnte (:func:`fuer_ki`). Gelesen wird nur
das JSON am ANFANG der Antwort — ein JSON, das irgendwo in einem Titel steht, zählt nicht.
"""

from __future__ import annotations

import copy
import re
import unicodedata
from typing import Any, Final, NamedTuple

from boerdi.services.mcp import faehigkeiten

PARAMETER: Final = "collection"
#: Fehlercode des Servers für „kein oder mehr als ein Treffer, oder nicht sicher feststellbar“.
MEHRDEUTIG: Final = "ambiguous_collection"

#: Werkzeug → (Parameter der Kennung, Parameter für das Fach der Sammlung). ``discipline`` ist bei
#: ``search_wlo_within_collection`` schon der Inhaltsfilter — dort heißt das Fach der Sammlung
#: ``collectionDiscipline`` (``wlo-mcp-server-sc/src/tools/collection-arg.ts``).
WERKZEUGE: Final[dict[str, tuple[str, str]]] = {
    "get_collection_contents": ("nodeId", "discipline"),
    "search_wlo_within_collection": ("nodeId", "collectionDiscipline"),
    "browse_collection_tree": ("nodeId", "discipline"),
    "get_compendium_text": ("nodeId", "discipline"),
    "get_collection_overview": ("collectionId", "discipline"),
}

_TITEL: Final = (
    "Titel der Sammlung STATT ihrer Kennung, z. B. 'Optik' — nur, wenn du die Kennung nicht schon "
    "hast. Der Titel muss genau stimmen; der Server raet nie. Traegt keine oder mehr als eine "
    "Sammlung den Titel, kommen statt des Ergebnisses Kandidaten mit Pfad und Kennung: waehle "
    "daraus per Kennung, oder frage nach, wenn keiner passt. Bei Erfolg nennt das Ergebnis die "
    "gewaehlte Sammlung mit Pfad und Kennung; liegt sie nicht dort, wo die Frage hinzielt (z. B. "
    "unter 'Communities' statt unter einem Fach), suche mit search_wlo_collections."
)
_FACH: Final = (
    "Nur zusammen mit collection: Fach der gesuchten Sammlung, z. B. 'Physik' — unterscheidet "
    "gleichnamige Sammlungen. Immer angeben, wenn das Fach bekannt ist."
)
_FACH_EIGENER_NAME: Final = _FACH + " NICHT der Inhaltsfilter discipline."
_SATZ: Final = (" Statt der Kennung geht der Titel der Sammlung als collection (mit {fach} fuer "
                "das Fach), wenn du die Kennung nicht schon hast.")


def angeboten(werkzeug: str) -> bool:
    """Bekommt das Modell ``collection`` an diesem Werkzeug angeboten?"""
    return werkzeug in WERKZEUGE and faehigkeiten.kennt(werkzeug, PARAMETER)


def erweitert(definition: dict[str, Any]) -> dict[str, Any]:
    """Die Werkzeug-Definition mit ``collection`` und dem Fach-Parameter — eine Kopie; die
    Kennung ist darin keine Pflicht mehr. Für ein Werkzeug ohne Angebot die Definition selbst."""
    name = definition["function"]["name"]
    if not angeboten(name):
        return definition
    kennung, fach = WERKZEUGE[name]
    neu = copy.deepcopy(definition)
    funktion = neu["function"]
    parameter = funktion["parameters"]
    eigenschaften = parameter.setdefault("properties", {})
    eigenschaften[PARAMETER] = {"type": "string", "description": _TITEL}
    eigenschaften[fach] = {"type": "string",
                           "description": _FACH if fach == "discipline" else _FACH_EIGENER_NAME}
    pflicht = [p for p in parameter.get("required", []) if p != kennung]
    if pflicht:
        parameter["required"] = pflicht
    else:
        parameter.pop("required", None)
    funktion["description"] = funktion["description"].rstrip() + _SATZ.format(fach=fach)
    return neu


# ── Was die KI über die Wahl des Servers erfährt ────────────────────────────────────────────────

_KENNUNG: Final = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
#: Etwas in der Form einer Kennung mitten in einem Titel — auch mit fremden Trennern oder ohne.
_KENNUNG_IM_TEXT: Final = re.compile(
    r"[0-9a-fA-F]{8}(?:[\W_]{0,3}[0-9a-fA-F]{4}){3}[\W_]{0,3}[0-9a-fA-F]{12}")
_VORSATZ: Final = re.compile(r"^MCP error(?: \[[^\]]{1,40}\])?:\s*")
_TITEL_ZEICHEN: Final = 120
_PFAD_TEIL_ZEICHEN: Final = 60
_PFAD_TEILE: Final = 6
_HOECHSTENS_KANDIDATEN: Final = 5
_HOECHSTENS_INHALTE: Final = 10_000_000


def ist_kennung(wert: Any) -> bool:
    """Hat ``wert`` die Form einer edu-sharing-Kennung?"""
    return isinstance(wert, str) and bool(_KENNUNG.fullmatch(wert))


def _zeichen(z: str) -> str:
    """Ein Zeichen eines Titels: bleibt, fällt weg oder wird zum Leerzeichen."""
    art = unicodedata.category(z)
    if art in ("Mn", "Me", "Cf"):
        return ""            # kombinierende und unsichtbare Zeichen: sie tarnen eine Kennung
    if not z.isprintable() or z == '"' or art in ("Pi", "Pf"):
        return " "           # Steuer- und Trennzeichen, Anführungszeichen jeder Art
    if art in ("Ps", "Pe") and not z.isascii():
        return " "           # „ ‚ und fremde Klammern; ( ) [ ] { } bleiben
    return z


def fuer_ki(wert: Any, zeichen: int = _TITEL_ZEICHEN) -> str:
    """Ein Titel oder Pfadteil aus dem Repository für einen Satz an die KI: eine Zeile, gedeckelt,
    ohne Steuer- und Trennzeichen (auch U+2028, U+0085), ohne Anführungszeichen jeder Art (sie
    würden die Fassung in „…“ brechen), ohne unsichtbare Zeichen und ohne etwas in der Form einer
    Kennung. Vorher NFKC: Vollbreite-Ziffern und ähnliche Doppelgänger werden zu dem, was sie
    darstellen. Klammern und Apostroph bleiben — „Deutsch als Zweitsprache (DaZ)“ soll so heißen.
    """
    text = unicodedata.normalize("NFKC", str(wert or ""))
    text = "".join(_zeichen(z) for z in text)
    text = _KENNUNG_IM_TEXT.sub("…", text)
    return " ".join(text.split())[:zeichen]


def _pfad(roh: Any) -> str:
    """Der Pfad, Fachportal zuerst. Bei mehr als sechs Teilen bleiben die zwei obersten und die
    drei nächsten Eltern — das Fach und die direkte Umgebung sagen, wo die Sammlung liegt."""
    if not isinstance(roh, list):
        return ""
    teile = [t for t in (fuer_ki(p, _PFAD_TEIL_ZEICHEN) for p in roh if isinstance(p, str)) if t]
    if len(teile) > _PFAD_TEILE:
        teile = [*teile[:2], "…", *teile[-3:]]
    return " › ".join(teile)


def gewaehlt(payload: Any) -> dict[str, str] | None:
    """Die Sammlung, die der Server zu einem Titel gewählt hat (``resolvedCollection``): Kennung,
    Titel und Pfad entschärft, dazu der Titel unverändert (``titel_roh``, für die Überschrift im
    Widget). ``None``, wenn mit einer Kennung oder einem Fach gerufen wurde."""
    roh = payload.get("resolvedCollection") if isinstance(payload, dict) else None
    if not isinstance(roh, dict) or not ist_kennung(roh.get("nodeId")):
        return None
    titel = roh.get("title")
    return {"titel": fuer_ki(titel), "titel_roh": titel if isinstance(titel, str) else "",
            "kennung": roh["nodeId"], "pfad": _pfad(roh.get("path")),
            "lose": "ja" if roh.get("matched") == "loose" else "",
            "fach_unerkannt": "ja" if isinstance(roh.get("unresolvedDiscipline"), dict) else ""}


def gewaehlt_satz(wahl: dict[str, str]) -> str:
    """Ein Satz über die gewählte Sammlung: Kennung zuerst, Titel und Pfad in „…“."""
    unter = f", sie liegt unter „{wahl['pfad']}“" if wahl["pfad"] else ""
    lose = (" Der Titel stimmt nur in abweichender Schreibweise überein."
            if wahl["lose"] else "")
    fach = (" Das genannte Fach wurde nicht erkannt und hat nichts eingegrenzt."
            if wahl.get("fach_unerkannt") else "")
    return (f"Gewählt wurde die Sammlung mit der nodeId {wahl['kennung']}: "
            f"„{wahl['titel']}“{unter}.{lose}{fach}")


class Ablehnung(NamedTuple):
    """Was der Server zu ``ambiguous_collection`` sagt — ohne seinen Wortlaut."""

    kandidaten: tuple[str, ...] = ()
    #: Die Sammlungssuche war unvollständig (ein Index antwortete nicht, das Suchfenster war voll).
    unvollstaendig: bool = False
    #: Das genannte Fach wurde nicht erkannt und hat nichts eingegrenzt.
    fach_unerkannt: bool = False


def ablehnung(fehlertext: str) -> Ablehnung:
    """Die Ablehnung zu einem Titel aus dem strukturierten Teil der Fehlerantwort — dem JSON
    direkt hinter dem Vorsatz ``MCP error [code]:``, nicht aus den gerenderten Zeilen des Servers:
    dort steht der Titel roh vor Pfad und Kennung.

    Höchstens fünf Kandidaten, nur mit echter Kennung, als eigene Zeilen: Kennung vorn, Titel und
    Pfad in „…“. Ohne strukturierten Teil (Werkzeuge ohne JSON-Ausgabe) eine leere Ablehnung —
    dann bleibt der KI die Suche.
    """
    from boerdi.services.mcp.parsers.json_scan import load_leading

    huelle = load_leading(_VORSATZ.sub("", fehlertext or "", count=1))
    fehler = huelle.get("error") if isinstance(huelle, dict) else None
    if not isinstance(fehler, dict):
        return Ablehnung()
    roh = fehler.get("candidates")
    zeilen: list[str] = []
    for k in roh if isinstance(roh, list) else []:
        if not isinstance(k, dict) or not ist_kennung(k.get("nodeId")):
            continue
        pfad = _pfad(k.get("path"))
        anzahl = k.get("contentsCount")
        gezaehlt = (isinstance(anzahl, int) and not isinstance(anzahl, bool)
                    and 0 <= anzahl < _HOECHSTENS_INHALTE)
        zeilen.append(
            f"- nodeId {k['nodeId']}: „{fuer_ki(k.get('title'))}“"
            + (f" unter „{pfad}“" if pfad else "")
            + (f" · {anzahl} Inhalte" if gezaehlt else "")
            + (" · Fach unbekannt" if k.get("disciplineUnknown") is True else ""))
        if len(zeilen) == _HOECHSTENS_KANDIDATEN:
            break
    return Ablehnung(tuple(zeilen), unvollstaendig=fehler.get("incomplete") is True,
                     fach_unerkannt=isinstance(fehler.get("unresolvedDiscipline"), dict))
