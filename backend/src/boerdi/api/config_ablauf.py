"""``POST /api/config/ablauf-pruefen`` — einen Ablauf prüfen, ohne ihn zu speichern (Paket K2c-1).

Das Studio prüft heute erst beim Speichern (400 mit Befunden). Mit diesem Endpunkt zeigt der
Knopf „Prüfen“ die Befunde vorher, je am Schritt (``pruefung.pruefe_gegliedert``; ``schritt: null``
für den ganzen Ablauf). Nur mit Studio-Schlüssel wie jede Konfiguration; schreibt nichts, ruft
keinen Fremddienst. Die Sprache folgt ``Accept-Language`` wie die übrigen Studio-Meldungen.
"""

from __future__ import annotations

from fastapi import APIRouter, Security
from pydantic import BaseModel

from boerdi.api.deps import Lang, require_studio_key
from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import pruefung

router = APIRouter(prefix="/api/config", tags=["config"],
                   dependencies=[Security(require_studio_key)])


class AblaufBefund(BaseModel):
    #: Die Kennung des Schritts; ``None``: ein Befund des ganzen Ablaufs.
    schritt: str | None
    #: Seine Stelle in ``schritte`` (0…) — eindeutig auch bei doppelten Kennungen.
    nr: int | None
    text: str


class AblaufPruefung(BaseModel):
    befunde: list[AblaufBefund]


@router.post("/ablauf-pruefen", response_model=AblaufPruefung)
async def ablauf_pruefen(ablauf: AblaufArea, lang: Lang) -> AblaufPruefung:
    return AblaufPruefung(befunde=[
        AblaufBefund(schritt=ablauf.schritte[i].id if i is not None else None, nr=i, text=t)
        for i, t in pruefung.pruefe_gegliedert(ablauf, lang)])
