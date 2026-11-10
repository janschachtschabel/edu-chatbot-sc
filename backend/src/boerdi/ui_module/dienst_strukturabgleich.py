"""Dienst ``strukturabgleich`` (Paket U4, Plan 2026-11-08 E-3…E-8): der Entwurf gegen eine
WLO-Sammlung.

Ohne LLM. Der Entwurf: der gemerkte (in diesem Gespräch zuletzt gezeigte), sonst der übernommene aus
dem Vorgang (Teil ``draft``) — dieselbe Reihenfolge wie beim Strukturentwurf (Review U4, Befund 9).
Die Sammlung über ``browse_collection_tree`` (Tiefe 2, mit Inhaltszahlen, ohne Cache — nur so trägt
die Antwort ihren strukturierten Teil). Der Abgleich selbst ist rein (``domain/strukturabgleich``).

Die KI bekommt nur Zahlen zurück, keine Titel: die stehen im Modul (Titel aus einem Dokument oder
einer fremden Sammlung sind Fremdtext). Das Manifest nennt ``browse_collection_tree`` unter
``dienst.braucht``: ist es im Lauf gesperrt, wird das Modul gar nicht angeboten (Review U4,
Befund 2).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import TYPE_CHECKING, Any, Final

from boerdi.api.schemas_debug import ToolOutcome
from boerdi.domain import strukturabgleich as sa
from boerdi.domain.ui_bloecke import neuer_block
from boerdi.ui_module import katalog
from boerdi.ui_module.datenquelle import Ergebnis
from boerdi.ui_module.katalog import Manifest

if TYPE_CHECKING:
    from boerdi.ui_module.aufruf import Umgebung

logger = logging.getLogger(__name__)

#: So viele Sammlungen „nur in WLO“ zeigt das Modul höchstens (der Rest: ``gekuerzt``).
NUR_IN_WLO: Final = 100
#: Reserve vor dem Fristende des Laufs (wie beim Strukturentwurf): danach bleibt die Zählung weg.
RESERVE_S: Final = 15.0
_UUID: Final = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                          r"[0-9a-fA-F]{12}$")
#: Zeichen, die Markdown deuten würde — in Titeln der Textfassung entschärft (Befund 11).
_MARKDOWN: Final = re.compile(r"([\\`*_\[\]()#<>!|~])")
FEHLER: Final = {
    "kein_entwurf": ("Fehler: Es gibt noch keinen Strukturentwurf, den ich abgleichen könnte. "
                     "Erstelle oder übernimm erst einen (ui_strukturentwurf); antworte ohne "
                     "Abgleich."),
    "sammlung": ("Fehler: Die Sammlung ließ sich nicht lesen (nodeId prüfen). Antworte ohne "
                 "Abgleich."),
    "timeout": "Fehler: WLO hat nicht rechtzeitig geantwortet. Antworte ohne Abgleich.",
    "abweichung": "Fehler: Der Abgleich ließ sich nicht darstellen. Antworte ohne ihn.",
}


def _fehlschlag(modul: str, grund: str, latenz_ms: int = 0) -> Ergebnis:
    return Ergebnis(None, FEHLER[grund], ToolOutcome(
        tool=modul, status="timeout" if grund == "timeout" else "error", error=grund,
        latency_ms=latenz_ms))


async def _sammlung(node_id: str) -> dict[str, Any] | str:
    """Der Baum — oder der Grund (``timeout``, ``sammlung``)."""
    from boerdi.services.mcp.client import call_mcp_tool_antwort, is_mcp_error

    antwort = await call_mcp_tool_antwort(
        "browse_collection_tree", {"nodeId": node_id, "depth": 2, "includeContentCounts": True,
                                   "maxResults": sa.WLO_OBEN, "outputFormat": "json"},
        use_cache=False)
    if antwort.art or is_mcp_error(antwort.text):
        grund = (antwort.code or antwort.art or "fehler")[:40]
        logger.info("Strukturabgleich: Sammlung nicht lesbar (%s)", grund)
        return "timeout" if antwort.art in ("timeout", "busy") else "sammlung"
    if isinstance(antwort.strukturiert, dict):
        return antwort.strukturiert
    try:
        roh = json.loads(antwort.text)
    except (TypeError, ValueError):
        return "sammlung"
    return roh if isinstance(roh, dict) else "sammlung"


#: Querschnitts-Review Gruppe E: Klammern als Entität — ``\(``/``\[`` wäre im Widget eine Formel.
_ENTITAETEN: Final = {"(": "&#40;", ")": "&#41;", "[": "&#91;", "]": "&#93;"}


def _md(titel: str) -> str:
    return _MARKDOWN.sub(lambda m: _ENTITAETEN.get(m.group(1), "\\" + m.group(1)), titel)


def textfassung(daten: dict[str, Any]) -> str:
    """Für Widgets ohne das Modul: die Zahlen und die neuen Punkte (Titel entschärft)."""
    z = daten["zahlen"]
    kopf = (f"Abgleich mit „{_md(daten['sammlung']['titel'] or 'der Sammlung')}“: "
            f"{z['vorhanden']} vorhanden, {z['aehnlich']} ähnlich, {z['neu']} neu, "
            f"{z['nur_in_wlo']} nur in WLO.")
    neu = [f"- {_md(zl['titel'])}" for zl in daten["zeilen"] if zl["art"] == "neu"][:20]
    alle = [f"- {_md(zl['titel'])} ({zl['abdeckung']['total']} Treffer in WLO)"
            for zl in daten["zeilen"] if (zl.get("abdeckung") or {}).get("luecke")]
    luecken = alle[:20] + ([f"- … und {len(alle) - 20} weitere"] if len(alle) > 20 else [])
    ab = daten.get("abdeckung") if isinstance(daten.get("abdeckung"), dict) else None
    ohne = ("\n\nTreffer in WLO ließen sich nicht zählen." if ab and not ab["gezaehlt"] else "")
    return (kopf + ("\n\nNeu:\n" + "\n".join(neu) if neu else "")
            + ("\n\nLücken (kaum Material in ganz WLO):\n" + "\n".join(luecken)
               if luecken else "") + ohne)


def quittung(daten: dict[str, Any]) -> str:
    z = daten["zahlen"]
    ungewiss = sum(1 for zl in daten["zeilen"] if zl.get("ungewiss"))
    kuerzung = (f" Die Sammlung ist größer als gezeigt: {ungewiss} der neuen Punkte sind nur "
                f"„nicht gefunden“, sie können in WLO doch stehen — sag das so."
                if daten.get("gekuerzt") and ungewiss else
                " Die Sammlung ist größer als gezeigt." if daten.get("gekuerzt") else "")
    ab = daten.get("abdeckung")
    abdeckung = ("" if not isinstance(ab, dict) else
                 " Treffer in ganz WLO ließen sich nicht zählen: Fach oder Bildungsstufe des "
                 "Entwurfs kennt WLO nicht — sag das so." if ab.get("filter_unaufgeloest") else
                 " Zählen der Treffer ist in diesem Zug nicht angeboten — sag das so."
                 if ab.get("gesperrt") else
                 " Die Zählung der Treffer kam nicht zustande — sag das so, nenne keine Lücken."
                 if not ab["gezaehlt"] else
                 f" Abdeckung in ganz WLO: {ab['gezaehlt']} von "
                 f"{ab['gezaehlt'] + ab['ungezaehlt']} "
                 f"Punkten gezählt, {ab['luecken']} davon Lücken (höchstens "
                 f"{ab['luecke_bis']} Treffer).")
    return (f"OK: Unter deiner Antwort steht der Abgleich des Entwurfs mit der Sammlung — "
            f"{z['vorhanden']} Punkte vorhanden, {z['aehnlich']} ähnlich, {z['neu']} neu, "
            f"{z['nur_in_wlo']} Sammlungen nur in WLO.{kuerzung}{abdeckung} Die Titel stehen im "
            f"Modul. "
            f"Fasse in ein bis zwei Sätzen zusammen, was das heißt; nenne keine Zahlen, die hier "
            f"nicht stehen. Rufe in diesem Zug kein weiteres Werkzeug.")


def _abdeckung_eintragen(z: Any, zeilen: list[dict[str, Any]], *, grund: str | None = None
                         ) -> dict[str, Any]:
    """Paket U5: je Zeile ``abdeckung`` (``total``, ``luecke``, ``top``, ``geraten``) oder
    ``abdeckung_fehlt`` (Code); zurück die Summe. ``grund``: nichts gezählt (``gesperrt``,
    ``frist``, ``sammlung``)."""
    from boerdi.services import abdeckung

    gesehen: set[str] = set()
    for zeile in zeilen:
        t = z.treffer.get(zeile["id"]) if z is not None and zeile["id"] not in gesehen else None
        gesehen.add(zeile["id"])
        if t is None:
            # Review U5, Befund 3: eine doppelte Kennung zählt nur die erste Zeile
            zeile["abdeckung_fehlt"] = grund or (z.fehlen.get(zeile["id"], "nicht_gezaehlt")
                                                 if z is not None else "nicht_gezaehlt")
            continue
        # Review U5, Befund 2: die Sammlung hat schon mehr — dann ist es keine Lücke, auch wenn
        # die Volltextsuche weniger findet
        in_sammlung = (zeile.get("wlo") or {}).get("anzahl", 0) if zeile["art"] != "neu" else 0
        luecke = abdeckung.ist_luecke(t) and not in_sammlung > abdeckung.LUECKE_BIS
        zeile["abdeckung"] = {"total": t["total"], "luecke": luecke,
                              **({"top": t["top"]} if t["top"] else {}),
                              **({"geraten": t["geraten"]} if t.get("geraten") else {})}
    gezaehlt = sum(1 for zl in zeilen if "abdeckung" in zl)
    return {"gezaehlt": gezaehlt,
            "luecken": sum(1 for zl in zeilen if (zl.get("abdeckung") or {}).get("luecke")),
            "ungezaehlt": sum(1 for zl in zeilen if "abdeckung_fehlt" in zl),
            "luecke_bis": abdeckung.LUECKE_BIS,
            "filter_unaufgeloest": z is not None and not z.treffer and bool(z.fehlen) and all(
                c == "unresolved_filter" for c in z.fehlen.values()),
            **({"gesperrt": True} if grund == "gesperrt" else {})}


def _zaehlung_starten(entwurf: dict[str, Any], umgebung: Umgebung) -> asyncio.Task | str:
    """Die Zählung als eigene Aufgabe (neben dem Lesen der Sammlung) — oder ``gesperrt``, wenn
    ``count_wlo_content_matches`` in diesem Zug nicht angeboten ist (Review U5, Befund 5)."""
    from boerdi.services import abdeckung

    if umgebung.verfuegbar is None or abdeckung.WERKZEUG not in umgebung.verfuegbar:
        return "gesperrt"
    return asyncio.create_task(abdeckung.zaehlen(abdeckung.punkte_aus_entwurf(entwurf)))


async def _zaehlung_abwarten(zaehlung: asyncio.Task | str | None, umgebung: Umgebung
                             ) -> tuple[Any, str | None]:
    """Das Ergebnis der Zählung — höchstens bis kurz vor der Frist des Laufs; danach steht der
    Abgleich ohne sie (``frist``)."""
    if not isinstance(zaehlung, asyncio.Task):
        return None, zaehlung or "nicht_gezaehlt"
    rest = None
    if umgebung.frist_ende is not None:
        rest = umgebung.frist_ende - RESERVE_S - asyncio.get_running_loop().time()
    try:
        return await asyncio.wait_for(zaehlung, timeout=max(rest, 0.1) if rest is not None
                                      else None), None
    except TimeoutError:
        logger.info("Strukturabgleich: Zählung vor der Frist abgebrochen")
        return None, "frist"
    except Exception as fehler:  # noqa: BLE001 — Gesamt-Review, Befund 2: der Abgleich bleibt
        logger.warning("Strukturabgleich: Zählung fehlgeschlagen (%s)", type(fehler).__name__)
        return None, "fehler"


def _entwurf_von(wert: Any) -> dict[str, Any] | None:
    return wert if isinstance(wert, dict) and isinstance(wert.get("knoten"), list) and \
        wert["knoten"] else None


async def strukturabgleich(manifest: Manifest, args: dict[str, Any], umgebung: Umgebung
                           ) -> Ergebnis:

    modul = manifest["name"]
    entwurf = _entwurf_von(umgebung.vorlage)
    if entwurf is None and umgebung.teile is not None:
        entwurf = _entwurf_von(await umgebung.teile("draft"))
    if entwurf is None:
        return _fehlschlag(modul, "kein_entwurf")
    t0 = time.monotonic()
    zaehlung = _zaehlung_starten(entwurf, umgebung) if args.get("abdeckung") is True else None
    try:
        return await _abgleich(manifest, args, umgebung, entwurf, zaehlung, t0)
    finally:
        # Gesamt-Review, Befund 1: Frist, Abbruch oder Fehler — keine Zählung läuft verwaist weiter
        if isinstance(zaehlung, asyncio.Task) and not zaehlung.done():
            zaehlung.cancel()


async def _abgleich(manifest: Manifest, args: dict[str, Any], umgebung: Umgebung,
                    entwurf: dict[str, Any], zaehlung: asyncio.Task | str | None, t0: float
                    ) -> Ergebnis:
    from boerdi.ui_module.themenbaum import _wurzel_url

    modul = manifest["name"]
    baum = await _sammlung(args["sammlung"])
    latenz_ms = int((time.monotonic() - t0) * 1000)
    if isinstance(baum, str):
        return _fehlschlag(modul, baum, latenz_ms)
    erg = sa.abgleichen(entwurf, sa.wlo_aus(baum), gekuerzt=baum.get("truncated") is True)
    # Review U4, Befund 1: ``parent`` ist die Kennung (ein Text). Hat der Client sie geändert
    # (Selbstheilung über das Fach), gilt die, die der Server gelesen hat (Befund 10).
    gelesen = baum.get("parent")
    kennung = gelesen if isinstance(gelesen, str) and _UUID.match(gelesen) else args["sammlung"]
    titel = " ".join(str(args.get("titel") or "").split())[:120] if kennung == args[
        "sammlung"] else ""
    nur = erg["nur_in_wlo"]
    zeilen = erg["zeilen"]
    daten: dict[str, Any] = {
        "titel": " ".join(str(entwurf.get("titel") or "").split())[:120],
        "sammlung": {"nodeId": kennung, "titel": titel},
        "zeilen": zeilen, "nur_in_wlo": nur[:NUR_IN_WLO], "zahlen": erg["zahlen"],
        "gekuerzt": erg["gekuerzt"] or len(nur) > NUR_IN_WLO,
    }
    if (url := _wurzel_url(kennung)) and url.startswith("https://"):
        daten["sammlung"]["url"] = url[:500]
    if args.get("abdeckung") is True:
        # Paket U5: Treffer je Punkt in ganz WLO (M1, ``services/abdeckung``) — gezählt wurde
        # schon während des Lesens der Sammlung (Review U5, Befund 4)
        z, grund = await _zaehlung_abwarten(zaehlung, umgebung)
        daten["abdeckung"] = _abdeckung_eintragen(z, zeilen, grund=grund)
        latenz_ms = int((time.monotonic() - t0) * 1000)
    if katalog.daten_fehler(manifest, daten):
        return _fehlschlag(modul, "abweichung", latenz_ms)
    block = neuer_block(modul, manifest["version"], manifest["art"], daten, textfassung(daten))
    return Ergebnis(block, quittung(daten), ToolOutcome(
        tool=modul, status="success", item_count=len(zeilen), latency_ms=latenz_ms))
