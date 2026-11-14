"""Dienst ``strukturabgleich`` (Paket U4, Plan 2026-11-08 E-3…E-8): der Entwurf gegen eine
WLO-Sammlung.

Ohne LLM. Der Entwurf: der gemerkte (in diesem Gespräch zuletzt gezeigte), sonst der übernommene aus
dem Vorgang (Teil ``draft``) — dieselbe Reihenfolge wie beim Strukturentwurf (Review U4, Befund 9).
Die Sammlung über ``browse_collection_tree`` (Tiefe 2, mit Inhaltszahlen, ohne Cache — nur so trägt
die Antwort ihren strukturierten Teil). Führt der Server ``list_collection_tree`` (SW-4, Plan
2026-11-14), liest der Dienst damit den ganzen Baum und gleicht bis Ebene 4 ab; fällt das aus oder
fehlt die Zeit, bleibt es beim alten Weg. Der Abgleich selbst ist rein
(``domain/strukturabgleich``).

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


#: SW-4: so viele Seiten der Baumliste liest der Abgleich höchstens (je 250 Einträge; der Server
#: nimmt ``skipCount`` bis 500).
_SEITEN: Final = 3
#: So lange darf eine Seite der Baumliste dauern, und so viel Zeit muss dem Lauf dafür bleiben.
#: Gemessen am lokal gestarteten neuen MCP (14.11.2026): Fachportal Physik, 144 Sammlungen mit
#: Inhaltszahlen, 10,5–12,8 s (sechsmal), im ersten Aufruf eines Prozesses 19 und 38 s;
#: ``browse_collection_tree`` (Tiefe 2) 3,6–5 s. Bleibt weniger oder dauert es länger, liest der
#: Dienst zwei Ebenen.
_LISTE_BRAUCHT_S: Final = 30.0
#: So viel muss zusätzlich bleiben, bevor die Liste begonnen wird: Läuft ihre erste Seite in die
#: Frist, liest der alte Weg — und der soll nicht aus der Reserve des Laufs leben.
_RUECKFALL_S: Final = 10.0


def _jetzt() -> float:
    return asyncio.get_running_loop().time()


def _zeit_reicht(umgebung: Umgebung, dazu: float = 0.0) -> bool:
    """Bleibt dem Lauf genug für (noch) eine Seite der Baumliste — und ``dazu``? Ohne Frist: ja."""
    return umgebung.frist_ende is None or \
        umgebung.frist_ende - RESERVE_S - _jetzt() >= _LISTE_BRAUCHT_S + dazu


def _liste_erlaubt(umgebung: Umgebung) -> bool:
    """SW-4 (Entscheid SE-5): die Baumliste, wenn der Server sie führt, die Redaktion sie nicht
    abgeschaltet hat (Studio, je MCP-Server) und dem Lauf genug Zeit bleibt.

    Ob sie der KI in diesem Zug angeboten ist, zählt nicht: Ein KI-Schritt eines Ablaufs engt
    das Angebot auf seine Werkzeuge ein, und gerade dort wird tief abgeglichen. Lesen darf der
    Dienst die Sammlung über ``dienst.braucht`` (``browse_collection_tree``) — ist das gesperrt,
    wird das Modul gar nicht angeboten. Eine Sperre je Lauf (Policy), die nur die Baumliste
    nennt, erreicht den Dienst nicht."""
    from boerdi.services.agent_tools import verborgene_werkzeuge
    from boerdi.services.mcp import baum_lesen

    if not baum_lesen.angeboten() or baum_lesen.WERKZEUG in verborgene_werkzeuge():
        return False
    if not _zeit_reicht(umgebung, _RUECKFALL_S):
        logger.info("Strukturabgleich: zu wenig Zeit für die Baumliste — zwei Ebenen")
        return False
    return True


async def _ganzer_baum(node_id: str, umgebung: Umgebung, tiefe: int
                       ) -> tuple[list[dict[str, Any]], int | None, str, str] | None:
    """SW-4: der Bestand bis ``tiefe`` Ebenen aus ``list_collection_tree`` — ``(Sammlungen,
    unvollständig ab Ebene, gelesene Kennung, ihr Titel)``. ``None``, wenn schon die erste Seite
    ausfällt: Dann liest der Aufrufer wie bisher zwei Ebenen (und meldet dessen Fehler).

    Der Server liest Ebene für Ebene und liefert in dieser Reihenfolge.

    - Bricht die Liste ab — Grenze des Servers (``walkCapped``, ``skipLimitReached``), mehr als
      :data:`_SEITEN` Seiten, keine Zeit mehr (je Seite geprüft; nach :data:`_LISTE_BRAUCHT_S`
      insgesamt beginnt keine weitere), eine Folgeseite fällt aus —, ist die tiefste gelesene
      Ebene unvollständig, die darüber nicht.
    - Konnte er irgendwo nicht lesen (``incomplete``, ``restricted``), ist nichts sicher: Wo,
      sagt die Antwort nicht verlässlich (zweites Review SW-4, Befund 1) — dann gilt Ebene 1.

    Die Sammlung Optik (16 Sammlungen) dauerte 2,2 s; zum Fachportal siehe
    :data:`_LISTE_BRAUCHT_S`."""
    from boerdi.services.mcp import baum_lesen
    from boerdi.services.mcp.client import McpAntwort, call_mcp_tool_antwort, is_mcp_error
    from boerdi.ui_module.themenbaum import _wurzel_url

    beginn = _jetzt()
    sammlungen: list[dict[str, Any]] = []
    gesehen: set[str] = set()
    ausfall = abgebrochen = False
    gelesen, titel, ab = node_id, "", 0
    for seite in range(_SEITEN):
        if seite and (not _zeit_reicht(umgebung) or _jetzt() - beginn > _LISTE_BRAUCHT_S):
            abgebrochen = True
            break
        try:
            antwort = await asyncio.wait_for(call_mcp_tool_antwort(
                baum_lesen.WERKZEUG, {"nodeId": node_id, "depth": tiefe,
                                      "maxItems": sa.LISTE_SEITE, "skipCount": ab,
                                      "includeContentCounts": True}, use_cache=False),
                timeout=_LISTE_BRAUCHT_S)
        except TimeoutError:
            # Die eigene Frist: Der alte Weg (zwei Ebenen) gelingt in wenigen Sekunden.
            antwort = McpAntwort("", "timeout")
        liste = antwort.strukturiert
        if antwort.art or is_mcp_error(antwort.text) or not isinstance(liste, dict) or \
                not isinstance(liste.get("items"), list):
            # Ohne ``items`` ist es keine Baumliste — sonst hieße eine fremde Antwort „die
            # Sammlung hat keine Untersammlungen“ und jeder Punkt verbindlich „neu“.
            grund = (antwort.code or antwort.art or "form")[:40]
            logger.info("Strukturabgleich: Baumliste nicht lesbar (%s, Seite %d)", grund,
                        seite + 1)
            if seite == 0:
                return None
            abgebrochen = True
            break
        for w in sa.wlo_aus_liste(liste):
            # Der Server sagt selbst: bei einem Ausfall sind die Positionen nicht verlässlich —
            # eine Sammlung kann auf zwei Seiten stehen. Die erste gilt.
            if w["nodeId"] not in gesehen:
                gesehen.add(w["nodeId"])
                sammlungen.append(w)
        wurzel = liste.get("root") if isinstance(liste.get("root"), dict) else {}
        if seite == 0 and isinstance(wurzel.get("nodeId"), str):
            gelesen = wurzel["nodeId"]
            # Ohne Titel setzt der Server die Kennung ein — die ist kein Titel.
            if isinstance(wurzel.get("title"), str) and wurzel["title"] != gelesen:
                titel = " ".join(wurzel["title"].split())[:120]
        if liste.get("incomplete") or liste.get("restricted"):
            ausfall = True
        if liste.get("walkCapped") or liste.get("skipLimitReached"):
            abgebrochen = True
        if liste.get("more") is None:
            break
        mehr = liste["more"]
        weiter = mehr.get("nextSkipCount") if isinstance(mehr, dict) else None
        if type(weiter) is not int or weiter <= ab or seite == _SEITEN - 1:
            abgebrochen = True              # es gäbe mehr, als gelesen wurde
            break
        ab = weiter
    unvollstaendig_ab = max((w["ebene"] for w in sammlungen), default=1) if abgebrochen else None
    if ausfall:
        unvollstaendig_ab = 1
    for w in sammlungen:
        # Die Liste trägt keine Adresse; dieselbe wie die der Sammlung selbst.
        if _UUID.match(w["nodeId"]) and (url := _wurzel_url(w["nodeId"])) and \
                url.startswith("https://"):
            w["url"] = url[:500]
    return sammlungen, unvollstaendig_ab, gelesen, titel


#: Querschnitts-Review Gruppe E: Klammern als Entität — ``\(``/``\[`` wäre im Widget eine Formel.
_ENTITAETEN: Final = {"(": "&#40;", ")": "&#41;", "[": "&#91;", "]": "&#93;"}


def _md(titel: str) -> str:
    return _MARKDOWN.sub(lambda m: _ENTITAETEN.get(m.group(1), "\\" + m.group(1)), titel)


def textfassung(daten: dict[str, Any]) -> str:
    """Für Widgets ohne das Modul: die Zahlen und die neuen Punkte (Titel entschärft). Was nur
    „nicht gefunden“ ist (``ungewiss``), steht getrennt von „neu“ — wie im Modul."""
    z = daten["zahlen"]
    kopf = (f"Abgleich mit „{_md(daten['sammlung']['titel'] or 'der Sammlung')}“: "
            f"{z['vorhanden']} vorhanden, {z['aehnlich']} ähnlich, {z['neu']} neu, "
            f"{z['nur_in_wlo']} nur in WLO.")
    neue = [zl for zl in daten["zeilen"] if zl["art"] == "neu"]
    neu = [f"- {_md(zl['titel'])}" for zl in neue if not zl.get("ungewiss")][:20]
    offen = [f"- {_md(zl['titel'])}" for zl in neue if zl.get("ungewiss")][:20]
    warum = ("Die Sammlung wurde nicht vollständig gelesen" if daten.get("unvollstaendig")
             else "Die Sammlung ist größer als gezeigt")
    nicht_gefunden = ("\n\nNicht gefunden (nicht sicher neu):\n" + "\n".join(offen)
                      + f"\n\n{warum}." if offen else "")
    # Paket R3-c: ein Unterpunkt steht mit seinem Punkt (wie im Modul) — sonst nicht zuzuordnen.
    # Lücken gibt es nur auf Ebene 1 und 2 (``abdeckung.TIEFE``); tiefere Zeilen dazwischen
    # (SW-4) ändern den Punkt nicht.
    eltern: dict[int, str] = {}
    punkt = ""
    for i, zl in enumerate(daten["zeilen"]):
        if zl.get("ebene") == 1:
            punkt = str(zl.get("titel") or "")
        elif zl.get("ebene") == 2 and punkt:
            eltern[i] = punkt
    alle = [f"- {_md(eltern[i]) + ' › ' if i in eltern else ''}{_md(zl['titel'])} "
            f"({zl['abdeckung']['total']} Treffer in WLO)"
            for i, zl in enumerate(daten["zeilen"]) if (zl.get("abdeckung") or {}).get("luecke")]
    luecken = alle[:20] + ([f"- … und {len(alle) - 20} weitere"] if len(alle) > 20 else [])
    ab = daten.get("abdeckung") if isinstance(daten.get("abdeckung"), dict) else None
    ohne = ("\n\nTreffer in WLO ließen sich nicht zählen." if ab and not ab["gezaehlt"] else "")
    return (kopf + ("\n\nNeu:\n" + "\n".join(neu) if neu else "") + nicht_gefunden
            + ("\n\nLücken (kaum Material in ganz WLO):\n" + "\n".join(luecken)
               if luecken else "") + ohne)


def quittung(daten: dict[str, Any]) -> str:
    z = daten["zahlen"]
    ungewiss = sum(1 for zl in daten["zeilen"] if zl.get("ungewiss"))
    # SW-4: „nicht vollständig gelesen“ (ein Zweig ohne Antwort, nicht lesbar, zu groß) ist ein
    # anderer Grund als „größer als gezeigt“ — die KI gibt ihn weiter.
    warum = ("Die Sammlung wurde nicht vollständig gelesen" if daten.get("unvollstaendig")
             else "Die Sammlung ist größer als gezeigt")
    kuerzung = (f" {warum}: {ungewiss} der neuen Punkte sind nur "
                f"„nicht gefunden“, sie können in WLO doch stehen — sag das so."
                if daten.get("gekuerzt") and ungewiss else
                f" {warum}." if daten.get("gekuerzt") else "")
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
                 f"{ab['luecke_bis']} Treffer)."
                 + (f" Gezählt wird nur für Ebene 1 bis {ab['nur_bis_ebene']}."
                    if ab.get("nur_bis_ebene") else ""))
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
        if zeile["ebene"] > abdeckung.TIEFE:
            # SE-9: nach Regel nicht gezählt — das ist kein Ausfall und verbraucht keine Kennung
            # (eine tiefe Zeile mit der Kennung eines Punkts bekäme sonst dessen Treffer).
            zeile["abdeckung_fehlt"] = "ebene"
            continue
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
    tiefer = any(zl.get("abdeckung_fehlt") == "ebene" for zl in zeilen)
    return {"gezaehlt": gezaehlt,
            "luecken": sum(1 for zl in zeilen if (zl.get("abdeckung") or {}).get("luecke")),
            "ungezaehlt": sum(1 for zl in zeilen
                              if zl.get("abdeckung_fehlt") not in (None, "ebene")),
            **({"nur_bis_ebene": abdeckung.TIEFE} if tiefer else {}),
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
    gelesen: Any
    wurzel_titel = ""
    unvollstaendig = False
    # SW-4: führt der Server die Baumliste, so tief wie der Entwurf (mindestens zwei, höchstens
    # vier Ebenen) — nichts je Elternknoten gekürzt. Tiefer zu lesen kostete je Sammlung eine
    # Abfrage, ohne dass ein Punkt dazu passte. Ohne die Liste (älterer Server, abgeschaltet,
    # keine Zeit, Ausfall) bleibt es bei zwei Ebenen.
    tiefe = max(sa.TIEFE_BAUM, sa.tiefe_von(entwurf))
    ganz = (await _ganzer_baum(args["sammlung"], umgebung, tiefe)
            if _liste_erlaubt(umgebung) else None)
    if ganz is not None:
        sammlungen, unvollstaendig_ab, gelesen, wurzel_titel = ganz
        unvollstaendig = unvollstaendig_ab is not None
        erg = sa.abgleichen(entwurf, sammlungen, tiefe=tiefe,
                            unvollstaendig_ab=unvollstaendig_ab)
        latenz_ms = int((time.monotonic() - t0) * 1000)
    else:
        baum = await _sammlung(args["sammlung"])
        latenz_ms = int((time.monotonic() - t0) * 1000)
        if isinstance(baum, str):
            return _fehlschlag(modul, baum, latenz_ms)
        erg = sa.abgleichen(entwurf, sa.wlo_aus(baum), gekuerzt=baum.get("truncated") is True)
        # Review U4, Befund 1: ``parent`` ist die Kennung (ein Text). Hat der Client sie geändert
        # (Selbstheilung über das Fach), gilt die, die der Server gelesen hat (Befund 10).
        gelesen = baum.get("parent")
    kennung = gelesen if isinstance(gelesen, str) and _UUID.match(gelesen) else args["sammlung"]
    # Der Titel aus dem Argument gilt nur für die Kennung aus dem Argument; die Baumliste nennt
    # den Titel der gelesenen Sammlung selbst (SW-4) — der geht vor, wenn er da ist.
    titel = wurzel_titel or (" ".join(str(args.get("titel") or "").split())[:120]
                             if kennung == args["sammlung"] else "")
    nur = erg["nur_in_wlo"]
    zeilen = erg["zeilen"]
    daten: dict[str, Any] = {
        "titel": " ".join(str(entwurf.get("titel") or "").split())[:120],
        "sammlung": {"nodeId": kennung, "titel": titel},
        "zeilen": zeilen, "nur_in_wlo": nur[:NUR_IN_WLO], "zahlen": erg["zahlen"],
        # ``gekuerzt`` heißt im Modul: „nicht gefunden“ ist nicht sicher neu. Aus der Baumliste
        # (SW-4) gilt das nur, wenn sie unvollständig ist — dass „nur in WLO“ gedeckelt ist,
        # sagt deren Überschrift („100 von 138“).
        "gekuerzt": erg["gekuerzt"] or (len(nur) > NUR_IN_WLO and ganz is None),
        **({"unvollstaendig": True} if unvollstaendig else {}),
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
