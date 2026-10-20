"""Der geteilte Stand des Master-Skills (Paket 17, C3): eine Zeile je Kennung.

Eine Kopie, die unter :data:`SPERRE` abgefragt hat, schreibt hier ihren Stand und meldet ihn
über die NOTIFY-Bahn der Konfiguration (``config_changed`` mit :data:`SIGNAL`); die übrigen
lesen die Zeile (``services/master_skill``). Nur Datenzugriff — wann geholt und übernommen
wird, entscheidet ``master_skill``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

#: Sperre der Abfrage, über alle Kopien (``services/sitzungssperre``).
SPERRE: Final = "__lauf:master-skill"
#: Nutzlast auf ``config_changed``. Der Vorsatz ``__`` sagt dem ConfigStore: Signal, kein
#: Bereich (``ConfigStore._on_area_changed``).
SIGNAL: Final = "__master_skill"


@dataclass(frozen=True)
class Stand:
    text: str | None
    abgerufen_um: datetime | None
    letzter_fehler: str | None
    #: Sekunden seit dem letzten Versuch — von der Datenbank gerechnet, damit abweichende
    #: Uhren der Kopien nichts verschieben.
    alter_s: float
    #: Zeitpunkt des letzten Versuchs (Uhr der Datenbank) — ordnet Stände: ein früher
    #: gelesener überschreibt keinen später geschriebenen. ``None`` = nicht aus der Zeile.
    geprueft_um: datetime | None = None


_LIES = text(
    "SELECT text, abgerufen_um, letzter_fehler, "
    "EXTRACT(EPOCH FROM now() - geprueft_um)::float8, geprueft_um "
    "FROM master_skill_stand WHERE node_id = :k"
)
_SCHREIB = text(
    "INSERT INTO master_skill_stand (node_id, text, abgerufen_um, letzter_fehler, geprueft_um) "
    "VALUES (:k, :t, :a, :f, now()) "
    "ON CONFLICT (node_id) DO UPDATE SET text = EXCLUDED.text, "
    "abgerufen_um = EXCLUDED.abgerufen_um, letzter_fehler = EXCLUDED.letzter_fehler, "
    "geprueft_um = now() RETURNING geprueft_um"
)
_MELDE = text("SELECT pg_notify('config_changed', :s)")


async def lies(engine: AsyncEngine, kennung: str) -> Stand | None:
    async with engine.connect() as conn:
        zeile = (await conn.execute(_LIES, {"k": kennung})).first()
    if zeile is None:
        return None
    return Stand(text=zeile[0], abgerufen_um=zeile[1], letzter_fehler=zeile[2],
                 alter_s=float(zeile[3]), geprueft_um=zeile[4])


async def schreibe(engine: AsyncEngine, kennung: str, *, text_: str | None,
                   abgerufen_um: datetime | None, letzter_fehler: str | None) -> datetime:
    """Den Stand ablegen und melden — in einer Transaktion, das Signal geht mit dem Commit.
    Gibt den Zeitpunkt des Versuchs nach der Uhr der Datenbank zurück."""
    async with engine.begin() as conn:
        geprueft = (await conn.execute(_SCHREIB, {"k": kennung, "t": text_, "a": abgerufen_um,
                                                  "f": letzter_fehler})).scalar_one()
        await conn.execute(_MELDE, {"s": SIGNAL})
    return geprueft
