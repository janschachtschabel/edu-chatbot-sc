"""Plan 2026-11-10, TB-F2: die Metadaten hochgeladener Nodes für einen Ablauf lesen.

Der Kestra-Flow ``node-metadata-write`` meldet nur, welche Felder er geschrieben hat, nicht ihre
Werte. Der Themenbaum aus Inhalten braucht sie: dieses Werkzeug liest sie nach dem Flow.

- Die nodeIds kommen aus dem Teil ``ablage`` (``wlo.ablage@1``, vom Ablage-Endpunkt geschrieben,
  nie vom Modell): nur die abgelegten Einträge des jetzigen Stapels — dieselben, die der Flow
  bekommt (Querschnitts-Review F/T, Befund 6; ``frueher`` eines ersetzten Stapels nicht).
- ``get_nodes_details`` (höchstens :data:`MAX_NODES`) nur unter der persönlichen Anmeldung des
  Zuges (sonst läse der Server anonym oder mit dem Dienstkonto) und ohne Lesen aus dem Cache: die
  Werte sollen frisch sein, gleich nachdem Kestra sie geschrieben hat (der Cache hängt an der
  Person, legt die frische Antwort aber wieder ab).
- Je Node nur, was ein Themenbaum braucht, gekürzt; der ganze Teil passt unter
  ``teil_verweise.MAX_BYTES``. Scheitert der Aufruf oder ist kein Node lesbar, entsteht kein Teil.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from boerdi.services.dokumente.stand import DokumentStand

logger = logging.getLogger(__name__)

WERKZEUG: Final = "get_nodes_details"
FORMAT: Final = "wlo.metadaten@1"
MAX_NODES: Final = 50
MAX_BESCHREIBUNG: Final = 300
MAX_SCHLAGWORTE: Final = 10
_MAX_LISTE: Final = 5
_MAX_TEXT: Final = 120
#: Unter ``teil_verweise.MAX_BYTES`` (64 000), mit Rand für Format und Titel.
_MAX_TEIL: Final = 60_000
_UUID: Final = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                          r"[0-9a-fA-F]{12}$")


def _kennungen(ablage: Any) -> dict[str, str]:
    """nodeId → Rolle der abgelegten Einträge, in Reihenfolge, ohne Doppel (alle; gelesen werden
    höchstens :data:`MAX_NODES`, der Rest steht in ``fehlend``)."""
    if not isinstance(ablage, dict):
        return {}
    eintraege = [e for e in ablage.get("inhalte") or [] if isinstance(e, dict)
                 and e.get("stand") == "stored"]
    aus: dict[str, str] = {}
    for e in eintraege:
        kennung = e.get("node_id")
        if isinstance(kennung, str) and _UUID.fullmatch(kennung) and kennung not in aus:
            aus[kennung] = e.get("rolle") if e.get("rolle") in ("inhalt", "struktur") else "inhalt"
    return aus


def _texte(wert: Any, hoechstens: int) -> list[str]:
    if not isinstance(wert, list):
        return []
    return [str(w)[:_MAX_TEXT] for w in wert if isinstance(w, str) and w.strip()][:hoechstens]


def _knapp(kennung: str, rolle: str, roh: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_id": kennung, "rolle": rolle,
        "titel": str(roh.get("title") or "")[:200],
        "beschreibung": str(roh.get("description") or "")[:MAX_BESCHREIBUNG],
        "schlagworte": _texte(roh.get("keywords"), MAX_SCHLAGWORTE),
        "faecher": _texte(roh.get("disciplines"), _MAX_LISTE),
        "stufen": _texte(roh.get("educationalContexts"), _MAX_LISTE),
        "arten": _texte(roh.get("learningResourceTypes"), _MAX_LISTE),
    }


def _groesse(inhalte: list[dict[str, Any]]) -> int:
    return len(json.dumps(inhalte, ensure_ascii=False).encode("utf-8"))


def _einpassen(inhalte: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Review TB-F2, Befund 4: zuerst die Beschreibungen kürzen, dann weglassen, dann die
    Listen, zuletzt Inhalte vom Ende (Review TB-T1, Befund 6: der Aufrufer nennt sie in
    ``fehlend``) — der Teil bleibt für jeden Folgeschritt nutzbar."""
    schritte = [("beschreibung", lambda w: w[:100]), ("beschreibung", lambda w: "")]
    schritte += [(feld, lambda w: w[:2]) for feld in ("schlagworte", "faecher", "stufen", "arten")]
    for feld, kuerzen in schritte:
        if _groesse(inhalte) <= _MAX_TEIL:
            return inhalte
        inhalte = [{**i, feld: kuerzen(i[feld])} for i in inhalte]
    while inhalte and _groesse(inhalte) > _MAX_TEIL:
        inhalte = inhalte[:-1]
    return inhalte


async def lesen(ablage: Any) -> dict[str, Any] | None:
    """Der Teil ``wlo.metadaten@1`` zu den abgelegten Nodes — ``None`` ohne Nodes, ohne
    persönliche Anmeldung, bei einem Fehler des Servers oder wenn kein Node lesbar war."""
    from boerdi.services.mcp import auth, client

    alle = _kennungen(ablage)
    if not alle:
        return None
    # Querschnitts-Review F/T, Befund 2: ein Stapel hat bis 200 Dateien — gelesen werden 50, der
    # Rest steht in ``fehlend`` (nie still weg)
    kennungen = dict(list(alle.items())[:MAX_NODES])
    gekappt = list(alle)[MAX_NODES:]
    if not auth.has_personal_auth():
        logger.info("Metadaten lesen: ohne persönliche Anmeldung, nichts gelesen")
        return None
    antwort = await client.call_mcp_tool_antwort(WERKZEUG, {"nodeIds": list(kennungen)},
                                                 use_cache=False)
    if fehlerart := antwort.art:   # nur die Art des Fehlers ins Log, nie die Antwort
        logger.info("Metadaten lesen: %s gescheitert (%s)", WERKZEUG, fehlerart)
        return None
    try:
        daten = json.loads(antwort.text)
    except ValueError:
        logger.warning("Metadaten lesen: Antwort ist kein JSON")
        return None
    ergebnisse = daten.get("results") if isinstance(daten, dict) else None
    if not isinstance(ergebnisse, dict):
        return None
    inhalte = [_knapp(k, rolle, ergebnisse[k]) for k, rolle in kennungen.items()
               if isinstance(ergebnisse.get(k), dict)]
    if not inhalte:
        # Review TB-F2, Befund 1: der Server meldet unlesbare Nodes in ``failed`` und schickt
        # ``results: {}`` — ein leerer Teil ließe den Ablauf still weiterlaufen statt ``bei_fehler``
        logger.info("Metadaten lesen: keiner von %d Nodes lesbar", len(kennungen))
        return None
    fehlend = [k for k in kennungen if not isinstance(ergebnisse.get(k), dict)] + gekappt
    eingepasst = _einpassen(inhalte)
    fehlend += [i["node_id"] for i in inhalte[len(eingepasst):]]
    inhalte = eingepasst
    return {"format": FORMAT, "titel": f"Metadaten zu {len(inhalte)} Inhalten",
            "inhalte": inhalte, "fehlend": fehlend}


#: Der Teil, aus dem ``ui_strukturentwurf`` mit ``aus_inhalten`` liest — fest wie ``draft`` für
#: ``vorlage``; ein Ablauf schreibt das Ergebnis von ``metadaten_lesen`` unter diesen Namen.
TEIL: Final = "metadaten"
#: ``DokumentStand.format`` der Materialliste — der Strukturentwurf gruppiert sie (TB-T1).
DOKUMENT_FORMAT: Final = "wlo-inhalte"
_ZEILEN: Final = (("schlagworte", "Schlagworte"), ("faecher", "Fächer"), ("stufen", "Stufen"),
                  ("arten", "Art"))


def als_dokument(teil: Any) -> DokumentStand | None:
    """TB-T1: der Teil ``wlo.metadaten@1`` als Dokument für ``ui_strukturentwurf``
    (``aus_inhalten``) — je Material ein Abschnitt (Titel, Beschreibung, Schlagworte …).
    ``None`` ohne Materialien oder bei einem Teil anderer Form (Review TB-T1, Befund 4). Die
    Werte stammen von WLO (vom Metadaten-Agenten oder der Person), nie vom Modell; der Dienst
    moderiert Übersicht und Anfang (:func:`moderationstext`), der Entwurf die Auszüge."""
    from boerdi.domain.dokument_gliederung import TITEL_ZEICHEN, Abschnitt
    from boerdi.services.dokumente.stand import DokumentStand

    if not isinstance(teil, dict) or teil.get("format") != FORMAT:
        return None
    inhalte = teil.get("inhalte")
    if not isinstance(inhalte, list):
        return None
    teile: list[str] = []
    abschnitte: list[Abschnitt] = []
    laenge = 0
    for n, i in enumerate((i for i in inhalte if isinstance(i, dict)), 1):
        titel = " ".join(str(i.get("titel") or "").split())[:TITEL_ZEICHEN] or f"Material {n}"
        zeilen = [f"## {titel}"]
        if beschreibung := " ".join(str(i.get("beschreibung") or "").split()):
            zeilen.append(beschreibung)
        zeilen += [f"{name}: {', '.join(werte)}" for feld, name in _ZEILEN
                   if (werte := _texte(i.get(feld), _MAX_LISTE * 2))]
        text = "\n".join(zeilen) + "\n\n"
        abschnitte.append(Abschnitt(id=f"a{n}", ebene=1, titel=titel, start=laenge,
                                    ende=laenge + len(text)))
        teile.append(text)
        laenge += len(text)
    if not abschnitte:
        return None
    return DokumentStand(upload_id="", name="Materialien", format=DOKUMENT_FORMAT, befund={},
                         abschnitte=abschnitte, markdown="".join(teile))


def moderationstext(dokument: DokumentStand) -> str:
    """Review TB-T1, Befund 1: was Ebene 1 sieht (Übersicht und Anfang) — geht vor dem Entwurf
    durch die Moderation, wie ein Dokument der Person beim Hochladen (``dokumente/aufnahme``)."""
    from boerdi.domain.dokument_gliederung import uebersicht
    from boerdi.services.dokumente.aufnahme import MODERATION_ANFANG, MODERATION_UEBERSICHT

    kurz, _ = uebersicht(dokument.abschnitte, MODERATION_UEBERSICHT)
    return kurz + "\n\n" + dokument.markdown[:MODERATION_ANFANG]

