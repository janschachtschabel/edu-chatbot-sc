"""Die 422 auf einen Prüffehler — ohne die Eingabe (Paket 19, N-5).

FastAPIs Standard-Antwort trägt je Eintrag ``input`` (bei ``/api/chat`` die ganze Nachricht,
bei kaputtem JSON den Rumpf) und ``ctx`` (bei kaputtem JSON unter ``error`` die Stelle samt
Text). Die Antwort läuft durch Proxys (b-api, Team 6), die Rümpfe protokollieren können.

Es bleiben Ort, Art und Satz und aus ``ctx`` nur die Grenzen des Schemas als einfache Werte
(Review 19-1): das Studio baut daraus seinen Satz am Feld („Mindestens 1.“,
``core/field-problems.ts``, ``NEEDS``), ``describeValidationError`` nimmt ``loc`` und ``msg``.
Das Widget wertet den Rumpf einer 422 gar nicht aus. Die eigenen 422 der Konfiguration
(``api/config``) bauen ihre Liste selbst und sind davon nicht berührt.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

#: Schlüssel aus ``ctx``, die eine Grenze des Schemas nennen — nie die Eingabe, nie ``error``.
_CTX_ERLAUBT = frozenset({"ge", "le", "gt", "lt", "expected", "max_length", "min_length"})


def _grenzen(ctx: Any) -> dict[str, str | int | float]:
    if not isinstance(ctx, dict):
        return {}
    return {k: v for k, v in ctx.items()
            if k in _CTX_ERLAUBT and isinstance(v, (str, int, float)) and not isinstance(v, bool)}


def _eintrag(fehler: dict[str, Any]) -> dict[str, Any]:
    eintrag: dict[str, Any] = {"loc": list(fehler.get("loc") or ()),
                               "type": str(fehler.get("type") or ""),
                               "msg": str(fehler.get("msg") or "")}
    if grenzen := _grenzen(fehler.get("ctx")):
        eintrag["ctx"] = grenzen
    return eintrag


async def pruef_fehler_antwort(_request: Request, exc: Exception) -> JSONResponse:
    """``RequestValidationError`` → 422 mit ``loc``, ``type``, ``msg`` und Schema-Grenzen."""
    fehler = exc.errors() if isinstance(exc, RequestValidationError) else []
    return JSONResponse(status_code=422, content={"detail": [_eintrag(e) for e in fehler]})


__all__ = ["pruef_fehler_antwort"]
