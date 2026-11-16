"""Plan 2026-11-16, TG-4 (G-E9): lose Dateien ohne WLO — aus den Dateinamen ein Teil ``metadaten``.

Der Weg „aus eigenen Inhalten“ baut den Themenbaum aus Titeln und Beschreibungen der Materialien
(``ui_strukturentwurf`` mit ``aus_inhalten``, gelesen über ``metadaten.als_dokument``). Mit WLO
liefern sie der Kestra-Flow und ``metadaten_lesen``; ohne Anmeldung, ohne Ablage oder auf Wunsch
schnell gibt es nur die Namen aus dem Upload-Feld (Teil ``struktur``, ``wlo.auswahl@1``). Dieser
Dienst macht daraus dasselbe Format ``wlo.metadaten@1`` — ohne Sprachmodell, ohne Netz:

- **nur Dateien mit Rolle ``inhalt``** (ein Strukturdokument ist kein Material, ignorierte tragen
  keinen Namen, R3-4);
- **Titel aus dem Dateinamen:** ohne Endung, ``_`` und ``-`` werden Leerzeichen, an der Wortgrenze
  auf :data:`TITEL_ZEICHEN` gekürzt; ein leerer Rest wird „Datei n“;
- **der Ordnerpfad als Beschreibung** („Ordner: Physik 7 / Mechanik“) — für den Generator Herkunft,
  kein Punkt (G-E10, die Vorgaben am KI-Schritt sagen das);
- je Eintrag die feste Nummer ``i`` der Auswahl, **kein** ``node_id`` (es gibt noch keinen Knoten);
  die ``block_id`` der Auswahl reist mit (Review TG-3a–c, R3-2: ``i`` gilt nur für sie).

Der ganze Teil bleibt unter ``metadaten.MAX_TEIL`` (wie ``metadaten_lesen``): zuerst werden die
Pfade kurz, dann weggelassen, dann die Titel kurz; was dann noch nicht passt, fällt vom Ende weg
und steht als Zahl in ``ausgelassen`` (``fehlend`` trägt nach dem Format nodeIds — hier keine).

Die Namen gehen erst im Strukturentwurf an ein Modell; dort prüft die Moderation Übersicht und
Anfang vor Ebene 1 (``ui_module/dienst._ebene_eins_pruefen``), wie bei Metadaten aus WLO.
"""

from __future__ import annotations

import json
import re
from typing import Any, Final

from boerdi.services.ablauf import metadaten

#: Titel aus einem Dateinamen — kurz wie ein Materialtitel, nicht wie ein ganzer Dateipfad.
TITEL_ZEICHEN: Final = 80
#: Der Ordnerpfad als Beschreibung (vom Ende her, die nächsten Ordner zählen am meisten).
PFAD_ZEICHEN: Final = 120
_TRENNER: Final = " / "
#: Eine Endung: bis zu fünf Buchstaben oder Ziffern hinter dem letzten Punkt.
_ENDUNG: Final = re.compile(r"\.[A-Za-z0-9]{1,5}$")
_UNTERSTRICHE: Final = re.compile(r"[_\-]+")


def titel(name: str, endung: str = "") -> str:
    """Ein lesbarer Titel aus dem Dateinamen — ohne Endung, ``_``/``-`` als Leerzeichen, gekürzt.

    ``endung`` (aus ``dateiliste``) geht vor; sonst gilt ein kurzer Rest hinter dem letzten Punkt
    als Endung („Kapitel 1.2 Optik“ behält seinen Punkt, „Linsen.pdf“ verliert „.pdf“)."""
    roh = " ".join(str(name or "").split())
    if endung and roh.casefold().endswith("." + endung.casefold()):
        roh = roh[:-(len(endung) + 1)]
    else:
        roh = _ENDUNG.sub("", roh)
    text = " ".join(_UNTERSTRICHE.sub(" ", roh).split())
    return _gekuerzt(text, TITEL_ZEICHEN)


def _gekuerzt(text: str, hoechstens: int) -> str:
    """An der Wortgrenze kürzen, mit „…“ — ein halbes Wort führte den Generator irre."""
    if len(text) <= hoechstens:
        return text
    stueck = text[:hoechstens - 1]
    if " " in stueck:
        stueck = stueck.rsplit(" ", 1)[0]
    return stueck.rstrip(" ,;:.") + "…"


def _pfad(teile: list[str], hoechstens: int) -> str:
    """„Ordner: a / b / c“ — vom Ende her gekürzt, damit der nächste Ordner bleibt."""
    if not teile:
        return ""
    pfad = _TRENNER.join(teile)
    if len(pfad) > hoechstens:
        pfad = "…" + pfad[-(hoechstens - 1):]
    return f"Ordner: {pfad}"


def _dateien(ordner: Any, pfad: list[str]) -> list[tuple[dict[str, Any], list[str]]]:
    """Alle Dateien mit Rolle ``inhalt`` samt Ordnerpfad, von oben nach unten (wie
    ``upload_antwort.dateien``)."""
    if not isinstance(ordner, dict):
        return []
    name = " ".join(str(ordner.get("name") or "").split())
    hier = [*pfad, name[:60]] if name else list(pfad)
    eigene = [(d, hier) for d in ordner.get("dateiliste") or []
              if isinstance(d, dict) and d.get("rolle") == "inhalt"
              and isinstance(d.get("name"), str)]
    return eigene + [x for k in ordner.get("kinder") or [] for x in _dateien(k, hier)]


def _nummer(d: dict[str, Any]) -> int | None:
    i = d.get("i")
    return i if isinstance(i, int) and not isinstance(i, bool) and i >= 0 else None


def _groesse(wert: Any) -> int:
    return len(json.dumps(wert, ensure_ascii=False).encode("utf-8"))


#: Review TG-4–6, NIT 18: der Titel des Teils je Sprache (Leiste, „Gesammelte Daten“).
_TITEL: Final = {"de": "Inhalte aus {n} Dateinamen", "en": "Content from {n} file names"}


def _teil(inhalte: list[dict[str, Any]], ausgelassen: int, block_id: Any,
          sprache: str = "de") -> dict[str, Any]:
    titel = _TITEL.get(sprache, _TITEL["de"]).format(n=len(inhalte))
    teil: dict[str, Any] = {"format": metadaten.FORMAT, "titel": titel,
                            "quelle": "dateinamen", "inhalte": inhalte, "fehlend": []}
    if ausgelassen:
        teil["ausgelassen"] = ausgelassen
    if isinstance(block_id, str) and block_id:
        teil["block_id"] = block_id
    return teil


def _einpassen(roh: list[tuple[dict[str, Any], list[str]]], block_id: Any,
               sprache: str = "de") -> dict[str, Any]:
    """Wie ``metadaten._einpassen``: erst die Pfade kürzen, dann weglassen, dann die Titel — zuletzt
    Einträge vom Ende (als Zahl in ``ausgelassen``)."""
    stufen: list[tuple[int | None, int]] = [(PFAD_ZEICHEN, TITEL_ZEICHEN), (40, TITEL_ZEICHEN),
                                            (None, TITEL_ZEICHEN), (None, 40)]
    for n, (pfad_max, titel_max) in enumerate(stufen):
        inhalte = []
        for d, pfad in roh:
            eintrag: dict[str, Any] = {"i": _nummer(d), "rolle": "inhalt",
                                       "titel": _gekuerzt(titel(d["name"], str(
                                           d.get("endung") or "")), titel_max)
                                       or f"Datei {(_nummer(d) or 0) + 1}"}
            if pfad_max is not None and (beschreibung := _pfad(pfad, pfad_max)):
                eintrag["beschreibung"] = beschreibung
            inhalte.append(eintrag)
        teil = _teil(inhalte, 0, block_id, sprache)
        if _groesse(teil) <= metadaten.MAX_TEIL or n == len(stufen) - 1:
            break
    behalten = len(inhalte)
    while behalten and _groesse(_teil(inhalte[:behalten], len(inhalte) - behalten,
                                      block_id, sprache)) > metadaten.MAX_TEIL:
        # je Schritt ein Zehntel weniger — 500 Einträge brauchen so keine 500 Messungen
        behalten -= max(1, behalten // 10)
    return _teil(inhalte[:behalten], len(inhalte) - behalten, block_id, sprache)


def aus_struktur(teil: Any, sprache: str = "de") -> dict[str, Any] | None:
    """Der Teil ``wlo.metadaten@1`` aus dem Teil ``struktur`` (``wlo.auswahl@1``) — ``None`` ohne
    Datei mit Rolle ``inhalt`` (dann ``bei_fehler`` am Schritt) oder bei einem Teil anderer Form.
    Der Teil ``structure`` (nur Ordner, ohne Dateien) trägt keine Namen — auch dann ``None``."""
    if not isinstance(teil, dict) or not isinstance(teil.get("struktur"), dict):
        return None
    roh = _dateien(teil["struktur"], [])
    if not roh:
        return None
    return _einpassen(roh, teil.get("block_id"), sprache)
