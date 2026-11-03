"""Blöcke, die aus der fertigen Antwort abgeleitet werden (Paket U1-c, Plan §12).

Entscheid des Nutzers: Treffer und Links kommen ZUSÄTZLICH als Blöcke — ``web_links`` (und
später ``cards``) bleiben, weil Host-Ereignisse, ``page_action``, Folgezug, Evals und alte
Widgets sie lesen. Abgeleitet wird an der API-Grenze (``api/publikum``): live aus der Antwort
nach ``widget_postprocess``, das Links noch ergänzt, und im Verlauf aus ``_web_links``.

Die Kennung eines abgeleiteten Blocks hängt nur an Modul und Daten — gleich also nur bei gleichen
Daten. Live und Verlauf unterscheiden sich, wenn ``widget_postprocess`` Links oder Karten nach dem
Speichern ändert, und bei der Trefferliste mit Seitenangabe (``seiten`` gibt es nur live). Eindeutig
ist die Kennung je Nachricht, nicht über alle Nachrichten.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any, Final

from boerdi.api.schemas_ui import UiBlock
from boerdi.domain.ui_bloecke import regeln_anwenden
from boerdi.ui_module import katalog, schalter
from boerdi.ui_module.namen import ABGELEITETE, LINKBOX, TREFFERLISTE

__all__ = ["ABGELEITETE", "LINKBOX", "TREFFERLISTE", "abgeleitete_bloecke", "erlaubte_module",
           "http_url", "md_link",
           "ergaenzt", "linkbox_block", "trefferliste_block", "webseiten_max"]

_HOECHSTENS_LINKS: Final = 30
_TITEL_ZEICHEN: Final = 300
_URL_ZEICHEN: Final = 2000
_HOECHSTENS_KARTEN: Final = 100
_HOECHSTENS_METAS: Final = 20


def _block_id(modul: str, daten: dict[str, Any]) -> str:
    roh = json.dumps([modul, daten], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()[:16]


def _feld(eintrag: Any, name: str) -> str:
    wert = eintrag.get(name) if isinstance(eintrag, dict) else getattr(eintrag, name, None)
    return wert.strip() if isinstance(wert, str) else ""


def http_url(url: str) -> str | None:
    """Nur http/https, Schema klein geschrieben (das Manifest prüft ``^https?://``)."""
    schema, trenner, rest = url.partition("://")
    if not trenner or schema.lower() not in ("http", "https") or len(url) > _URL_ZEICHEN:
        return None
    return f"{schema.lower()}://{rest}"


#: In der Adresse eines Markdown-Links: Leerzeichen und runde Klammern beendeten den Link.
_URL_MASKE: Final = str.maketrans({" ": "%20", "(": "%28", ")": "%29"})


def md_link(titel: str, url: str) -> str:
    """Ein Markdown-Link für eine Textfassung (Review U1 gesamt, Befund 7): eckige Klammern im
    Titel maskiert, die Adresse nur http/https — sonst bleibt der Titel als Text ohne Link."""
    text = (titel or "").replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
    sauber = http_url(url or "")
    return f"[{text}]({sauber.translate(_URL_MASKE)})" if sauber else text


def linkbox_block(web_links: Iterable[Any], hoechstens: int = _HOECHSTENS_LINKS) -> UiBlock | None:
    """Die Linkbox aus den Web-Links einer Antwort; ``None`` ohne brauchbaren Link.

    Nur http/https (die Links stammen aus Modelltext), ohne Doppelte, höchstens 30 — wie das
    Manifest es verlangt — und höchstens ``hoechstens`` (die Anzeige-Regel ``webseiten_max``).
    Ein Link ohne Beschriftung bleibt; das Widget beschriftet ihn („Webseite“).
    """
    hoechstens = max(1, min(hoechstens, _HOECHSTENS_LINKS))
    links: list[dict[str, str]] = []
    gesehen: set[str] = set()
    for eintrag in web_links or ():
        url = http_url(_feld(eintrag, "url"))
        if url is None or url in gesehen:
            continue
        gesehen.add(url)
        links.append({"titel": _feld(eintrag, "title")[:_TITEL_ZEICHEN], "url": url})
        if len(links) == hoechstens:
            break
    if not links:
        return None
    daten = {"links": links}
    text = "\n".join(f"- {md_link(link['titel'] or link['url'], link['url'])}" for link in links)
    return UiBlock(block_id=_block_id(LINKBOX, daten), modul=LINKBOX,
                   version=katalog.katalog()[LINKBOX]["version"], art="anzeigen",
                   daten=daten, text=text)


def _als_dict(eintrag: Any) -> dict[str, Any] | None:
    if hasattr(eintrag, "model_dump"):
        return eintrag.model_dump(mode="json")
    return dict(eintrag) if isinstance(eintrag, dict) else None


def trefferliste_block(karten: Iterable[Any], such_metas: Iterable[Any], seiten: Any,
                       typ_fokus: str) -> UiBlock | None:
    """Die Trefferliste aus den fertigen Karten, den Such-Angaben und der Seitenangabe; ``None``
    ohne Karten und ohne Such-Angaben. Bei Typ-Fokus übernimmt sie, was ankommt: ``turn_links``
    streicht dort Sammlungen und Themenseiten, Einzelinhalte bleiben — wie bisher in der
    Materialien-Box samt „Inhalt anzeigen“ (Web-Links unterdrückt das Widget über ``typ_fokus``)."""
    karten_liste = [
        k for k in (_als_dict(e) for e in karten or ()) if k and isinstance(k.get("node_id"), str)
    ][:_HOECHSTENS_KARTEN]
    metas = [m for m in (_als_dict(e) for e in such_metas or ()) if m][:_HOECHSTENS_METAS]
    if not karten_liste and not metas:
        return None
    daten = {"karten": karten_liste, "such_metas": metas,
             "seiten": _als_dict(seiten) if seiten is not None else None,
             "typ_fokus": typ_fokus or ""}
    zeilen = [f"- {md_link(_feld(k, 'title') or k['node_id'],
                           _feld(k, 'url') or _feld(k, 'wlo_url'))}" for k in karten_liste]
    text = "\n".join(zeilen) or "\n".join(
        f"- {md_link(_feld(m, 'search_term') or 'WLO-Suche', _feld(m, 'search_url'))}"
        for m in metas)
    return UiBlock(block_id=_block_id(TREFFERLISTE, daten), modul=TREFFERLISTE,
                   version=katalog.katalog()[TREFFERLISTE]["version"], art="anzeigen",
                   daten=daten, text=text)


def webseiten_max() -> int:
    """``display_rules.groups.webseiten_max`` (1–30, Vorgabe 3) — dieselbe Grenze wie die bisherige
    Box im Widget (``_groupLimit``), live und im Verlauf aus derselben Einstellung."""
    from boerdi.services.config_loader import load_display_rules_config

    wert = ((load_display_rules_config() or {}).get("groups") or {}).get("webseiten_max")
    return wert if isinstance(wert, int) and 1 <= wert <= _HOECHSTENS_LINKS else 3


def muster_zuordnung() -> dict[str, frozenset[str] | None]:
    """Kennung → erlaubte abgeleitete Module für alle Muster, einmal gelesen — für den Verlauf, der
    sonst je Nachricht alle Muster-Definitionen neu aufbauen ließe."""
    from boerdi.services.config_loader import load_pattern_definitions

    zuordnung: dict[str, frozenset[str] | None] = {}
    for definition in load_pattern_definitions():
        if isinstance(definition, dict) and isinstance(definition.get("id"), str):
            wert = definition.get("ui_module")
            zuordnung[definition["id"]] = (frozenset(n for n in wert if isinstance(n, str))
                                           if isinstance(wert, list) else None)
    return zuordnung


Muster = Mapping[str, frozenset[str] | None]


def erlaubte_module(pattern: str, muster: Muster | None = None) -> frozenset[str] | None:
    """Die abgeleiteten Module, die das Muster zeigt (``ui_module:``); ``None`` = alle.

    ``pattern`` kommt aus dem Debug-Block als ``"M05 (Suche)"`` — gemeint ist die Kennung davor
    (wie in ``quick_reply_policy``). Kein Muster (Agent, Aktion), ein Muster ohne den Schlüssel
    und Bestand, der nicht als Liste vorliegt (alte Sicherung am Validator vorbei): alle, also
    das heutige Verhalten — eine Antwort bricht daran nie.
    """
    kennung = (pattern or "").split(" ")[0].strip()
    if not kennung:
        return None
    return (muster if muster is not None else muster_zuordnung()).get(kennung)


def abgeleitete_bloecke(*, web_links: Iterable[Any], erlaubt: frozenset[str] | None,
                        hoechstens_links: int = _HOECHSTENS_LINKS, cards: Iterable[Any] = (),
                        query_metas: Iterable[Any] = (), pagination: Any = None,
                        type_focus: str = "") -> list[UiBlock]:
    """Die abgeleiteten Blöcke einer Antwort in Anzeige-Reihenfolge; ``erlaubt=None`` heißt alle
    (kein ``ui_module:``). Bei Typ-Fokus keine Linkbox — die bisherige Box schwieg dort."""
    bloecke: list[UiBlock] = []
    if erlaubt is None or TREFFERLISTE in erlaubt:
        if block := trefferliste_block(cards, query_metas, pagination, type_focus):
            bloecke.append(block)
    if not type_focus and (erlaubt is None or LINKBOX in erlaubt):
        if block := linkbox_block(web_links, hoechstens_links):
            bloecke.append(block)
    return bloecke


def _nur_aktive(erlaubt: frozenset[str] | None) -> frozenset[str] | None:
    """Paket U1-f: was das Muster erlaubt (``None`` = alle), ohne die im Studio abgeschalteten —
    live und im Verlauf nach der aktuellen Einstellung, wie ``ui_module:`` des Musters. Fehlt ein
    Block, zeigt das Widget die bisherigen Boxen aus ``cards``/``web_links``."""
    aktive = frozenset(n for n in ABGELEITETE if schalter.aktiv(n))
    if erlaubt is None and len(aktive) == len(ABGELEITETE):
        return None
    return aktive if erlaubt is None else erlaubt & aktive


def ergaenzt(gelieferte: list[UiBlock], *, pattern: str, web_links: Iterable[Any],
             type_focus: str = "", cards: Iterable[Any] = (), query_metas: Iterable[Any] = (),
             pagination: Any = None,
             muster: Mapping[str, frozenset[str] | None] | None = None) -> list[UiBlock]:
    """Gelieferte Blöcke plus die abgeleiteten — danach, nach den Regeln je Antwort.

    Nichts abgeleitet wird für Führungs-Nachrichten (``TOUR:…``) — sie zeigten auch bisher keine
    Boxen — und ohne Links, Karten und Such-Angaben. Erst danach werden Muster, Anzeige-Regeln und
    die Studio-Schalter (U1-f) gelesen: der Verlauf fragt je Nachricht.
    Ein schon vorhandener Block derselben Kennung wird nicht verdoppelt. Die Regeln gelten auch,
    wenn nichts abgeleitet wird (Review U1 gesamt, Befund 6): nicht jeder Weg zu ``ui`` wendet
    sie vorher an (Direktaktionen), und sie zweimal anzuwenden ändert nichts.
    """
    links, karten, metas = list(web_links or ()), list(cards or ()), list(query_metas or ())
    if (pattern or "").startswith("TOUR:") or not (links or karten or metas):
        return regeln_anwenden(gelieferte)
    vorhanden = {b.block_id for b in gelieferte}
    neu = [b for b in abgeleitete_bloecke(
               web_links=links, erlaubt=_nur_aktive(erlaubte_module(pattern, muster)),
               hoechstens_links=webseiten_max() if links and not type_focus else 1,
               cards=karten, query_metas=metas, pagination=pagination, type_focus=type_focus)
           if b.block_id not in vorhanden]
    return regeln_anwenden([*gelieferte, *neu])
