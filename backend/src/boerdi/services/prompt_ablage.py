"""Ablage der festen Prompt-Bausteine (Paket 13, A5).

Während eines Zuges merkt ``merke`` Prüfsumme und Text im Prozess und trägt die Prüfsumme in den
Merkposten des Zuges (``acc["prompts"][art]``) — so steht im Debug-Block und in jedem Eval-Zug,
mit welcher Fassung geantwortet wurde. Am Zugende schreibt ``speichere`` neue Fassungen in
``prompt_versions``, auf der Sitzung der Anfrage, wie ``usage_store`` mit SAVEPOINT.

**Nur feste Teile.** Gemerkt werden Agent-Kopf, Master-Skill, Seitenregeln und der feste
Klassifikator-Prompt — Texte, die nicht von Nachricht, Verlauf oder Seite abhängen. Die
Muster-Antwortprompts tragen erkannte Entitäten (Nutzertext); ihre festen Schichten sind
Konfigurationsbereiche und stehen schon im Fingerabdruck des Laufs (``eval/fingerprint``).

**Ein Schreibfehler darf den Zug nie scheitern lassen** — geloggt, nicht geworfen.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

#: Gemerkt, noch nicht geschrieben: Prüfsumme → (Art, Text).
_OFFEN: dict[str, tuple[str, str]] = {}
#: In diesem Prozess schon geschrieben — der nächste Zug schreibt sie nicht noch einmal.
_GESCHRIEBEN: set[str] = set()
#: Deckel der offenen Ablage: hängt das Schreiben (DB weg), wächst sie nicht ohne Ende.
_MAX_OFFEN = 64

#: ``zuletzt`` heißt „zuletzt von einem Prozess geschrieben“, nicht „zuletzt benutzt“: jeder Prozess
#: schreibt eine Fassung nur einmal (``_GESCHRIEBEN``) — genauer bräuchte es eine Schreibung je Zug,
#: und die Spalte trägt nichts, das das Studio heute liest (Review PR #18).
_UPSERT = text("""
    INSERT INTO prompt_versions (hash, art, text) VALUES (:hash, :art, :text)
    ON CONFLICT (hash) DO UPDATE SET zuletzt = now()
""")


def pruefsumme(inhalt: str) -> str:
    """Gekürzte SHA-256 des Textes (12 Zeichen wie die übrigen Prüfsummen eines Laufs)."""
    return hashlib.sha256(inhalt.encode("utf-8")).hexdigest()[:12]


def merke(acc: dict[str, Any] | None, art: str, inhalt: str | None) -> str | None:
    """Den Baustein ``art`` für diesen Zug vermerken; Rückgabe: die Prüfsumme oder ``None``."""
    if not inhalt:
        return None
    h = pruefsumme(inhalt)
    if h not in _GESCHRIEBEN and h not in _OFFEN and len(_OFFEN) < _MAX_OFFEN:
        _OFFEN[h] = (art, inhalt)
    if acc is not None:
        acc.setdefault("prompts", {})[art] = h
    return h


async def speichere(session: AsyncSession, acc: dict[str, Any] | None) -> int:
    """Die neuen Fassungen dieses Zuges schreiben; Rückgabe: geschriebene Zeilen."""
    hashes = set(((acc or {}).get("prompts") or {}).values())
    neu = [(h, *_OFFEN[h]) for h in sorted(hashes) if h in _OFFEN]
    if not neu:
        return 0
    try:
        async with session.begin_nested():
            for h, art, inhalt in neu:
                await session.execute(_UPSERT, {"hash": h, "art": art, "text": inhalt})
        await session.commit()
    except Exception:
        logger.warning("Prompt-Fassungen nicht geschrieben", exc_info=True)
        try:
            await session.rollback()
        except Exception:
            logger.debug("prompt_ablage: rollback ebenfalls fehlgeschlagen", exc_info=True)
        return 0
    for h, _art, _inhalt in neu:
        _OFFEN.pop(h, None)
        _GESCHRIEBEN.add(h)
    return len(neu)
