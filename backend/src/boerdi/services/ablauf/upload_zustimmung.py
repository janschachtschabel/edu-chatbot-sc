"""Plan 2026-11-20, P3 (Nutzer-Entscheid UO-3): der Upload-Klick als Zustimmung zum Flow.

Ein ``auftrag``-Schritt mit ``repo_schreibt`` startet sonst erst nach der Freigabe-Box (Paket N4).
Mit ``zustimmung: upload`` gilt der Klick „In WLO ablegen und erschließen“ als Zustimmung — aber
nur, wenn der Server es hier nachweist (:func:`passt`), sonst kommt die Box wie bisher
(fail closed; nie ein Start ohne Zustimmung, nie ein stiller Fehler):

- eine **persönliche Anmeldung** in diesem Zug;
- der Teil ``ablage`` mit dem Häkchen (``erschliessen`` genau ``True`` — der Server hielt es beim
  Vorbereiten nur fest, wenn der Metadaten-Flow startbar war);
- **derselbe Aufrufer**: die Marke ``aufrufer`` im Teil (``vorgang_teil.aufrufer_marke``) ist die
  dieses Zugs;
- **nur der Metadaten-Flow** (Review P3, Befund 1): jeder andere schreibende Flow bekommt die Box;
- **dieser Lauf**: der Teil stammt aus dem Upload-Block, den der Lauf zuletzt mit einer fertigen
  Ablage in WLO beantwortet hat (:data:`BLOCK` im Lauf, gesetzt von ``treiber.weiter`` nach
  :func:`bindet`) — ein Direktstart ab dem Auftrag, ein Modul-Auslöser oder ein neu gestarteter
  Lauf hat keinen und bekommt die Box; nach dem Start ohne Box ist der Block verbraucht (Befund 2);
- **nur frische Knoten**: jede ``node_id`` (nicht leer) steht in den aktuellen ``inhalte`` mit
  ``stand: stored`` und ``neu: true`` und nicht in ``frueher``; die freigegebenen Teile der
  MCP-Vorschau sind Teilmengen davon, und die Vorschau meldet keine Probleme (nur die Box zeigt
  sie).

Kein Zeitlimit: die Bindung an den Upload-Block des Laufs ist enger als eine Uhr (ein neuer Upload
ersetzt den Teil, ein neuer Lauf hat keinen Block). Die Gründe stehen im Log, ohne Kennungen.
"""

from __future__ import annotations

import logging
from typing import Any, Final

from boerdi.domain.config_models.kestra_flows import METADATEN_FLOW
from boerdi.services.ablage import vorgang_teil
from boerdi.services.ablauf.auftrag_teile import KNOTEN_LISTE
from boerdi.services.mcp.auth import has_personal_auth

logger = logging.getLogger(__name__)

#: Der Wert am Auftragsschritt (``Schritt.zustimmung``).
UPLOAD: Final = "upload"
#: Der Upload-Block, den der Lauf zuletzt beantwortet hat (Schlüssel im Lauf).
BLOCK: Final = "upload_block"
#: Zweites Review P3, NIT 3: Vermerk am Lauf, dass der laufende Auftrag ohne Box startete
#: (Wert :data:`UPLOAD`) — für spätere Prüfung; ein Start nach der Box löscht ihn.
ZUSTIMMUNG: Final = "auftrag_zustimmung"


def _grund(ablage: Any, block_id: Any, node_ids: Any) -> str | None:
    """Warum der Upload nicht als Zustimmung gilt — ``None``, wenn er gilt."""
    if not has_personal_auth():
        return "ohne_anmeldung"
    if not isinstance(ablage, dict) or ablage.get("format") != vorgang_teil.TYP:
        return "ohne_ablage"
    if ablage.get("erschliessen") is not True:
        return "ohne_haekchen"
    if not isinstance(block_id, str) or not block_id or ablage.get("block_id") != block_id:
        return "anderer_block"
    marke = vorgang_teil.aufrufer_marke()
    if not marke or ablage.get("aufrufer") != marke:
        return "anderer_aufrufer"
    if (not isinstance(node_ids, list) or not node_ids
            or not all(isinstance(n, str) and n for n in node_ids)):
        return "ohne_knoten"
    frisch = {e["node_id"] for e in ablage.get("inhalte") or []
              if isinstance(e, dict) and e.get("stand") == "stored" and e.get("neu") is True
              and isinstance(e.get("node_id"), str)}
    frueher = {e.get("node_id") for e in ablage.get("frueher") or [] if isinstance(e, dict)}
    if not set(node_ids) <= frisch or set(node_ids) & frueher:
        return "fremde_knoten"
    return None


def wlo_antwort(antwort: Any) -> bool:
    """Ist die Antwort am Upload-Schritt eine Ablage in WLO (``bereitgestellt`` mit ``ort: wlo``
    oder die ältere Form ``uebertragen``) — auch eine angehaltene? Zweites Review P4–P6, MINOR 1:
    jede andere Antwort („Nur hier im Chat lesen“, „Nur die Dateinamen senden“) nimmt den Weg ohne
    WLO (``treiber.weiter`` löst die Marke ``abgelegt_block`` des Blocks)."""
    return isinstance(antwort, dict) and (
        (antwort.get("aktion") == "bereitgestellt" and antwort.get("ort") == "wlo")
        or antwort.get("aktion") == "uebertragen")


def bindet(antwort: Any) -> bool:
    """Review P3, Befund 3: bindet die Antwort am Upload-Schritt den Lauf an ihren Block? Nur eine
    fertige Ablage in WLO (:func:`wlo_antwort`), bei der nichts angehalten wurde
    (``ablage.abgebrochen`` 0) — nicht „Hier im Chat“ oder „nur Namen“ nach einer teilweisen
    Ablage, nicht „Anhalten“. Angabe des Browsers: nur eine notwendige Bedingung; den Nachweis
    führt der Teil ``ablage`` (:func:`gilt`)."""
    ablage = antwort.get("ablage") if isinstance(antwort, dict) else None
    return wlo_antwort(antwort) and isinstance(ablage, dict) and ablage.get("abgebrochen") == 0


def gilt(ablage: Any, block_id: Any, node_ids: Any) -> bool:
    """Gilt der Upload-Klick als Zustimmung für ``node_ids``? ``block_id``: der Upload-Block, den
    der Lauf zuletzt beantwortet hat (:data:`BLOCK`)."""
    if (grund := _grund(ablage, block_id, node_ids)) is not None:
        logger.info("Zustimmung durch Upload gilt nicht (%s) — Freigabe-Box", grund)
        return False
    return True


def passt(s: Any, args: dict[str, Any], vorlage: Any, ablage: Any, lauf: dict[str, Any]) -> bool:
    """Darf der Auftragsschritt ``s`` nach der Vorschau ``vorlage`` ohne Box starten? ``args``:
    die eingesetzten Argumente aller Teile."""
    if getattr(s, "zustimmung", None) != UPLOAD or not getattr(s, "repo_schreibt", False):
        return False
    if getattr(s, "flow", None) != METADATEN_FLOW:
        # Befund 1: der Upload-Klick sagt nur „Metadaten erzeugen“ — kein anderer Flow
        logger.info("Zustimmung durch Upload gilt nicht (anderer_flow) — Freigabe-Box")
        return False
    if vorlage.probleme:
        logger.info("Zustimmung durch Upload gilt nicht (probleme) — Freigabe-Box")
        return False
    liste = s.aufteilen.argument if s.aufteilen is not None else KNOTEN_LISTE
    ids = args.get(liste)
    if not gilt(ablage, lauf.get(BLOCK), ids):
        return False
    alle = set(ids)
    for teil in (vorlage.args, vorlage.erst):
        gewaehlt = teil.get(liste) if isinstance(teil, dict) else None
        if not isinstance(gewaehlt, list) or not gewaehlt or not set(gewaehlt) <= alle:
            logger.info("Zustimmung durch Upload gilt nicht (vorschau) — Freigabe-Box")
            return False
    return True
