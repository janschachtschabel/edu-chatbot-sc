"""Die eine Weiche für asynchrone Modul-Aufrufe (Paket U2, Plan 2026-11-04 T-4).

Zwei Wege führen zu Block-Daten, die nicht durch das Modell laufen: die **Datenquelle** (ein
MCP-Werkzeug, ``ui_module/datenquelle``, U1-e) und der **Dienst** (das Backend erzeugt sie,
``ui_module/dienst``, U2). Die Schleifen fragen ``werkzeuge.ist_asynchron`` und rufen hier — so
kennt keine Schleife die Wege einzeln.

:class:`Umgebung` trägt, was ein Dienst vom Zug braucht: den Token-Zähler (Buchung wie jeder
LLM-Aufruf des Zugs), das Fristende des Laufs (Zeit der Ereignisschleife, ``agent_frist``) und
den Entwurf, den die Person mit dieser Nachricht geschickt hat (``vorlage``) und — seit U3-2b —
den Lader für das Dokument der Sitzung (``dokument``, ``services/dokumente/stand``).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from boerdi.ui_module import datenquelle, dienst, katalog
from boerdi.ui_module.datenquelle import Ergebnis

if TYPE_CHECKING:
    from boerdi.services.arbeitsstand import TeilLader
    from boerdi.services.dokumente.stand import DokumentLader

RESERVE_S: Final = dienst.RESERVE_S
#: Review Paket U, MAJOR 3: Anzahl und Bytes der nicht abgelaufenen Uploads der Sitzung.
BelegungLader = Callable[[], Awaitable[tuple[int, int]]]


@dataclass(frozen=True, slots=True)
class Umgebung:
    usage_acc: dict[str, Any] | None = None
    frist_ende: float | None = None
    vorlage: dict[str, Any] | None = None
    dokument: DokumentLader | None = None
    #: Paket V1: liest einen Teil des aktiven Vorgangs per Name (``services/arbeitsstand``).
    teile: TeilLader | None = None
    #: Paket U5 (Review, Befund 5): die in diesem Zug angebotenen Werkzeuge — ein Dienst ruft ein
    #: MCP-Werkzeug, das er nur nebenbei nutzt, nur, wenn es darin steht (``None``: nie).
    #: Nicht daran hängt die Baumliste des Strukturabgleichs (SW-4): Sie liest dasselbe wie
    #: ``dienst.braucht`` und beachtet den Studio-Schalter selbst (``_liste_erlaubt``).
    verfuegbar: frozenset[str] | None = None
    #: Plan 2026-11-11, TW-2: Vorgaben der Redaktion aus dem KI-Schritt eines Laufs
    #: (``ki_schritt.vorgaben``) — ein Dienst setzt sie in seinen Systemteil.
    vorgaben: str = ""
    #: Plan 2026-11-16, TG-5 (G-E8): Argumente von ``ui_strukturentwurf``, die der KI-Schritt eines
    #: Laufs aus den Antworten vorbelegt (``services/ablauf/vorbelegung``) — die KI geht vor.
    vorbelegung: dict[str, Any] | None = None
    #: Review TW-6, Befund 7: der Aufruf kommt aus einem Ablauf-Schritt (``treiber_bloecke``) — nur
    #: dort gelten Schalter, die die KI nicht setzen soll (``einzeldatei_als_struktur``).
    aus_ablauf: bool = False
    #: Review Paket U (19.11.), MAJOR 3: die Belegung der Sitzung (``dokumente/ablage.belegung``)
    #: — der Upload-Dienst sperrt „Hier im Chat“ bei voller Sitzung. ``None``: nicht gezählt.
    belegung: BelegungLader | None = None


async def asynchron(name: str, args: Any, umgebung: Umgebung | None = None) -> Ergebnis:
    """Ein Modul-Aufruf mit Datenquelle oder Dienst → ``Ergebnis``."""
    manifest = katalog.katalog().get(name)
    if manifest is not None and dienst.name(manifest):
        return await dienst.aufruf(manifest, args, umgebung or Umgebung())
    return await datenquelle.aufruf(name, args)
