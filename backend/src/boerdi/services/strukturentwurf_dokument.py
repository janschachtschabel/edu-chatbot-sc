"""Ebene 1 eines Strukturentwurfs aus einem Dokument (aus ``strukturentwurf_dienst`` gelöst,
Querschnitts-Review 2026-11-06, Q4): die Aufforderung mit Gliederung und Anfang, die Fundstelle
eines Punktes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from boerdi.domain.dokument_gliederung import uebersicht
from boerdi.services import strukturentwurf_prompt as prompt
from boerdi.ui_module import strukturentwurf as se

if TYPE_CHECKING:
    from boerdi.services.dokumente.stand import DokumentStand

DOKUMENT_GLIEDERUNG: Final = 8000
DOKUMENT_ANFANG: Final = 1500
ABSCHNITTE_JE_PUNKT: Final = 12


def aufforderung_oben(a: Any, d: dict[str, Any], dokument: DokumentStand | None
                      ) -> list[dict[str, Any]]:
    """Die Aufforderung für Ebene 1 — mit Dokument dessen Gliederung und Anfang."""
    gemeinsam = {"thema": a.thema, "fach": d.get("fach"), "bildungsstufe": d.get("bildungsstufe"),
                 "anzahl_oben": a.anzahl_oben, "hinweise": a.hinweise}
    if dokument is None:
        return prompt.oben(**gemeinsam)
    gliederung, _ = uebersicht(dokument.abschnitte, DOKUMENT_GLIEDERUNG)
    from boerdi.services.ablauf.metadaten import DOKUMENT_FORMAT

    if getattr(dokument, "format", None) == DOKUMENT_FORMAT:   # TB-T1: gruppieren, nicht gliedern
        return prompt.oben_aus_inhalten(**gemeinsam, gliederung=gliederung,
                                        anfang=dokument.markdown[:DOKUMENT_ANFANG])
    return prompt.oben_aus_dokument(**gemeinsam, gliederung=gliederung,
                                    anfang=dokument.markdown[:DOKUMENT_ANFANG])


def fundstelle(knoten: dict[str, Any], roh: dict[str, Any], dokument: DokumentStand) -> None:
    """``abschnitte`` (nur bekannte Kennungen, gedeckelt) und ``fundstelle`` an den Punkt."""
    titel = {a.id: a.titel for a in dokument.abschnitte}
    roh_ids = roh.get("abschnitte") if isinstance(roh.get("abschnitte"), list) else []
    ids = list(dict.fromkeys(i for i in roh_ids if isinstance(i, str) and i in titel))
    if ids:
        knoten["abschnitte"] = ids[:ABSCHNITTE_JE_PUNKT]
        knoten["fundstelle"] = titel[ids[0]][:se.TITEL_ZEICHEN]
