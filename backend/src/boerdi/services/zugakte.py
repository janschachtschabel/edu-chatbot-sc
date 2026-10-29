"""Die Zugakte: was ein Zug aufgerufen und umgeschrieben hat (Paket 18C/D, Phase 1).

Bis hier stand das nur im Log — die Argumente eines gescheiterten Werkzeugaufrufs, der Text vor
einer Umschreibung, das Thema eines Schnellwegs. Ein Log gehört aber nicht dafür: es liegt beim
Betrieb, wird rotiert und soll keine Inhalte tragen (Paket 18C, E3). Die Akte liegt stattdessen
im Diagnoseteil des gespeicherten Zugs (``debug._zugakte``, nur im Studio sichtbar, 30 Tage wie
der Verlauf), und die Trace-ID führt aus dem Log dorthin.

**Ein geteiltes Objekt je Zug.** LangGraph-Knoten laufen als eigene Tasks; ein ``ContextVar.set``
in einem Knoten käme beim Speichern nicht an (Paket 10). ``binde_zugakte`` bindet die Akte deshalb
einmal vor dem Graphen, und jeder Knoten ergänzt dasselbe Objekt.

**Deckel und Schwärzung** wie im Log: der Bestätigungs-Schlüssel nie, große Nutzlasten nur als
Länge, sonst je Wert höchstens :data:`MAX_WERT` Zeichen und je Zug :data:`MAX_WERKZEUGE` Aufrufe.
"""

from __future__ import annotations

import contextvars
import json
import math
from dataclasses import dataclass, field
from typing import Any

from boerdi.domain.write_confirm import CONFIRM_TOKEN_FIELD

#: Schlüssel im gespeicherten Debug-Block.
SCHLUESSEL = "_zugakte"
MAX_WERT = 1000
MAX_WERKZEUGE = 50
#: Höchstens so viele Einträge je Liste — ``excludeNodeIds`` trägt bei „zeig mehr“ bis zu 200
#: Kennungen. Der Rest steht als ``‹N weitere›``.
MAX_EINTRAEGE = 20
#: Nutzlasten, deren Wert nie abgelegt wird — nur ihre Länge (Datei, ganzer Dokumenttext).
_NUR_LAENGE = frozenset({"fileBase64", "content"})

_akte: contextvars.ContextVar[Zugakte | None] = contextvars.ContextVar("_zugakte", default=None)


def _gekuerzt(text: str) -> str:
    return text if len(text) <= MAX_WERT else text[:MAX_WERT] + "…"


def _wert(schluessel: str, wert: Any) -> Any:
    if schluessel == CONFIRM_TOKEN_FIELD:
        return "‹geschwärzt›"
    if schluessel in _NUR_LAENGE and wert is not None:
        laenge = len(wert) if isinstance(wert, str) else len(json.dumps(wert, default=str))
        return f"‹{laenge} Zeichen›"
    if isinstance(wert, str):
        return _gekuerzt(wert)
    if isinstance(wert, dict):
        return {str(k): _wert(str(k), v) for k, v in wert.items()}
    if isinstance(wert, list | tuple):
        kopf = [_wert(schluessel, v) for v in wert[:MAX_EINTRAEGE]]
        rest = len(wert) - MAX_EINTRAEGE
        return [*kopf, f"‹{rest} weitere›"] if rest > 0 else kopf
    if wert is None or isinstance(wert, bool | int):
        return wert
    if isinstance(wert, float) and math.isfinite(wert):
        return wert
    # Was JSONB nicht nimmt (Menge, UUID, inf …), als Text: sonst scheiterte das Speichern
    # der ganzen Antwort an ihrem Diagnoseteil.
    return _gekuerzt(str(wert))


def _argumente(argumente: Any) -> Any:
    return _wert("", argumente) if isinstance(argumente, dict) else {}


@dataclass
class Zugakte:
    werkzeuge: list[dict[str, Any]] = field(default_factory=list)
    werkzeuge_ausgelassen: int = 0
    umschreibungen: list[dict[str, Any]] = field(default_factory=list)
    schnellwege: list[dict[str, Any]] = field(default_factory=list)

    def werkzeug(self, name: str, *, argumente_eingang: Any, argumente_gesendet: Any,
                 status: str, aus_cache: bool, dauer_ms: int, zeichen: int | None = None,
                 fehler: str | None = None) -> None:
        """Ein MCP-Aufruf: die Argumente beim Eingang (vom Modell, Vorabruf oder einer
        Direktaktion) und wie sie nach Prüfung und Auflösung hinausgingen; ``status`` wie
        ``call_mcp_tool_status`` (``ok`` oder die Fehlerart)."""
        if len(self.werkzeuge) >= MAX_WERKZEUGE:
            self.werkzeuge_ausgelassen += 1
            return
        self.werkzeuge.append({
            "name": name,
            "argumente_eingang": _argumente(argumente_eingang),
            "argumente_gesendet": _argumente(argumente_gesendet),
            "status": status, "aus_cache": aus_cache, "dauer_ms": dauer_ms,
            "zeichen": zeichen, "fehler": _gekuerzt(fehler) if fehler else None,
        })

    def umschreibung(self, art: str, *, original: str, ersatz: str, grund: str = "") -> None:
        """Eine Antwort, die nach dem Modell ersetzt wurde (Typ-Fokus, Halluzinations-Wächter)."""
        self.umschreibungen.append({"art": art, "original": _gekuerzt(original),
                                    "ersatz": _gekuerzt(ersatz), "grund": grund})

    def schnellweg(self, art: str, *, thema: str) -> None:
        """Ein Zug, der am Modell vorbei beantwortet wurde (Canvas, Lernpfad)."""
        self.schnellwege.append({"art": art, "thema": _gekuerzt(thema)})

    @property
    def umfang(self) -> int:
        """Zahl der Einträge — es wird nur angehängt, also zeigt ein anderer Wert Neues an."""
        return (len(self.werkzeuge) + self.werkzeuge_ausgelassen + len(self.umschreibungen)
                + len(self.schnellwege))

    def als_dict(self) -> dict[str, Any]:
        """Für ``debug._zugakte``; leer, wenn nichts eingetragen wurde."""
        aus: dict[str, Any] = {}
        if self.werkzeuge:
            aus["werkzeuge"] = list(self.werkzeuge)
        if self.werkzeuge_ausgelassen:
            aus["werkzeuge_ausgelassen"] = self.werkzeuge_ausgelassen
        if self.umschreibungen:
            aus["umschreibungen"] = list(self.umschreibungen)
        if self.schnellwege:
            aus["schnellwege"] = list(self.schnellwege)
        return aus


def binde_zugakte() -> Zugakte:
    """Eine frische Akte für den Zug binden — einmal, vor dem Graphen (siehe Modulkopf)."""
    akte = Zugakte()
    _akte.set(akte)
    return akte


def aktuelle_zugakte() -> Zugakte | None:
    """Die Akte des laufenden Zugs, oder ``None`` außerhalb eines Zugs (Hintergrundlauf)."""
    return _akte.get()


def merke_umschreibung(art: str, *, original: str, ersatz: str, grund: str = "") -> None:
    """:meth:`Zugakte.umschreibung` für den laufenden Zug; außerhalb eines Zugs nichts."""
    if (akte := _akte.get()) is not None:
        akte.umschreibung(art, original=original, ersatz=ersatz, grund=grund)


def merke_schnellweg(art: str, *, thema: str) -> None:
    """:meth:`Zugakte.schnellweg` für den laufenden Zug; außerhalb eines Zugs nichts."""
    if (akte := _akte.get()) is not None:
        akte.schnellweg(art, thema=thema)
