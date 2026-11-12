"""Lader für ``01-base/kestra-flows`` (Paket KF).

``None``: im Studio nichts freigegeben — dann gilt die Umgebung (``B_API_JOBS_FLOWS``, Regel K-E2).
Ein Bestand am Validator vorbei darf keinen Zug mit einem 500 beenden; er **schließt** aber
(Review KF, Befund 3): übernommen werden nur seine gültigen Kennungen, sonst keine — sonst
erweiterte ein defekter Bestand die Freigabe still auf die ganze Obergrenze.
"""

from __future__ import annotations

import logging

from boerdi.domain.config_models.kestra_flows import KestraFlowsArea, ist_flow
from boerdi.services.config_loader._store import area

logger = logging.getLogger(__name__)

BEREICH = "01-base/kestra-flows"


def load_kestra_flows() -> list[str] | None:
    """Die im Studio freigegebenen Flows — ``None``, wenn dort nichts freigegeben ist."""
    roh = area(BEREICH)
    try:
        return list(KestraFlowsArea.model_validate(roh).kestra.flows) or None
    except Exception:
        logger.warning("kestra-flows: %s ist unlesbar — nur gültige Einträge gelten", BEREICH,
                       exc_info=True)
    kestra = roh.get("kestra") if isinstance(roh, dict) else None
    liste = kestra.get("flows") if isinstance(kestra, dict) else None
    if not isinstance(liste, list):
        return []
    gueltig = (f.strip() for f in liste if isinstance(f, str) and ist_flow(f.strip()))
    return list(dict.fromkeys(gueltig))
