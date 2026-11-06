"""Den Katalog lesen und Auslöser finden (Pakete A1/A2a) — ohne Modell, ohne I/O außer dem Lader.

- :func:`laden` / :func:`katalog`: die Einträge von ``06-ablaeufe/katalog``, die zum Modell passen.
- :func:`per_text` (Auslöser ``text``): eine **Wendung** kommt in der Nachricht vor —
  Teilzeichenkette nach :func:`pruefung.wendung` (klein, Leerraum egal), bewusst kein regulärer
  Ausdruck: Studio-Text im Zug wäre sonst ein ReDoS-Risiko.
- :func:`per_modul` (Auslöser ``modul``): eine geprüfte Antwort dieses Moduls, die den Teil
  ``wenn_teil`` bringt (``arbeitsstand.teile_aus_antwort``) → Start **nach** dem Modul-Schritt.
- :func:`vorschlaege` (Auslöser ``agent``): was die KI vorschlagen darf.
- :func:`per_knopf`: darf die Direktaktion ``ablauf_starten`` den Ablauf starten (``knopf`` oder
  ``agent`` — dessen Vorschlag ist ein Knopf)?
- :func:`erfuellt`: die Voraussetzungen (für jeden Auslöser).

Nur aktive Einträge; der erste passende gewinnt (Reihenfolge des Katalogs). Voraussetzungen prüft
der Start (``zug``).
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Final

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf.pruefung import VORAUSSETZUNGEN, modul_start, wendung
from boerdi.services.arbeitsstand import teile_aus_antwort
from boerdi.services.config_loader._store import area
from boerdi.services.mcp.auth import has_personal_auth

logger = logging.getLogger(__name__)

BEREICH: Final = "06-ablaeufe/katalog"
#: Längere Nachrichten werden nur so weit nach Wendungen durchsucht.
_TEXT_ZEICHEN: Final = 2000


_gepruefter: tuple[str, list[AblaufArea]] | None = None


def katalog() -> list[AblaufArea]:
    """Alle Einträge, die zum Modell passen (ein kaputter wird übersprungen und gemeldet). Geprüft
    wird je Speicherstand einmal (Querschnitts-Review): der Katalog wird bei jedem getippten Zug
    (Wendung) und jedem Agent-Zug gelesen."""
    global _gepruefter
    roh_liste = area(BEREICH).get("ablaeufe") or []
    schluessel = hashlib.sha256(json.dumps(roh_liste, sort_keys=True, default=str,
                                           ensure_ascii=False).encode()).hexdigest()
    if _gepruefter is not None and _gepruefter[0] == schluessel:
        return list(_gepruefter[1])
    eintraege = _pruefe(roh_liste)
    _gepruefter = (schluessel, eintraege)
    return list(eintraege)


def _pruefe(roh_liste: list[Any]) -> list[AblaufArea]:
    eintraege: list[AblaufArea] = []
    for nummer, roh in enumerate(roh_liste, start=1):
        if not isinstance(roh, dict):
            continue
        try:
            eintraege.append(AblaufArea.model_validate(roh))
        except ValueError:
            logger.warning("Ablauf Nr. %d im Katalog passt nicht zum Modell", nummer)
    return eintraege


def erfuellt(ablauf: AblaufArea) -> bool:
    """Sind die Voraussetzungen erfüllt? Eine unbekannte gilt als nicht erfüllt (Review A1, 8)."""
    if any(v not in VORAUSSETZUNGEN for v in ablauf.voraussetzungen):
        logger.warning("Ablauf: unbekannte Voraussetzung — startet nicht")
        return False
    return "anmeldung" not in ablauf.voraussetzungen or has_personal_auth()


def laden(ablauf_id: Any) -> AblaufArea | None:
    """Der Eintrag ``ablauf_id`` — ``None``, wenn es ihn nicht gibt oder er nicht passt."""
    if not isinstance(ablauf_id, str) or not ablauf_id.isidentifier():
        return None
    return next((a for a in katalog() if a.id == ablauf_id), None)


def _aktive(art: str) -> list[tuple[AblaufArea, Any]]:
    return [(a, aus) for a in katalog() if a.aktiv for aus in a.ausloeser if aus.art == art]


def per_text(nachricht: str | None) -> AblaufArea | None:
    text = wendung((nachricht or "")[:_TEXT_ZEICHEN])
    if not text:
        return None
    for ablauf, aus in _aktive("text"):
        if any((w := wendung(roh)) and w in text for roh in aus.wendungen):
            return ablauf
    return None


def per_modul(geprueft: dict[str, Any] | None) -> tuple[AblaufArea, int] | None:
    """Ablauf und Startschritt für eine geprüfte Modul-Antwort (``None``: kein Auslöser passt)."""
    if not geprueft or not isinstance(modul := geprueft.get("modul"), str):
        return None
    passend = [(a, aus) for a, aus in _aktive("modul") if aus.modul == modul]
    if not passend:
        return None
    teile = {t[0] for t in teile_aus_antwort(geprueft)}
    for ablauf, aus in passend:
        ab = modul_start(ablauf, modul)
        if ab is not None and (aus.wenn_teil is None or aus.wenn_teil in teile):
            return ablauf, ab
    return None


def per_knopf(ablauf: AblaufArea) -> bool:
    """Review A2a (Vorbefund aus A1): die Liste der Auslöser gilt auch für den Knopf."""
    return ablauf.aktiv and any(a.art in ("knopf", "agent") for a in ablauf.ausloeser)


def vorschlaege() -> list[AblaufArea]:
    """Aktive Abläufe mit dem Auslöser ``agent`` (je einmal), deren Voraussetzungen erfüllt sind —
    die KI schlägt nichts vor, was der Knopf dann abwiese (Review A2a, Befund 4)."""
    gesehen: dict[str, AblaufArea] = {}
    for ablauf, _aus in _aktive("agent"):
        if ablauf.id not in gesehen and erfuellt(ablauf):
            gesehen[ablauf.id] = ablauf
    return list(gesehen.values())
