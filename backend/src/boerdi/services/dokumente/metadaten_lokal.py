"""Teil ``metadaten`` aus „Hier im Chat“ (Plan 2026-11-17, Paket U3, E8/E11).

Liest das Upload-Feld Inhalte hier im Chat (``ort: chat``), entsteht derselbe Teil wie nach dem
Kestra-Flow (``metadaten_lesen``): Format ``wlo.metadaten@1``, gelesen von
``metadaten.als_dokument``
und damit von ``ui_strukturentwurf`` mit ``aus_inhalten`` — mit ``quelle: chatbot``.

- **nur Dateien mit Rolle ``inhalt``** aus der Auswahl (``dateiliste``; Strukturdokumente stehen im
  Teil ``strukturdokument``; P1, Plan 2026-11-20: ``beides`` steht in beiden), je Eintrag die feste
  Nummer ``i``, kein ``node_id``;
- **gelesen** (``upload_id`` einer lesbaren Zeile dieser Sitzung mit Rolle ``inhalt`` oder
  ``beides``): Titel,
  Beschreibung, Schlagworte, Fach (``faecher``) und Stufe (``stufen``) aus den Kurzangaben, die der
  Server beim Hochladen speicherte (``inhalt_angaben``); ohne Angaben der Titel aus dem Namen;
  ``lesbar: true`` und die ``upload_id`` (``dokument_lesen`` liest den Text);
- **nicht lesbar** (Format, oder die Kennung passt nicht): Titel aus dem Namen, der Ordnerpfad als
  Beschreibung — wie ``inhalte_aus_dateien`` (der Weg nur mit Namen bleibt dort) — und
  ``lesbar: false``.

Zweistufig wie die übrigen Teile aus Antworten: :func:`aus_antwort` (rein, aus der Antwort des
Browsers — die Simulation nutzt ihn so) legt den Platzhalter mit den Verweisen an;
:func:`neu_berechnet` rechnet ihn beim Speichern aus den Zeilen der Datenbank neu
(``arbeitsstand._speichern``) — was der Browser an Titeln oder Beschreibungen schickte, gilt nie.
Der Teil bleibt unter ``metadaten.MAX_TEIL``.
"""

from __future__ import annotations

import json
from typing import Any, Final

from boerdi.services.ablauf import metadaten
from boerdi.services.ablauf.inhalte_aus_dateien import (
    PFAD_ZEICHEN,
    dateien_mit_pfad,
    gekuerzt,
    nummer,
    ordnerpfad,
    titel,
)
from boerdi.ui_module.rollen import als_material, ist_material

QUELLE: Final = "chatbot"
_TITEL: Final = {"de": "Inhalte aus {n} Dateien ({k} gelesen)",
                 "en": "Content from {n} files ({k} read)"}
_MAX_LISTE: Final = 5


def ist_lokal(wert: Any) -> bool:
    return (isinstance(wert, dict) and wert.get("format") == metadaten.FORMAT
            and wert.get("quelle") == QUELLE)


def _groesse(wert: Any) -> int:
    return len(json.dumps(wert, ensure_ascii=False).encode("utf-8"))


def _teil(inhalte: list[dict[str, Any]], ausgelassen: int, block_id: Any,
          sprache: str = "de") -> dict[str, Any]:
    gelesen = sum(1 for e in inhalte if e.get("lesbar"))
    teil: dict[str, Any] = {
        "format": metadaten.FORMAT, "quelle": QUELLE,
        "titel": _TITEL.get(sprache, _TITEL["de"]).format(n=len(inhalte), k=gelesen),
        "inhalte": inhalte, "fehlend": []}
    if ausgelassen:
        teil["ausgelassen"] = ausgelassen
    if isinstance(block_id, str) and block_id:
        # wie ``metadaten``: ``i`` gilt nur für die Auswahl desselben Felds
        teil["block_id"] = block_id
    return teil


def _nach_namen(d: dict[str, Any], pfad: list[str]) -> dict[str, Any]:
    eintrag: dict[str, Any] = {"i": nummer(d), "rolle": als_material(d.get("rolle")),
                               "titel": titel(d["name"], str(d.get("endung") or ""))
                               or f"Datei {(nummer(d) or 0) + 1}", "lesbar": False}
    if beschreibung := ordnerpfad(pfad, PFAD_ZEICHEN):
        eintrag["beschreibung"] = beschreibung
    return eintrag


def _einpassen(inhalte: list[dict[str, Any]], block_id: Any,
               sprache: str = "de") -> dict[str, Any]:
    """Erst die Pfade der nicht lesbaren weg, dann die Beschreibungen kürzen, zuletzt Einträge vom
    Ende (als Zahl in ``ausgelassen``) — die gelesenen stehen vorn und bleiben am längsten."""
    stufen = [lambda e: e,
              lambda e: e if e.get("lesbar") else {k: v for k, v in e.items()
                                                   if k != "beschreibung"},
              lambda e: {**e, "beschreibung": gekuerzt(str(e.get("beschreibung") or ""), 100)}
              if e.get("beschreibung") else e]
    for stufe in stufen:
        inhalte = [stufe(e) for e in inhalte]
        if _groesse(_teil(inhalte, 0, block_id, sprache)) <= metadaten.MAX_TEIL:
            return _teil(inhalte, 0, block_id, sprache)
    behalten = len(inhalte)
    while behalten and _groesse(_teil(inhalte[:behalten], len(inhalte) - behalten, block_id,
                                      sprache)) > metadaten.MAX_TEIL:
        behalten -= max(1, behalten // 10)
    return _teil(inhalte[:behalten], len(inhalte) - behalten, block_id, sprache)


def aus_antwort(daten: dict[str, Any], block_id: Any, sprache: str = "de"
                ) -> dict[str, Any] | None:
    """Der Platzhalter aus einer Antwort ``ort: chat`` — Titel aus den Namen, die gelesenen mit
    ``upload_id`` (ungeprüft; :func:`neu_berechnet` gilt). ``None`` ohne Inhalt."""
    gelesen = {d.get("i"): d["upload_id"] for d in daten.get("dateien") or []
               if isinstance(d, dict) and ist_material(d.get("rolle"))
               and isinstance(d.get("upload_id"), str)}
    roh = dateien_mit_pfad(daten.get("struktur"), [])
    if not roh:
        return None
    inhalte = []
    for d, pfad in roh:
        eintrag = _nach_namen(d, pfad)
        if (kennung := gelesen.get(nummer(d))) is not None:
            eintrag = {k: v for k, v in eintrag.items() if k != "beschreibung"}
            eintrag.update(lesbar=True, upload_id=kennung)
        inhalte.append(eintrag)
    # die gelesenen zuerst: sie tragen die Angaben und bleiben beim Einpassen am längsten
    inhalte.sort(key=lambda e: not e["lesbar"])
    return _einpassen(inhalte, block_id, sprache)


def _texte(wert: Any) -> list[str]:
    return [w for w in wert if isinstance(w, str) and w][:metadaten.MAX_SCHLAGWORTE] \
        if isinstance(wert, list) else []


def _aus_angaben(eintrag: dict[str, Any], angaben: dict[str, Any] | None) -> dict[str, Any]:
    neu = {k: eintrag[k] for k in ("i", "titel", "upload_id") if k in eintrag}
    neu["rolle"] = als_material(eintrag.get("rolle"))
    neu["lesbar"] = True
    if angaben:
        neu["titel"] = " ".join(str(angaben.get("titel") or "").split())[:200] or neu["titel"]
        if beschreibung := " ".join(str(angaben.get("beschreibung") or "").split()):
            neu["beschreibung"] = beschreibung[:metadaten.MAX_BESCHREIBUNG + 100]
        if schlagworte := _texte(angaben.get("schlagworte")):
            neu["schlagworte"] = schlagworte
        if isinstance(fach := angaben.get("fach"), str) and fach:
            neu["faecher"] = [fach][:_MAX_LISTE]
        if isinstance(stufe := angaben.get("stufe"), str) and stufe:
            neu["stufen"] = [stufe][:_MAX_LISTE]
    return neu


def _sprache(wert: dict[str, Any]) -> str:
    """Die Sprache des Teils, gelesen an seinem Titel (der Platzhalter trägt sie aus
    :func:`aus_antwort`) — Review U, NIT 8: Neuberechnen und Aufräumen behalten sie."""
    kopf = _TITEL["en"].split("{", 1)[0]
    return "en" if str(wert.get("titel") or "").startswith(kopf) else "de"


def zusammenfassung(teil: dict[str, Any]) -> str:
    """Die Kurzbeschreibung des Teils im Vorgang."""
    gelesen = sum(1 for e in teil["inhalte"] if e.get("lesbar"))
    return f"{len(teil['inhalte'])} Inhalte, {gelesen} gelesen"


def neu_berechnet(wert: dict[str, Any], zeilen: list[Any], sprache: str | None = None
                  ) -> tuple[dict[str, Any], str]:
    """Der Teil des Servers: je Eintrag mit ``upload_id`` die Kurzangaben aus ``zeilen`` (die
    lesbaren Dokumente dieser Sitzung bzw. Person, beide Rollen) — nur, wenn die Zeile ein Inhalt
    ist; sonst gilt der Eintrag als nicht gelesen. ``sprache`` ohne Angabe die des Platzhalters.
    Zurück: Wert und Kurzbeschreibung."""
    from boerdi.services.dokumente import ablage

    inhalte_db = {z.id: z for z in zeilen if ist_material(ablage.rolle(z))}
    inhalte = []
    for e in wert.get("inhalte") or []:
        if not isinstance(e, dict):
            continue
        basis = {k: e[k] for k in ("i", "rolle", "titel", "beschreibung") if k in e}
        basis["titel"] = " ".join(str(basis.get("titel") or "").split())[:200] or "Datei"
        zeile_db = inhalte_db.get(e.get("upload_id")) if e.get("lesbar") else None
        if zeile_db is not None:
            inhalte.append(_aus_angaben({**basis, "upload_id": zeile_db.id},
                                        ablage.angaben(zeile_db)))
        else:
            # nicht gelesen: nur Name und Ordnerpfad — eine Beschreibung des Browsers ist der Pfad
            # (aus ``aus_antwort``), gekürzt wie dort
            basis["beschreibung"] = gekuerzt(str(basis.get("beschreibung") or ""), PFAD_ZEICHEN)
            if not basis["beschreibung"]:
                basis.pop("beschreibung")
            inhalte.append({**basis, "rolle": als_material(basis.get("rolle")), "lesbar": False})
    neu = _einpassen(inhalte, wert.get("block_id"), sprache or _sprache(wert))
    if ausgelassen := int(wert.get("ausgelassen") or 0):
        neu["ausgelassen"] = int(neu.get("ausgelassen") or 0) + ausgelassen
    return neu, zusammenfassung(neu)


def upload_ids(wert: Any) -> set[str]:
    """Die Kennungen gelesener Inhalte, auf die ein Teil ``metadaten`` verweist."""
    eintraege = wert.get("inhalte") if isinstance(wert, dict) else None
    return {e["upload_id"] for e in eintraege or []
            if isinstance(e, dict) and isinstance(e.get("upload_id"), str)}


def _nur_namen(wert: dict[str, Any], struktur: Any) -> dict[Any, dict[str, Any]]:
    """Je Nummer ``i`` der Eintrag „nur Name“ aus der Auswahl — nur, wenn sie zum Teil gehört
    (dasselbe Upload-Feld, ``block_id``); sonst keiner."""
    if (not isinstance(struktur, dict) or not wert.get("block_id")
            or struktur.get("block_id") != wert.get("block_id")):
        return {}
    return {nummer(d): _nach_namen(d, pfad)
            for d, pfad in dateien_mit_pfad(struktur.get("struktur"), [])}


def ohne_uploads(wert: Any, weg: set[str], struktur: Any = None) -> dict[str, Any] | None:
    """Review Paket U (19.11.), MAJOR 2 (Datenschutz): ist ein hier im Chat gelesener Inhalt weg
    (gelöscht, ersetzt, abgelaufen), fällt sein Eintrag auf „nur Name“ zurück — ``lesbar: false``,
    ohne die Kurzangaben des LLM und ohne ``upload_id``; Titel und Ordnerpfad aus der Auswahl
    (Teil ``struktur`` desselben Felds), sonst „Datei n“. ``None``, wenn kein Eintrag betroffen
    ist. Rein — das Speichern übernimmt ``vorgaenge``."""
    if not isinstance(wert, dict) or not (upload_ids(wert) & weg):
        return None
    namen = _nur_namen(wert, struktur)
    inhalte = []
    for e in wert.get("inhalte") or []:
        if isinstance(e, dict) and e.get("upload_id") in weg:
            i = nummer(e)
            e = namen.get(i) or {"i": i, "rolle": "inhalt",
                                 "titel": f"Datei {(i or 0) + 1}", "lesbar": False}
        inhalte.append(e)
    neu = _einpassen(inhalte, wert.get("block_id"), _sprache(wert))
    if ausgelassen := int(wert.get("ausgelassen") or 0):
        neu["ausgelassen"] = int(neu.get("ausgelassen") or 0) + ausgelassen
    return neu

