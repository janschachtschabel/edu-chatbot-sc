"""Der Auszug des Dokuments für Ebene 2 eines Strukturentwurfs — geprüft, bevor er ans Modell geht.

Querschnitts-Review 2026-11-06: die Moderation beim Hochladen sieht nur Übersicht und Anfang des
Dokuments (``dokumente/aufnahme``); Ebene 2 schickt aber den Text von Abschnitten beliebiger Stelle
(je Punkt höchstens ``DOKUMENT_AUSZUG`` Zeichen). Jeder Auszug geht deshalb einmal durch die
Moderation:

- **je Text einmal**, auch wenn zwei Punkte zugleich denselben Auszug brauchen (die laufende
  Prüfung wird geteilt; Review Q4, Befund 2) — gleicher Text, gleiches Urteil;
- **ein Platz je Entwurf**: die Moderation teilt ihre Plätze (``MODERATION_PARALLEL``) mit den
  Chat-Zügen aller Personen; ein Entwurf prüft nacheinander (Review Q4, Befund 1). Gezählt wird
  unter eigener Stufe (``strukturentwurf_auszug``), nicht im Alarm der Züge;
- beanstandet → kein Auszug (der Punkt entsteht aus Titel und Gliederung);
- kein Urteil (Ausfall) → wie bei Nachrichten entscheidet ``MODERATION_FAILURE_MODE``: ``closed``
  schickt nichts, ``open`` schickt ihn ungeprüft — protokolliert einmal je Entwurf (Befund 3).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from boerdi.domain.dokument_gliederung import abschnitt_text, mit_unterabschnitten
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

Moderieren = Callable[[str], Awaitable[dict[str, Any]]]


class Auszuege:
    def __init__(self, dokument: Any, grenze: int, moderieren: Moderieren | None) -> None:
        self.dokument, self.grenze, self.moderieren = dokument, grenze, moderieren
        self._gemerkt: dict[str, asyncio.Task[str]] = {}
        self._platz = asyncio.Semaphore(1)
        self._ungeprueft_gemeldet = False

    def roh(self, knoten: dict[str, Any]) -> str:
        """Der Text des Dokuments zu ``knoten`` — leer ohne Dokument oder ohne Abschnitte."""
        if self.dokument is None or not knoten.get("abschnitte"):
            return ""
        ids = mit_unterabschnitten(self.dokument.abschnitte, knoten["abschnitte"])
        return abschnitt_text(self.dokument.markdown, self.dokument.abschnitte, ids, self.grenze)

    async def fuer(self, knoten: dict[str, Any]) -> str:
        """Der geprüfte Auszug (leer, wenn er nicht ans Modell darf)."""
        text = self.roh(knoten)
        if not text or self.moderieren is None:
            return text
        schluessel = hashlib.sha256(text.encode()).hexdigest()
        if schluessel not in self._gemerkt:
            self._gemerkt[schluessel] = asyncio.ensure_future(self._pruefe(text))
        # ``shield``: bricht ein wartender Punkt ab (Frist), bleibt die Prüfung für die anderen.
        return await asyncio.shield(self._gemerkt[schluessel])

    async def _pruefe(self, text: str) -> str:
        # Alles im ``try``: wartet niemand mehr (Frist), läse sonst keiner eine Ausnahme der
        # geteilten Prüfung ab (Nachprüfung Q4, Befund 4); ein Urteil, das kein Dict ist, gilt wie
        # keins.
        async with self._platz:
            try:
                urteil = await self.moderieren(text) if self.moderieren is not None else {}
            except Exception as fehler:  # noqa: BLE001 — wie ein fehlendes Urteil
                logger.warning("Strukturentwurf: Moderation des Auszugs gescheitert (%s)",
                               type(fehler).__name__)
                urteil = {}
        if not isinstance(urteil, dict):
            urteil = {}
        if urteil.get("flagged"):
            logger.info("Strukturentwurf: Auszug von der Moderation abgewiesen")
            return ""
        if not urteil:
            if get_settings().moderation_failure_mode == "closed":
                return ""
            if not self._ungeprueft_gemeldet:
                logger.warning("Strukturentwurf: Auszüge ohne Moderation verwendet")
                self._ungeprueft_gemeldet = True
        return text
