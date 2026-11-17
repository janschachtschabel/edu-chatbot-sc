"""Plan 2026-11-10, TB-F2: die Metadaten hochgeladener Nodes für einen Ablauf lesen.

Der Kestra-Flow ``node-metadata-write`` meldet nur, welche Felder er geschrieben hat, nicht ihre
Werte. Der Themenbaum aus Inhalten braucht sie: dieses Werkzeug liest sie nach dem Flow.

- Die nodeIds kommen aus dem Teil ``ablage`` (``wlo.ablage@1``, vom Ablage-Endpunkt geschrieben,
  nie vom Modell): nur die abgelegten Einträge des jetzigen Stapels — dieselben, die der Flow
  bekommt (Querschnitts-Review F/T, Befund 6; ``frueher`` eines ersetzten Stapels nicht).
- ``get_nodes_details`` nur unter der persönlichen Anmeldung des Zuges (sonst läse der Server
  anonym oder mit dem Dienstkonto) und ohne Lesen aus dem Cache: die Werte sollen frisch sein,
  gleich nachdem Kestra sie geschrieben hat (der Cache hängt an der Person, legt die frische
  Antwort aber wieder ab).
- Je Node nur, was ein Themenbaum braucht, gekürzt; der ganze Teil passt unter
  ``teil_verweise.MAX_BYTES``. Scheitert der Aufruf oder ist kein Node lesbar, entsteht kein Teil.

Plan 2026-11-16, TG-3c (Datenmodell, Teil ``inhalte`` unter dem Namen ``metadaten``):

- je Node die **Lizenz** (``license`` des MCP: die lesbare Bezeichnung aus
  ``ccm:commonlicense_key``, etwa „CC BY-SA“) und die feste Nummer **``i``** der Datei in der
  Auswahl — aus dem Eintrag im Teil ``ablage`` (TG-3b; ``None`` bei einem Stapel ohne Nummern);
- gelesen in **Blöcken** zu :data:`BLOCK` (so viele nimmt ``get_nodes_details`` je Aufruf), bis
  :data:`MAX_NODES`, nacheinander. Scheitert ein Block, bricht das Lesen ab — der Rest steht in
  ``fehlend``; ein Teil entsteht, wenn ein Block davor etwas lieferte;
- der ganze Teil (auch ``fehlend``) bleibt unter :data:`_MAX_TEIL`; was nicht hineinpasst, steht
  in ``fehlend`` (:func:`_einpassen`).
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
#: TG-3c: so viele Nodes liest ein Lauf höchstens (vorher 50 — ein Stapel hat bis 200 Dateien, eine
#: Auswahl bis 500).
MAX_NODES: Final = 500
#: TG-3c: so viele Nodes je Aufruf (``MAX_IDS`` von ``get_nodes_details`` im MCP).
BLOCK: Final = 50
#: TG-3c: die Lizenz ist eine kurze Bezeichnung („CC BY-SA“, „Copyright, freier Zugang“).
_MAX_LIZENZ: Final = 60
MAX_BESCHREIBUNG: Final = 300
MAX_SCHLAGWORTE: Final = 10
_MAX_LISTE: Final = 5
_MAX_TEXT: Final = 120
#: Unter ``teil_verweise.MAX_BYTES`` (64 000), mit Rand für Format und Titel.
_MAX_TEIL: Final = 60_000
#: Plan 2026-11-16, TG-4: dieselbe Grenze für den Teil aus Dateinamen (``inhalte_aus_dateien``).
MAX_TEIL: Final = _MAX_TEIL
_UUID: Final = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                          r"[0-9a-fA-F]{12}$")


def _nummer(e: dict[str, Any]) -> int | None:
    i = e.get("i")
    return i if isinstance(i, int) and not isinstance(i, bool) and i >= 0 else None


def _kennungen(ablage: Any) -> dict[str, tuple[str, int | None]]:
    """nodeId → (Rolle, feste Nummer ``i``) der abgelegten Einträge, in Reihenfolge, ohne Doppel
    (alle; gelesen werden höchstens :data:`MAX_NODES`, der Rest steht in ``fehlend``)."""
    if not isinstance(ablage, dict):
        return {}
    eintraege = [e for e in ablage.get("inhalte") or [] if isinstance(e, dict)
                 and e.get("stand") == "stored"]
    aus: dict[str, tuple[str, int | None]] = {}
    for e in eintraege:
        kennung = e.get("node_id")
        if isinstance(kennung, str) and _UUID.fullmatch(kennung) and kennung not in aus:
            rolle = e.get("rolle") if e.get("rolle") in ("inhalt", "struktur") else "inhalt"
            aus[kennung] = (rolle, _nummer(e))
    return aus


def _texte(wert: Any, hoechstens: int) -> list[str]:
    if not isinstance(wert, list):
        return []
    return [str(w)[:_MAX_TEXT] for w in wert if isinstance(w, str) and w.strip()][:hoechstens]


def _knapp(kennung: str, rolle: str, i: int | None, roh: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_id": kennung, "i": i, "rolle": rolle,
        "titel": str(roh.get("title") or "")[:200],
        "beschreibung": str(roh.get("description") or "")[:MAX_BESCHREIBUNG],
        "schlagworte": _texte(roh.get("keywords"), MAX_SCHLAGWORTE),
        "faecher": _texte(roh.get("disciplines"), _MAX_LISTE),
        "stufen": _texte(roh.get("educationalContexts"), _MAX_LISTE),
        "arten": _texte(roh.get("learningResourceTypes"), _MAX_LISTE),
        # TG-3c: die lesbare Lizenz des MCP (``FormattedNode.license``), leer ohne Angabe
        "lizenz": " ".join(str(roh.get("license") or "").split())[:_MAX_LIZENZ],
    }


def _groesse(wert: Any) -> int:
    return len(json.dumps(wert, ensure_ascii=False).encode("utf-8"))


def _teil(inhalte: list[dict[str, Any]], fehlend: list[str],
          block_id: Any = None) -> dict[str, Any]:
    teil = {"format": FORMAT, "titel": f"Metadaten zu {len(inhalte)} Inhalten",
            "inhalte": inhalte, "fehlend": fehlend}
    if isinstance(block_id, str) and block_id:
        # Review TG-3a–c, R3-2: ``i`` gilt nur für die Auswahl desselben Upload-Felds — wer
        # ``metadaten.i`` mit ``struktur`` verknüpft, prüft diese Kennung
        # (``arbeitsstand_teile.gebunden``)
        teil["block_id"] = block_id
    return teil


def _einpassen(inhalte: list[dict[str, Any]], fehlend: list[str]
               ) -> tuple[list[dict[str, Any]], list[str]]:
    """Review TB-F2, Befund 4: zuerst die Beschreibungen kürzen, dann weglassen, dann die
    Listen, zuletzt Inhalte vom Ende (Review TB-T1, Befund 6: sie kommen nach ``fehlend``) — der
    Teil bleibt für jeden Folgeschritt nutzbar. TG-3c: gemessen wird der ganze Teil samt
    ``fehlend`` (bei 500 Nodes ist ``fehlend`` selbst einige KB); vor dem Weglassen werden die
    Listen leer, die Titel kurz, und leere Felder fallen weg (Leser nehmen ``get``: so passen
    rund 500 Nodes mit kurzem Titel)."""
    schritte = [("beschreibung", lambda w: w[:100]), ("beschreibung", lambda w: "")]
    schritte += [(feld, lambda w: w[:2]) for feld in ("schlagworte", "faecher", "stufen", "arten")]
    schritte += [(feld, lambda w: []) for feld in ("schlagworte", "faecher", "stufen", "arten")]
    schritte += [("titel", lambda w: w[:80])]
    for feld, kuerzen in schritte:
        if _groesse(_teil(inhalte, fehlend)) <= _MAX_TEIL:
            return inhalte, fehlend
        inhalte = [{**i, feld: kuerzen(i[feld])} for i in inhalte]
    if _groesse(_teil(inhalte, fehlend)) > _MAX_TEIL:
        inhalte = [{k: v for k, v in i.items() if k == "node_id" or v not in ("", [], None)}
                   for i in inhalte]
    # Ein Inhalt kostet seine Zeile, kommt aber als Kennung nach ``fehlend`` — gerechnet statt je
    # Schritt neu serialisiert (500 Nodes).
    zuviel = _groesse(_teil(inhalte, fehlend)) - _MAX_TEIL
    behalten = len(inhalte)
    while behalten and zuviel > 0:
        weg = inhalte[behalten - 1]
        zuviel -= _groesse(weg) + 1 - (_groesse(weg["node_id"]) + 1)
        behalten -= 1
    fehlend = fehlend + [i["node_id"] for i in inhalte[behalten:]]
    inhalte = inhalte[:behalten]
    while inhalte and _groesse(_teil(inhalte, fehlend)) > _MAX_TEIL:   # Rundung (Titelzahl)
        fehlend = [*fehlend, inhalte[-1]["node_id"]]
        inhalte = inhalte[:-1]
    return inhalte, fehlend


async def _block(kennungen: list[str]) -> dict[str, Any] | None:
    """Ein Aufruf von ``get_nodes_details`` für höchstens :data:`BLOCK` Nodes — ``results`` oder
    ``None`` bei einem Fehler (nur die Art ins Log, nie die Antwort)."""
    from boerdi.services.mcp import client

    antwort = await client.call_mcp_tool_antwort(WERKZEUG, {"nodeIds": kennungen},
                                                 use_cache=False)
    if fehlerart := antwort.art:
        logger.info("Metadaten lesen: %s gescheitert (%s)", WERKZEUG, fehlerart)
        return None
    try:
        daten = json.loads(antwort.text)
    except ValueError:
        logger.warning("Metadaten lesen: Antwort ist kein JSON")
        return None
    ergebnisse = daten.get("results") if isinstance(daten, dict) else None
    return ergebnisse if isinstance(ergebnisse, dict) else None


async def lesen(ablage: Any) -> dict[str, Any] | None:
    """Der Teil ``wlo.metadaten@1`` zu den abgelegten Nodes — ``None`` ohne Nodes, ohne
    persönliche Anmeldung, wenn schon der erste Block scheitert oder kein Node lesbar war."""
    from boerdi.services.mcp import auth

    alle = _kennungen(ablage)
    if not alle:
        return None
    # Querschnitts-Review F/T, Befund 2: nie still weg — über :data:`MAX_NODES` steht der Rest in
    # ``fehlend`` (TG-3c: 500 statt 50, in Blöcken)
    kennungen = list(alle)[:MAX_NODES]
    gekappt = list(alle)[MAX_NODES:]
    if not auth.has_personal_auth():
        logger.info("Metadaten lesen: ohne persönliche Anmeldung, nichts gelesen")
        return None
    ergebnisse: dict[str, Any] = {}
    gelesen = 0
    for start in range(0, len(kennungen), BLOCK):
        block = await _block(kennungen[start:start + BLOCK])
        if block is None:
            # TG-3c: ein gescheiterter Block hält das Lesen an (Anmeldung, MCP weg …) — die
            # übrigen Aufrufe scheiterten meist ebenso; was fehlt, steht in ``fehlend``
            break
        ergebnisse.update(block)
        gelesen = start + BLOCK
    inhalte = [_knapp(k, *alle[k], ergebnisse[k]) for k in kennungen[:gelesen]
               if isinstance(ergebnisse.get(k), dict)]
    if not inhalte:
        # Review TB-F2, Befund 1: der Server meldet unlesbare Nodes in ``failed`` und schickt
        # ``results: {}`` — ein leerer Teil ließe den Ablauf still weiterlaufen statt ``bei_fehler``
        logger.info("Metadaten lesen: keiner von %d Nodes lesbar", len(kennungen))
        return None
    fehlend = [k for k in kennungen if not isinstance(ergebnisse.get(k), dict)] + gekappt
    inhalte, fehlend = _einpassen(inhalte, fehlend)
    return _teil(inhalte, fehlend,
                 ablage.get("block_id") if isinstance(ablage, dict) else None)


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

