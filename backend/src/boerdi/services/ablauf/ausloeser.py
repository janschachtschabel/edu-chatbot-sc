"""Den Katalog lesen und Auslöser finden (Pakete A1/A2a) — ohne Modell, ohne I/O außer dem Lader.

- :func:`laden` / :func:`katalog`: die Abläufe aus ``06-ablaeufe/<id>`` (ein Dokument je Ablauf
  seit AS-0), die zum Modell passen — in der Reihenfolge der Schlüssel.
- :func:`per_text` (Auslöser ``text``): eine **Wendung** kommt in der Nachricht vor —
  Teilzeichenkette nach :func:`pruefung.wendung` (klein, Leerraum egal), bewusst kein regulärer
  Ausdruck: Studio-Text im Zug wäre sonst ein ReDoS-Risiko.
- :func:`per_modul` (Auslöser ``modul``): eine geprüfte Antwort dieses Moduls, die den Teil
  ``wenn_teil`` bringt (``arbeitsstand.teile_aus_antwort``) → Start **nach** dem Modul-Schritt.
- :func:`vorschlaege` (Auslöser ``agent``): was die KI vorschlagen darf.
- :func:`per_knopf`: darf die Direktaktion ``ablauf_starten`` den Ablauf starten (``knopf``,
  ``agent`` — dessen Vorschlag ist ein Knopf —, seit AS-7b ``seite``: der Chip unter der Begrüßung)?
- :func:`seiten_angebote` (Auslöser ``seite``, AS-7b): was das Widget unter der Begrüßung anbietet,
  wenn die Seite passt — der Abgleich läuft im Widget (Plan 2026-11-09 §5m, F-7).
- :func:`erfuellt`: die Voraussetzungen (für jeden Auslöser).

Nur aktive Einträge; der erste passende gewinnt (Reihenfolge der Schlüssel — fest, damit dieselbe
Wendung nicht je nach Ladereihenfolge einen anderen Ablauf startet; das Studio warnt bei gleichen
Wendungen, ``pruefung.wendungs_warnungen``). Voraussetzungen prüft der Start (``zug``).
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Final

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import startdaten
from boerdi.services.ablauf.pruefung import VORAUSSETZUNGEN, modul_start, wendung
from boerdi.services.arbeitsstand import teile_aus_antwort
from boerdi.services.config_loader._store import area, cached_keys
from boerdi.services.mcp.auth import has_personal_auth

logger = logging.getLogger(__name__)

#: Der Ordner der Abläufe (``domain/config_models/ablauf.ORDNER``) samt Trenner.
PRAEFIX: Final = "06-ablaeufe/"
#: Längere Nachrichten werden nur so weit nach Wendungen durchsucht.
_TEXT_ZEICHEN: Final = 2000


_gepruefter: tuple[str, list[AblaufArea]] | None = None


def katalog() -> list[AblaufArea]:
    """Alle Einträge, die zum Modell passen (ein kaputter wird übersprungen und gemeldet). Geprüft
    wird je Speicherstand einmal (Querschnitts-Review): der Katalog wird bei jedem getippten Zug
    (Wendung) und jedem Agent-Zug gelesen."""
    global _gepruefter
    roh_liste = _roh_liste()
    schluessel = hashlib.sha256(json.dumps(roh_liste, sort_keys=True, default=str,
                                           ensure_ascii=False).encode()).hexdigest()
    if _gepruefter is not None and _gepruefter[0] == schluessel:
        return list(_gepruefter[1])
    eintraege = _pruefe(roh_liste)
    _gepruefter = (schluessel, eintraege)
    return list(eintraege)


def _roh_liste() -> list[Any]:
    """Die gespeicherten Ablauf-Dokumente, nach Schlüssel sortiert (``cached_keys`` sortiert) —
    ohne ihre Testfälle: die Laufzeit liest sie nie, und ein Testteil, der nicht mehr zum Modell
    passt, nähme sonst den echten Ablauf aus der Laufzeit (Querschnitts-Review AS-0…AS-2)."""
    return [_ohne_tests(area(key)) for key in cached_keys(PRAEFIX)]


def _ohne_tests(roh: Any) -> Any:
    return {k: v for k, v in roh.items() if k != "tests"} if isinstance(roh, dict) else roh


def _pruefe(roh_liste: list[Any]) -> list[AblaufArea]:
    eintraege: list[AblaufArea] = []
    for nummer, roh in enumerate(roh_liste, start=1):
        if not isinstance(roh, dict) or not roh:
            continue
        try:
            eintraege.append(AblaufArea.model_validate(roh))
        except ValueError:
            # nur die Stelle (nach Schlüssel sortiert): die Kennung ist Inhalt der Redaktion, und
            # Logs tragen keine Inhalte (``tests/test_log_ohne_inhalt``)
            logger.warning("Ablauf-Dokument Nr. %d passt nicht zum Modell", nummer)
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
    """Aktive Abläufe mit Auslösern der Art ``art``. Ein Ablauf mit Pflichtfeldern in den
    Startdaten startet nur mit Daten — von der Gastseite oder (AS-5a) durch die KI. Wendung und
    Modul bringen nie Daten und wählen ihn deshalb gar nicht erst (Review AS-4a, Befund 1: sonst
    nur eine Abweisung, beim Modul nach dem Anlegen eines Vorgangs)."""
    return [(a, aus) for a in katalog() if a.aktiv
            and (art in _MIT_DATEN or not startdaten.pflichtfelder(a))
            for aus in a.ausloeser if aus.art == art]


#: Auslöser, die Startdaten bringen: die Gastseite (AS-4a) und seit AS-5a die KI (Werkzeug
#: ``ablauf-<id>``, gestartet per Knopf).
_MIT_DATEN: Final = frozenset({"extern", "agent"})


def nimmt_daten(ablauf: AblaufArea) -> bool:
    """Darf ein Start dieses Ablaufs Startdaten bringen (Auslöser ``extern`` oder ``agent``)?"""
    return ablauf.aktiv and any(a.art in _MIT_DATEN for a in ablauf.ausloeser)


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


def per_extern(ablauf: AblaufArea) -> bool:
    """AS-4a: Start von der Gastseite (Widget-API, Attribut) — nur so mit Startdaten."""
    return ablauf.aktiv and any(a.art == "extern" for a in ablauf.ausloeser)


def per_knopf(ablauf: AblaufArea) -> bool:
    """Review A2a (Vorbefund aus A1): die Liste der Auslöser gilt auch für den Knopf."""
    return ablauf.aktiv and any(a.art in ("knopf", "agent", "seite") for a in ablauf.ausloeser)


def seiten_angebote() -> list[dict[str, Any]]:
    """AS-7b (F-7): aktive Abläufe mit Auslöser ``seite`` — Kennung, Titel je Sprache und die Muster
    (aller ``seite``-Auslöser). Öffentlich im Boot-Bündel des Widgets; nur, was die Redaktion als
    Angebot gemeint hat, keine Schritte."""
    angebote: dict[str, dict[str, Any]] = {}
    for ablauf, aus in _aktive("seite"):
        if "anmeldung" in ablauf.voraussetzungen:
            # Querschnitts-Review AS-7, Befund 5: das Boot-Bündel kennt die Anmeldung nicht — ein
            # Chip, der anonym nur abgewiesen würde, steht gar nicht erst da
            continue
        eintrag = angebote.setdefault(ablauf.id, {"id": ablauf.id, "titel": dict(ablauf.titel),
                                                  "muster": []})
        eintrag["muster"] += [m for m in aus.muster if m not in eintrag["muster"]]
    return list(angebote.values())


def vorschlaege() -> list[AblaufArea]:
    """Aktive Abläufe mit dem Auslöser ``agent`` (je einmal), deren Voraussetzungen erfüllt sind —
    die KI schlägt nichts vor, was der Knopf dann abwiese (Review A2a, Befund 4)."""
    gesehen: dict[str, AblaufArea] = {}
    for ablauf, _aus in _aktive("agent"):
        if ablauf.id not in gesehen and erfuellt(ablauf):
            gesehen[ablauf.id] = ablauf
    return list(gesehen.values())
