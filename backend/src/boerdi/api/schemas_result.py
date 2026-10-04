"""Die Eingangsprüfung für ``result_schema`` — geteilt von Chat und Agent-Endpunkt.

Seit Paket 4 (A3) wird ein Ergebnis gegen dieses Schema geprüft
(``domain/ergebnis_schema``). Ein kaputtes Schema oder ein Verweis nach draußen
fällt deshalb schon hier auf (422), statt mitten im Lauf.
"""

from __future__ import annotations

from typing import Any

from boerdi.domain.ergebnis_schema import schema_fehler


def pruefe_ergebnis_schema(wert: dict[str, Any]) -> dict[str, Any]:
    """``wert`` unverändert zurück — oder ``ValueError`` (pydantic macht 422 daraus)."""
    fehler = schema_fehler(wert)
    if fehler:
        raise ValueError(f"result_schema ist kein gültiges JSON-Schema: {fehler}")
    return wert
