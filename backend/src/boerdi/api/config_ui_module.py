"""Studio-Seite „UI-Module“ (Paket U1-f, Plan §16 F-6): der Modul-Katalog samt Schaltbarkeit.

Nur lesend. Die Schalter selbst stehen im Bereich ``01-base/display-rules`` unter
``display_rules.ui_module`` und werden über ``PUT /api/config/data/{area}`` geschrieben — mit
Version, Werk-/eigener Fassung und Sicherung wie jeder Bereich. Diese Route liefert, was das Studio
dafür nicht aus dem Bereich lesen kann: die Manifeste aus dem ausgelieferten Katalog (dieselbe
Quelle wie Werkzeugbeschreibung und Prüfung) und welche Schalter je Modul gelten.

Eigener Endpunkt statt ``GET /api/config/choices``: ein Auswahlfeld braucht Wert und Beschriftung,
die Seite ganze Manifeste samt Schemas und Beispielen.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Security

from boerdi.api.deps import require_studio_key
from boerdi.ui_module import katalog, schalter
from boerdi.ui_module.namen import ABGELEITETE

router = APIRouter(
    prefix="/api/config", tags=["ui-module"],
    dependencies=[Security(require_studio_key)],
)

#: Der Bereich, in dem die Schalter stehen — das Studio liest und schreibt ihn über ``/data``.
BEREICH = "01-base/display-rules"


@router.get("/ui-module")
async def ui_module_katalog() -> dict[str, Any]:
    """Je Modul (nach Namen): das Manifest, welche Schalter gelten (``schaltbar``) und ob es aus
    der fertigen Antwort abgeleitet wird; dazu der Bereich der Schalter."""
    return {
        "bereich": BEREICH,
        "module": [
            {"name": name, "manifest": manifest, "schaltbar": schalter.schaltbar(name),
             "abgeleitet": name in ABGELEITETE}
            for name, manifest in sorted(katalog.katalog().items())
        ],
    }
