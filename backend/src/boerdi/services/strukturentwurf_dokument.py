"""Ebene 1 eines Strukturentwurfs aus einem Dokument (aus ``strukturentwurf_dienst`` gelöst,
Querschnitts-Review 2026-11-06, Q4): die Aufforderung mit Gliederung und Anfang, die Fundstelle
eines Punktes.

Plan 2026-11-16, TG-3e: aus mehreren Dokumenten (``dokumente/stand.vereint``) — jedes ist ein
Abschnitt oberster Ebene (``d1``), Kennungen tragen den Präfix (``d1-a3``), und die Fundstelle nennt
Dokument und Abschnitt. Gliederung (:data:`DOKUMENT_GLIEDERUNG`) und Anfang
(:data:`DOKUMENT_ANFANG`) gelten insgesamt. Mit einem Dokument bleibt alles wie vorher.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from boerdi.domain.dokument_gliederung import dokument_von, uebersicht
from boerdi.services import strukturentwurf_prompt as prompt
from boerdi.ui_module import strukturentwurf as se

if TYPE_CHECKING:
    from boerdi.services.dokumente.stand import DokumentStand

DOKUMENT_GLIEDERUNG: Final = 8000
DOKUMENT_ANFANG: Final = 1500
ABSCHNITTE_JE_PUNKT: Final = 12
#: TG-3e: zwischen Dokument und Abschnitt in der Fundstelle.
FUNDSTELLE_TRENNER: Final = " › "


def _mehrere(dokument: Any) -> bool:
    return int(getattr(dokument, "dokumente", 1) or 1) > 1


def uebersicht_und_anfang(dokument: DokumentStand) -> tuple[str, str]:
    """Gliederung (gedeckelt) und Anfang, wie sie an Ebene 1 gehen — auch für die Prüfung eines
    ungeprüften Texts (``ui_module/dienst``). TG-3e: bei mehreren eine Ebene tiefer sichtbar (jedes
    Dokument ist eine Ebene), der Anfang je Dokument ein Stück."""
    gliederung, _ = uebersicht(dokument.abschnitte, DOKUMENT_GLIEDERUNG,
                               bis_ebene=4 if _mehrere(dokument) else 3)
    anfang = getattr(dokument, "anfang", None)
    return gliederung, (anfang if anfang is not None else dokument.markdown)[:DOKUMENT_ANFANG]


def aufforderung_oben(a: Any, d: dict[str, Any], dokument: DokumentStand | None
                      ) -> list[dict[str, Any]]:
    """Die Aufforderung für Ebene 1 — mit Dokument dessen Gliederung und Anfang."""
    gemeinsam = {"thema": a.thema, "fach": d.get("fach"), "bildungsstufe": d.get("bildungsstufe"),
                 "anzahl_oben": a.anzahl_oben, "hinweise": a.hinweise}
    if dokument is None:
        return prompt.oben(**gemeinsam, vorgaben=a.vorgaben)
    gliederung, anfang = uebersicht_und_anfang(dokument)
    from boerdi.services.ablauf.metadaten import DOKUMENT_FORMAT

    if getattr(dokument, "format", None) == DOKUMENT_FORMAT:   # TB-T1: gruppieren, nicht gliedern
        return prompt.oben_aus_inhalten(**gemeinsam, gliederung=gliederung, anfang=anfang,
                                        vorgaben=a.vorgaben)
    if _mehrere(dokument):
        return prompt.oben_aus_dokument(**gemeinsam, gliederung=gliederung, anfang=anfang,
                                        vorgaben=a.vorgaben, mehrere=True)
    return prompt.oben_aus_dokument(**gemeinsam, gliederung=gliederung, anfang=anfang,
                                    vorgaben=a.vorgaben)


def fundstelle(knoten: dict[str, Any], roh: dict[str, Any], dokument: DokumentStand) -> None:
    """``abschnitte`` (nur bekannte Kennungen, gedeckelt) und ``fundstelle`` an den Punkt. TG-3e:
    bei mehreren Dokumenten „Dokument › Abschnitt“."""
    titel = {a.id: a.titel for a in dokument.abschnitte}
    roh_ids = roh.get("abschnitte") if isinstance(roh.get("abschnitte"), list) else []
    ids = list(dict.fromkeys(i for i in roh_ids if isinstance(i, str) and i in titel))
    if ids:
        knoten["abschnitte"] = ids[:ABSCHNITTE_JE_PUNKT]
        erste = titel[ids[0]]
        if (dok := dokument_von(ids[0])) is not None and dok in titel:
            erste = f"{titel[dok]}{FUNDSTELLE_TRENNER}{erste}"
        knoten["fundstelle"] = erste[:se.TITEL_ZEICHEN]


def ohne_gleiche_fundstelle(knoten: list[dict[str, Any]]) -> None:
    """Plan 2026-11-16, Durchtest TG-7 (NIT): zeigen alle oberen Punkte (mindestens zwei) dieselbe
    Fundstelle — etwa ein PDF ohne erkannte Überschriften, das nur „Teil 1: …“ kennt —, sagt sie
    nichts; sie entfällt. Die ``abschnitte`` bleiben (sie tragen den Text für Ebene 2)."""
    stellen = [k.get("fundstelle") for k in knoten]
    if len(stellen) >= 2 and stellen[0] and len(set(stellen)) == 1:
        for k in knoten:
            k.pop("fundstelle", None)
