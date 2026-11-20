"""Ebene 1 eines Strukturentwurfs aus einem Dokument (aus ``strukturentwurf_dienst`` gelöst,
Querschnitts-Review 2026-11-06, Q4): die Aufforderung mit Gliederung und Anfang, die Fundstelle
eines Punktes.

Plan 2026-11-16, TG-3e: aus mehreren Dokumenten (``dokumente/stand.vereint``) — jedes ist ein
Abschnitt oberster Ebene (``d1``), Kennungen tragen den Präfix (``d1-a3``), und die Fundstelle nennt
Dokument und Abschnitt. Gliederung (:data:`DOKUMENT_GLIEDERUNG`) und Anfang
(:data:`DOKUMENT_ANFANG`) gelten insgesamt. Mit einem Dokument bleibt alles wie vorher.

Plan 2026-11-19, A4 (E1, Befund S4): hat das Markdown höchstens :data:`GANZTEXT_ZEICHEN` Zeichen
(bei mehreren Dokumenten alle zusammen), sieht Ebene 1 statt des Anfangs den ganzen Text — die
Lernfelder eines Lehrplans findet das Modell im Text, auch wo die Gliederung sie nicht zeigt (keine
eigene Erkennung im Code). Moderiert wird er vorher (``ui_module/dienst_ganztext``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from boerdi.domain.dokument_gliederung import (
    PRAEFIX_TRENNER,
    dokument_von,
    uebersicht,
)
from boerdi.services import strukturentwurf_prompt as prompt
from boerdi.ui_module import strukturentwurf as se

if TYPE_CHECKING:
    from boerdi.services.dokumente.stand import DokumentStand

DOKUMENT_GLIEDERUNG: Final = 8000
DOKUMENT_ANFANG: Final = 1500
#: A4 (E1): bis zu so vielen Zeichen geht das ganze Markdown an Ebene 1. A7 (P1-0, gemessen an den
#: Rahmenlehrplänen des Nutzers): 80 000 im Plan; 100 000 nimmt 15 von 20 Plänen mit Text statt 13
#: (die nächsten haben 114 000 und mehr), Ebene 1 mit 95 000 Zeichen brauchte 19 s (Frist 40 s).
GANZTEXT_ZEICHEN: Final = 100_000
#: A6 (E7): die Rückkontrolle ``gelesen`` — je Dokument so viel Anfang und so viele Abschnittstitel,
#: höchstens so viele Dokumente (ein Vorgang kann bis zu 35 Strukturdokumente tragen).
GELESEN_ANFANG: Final = 2000
GELESEN_ABSCHNITTE: Final = 30
GELESEN_DOKUMENTE: Final = 10
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


def _aus_inhalten(dokument: Any) -> bool:
    from boerdi.services.ablauf.metadaten import DOKUMENT_FORMAT

    return getattr(dokument, "format", None) == DOKUMENT_FORMAT


def ganzer_text(dokument: Any) -> str | None:
    """A4 (E1): das ganze Markdown für Ebene 1 und (E1c) Ebene 2 samt Vorwärmen — ``None`` über
    :data:`GANZTEXT_ZEICHEN` und für die Materialien der Person (``aus_inhalten`` gruppiert
    Angaben, es gibt keinen Text)."""
    if dokument is None or _aus_inhalten(dokument):
        return None
    markdown = str(getattr(dokument, "markdown", "") or "")
    return markdown if len(markdown) <= GANZTEXT_ZEICHEN else None


def aufforderung_oben(a: Any, d: dict[str, Any], dokument: DokumentStand | None, *,
                      text: str = "") -> list[dict[str, Any]]:
    """Die Aufforderung für Ebene 1 — mit Dokument dessen Gliederung und Anfang; mit ``text`` (der
    ganze, moderierte Text des Laufs, zweites Review A, MINOR 5; fünftes, NIT 7: eine Quelle)
    statt des Anfangs der ganze Text (A4)."""
    gemeinsam = {"thema": a.thema, "fach": d.get("fach"), "bildungsstufe": d.get("bildungsstufe"),
                 "anzahl_oben": a.anzahl_oben, "hinweise": a.hinweise}
    if dokument is None:
        return prompt.oben(**gemeinsam, vorgaben=a.vorgaben)
    gliederung, anfang = uebersicht_und_anfang(dokument)
    if _aus_inhalten(dokument):   # TB-T1: gruppieren, nicht gliedern
        return prompt.oben_aus_inhalten(**gemeinsam, gliederung=gliederung, anfang=anfang,
                                        vorgaben=a.vorgaben)
    return prompt.oben_aus_dokument(**gemeinsam, gliederung=gliederung, anfang=anfang,
                                    text=text,
                                    vorgaben=a.vorgaben,
                                    mehrere=_mehrere(dokument))


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


def plan_ohne_angabe(plaene: dict[str, int], mit_text: set[str], dokument: Any) -> None:
    """Plan 2026-11-19, A5 (E6, Befund S4): ``unterthemen: 0`` an einem oberen Punkt eines
    Dokuments heißt „nicht angegeben“ — das Modell sah die Ordnung darunter oft nicht (etwa nur die
    Gliederung eines langen Lehrplans). Review A, MINOR 5: je Punkt, nicht nur wenn alle 0 melden
    (Anlagenmechaniker SHK: 6 von 12 flach), und nur mit Text dafür (``mit_text``: Abschnitte, auf
    dem Weg „ganz“ jeder Punkt, Plan E1c) — der Punkt bekommt
    :data:`~strukturentwurf_prompt.UNTERTHEMEN_OBEN`. Die
    Materialien der Person (``aus_inhalten``) bleiben, wie das Modell sie plant."""
    if _aus_inhalten(dokument):
        return
    for kennung, plan in plaene.items():
        if not plan and kennung in mit_text:
            plaene[kennung] = prompt.UNTERTHEMEN_OBEN


def _eintrag(name: str, text: str, titel: list[str], weg: str) -> dict[str, Any]:
    return {"name": " ".join(name.split())[:200] or "Dokument", "zeichen": len(text), "weg": weg,
            "anfang": text[:GELESEN_ANFANG], "abschnitte": titel[:GELESEN_ABSCHNITTE]}


def gelesen(dokument: Any, *, ganz: bool = False) -> list[dict[str, Any]]:
    """Plan 2026-11-19, A6 (E7): die Rückkontrolle für die Person — je Dokument Name, Zeichen, Weg
    (``ganz``: der ganze Text ging an Ebene 1, sonst ``gliederung``), Anfang des gelesenen Texts
    und Abschnittstitel. Nur Anzeige: die KI sieht es nie (``x-nur-system`` im Manifest). Bei
    mehreren Dokumenten aus dem vereinten Stand zurückgewonnen (``zusammenfuehren``: je Dokument ein
    Abschnitt ``dN`` mit Kopfzeile ``# Name``). Die Materialien der Person tragen nichts."""
    if dokument is None or _aus_inhalten(dokument):
        return []
    weg = "ganz" if ganz and ganzer_text(dokument) is not None else "gliederung"
    markdown = str(getattr(dokument, "markdown", "") or "")
    abschnitte = list(getattr(dokument, "abschnitte", None) or [])
    if not _mehrere(dokument):
        return [_eintrag(str(getattr(dokument, "name", "") or ""), markdown,
                         [a.titel for a in abschnitte], weg)]
    koepfe = [a for a in abschnitte if a.ebene == 1 and dokument_von(a.id) is None]
    aus = []
    for n, kopf in enumerate(koepfe[:GELESEN_DOKUMENTE]):
        ende = koepfe[n + 1].start - 2 if n + 1 < len(koepfe) else len(markdown)
        text = markdown[kopf.start:ende].removeprefix(f"# {kopf.titel}\n\n")
        praefix = f"{kopf.id}{PRAEFIX_TRENNER}"
        aus.append(_eintrag(kopf.titel, text, [a.titel for a in abschnitte
                                               if a.id.startswith(praefix)], weg))
    return aus


def nacharbeit(paare: list[tuple[dict[str, Any], dict[str, Any]]], plaene: dict[str, int],
               dokument: Any, *, ganz: bool = False) -> None:
    """Ebene 1 aus einem Dokument nacharbeiten (aus ``strukturentwurf_dienst._obere_ebene``
    verschoben, Review Paket A, zweites Review, MINOR 7) — je (Punkt, Rohpunkt des Modells):
    ``abschnitte``/``fundstelle``; eine an jedem Punkt gleiche Fundstelle entfällt (Durchtest TG-7);
    ``unterthemen: 0`` an einem Punkt mit Text heißt „nicht angegeben“ (A5, Review A MINOR 5; auf
    dem Weg „ganz“ hat jeder Punkt Text, Plan E1c)."""
    for k, roh in paare:
        fundstelle(k, roh, dokument)
    knoten = [k for k, _ in paare]
    ohne_gleiche_fundstelle(knoten)
    # Plan E1c: auf dem Weg „ganz“ sieht Ebene 2 das ganze Dokument — jeder Punkt hat Text
    plan_ohne_angabe(plaene, {k["id"] for k in knoten if ganz or k.get("abschnitte")}, dokument)
