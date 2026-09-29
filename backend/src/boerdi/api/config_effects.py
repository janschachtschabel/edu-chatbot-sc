"""ST-5: wo ein Config-Bereich wirkt — die Zuordnung für das Studio.

Das Studio zeigt sie an jedem Abschnitt („Wirkt in: Muster-Maschine ·
Agent-Schleife") und warnt auf einer Seite, die die Vorgabe-Maschine nicht
nutzt. Die Zuordnung liegt in ``domain/area_effects.py`` (festgehalten von
``tests/test_area_effects.py``), nicht im Studio: eine abgetippte Liste im
Frontend driftete, sobald sich ein Leser im Backend ändert.

Eigener Endpunkt statt eines Zusatzes am Schema je Bereich: die Abschnitte einer
Seite laden ihr Schema erst beim Aufklappen, der Hinweis im Kopf und das Banner
brauchen die Zuordnung aber sofort — für alle Bereiche, mit einer Anfrage.

``engine`` ist die GEPFLEGTE Vorgabe (``01-base/engine``), nicht die Maschine
dieser Anfrage: das Studio schickt keine Maschinen-Kopfzeile, und eine
Einbettung ohne eigene Wahl bekommt genau diese Vorgabe.
"""

from __future__ import annotations

from fastapi import APIRouter, Security

from boerdi.api.deps import require_studio_key
from boerdi.domain.area_effects import AREA_EFFECTS
from boerdi.services.engine_choice import choose_engine

router = APIRouter(
    prefix="/api/config", tags=["config-effects"],
    dependencies=[Security(require_studio_key)],
)


@router.get("/effects")
async def get_effects() -> dict:
    """Je Bereich die Wirkung in Muster-Maschine und Agent-Schleife, dazu die Vorgabe-Maschine."""
    return {"engine": choose_engine(None), "areas": AREA_EFFECTS}
