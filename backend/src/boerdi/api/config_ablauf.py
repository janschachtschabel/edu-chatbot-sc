"""Abläufe im Studio: prüfen ohne zu speichern (K2c-1) und die Liste der Seite „Abläufe“ (AS-0).

``POST /api/config/ablauf-pruefen`` — einen Ablauf prüfen, ohne ihn zu speichern (Paket K2c-1).

Das Studio prüft heute erst beim Speichern (400 mit Befunden). Mit diesem Endpunkt zeigt der
Knopf „Prüfen“ die Befunde vorher, je am Schritt (``pruefung.pruefe_gegliedert``; ``schritt: null``
für den ganzen Ablauf). Nur mit Studio-Schlüssel wie jede Konfiguration; schreibt nichts, ruft
keinen Fremddienst. Die Sprache folgt ``Accept-Language`` wie die übrigen Studio-Meldungen.

``GET /api/config/ablaeufe`` (AS-0) — je Ablauf-Dokument (``06-ablaeufe/<id>``) eine Zeile für die
Liste: Kennung, Titel, aktiv, Arten der Auslöser, benutzte Module und die Zahl der Befunde der
Prüfung. Aus der Datenbank gelesen, nicht aus dem Cache einer Replika (wie ``GET /config/data``).
Ein Dokument, das das Modell nicht besteht, steht mit ``lesbar: false`` in der Liste — so bleibt es
im Studio erreichbar und lässt sich reparieren oder löschen.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Security
from pydantic import BaseModel, ValidationError

from boerdi.api.deps import Lang, require_studio_key
from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services import config_loader as cl
from boerdi.services.ablauf import ausloeser, datensicht, pruefung, simulation
from boerdi.ui_module import katalog

router = APIRouter(prefix="/api/config", tags=["config"],
                   dependencies=[Security(require_studio_key)])


class AblaufBefund(BaseModel):
    #: Die Kennung des Schritts; ``None``: ein Befund des ganzen Ablaufs.
    schritt: str | None
    #: Seine Stelle in ``schritte`` (0…) — eindeutig auch bei doppelten Kennungen.
    nr: int | None
    text: str


class AblaufTeil(BaseModel):
    """AS-Dc: eine Zeile der Sicht „Daten“ (``services/ablauf/datensicht``)."""

    name: str
    #: Die Typen der Schreiber (``?``: Ausgabe einer KI; ``…``: Teil eines Moduls ohne bekannte
    #: Normalform).
    typen: list[str]
    #: Stellen in ``schritte`` der schreibenden bzw. lesenden Schritte.
    schreiber: list[int]
    leser: list[int]
    #: Vor dem Start da (Antwort des Moduls eines Modul-Auslösers).
    vor_dem_start: bool = False
    #: Kann ein Modul im Gespräch hinterlassen — ohne Schreiber und ohne das schreibt ihn nichts.
    aus_gespraech: bool = False
    #: Ein Wert aus den Testfällen, gekürzt.
    beispiel: str | None = None


class AblaufPruefung(BaseModel):
    befunde: list[AblaufBefund]
    #: AS-0: Hinweise, die das Speichern nicht sperren — etwa dieselbe Wendung in einem anderen
    #: aktiven Ablauf (``pruefung.wendungs_warnungen``).
    warnungen: list[str] = []
    #: AS-Dc: die Sicht „Daten“ — je Teil Typ, Schreiber, Leser, Beispiel.
    teile: list[AblaufTeil] = []


@router.post("/ablauf-pruefen", response_model=AblaufPruefung)
async def ablauf_pruefen(ablauf: AblaufArea, lang: Lang) -> AblaufPruefung:
    return AblaufPruefung(
        befunde=[
            AblaufBefund(schritt=ablauf.schritte[i].id if i is not None else None, nr=i, text=t)
            for i, t in pruefung.pruefe_gegliedert(ablauf, lang)],
        # AS-Db: dazu die Hinweise zum Datenfluss (sperren das Speichern nicht)
        warnungen=[*pruefung.wendungs_warnungen(ablauf, ausloeser.katalog(), lang),
                   *pruefung.agent_warnungen(ablauf, ausloeser.katalog(), lang),
                   *pruefung.warnungen(ablauf, lang)],
        teile=[AblaufTeil(**vars(z)) for z in datensicht.tabelle(ablauf)])


class TestErgebnis(BaseModel):
    name: str
    ok: bool
    #: Der Status des Laufs am Ende (``fertig``, ``fehler``, ``wartet_…``).
    status: str
    #: Die besuchten Schritte in ihrer Reihenfolge.
    weg: list[str]
    #: Der Schritt, an dem der Lauf zuletzt stand.
    ende: str
    abweichungen: list[str]
    #: AS-3b: was der Lauf ausgab, mit eingesetzten Platzhaltern (gekürzt).
    texte: list[str] = []


class AblaufTests(BaseModel):
    ergebnisse: list[TestErgebnis]


@router.post("/ablauf-testen", response_model=AblaufTests)
async def ablauf_testen(ablauf: AblaufArea, lang: Lang) -> AblaufTests:
    """AS-1: die Testfälle des Ablaufs simulieren — mit dem echten Treiber, ohne LLM, MCP, Auftrag
    oder Vorlage beim Server (``services/ablauf/simulation``). Schreibt nichts."""
    return AblaufTests(ergebnisse=[
        TestErgebnis(name=e.name, ok=e.ok, status=e.status, weg=e.weg, ende=e.ende,
                     abweichungen=e.abweichungen, texte=e.texte)
        for e in await simulation.im_thread(ablauf, lang)])


class AblaufZeile(BaseModel):
    key: str
    id: str
    titel: dict[str, str]
    aktiv: bool
    #: Die Arten der Auslöser in ihrer Reihenfolge, ohne Wiederholung (``knopf``, ``text`` …).
    ausloeser: list[str]
    #: Die UI-Module der Schritte ``modul``, in ihrer Reihenfolge, ohne Wiederholung.
    module: list[str]
    #: Wie viele Befunde „Prüfen“ hätte (0 bei einem unlesbaren Dokument — dort zählt ``lesbar``).
    befunde: int
    lesbar: bool
    #: Paket R2-a: die KI startet den Ablauf direkt (``modus: direkt`` am Auslöser ``agent``).
    direkt: bool = False


class AblaufListe(BaseModel):
    ablaeufe: list[AblaufZeile]


@router.get("/ablaeufe", response_model=AblaufListe)
async def ablauf_liste(lang: Lang) -> AblaufListe:
    stand = await cl.current_config()
    return AblaufListe(ablaeufe=[_zeile(key, data, lang) for key, data in sorted(stand.items())
                                 if key.startswith(ausloeser.PRAEFIX)])


def _module(ablauf: AblaufArea) -> list[str]:
    """Die UI-Module, die ein Ablauf zeigt oder auf die er hört — für die Querverweise am Modul
    (AS-2c, Review AS-2): ``modul``-Schritte, UI-Module unter den Werkzeugen eines
    ``agent``-Schritts und Auslöser ``art: modul``."""
    bekannt = katalog.katalog()
    namen: list[str] = []
    for s in ablauf.schritte:
        if s.typ == "modul" and s.modul:
            namen.append(s.modul)
        if s.typ == "agent" and s.agent:
            namen.extend(w for w in s.agent.werkzeuge if w in bekannt)
    namen.extend(a.modul for a in ablauf.ausloeser if a.art == "modul" and a.modul)
    return list(dict.fromkeys(namen))


def _zeile(key: str, data: Any, lang: str) -> AblaufZeile:
    kennung = key[len(ausloeser.PRAEFIX):]
    try:
        ablauf = AblaufArea.model_validate(data)
    except ValidationError:
        titel = data.get("titel") if isinstance(data, dict) else None
        return AblaufZeile(key=key, id=kennung, aktiv=False, ausloeser=[], module=[], befunde=0,
                           lesbar=False, titel={k: str(v) for k, v in titel.items()
                                                if isinstance(v, str)}
                           if isinstance(titel, dict) else {})
    return AblaufZeile(
        key=key, id=ablauf.id, titel=dict(ablauf.titel), aktiv=ablauf.aktiv,
        ausloeser=list(dict.fromkeys(a.art for a in ablauf.ausloeser)),
        module=_module(ablauf),
        befunde=len(pruefung.pruefe_gegliedert(ablauf, lang)), lesbar=True,
        direkt=any(a.art == "agent" and a.modus == "direkt" for a in ablauf.ausloeser))
