"""01-base/kestra-flows — welche Kestra-Flows ein Ablauf starten darf (Paket KF, Plan 2026-11-12).

Gelesen von ``config_loader.kestra_flows``; wirksam über ``services/auftraege/client`` (Regel K-E2:
im Studio freigegeben → diese, ``B_API_JOBS_FLOWS`` als Obergrenze; im Studio nichts → die
Umgebung wie bisher). Die Form ist dieselbe, die der Client beim Start prüft.
"""

from __future__ import annotations

import re
from typing import Annotated, Final

from pydantic import AfterValidator, Field, field_validator

from boerdi.domain.config_models._shared import AreaModel, Catalog

#: ``namespace/flowId`` (auch ohne Namespace) wie im Pfad der b-api. Das Muster prüft pydantic
#: (Rust-Regex, ohne Lookahead) und das Studio; :func:`ist_flow` dazu: kein Abschnitt nur aus
#: Punkten — ``../etc`` machte aus ``/api/v1/jobs/flows/{flow}`` einen anderen Pfad (Paket KF).
FLOW_FORM: Final = r"^[A-Za-z0-9_.\-]{1,100}(/[A-Za-z0-9_.\-]{1,100})?$"
_FLOW: Final = re.compile(FLOW_FORM)
_NUR_PUNKTE: Final = re.compile(r"^\.+$")


def ist_flow(text: str | None) -> bool:
    """Gültige Flow-Kennung — dieselbe Prüfung im Studio (Modell) und beim Start (Client)."""
    return bool(_FLOW.fullmatch(text or "")) and not any(
        _NUR_PUNKTE.fullmatch(teil) for teil in (text or "").split("/"))


def _flow(text: str) -> str:
    if not ist_flow(text):
        raise ValueError("keine gültige Flow-Kennung (namespace/flowId)")
    return text


MAX_FLOWS: Final = 50


class KestraFlowsSettings(AreaModel):
    """Die freigegebenen Flows — leer: es gelten die der Server-Umgebung (``B_API_JOBS_FLOWS``)."""

    flows: list[Annotated[str, Catalog("kestra_flows"),
                          Field(pattern=FLOW_FORM, max_length=201), AfterValidator(_flow)]] = Field(
        default_factory=list, max_length=MAX_FLOWS)

    @field_validator("flows", mode="before")
    @classmethod
    def _ohne_doppelte(cls, wert: object) -> object:
        """Leerraum am Rand und Doppelte fallen weg — die Reihenfolge der Redaktion bleibt."""
        if not isinstance(wert, list):
            return wert
        gesehen: dict[str, None] = {}
        for eintrag in wert:
            text = eintrag.strip() if isinstance(eintrag, str) else eintrag
            if text != "":
                gesehen.setdefault(text, None)
        return list(gesehen)


class KestraFlowsArea(AreaModel):
    kestra: KestraFlowsSettings = KestraFlowsSettings()
