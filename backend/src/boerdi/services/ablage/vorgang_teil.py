"""Der Teil ``ablage`` im Vorgang (Paket U3-3a) — was in WLO abgelegt wurde.

Format ``wlo.ablage@1``: Ordner, Layout, je Eintrag Index, Titel, Art, Größe, Name, Stand
(``offen`` | ``stored`` | ``dropped`` | ``unverified`` | ``failed``), nodeId und Rolle (``inhalt`` |
``struktur``, W4; ``rolle_bestaetigt``: stand sie in der Vorschau des Servers) und — Plan
2026-11-16, TG-3b — ``i``, die feste Nummer der Datei in der Auswahl (Teil ``struktur``). ``index``
bleibt die Stelle in der Freigabe (so zählt das MCP, ``wlo_store_batch_file``); ``i`` verknüpft
Ordner und Knoten und fehlt bei einem Widget vor TG-3b. Dazu das
Prüf-Kürzel des Freigabe-Schlüssels (``token_kuerzel``, nie der Schlüssel selbst — der bleibt im
Widget), der Block, der ihn vorbereitet hat, wann, und ob der Stapel abgeschlossen ist. Die KI sieht
nur den Kurztext (:func:`zusammenfassung`): Zahlen, keine Titel, keine nodeIds.

Querschnitts-Review 2026-11-06:
- ``layout`` im Wortschatz des Moduls (``ordner``/``flach``), nicht dem des MCP
  (``folder``/``flat``).
- ``ohne_antwort`` markiert ein „unklar“, das das Backend selbst setzte (keine Antwort vom MCP) —
  es ist nicht endgültig; ein vom MCP gemeldetes ``unverified`` schon.
- ``frueher``: abgelegte Einträge eines nicht abgeschlossenen Stapels, den ein neuer ersetzt hat —
  ihre nodeIds gehen so nicht verloren.
"""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from boerdi.services import arbeitsstand

TEIL: Final = "ablage"
TYP: Final = "wlo.ablage@1"
#: So lange gilt eine Freigabe beim MCP (``BATCH_TTL_MS``) — so lange hält ein offener Stapel.
FREIGABE: Final = timedelta(minutes=30)
_FRUEHER_MAX: Final = 200


def layout(roh: Any) -> str:
    return "ordner" if roh in ("folder", "ordner") else "flach"


def kuerzel(batch_token: str) -> str:
    return hashlib.sha256(batch_token.encode()).hexdigest()[:16]


def _rolle(eintrag: dict[str, Any], erbeten: str | None) -> tuple[str, bool]:
    """W4: die Rolle aus der Vorschau des Servers (sie ist die Freigabe) — bestätigt; gibt ein
    Server vor W4 keine zurück, die erbetene, sonst ``inhalt`` — unbestätigt (Review W4, Befund 5:
    dann steht sie weder im Fingerabdruck noch im Manifest; ein späterer Schritt prüft das)."""
    if eintrag.get("role") in ("structure", "content"):
        return ("struktur" if eintrag["role"] == "structure" else "inhalt"), True
    return (erbeten if erbeten in ("struktur", "inhalt") else "inhalt"), False


def _rolle_felder(e: dict[str, Any], erbeten: list[str]) -> dict[str, Any]:
    i = int(e["index"])
    rolle, bestaetigt = _rolle(e, erbeten[i] if 0 <= i < len(erbeten) else None)
    return {"rolle": rolle, "rolle_bestaetigt": bestaetigt}


def _nummer(e: dict[str, Any], nummern: list[int | None]) -> dict[str, Any]:
    """TG-3b: ``{"i": n}`` für den Eintrag an Stelle ``index`` — leer ohne Nummer."""
    i = int(e["index"])
    n = nummern[i] if 0 <= i < len(nummern) else None
    return {"i": n} if isinstance(n, int) and not isinstance(n, bool) else {}


def aus_plan(plan: dict[str, Any], batch_token: str, block_id: str,
             vorher: dict[str, Any] | None = None, *,
             rollen: list[str] | None = None,
             nummern: list[int | None] | None = None) -> dict[str, Any]:
    """Der Teil aus der Vorschau des MCP-Servers (normalisierter Plan); ``vorher`` ist der Teil,
    den er ersetzt (dessen abgelegte Einträge bleiben als ``frueher``); ``rollen`` die erbetenen
    Rollen je Index (W4) — so weiß ein späterer Schritt, welcher Knoten das Strukturdokument ist;
    ``nummern`` die feste Nummer ``i`` der Auswahl je Index (TG-3b)."""
    erbeten = list(rollen or [])
    feste = list(nummern or [])
    teil: dict[str, Any] = {
        "format": TYP, "ordner": str(plan.get("folderName") or ""),
        "layout": layout(plan.get("layout")), "token_kuerzel": kuerzel(batch_token),
        "block_id": block_id, "erstellt": datetime.now(UTC).isoformat(), "abgeschlossen": False,
        "inhalte": [{"index": int(e["index"]), "titel": str(e.get("title") or ""),
                     "art": str(e.get("ext") or ""), "groesse": int(e.get("size") or 0),
                     "name": str(e.get("fileName") or ""), "stand": "offen",
                     **_rolle_felder(e, erbeten), **_nummer(e, feste)}
                    for e in plan.get("entries") or [] if isinstance(e, dict)],
    }
    if frueher := _frueher(vorher):
        teil["frueher"] = frueher
    return teil


def _frueher(vorher: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Was ein ersetzter Stapel hinterlässt: sein geerbtes ``frueher`` immer (Review Q1, Befund 7),
    seine eigenen abgelegten Einträge nur, wenn er nicht abgeschlossen ist (sonst stehen sie in
    seinem ``vorgang.json``)."""
    if not vorher:
        return []
    alt = [e for e in vorher.get("frueher") or [] if isinstance(e, dict)]
    neu = [] if vorher.get("abgeschlossen") else [
        {"titel": e.get("titel", ""), "node_id": e["node_id"], "rolle": e.get("rolle", "inhalt")}
        for e in vorher.get("inhalte") or []
        if e.get("stand") == "stored" and isinstance(e.get("node_id"), str)]
    return (alt + neu)[-_FRUEHER_MAX:]


def mit_frueher(wert: dict[str, Any], eintrag: dict[str, Any],
                ergebnis: dict[str, Any]) -> dict[str, Any] | None:
    """Ein Ergebnis eines inzwischen ersetzten Stapels: ein Abgelegtes kommt nach ``frueher``, sonst
    wird nichts geschrieben (``None``)."""
    if str(ergebnis.get("status")) != "stored" or not isinstance(ergebnis.get("nodeId"), str):
        return None
    neu = copy.deepcopy(wert)
    neu["frueher"] = ([*neu.get("frueher", []),
                       {"titel": str(eintrag.get("titel") or ""), "node_id": ergebnis["nodeId"],
                        "rolle": str(eintrag.get("rolle") or "inhalt")}]
                      )[-_FRUEHER_MAX:]
    return neu


def haelt_noch(teil: dict[str, Any] | None, jetzt: datetime | None = None) -> bool:
    """Ein nicht abgeschlossener Stapel mit abgelegten Einträgen, dessen Freigabe noch gilt — ihn
    ersetzt kein neuer (zweiter Tab, Review Querschnitt)."""
    if not teil or teil.get("abgeschlossen"):
        return False
    if not any(e.get("stand") == "stored" for e in teil.get("inhalte") or []):
        return False
    try:
        erstellt = datetime.fromisoformat(str(teil.get("erstellt")))
    except ValueError:
        return False
    if erstellt.tzinfo is None:          # nur selbst geschriebene Zeitpunkte (mit Zone) zählen
        return False
    return (jetzt or datetime.now(UTC)) - erstellt < FREIGABE


def mit_ergebnis(wert: dict[str, Any], index: int, ergebnis: dict[str, Any]) -> dict[str, Any]:
    neu = copy.deepcopy(wert)
    for e in neu["inhalte"]:
        if e["index"] == index:
            e["stand"] = str(ergebnis.get("status") or "unverified")
            if ergebnis.get("ohne_antwort"):
                e["ohne_antwort"] = True
            else:
                e.pop("ohne_antwort", None)
            if isinstance(ergebnis.get("nodeId"), str):
                e["node_id"] = ergebnis["nodeId"]
    if ergebnis.get("folderDenied"):
        neu["layout"] = "flach"
        neu["ordner_verweigert"] = True
    return neu


def zusammenfassung(wert: dict[str, Any]) -> str:
    inhalte = wert.get("inhalte") or []
    abgelegt = sum(1 for e in inhalte if e.get("stand") == "stored")
    fehler = sum(1 for e in inhalte if e.get("stand") in ("failed", "dropped", "unverified"))
    text = f"Ablage in WLO: {abgelegt} von {len(inhalte)} abgelegt"
    if fehler:
        text += f", {fehler} mit Problem"
    return text + (", abgeschlossen" if wert.get("abgeschlossen") else "")


async def lesen(s: Any, session_id: str, entities: dict[str, Any]) -> dict[str, Any] | None:
    wert = await arbeitsstand.teil_lader(s, session_id, entities)(TEIL)
    return wert if isinstance(wert, dict) and wert.get("format") == TYP else None


async def _mit_strukturdokument(s: Any, session_id: str, entities: dict[str, Any],
                                w: dict[str, Any]) -> list[arbeitsstand.Teil]:
    """Plan 2026-11-16, TG-3e („nach der Ablage“): der Teil ``ablage`` und — wenn sich die
    abgelegten Knoten mit der Rolle ``struktur`` ändern — der Teil ``strukturdokument`` mit ihnen
    (Quelle ``wlo``, Verweis node_id). So gehen sie mit ``BEREITSTELLUNG`` in einen neuen Vorgang,
    auch wenn ``ablage`` dort fehlt (N14)."""
    from boerdi.services.dokumente import strukturdokument_teil as sd

    teile: list[arbeitsstand.Teil] = [(TEIL, TYP, w, zusammenfassung(w))]
    alt = await arbeitsstand.teil_lader(s, session_id, entities)(sd.TEIL)
    if (neu_sd := sd.mit_ablage(alt, w)) is not None:
        teile.append((sd.TEIL, sd.TYP, neu_sd, sd.zusammenfassung(neu_sd[sd.FELD])))
    return teile


async def speichern(s: Any, session_id: str, entities: dict[str, Any], wert: dict[str, Any], *,
                    neu: Callable[[], Awaitable[dict[str, Any] | None]] | None = None,
                    nur_dieser: bool = False) -> bool:
    """``neu``: in jedem Versuch auf frischem Stand neu rechnen; ``nur_dieser``: nicht in einen
    anderen Vorgang ausweichen (beides siehe ``arbeitsstand.teile_speichern``). TG-3e: der Teil
    ``strukturdokument`` folgt den abgelegten Strukturdokumenten (:func:`_mit_strukturdokument`)."""
    async def frisch() -> list[arbeitsstand.Teil] | None:
        w = await neu() if neu is not None else None
        return None if w is None else await _mit_strukturdokument(s, session_id, entities, w)

    return await arbeitsstand.teile_speichern(
        s, session_id, entities, await _mit_strukturdokument(s, session_id, entities, wert),
        neu=frisch if neu is not None else None, nur_dieser=nur_dieser)
