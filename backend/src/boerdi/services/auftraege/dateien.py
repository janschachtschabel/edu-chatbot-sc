"""Dateien eines fertigen Auftrags holen und als Text lesbar machen (Paket K2d-2, Entscheid F3).

Nur die Dateien, die der Schritt nennt (``dateien_holen: [outputId]``, höchstens
:data:`MAX_DATEIEN`), und nur solange die B-API sie als abrufbar führt. Geholt wird mit dem
Schlüssel des Zuges (:func:`client.datei`, die Adresse bildet der Client aus Job-ID und Kennung),
höchstens so viel, wie ein Upload darf (Studio „Upload“, ``max_mb``).

Jede Datei geht durch **dieselbe Aufbereitung wie ein Upload** (``dokumente.aufnahme``: Art nach
Magic Bytes, Umwandlung im Kindprozess, Moderation, Befund) — ein Flow ist ein fremder Dienst, sein
Ergebnis so wenig vertrauenswürdig wie eine hochgeladene Datei. Zurück kommt der Markdown-Text
je Kennung (gekürzt auf :data:`MAX_ZEICHEN`) und je fehlender Datei ein Code — nie ein Text des
Servers.

Review K2d-2:
- Alles zusammen hält eine Frist (:data:`GESAMT_FRIST_S`, unter der Lesefrist des Ingress); was
  danach noch fehlt, bekommt ``zu_langsam`` (Befund 3).
- Nach ``schluessel_abgewiesen`` oder ``voll`` holt die Schleife mit demselben Schlüssel nichts
  mehr — der Rest bekommt denselben Code (Befund 4).
- Ein abgewiesener Schlüssel heißt ``schluessel_abgewiesen``, ein Treffer der Moderation
  ``abgewiesen`` wie beim Upload (Befund 5).
- :data:`VORUEBERGEHEND`: Codes, nach denen „Stand prüfen“ es noch einmal versucht, statt das
  Ergebnis ohne die Datei festzuschreiben (``auftrag_zug``, Befund 1).

Zweites Review K2d-2:
- Auch ``pruefung_fehlt`` (die Moderation war nicht erreichbar) ist vorübergehend (Befund 1).
- Die Frist gilt auch für die Aufbereitung — mit dem Warten auf ihren Platz und der Moderation
  (Befund 2); abgebrochen wird nur das Warten, der Kindprozess hält seinen Platz bis zur Frist.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import time
from typing import Any, Final

from boerdi.services.auftraege import client
from boerdi.services.config_loader.upload import load_upload_config
from boerdi.services.dokumente.aufnahme import Abweisung, Aufbereitet, aufbereiten
from boerdi.services.safety.moderation import moderate

__all__ = ["GESAMT_FRIST_S", "MAX_DATEIEN", "MAX_ZEICHEN", "VORUEBERGEHEND", "Abweisung",
           "Aufbereitet", "holen", "max_bytes"]

logger = logging.getLogger(__name__)

#: So viele Dateien holt ein Schritt höchstens.
MAX_DATEIEN: Final = 3
#: So viel Text einer Datei kommt in den Teil (die Akte legt große Teile in die Ablage). Ein
#: Werkzeug der KI bekommt davon höchstens ``teil_verweise.MAX_BYTES`` (Review K2d-2, Befund 2).
MAX_ZEICHEN: Final = 200_000
#: Frist der Umwandlung einer Datei — wie beim Upload.
FRIST_S: Final = 30.0
#: Frist eines Downloads.
DOWNLOAD_FRIST_S: Final = 30.0
#: Frist für alle Dateien eines Klicks, Download und Aufbereitung zusammen — mit der Abfrage des
#: Stands davor unter der Lesefrist des Ingress (120 s, ``deploy/helm``).
GESAMT_FRIST_S: Final = 60.0
#: Nach diesen Codes versucht „Stand prüfen“ es erneut (sie sagen nichts über die Datei).
VORUEBERGEHEND: Final = frozenset({"voll", "fehler", "ausgelastet", "zu_langsam",
                                   "pruefung_fehlt"})
#: Nach diesen Codes geht keine weitere Anfrage mit demselben Schlüssel hinaus.
_SCHLUSS: Final = frozenset({"schluessel_abgewiesen", "voll"})
_MIB: Final = 1024 * 1024


def max_bytes() -> int:
    """Größte Datei, die geholt wird — die Grenze eines Uploads (Studio, ``max_mb``)."""
    return load_upload_config().max_mb * _MIB


def _grund(fehler: client.AuftragFehler) -> str:
    return "schluessel_abgewiesen" if fehler.grund == "abgewiesen" else fehler.grund


async def holen(job_id: str, dateien: list[dict[str, Any]], kennungen: list[str], *,
                frist_s: float = GESAMT_FRIST_S) -> tuple[dict[str, str], dict[str, str]]:
    """``(texte, fehlen)``: der Text je geholter Kennung und je anderer ein Code
    (``unbekannt``, ``nicht_verfuegbar``, ``zu_gross``, ``zu_langsam``, ``schluessel_abgewiesen``,
    ``voll``, ``fehler`` und die Codes der Aufbereitung wie beim Upload)."""
    texte: dict[str, str] = {}
    fehlen: dict[str, str] = {}
    if not kennungen:
        return texte, fehlen
    cfg = load_upload_config()
    grenze = max_bytes()
    ende = time.monotonic() + frist_s
    bekannt = {d.get("kennung"): d for d in dateien if isinstance(d.get("kennung"), str)}
    schluss: str | None = None
    for kennung in dict.fromkeys(kennungen[:MAX_DATEIEN]):
        eintrag = bekannt.get(kennung)
        rest = ende - time.monotonic()
        if eintrag is None:
            fehlen[kennung] = "unbekannt"
        elif eintrag.get("verfuegbar") is False:
            fehlen[kennung] = "nicht_verfuegbar"
        elif isinstance(eintrag.get("groesse"), int) and eintrag["groesse"] > grenze:
            fehlen[kennung] = "zu_gross"
        elif schluss is not None:
            fehlen[kennung] = schluss
        elif rest <= 1:
            fehlen[kennung] = "zu_langsam"
        else:
            code = await _eine(job_id, kennung, eintrag, grenze, cfg.max_seiten, rest, texte)
            if code is not None:
                fehlen[kennung] = code
                if code in _SCHLUSS:
                    schluss = code
    return texte, fehlen


async def _eine(job_id: str, kennung: str, eintrag: dict[str, Any], grenze: int, max_seiten: int,
                rest: float, texte: dict[str, str]) -> str | None:
    """Eine Datei holen und aufbereiten — ``None`` (Text in ``texte``) oder der Code."""
    beginn = time.monotonic()
    try:
        rumpf = await asyncio.wait_for(client.datei(job_id, kennung, grenze),
                                       timeout=min(DOWNLOAD_FRIST_S, rest))
    except TimeoutError:
        return "zu_langsam"
    except client.AuftragFehler as fehler:
        return _grund(fehler)
    rest -= time.monotonic() - beginn
    if rest <= 1:
        return "zu_langsam"
    try:
        # Zweites Review K2d-2, Befund 2: die Frist deckt auch das Warten auf den Platz der
        # Umwandlung, ihren Puffer und die Moderation — sonst dauerte ein Klick bis ~90 s.
        async with asyncio.timeout(rest):
            erg = await aufbereiten(rumpf, str(eintrag.get("name") or ""), max_seiten=max_seiten,
                                    frist_s=min(FRIST_S, rest),
                                    moderieren=functools.partial(moderate, stufe="auftrag_datei"))
    except TimeoutError:
        return "zu_langsam"
    if isinstance(erg, Abweisung):
        logger.info("Auftrag: Datei nicht übernommen (%s)", erg.code)
        return erg.code
    texte[kennung] = erg.markdown[:MAX_ZEICHEN]
    return None
