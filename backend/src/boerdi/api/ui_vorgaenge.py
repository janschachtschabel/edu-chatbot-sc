"""``POST /api/ui/vorgaenge/offen`` — wartende Vorgänge der Person in anderen Gesprächen (K2a).

Das Widget fragt hier nach der Anmeldung oder beim Öffnen, ob ein Ablauf der Person in einem
**anderen** Gespräch wartet — auf einen b-api-Auftrag oder auf ihre Antwort. Dann bietet es
„Gespräch fortsetzen“ an und wechselt auf dessen Kennung (Plan 2026-11-08, Entscheid F2: über die
Anmeldung, keine Gesprächs-ID zum Eintippen).

Die Kennung eines Gesprächs ist dessen Geheimnis (wer sie hat, liest den Verlauf). Deshalb:
- nur mit **bestätigter Anmeldung** (403 ``nur_angemeldet``) — Aufträge starten ohnehin nur
  angemeldete Personen;
- die Besitzerin ist die Kennung der Anmeldung (``aufrufer_kennung``), nie eine mitgeschickte ID;
- die Antwort wird nicht zwischengespeichert (``no-store``), und kein Log nennt eine Kennung.

Angeboten wird nur der jüngste wartende Vorgang (Review K2a, Befund 7: das Widget nutzt nur ihn —
eine Kennung weniger, die hinausgeht), und nie der, auf den das aktuelle Gespräch schon verweist
(Befund 1: eine neue Sitzung übernimmt den jüngsten offenen Vorgang ohnehin, ``arbeitsstand.
auffrischen`` — dann führt er schon hier weiter).

Kein Zug, nichts wird geschrieben. IP-Drossel wie die übrigen Modul-Abrufe.

``POST /api/ui/vorgaenge/wiederkehr`` (AS-4c, Plan 2026-11-09 R3): ein Einstieg von außen — eine
Benachrichtigung, ein Link der Gastseite — nennt den Vorgang (``vorgang``) oder den Auftrag
(``auftrag``, die Job-ID). Die Kennung ist nie ein Recht: Dieselben Regeln wie oben, und fremd,
unbekannt, abgeschlossen, abgelaufen oder ohne Gespräch sehen gleich aus (404 ``unbekannt``,
kein Orakel). Die Antwort ist ein Vorgang wie in ``/offen``; das Widget wechselt dann und fragt
bei einem Auftrag „Stand prüfen“.

``POST /api/ui/vorgaenge/liste`` und ``/loeschen`` (AS-Ud, „Meine Vorgänge“, Plan 2026-11-09 §5j):
die eigenen, nicht abgeschlossenen Vorgänge **anderer** Gespräche (alle, Sicherung 20) und das
Löschen eines davon. Dieselben Regeln wie oben. Den Vorgang des aktuellen Gesprächs steuern dort die
Ablauf-Leiste und „Arbeitsstand löschen“ — hier fehlt er, und Löschen trifft ihn nie (404 wie
alles Fremde). Ein offener Auftrag endet nach dem Festschreiben auch bei der b-api, mit dem
Schlüssel der Person (wie bei „Arbeitsstand löschen“).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.deps import get_session
from boerdi.api.ratelimit import public_rate_limit
from boerdi.api.schemas import SITZUNGSKENNUNG
from boerdi.api.turn_auth import (
    adopt_turn_auth_block,
    pruefe_oeffentliche_kennung,
    uebernimm_llm_schluessel,
)
from boerdi.db.verbindung import verbindung_freigeben
from boerdi.services import arbeitsstand, probe, vorgaenge
from boerdi.services.ablauf import ausloeser
from boerdi.services.ablauf.zug_basis import bei_der_b_api_abbrechen
from boerdi.services.auftraege import ablage as auftraege_ablage
from boerdi.services.db_sessions import sitzung_entities
from boerdi.services.llm_auth import hat_zug_schluessel
from boerdi.services.mcp.anmeldung import bestaetige_anmeldung
from boerdi.services.mcp.auth import aufrufer_kennung, has_personal_auth

public_router = APIRouter(prefix="/api/ui/vorgaenge", tags=["ui"])


#: Querschnitts-Review AS-U/BU, Q-8: die Sprache des Widgets — der Titel eines Ablaufs kommt in ihr.
Sprache = Literal["de", "en"]


class OffenAnfrage(BaseModel):
    #: Das aktuelle Gespräch — nach ihm fragt das Widget nicht.
    session_id: str = Field(pattern=f"^{SITZUNGSKENNUNG}$")
    sprache: Sprache = "de"


class OffenerVorgang(BaseModel):
    titel: str
    #: Der wartende Ablauf (für „Stand prüfen“ nach dem Wechsel), ohne Lauf ``None``.
    ablauf: str | None
    #: ``wartet_auftrag`` oder ``wartet_person``; bei ``/wiederkehr`` und ``/liste`` auch ``aktiv``
    #: (ein Vorgang ohne wartenden Lauf — Review AS-4c, Befund 9).
    status: str
    #: Die Kennung des Gesprächs — nur für die Besitzerin.
    session_id: str
    geaendert: datetime


class OffeneVorgaenge(BaseModel):
    #: Höchstens einer: der jüngste.
    vorgaenge: list[OffenerVorgang]


_NO_STORE = {"Cache-Control": "private, no-store"}


async def _angemeldet(request: Request, session: AsyncSession, session_id: str, *,
                      mit_verweis: bool = True) -> tuple[str, str | None]:
    """Der gemeinsame Vorspann aller Pfade hier (Review AS-Ud, Befund 8): Kennung des Gesprächs
    prüfen, Anmeldung bestätigen (403 ``nur_angemeldet``, auch ohne Zwischenspeicher) — gibt die
    Besitzerin zurück und mit ``mit_verweis`` den Vorgang, auf den das aktuelle Gespräch
    verweist."""
    pruefe_oeffentliche_kennung(request, session_id)
    entities = await sitzung_entities(session, session_id) or {}
    if probe.in_sitzung(entities):
        # Review AS-8a, Befund 1: die Probe der Studio-Vorschau führt nie in echte Vorgänge (ein
        # „Fortsetzen“ machte sonst ein echtes Gespräch zur Probe — oder umgekehrt).
        raise HTTPException(status_code=409, detail="trockenlauf", headers=_NO_STORE)
    # Wie ``ui_auftrag``: die Bestätigung kann ein MCP-Rundlauf sein — ohne offene Lese-Transaktion.
    await verbindung_freigeben(session)
    adopt_turn_auth_block(request)
    await bestaetige_anmeldung()
    if not has_personal_auth():
        raise HTTPException(status_code=403, detail="nur_angemeldet", headers=_NO_STORE)
    kennung = aufrufer_kennung()
    if not mit_verweis:
        return kennung, None
    return kennung, (arbeitsstand.verweis(entities, kennung) or {}).get("id")


def _ablauf_von(v: vorgaenge.Vorgang) -> str | None:
    """Der Ablauf des Laufs (für „Stand prüfen“ nach dem Wechsel) — ohne Lauf ``None``."""
    lauf = (v.akte or {}).get("lauf")
    ablauf = lauf.get("ablauf") if isinstance(lauf, dict) else None
    return ablauf if isinstance(ablauf, str) else None


def _titel(v: vorgaenge.Vorgang, lang: str) -> str:
    """Q-8: gespeichert wird der deutsche Titel des Ablaufs (``zug._anlegen``). Stammt der Vorgang
    von diesem Ablauf (``zweck``), kommt sein Titel in der Sprache des Widgets; ein eigener Titel
    (etwa eines Entwurfs) bleibt."""
    ablauf_id = _ablauf_von(v)
    if lang == "de" or not ablauf_id or getattr(v, "zweck", None) != ablauf_id:
        return v.titel
    ablauf = ausloeser.laden(ablauf_id)
    return ((ablauf.titel.get(lang) or "").strip() or v.titel) if ablauf is not None else v.titel


def _als_offener(v: vorgaenge.Vorgang, lang: str = "de") -> OffenerVorgang:
    return OffenerVorgang(titel=_titel(v, lang), ablauf=_ablauf_von(v), status=v.status,
                          session_id=v.session_id, geaendert=v.geaendert)


@public_router.post("/offen", response_model=OffeneVorgaenge)
@public_rate_limit
async def offen(anfrage: OffenAnfrage, request: Request, response: Response,
                session: Annotated[AsyncSession, Depends(get_session)]) -> OffeneVorgaenge:
    kennung, hier = await _angemeldet(request, session, anfrage.session_id)
    liste = [v for v in await vorgaenge.offene(session, kennung, ohne=anfrage.session_id)
             if v.id != hier]
    response.headers["Cache-Control"] = "private, no-store"
    return OffeneVorgaenge(vorgaenge=[_als_offener(v, anfrage.sprache) for v in liste[:1]])


class WiederkehrAnfrage(BaseModel):
    """Genau eine Kennung: ``vorgang`` (UUID des Vorgangs) oder ``auftrag`` (Job-ID der b-api)."""

    session_id: str = Field(pattern=f"^{SITZUNGSKENNUNG}$")
    vorgang: str | None = Field(default=None, pattern=r"^[0-9a-fA-F-]{8,64}$")
    auftrag: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    #: Review PR #51 (R3): der Titel eines Ablaufs in der Sprache des Widgets, wie bei ``/offen``
    sprache: Sprache = "de"

    @model_validator(mode="after")
    def _genau_eine(self) -> WiederkehrAnfrage:
        if (self.vorgang is None) == (self.auftrag is None):
            raise ValueError("genau eine Kennung: vorgang oder auftrag")
        return self


def _unbekannt() -> HTTPException:
    """Dieselbe Antwort für alles, was nicht die eigene, offene Arbeit ist — kein Orakel. Je Wurf
    eine neue Ausnahme: eine Instanz auf Modulebene sammelte bei jedem ``raise`` die Frames samt
    Zugangsblock (Review AS-4c, Befund 1)."""
    return HTTPException(status_code=404, detail="unbekannt", headers=_NO_STORE)


@public_router.post("/wiederkehr", response_model=OffenerVorgang,
                    responses={403: {"description": "nur_angemeldet"},
                               404: {"description": "unbekannt — fremd, unbekannt, abgeschlossen, "
                                                    "abgelaufen oder ohne Gespräch"}})
@public_rate_limit
async def wiederkehr(anfrage: WiederkehrAnfrage, request: Request, response: Response,
                     session: Annotated[AsyncSession, Depends(get_session)]) -> OffenerVorgang:
    kennung, _ = await _angemeldet(request, session, anfrage.session_id, mit_verweis=False)
    # gespeichert werden Kennungen klein (``uuid4``) — eine groß geschriebene träfe nie
    vid = anfrage.vorgang.lower() if anfrage.vorgang else None
    if anfrage.auftrag is not None:
        vid = await auftraege_ablage.vorgang_zum_job(session, anfrage.auftrag, kennung)
    v = await vorgaenge.lesen(session, vid, kennung) if vid else None
    if v is None or v.status in vorgaenge.ABGESCHLOSSEN or not v.session_id:
        raise _unbekannt()
    response.headers["Cache-Control"] = "private, no-store"
    return _als_offener(v, anfrage.sprache)


class ListenAnfrage(BaseModel):
    #: Das aktuelle Gespräch — seine Vorgänge fehlen in der Liste.
    session_id: str = Field(pattern=f"^{SITZUNGSKENNUNG}$")
    sprache: Sprache = "de"


class EigenerVorgang(OffenerVorgang):
    #: Die Kennung des Vorgangs — zum Löschen, nur für die Besitzerin.
    id: str
    #: Q-7: der Status des Laufs (``laeuft``, ``wartet_freigabe``, ``fertig`` …) — feiner als
    #: ``status`` des Vorgangs (ein beendeter Lauf lässt ihn ``aktiv``); ohne Lauf ``None``.
    lauf_status: str | None = None


def _als_eigener(v: vorgaenge.Vorgang, lang: str) -> EigenerVorgang:
    lauf = (v.akte or {}).get("lauf")
    status = lauf.get("status") if isinstance(lauf, dict) else None
    return EigenerVorgang(id=v.id, lauf_status=status if isinstance(status, str) else None,
                          **_als_offener(v, lang).model_dump())


class EigeneVorgaenge(BaseModel):
    #: Die jüngsten zuerst (höchstens ``vorgaenge.LISTE_HOECHSTENS``).
    vorgaenge: list[EigenerVorgang]


class LoeschAnfrage(BaseModel):
    session_id: str = Field(pattern=f"^{SITZUNGSKENNUNG}$")
    vorgang: str = Field(pattern=r"^[0-9a-fA-F-]{8,64}$")


@public_router.post("/liste", response_model=EigeneVorgaenge,
                    responses={403: {"description": "nur_angemeldet"}})
@public_rate_limit
async def liste(anfrage: ListenAnfrage, request: Request, response: Response,
                session: Annotated[AsyncSession, Depends(get_session)]) -> EigeneVorgaenge:
    kennung, hier = await _angemeldet(request, session, anfrage.session_id)
    # Review AS-Ud, Befund 3: der Ausschluss gehört in die Abfrage, nicht hinter eine Grenze
    eigene = await vorgaenge.eigene(session, kennung, ohne=anfrage.session_id, ohne_id=hier)
    response.headers["Cache-Control"] = "private, no-store"
    return EigeneVorgaenge(vorgaenge=[_als_eigener(v, anfrage.sprache) for v in eigene])


_LOESCH_ANTWORTEN: dict[int | str, dict[str, Any]] = {
    403: {"description": "nur_angemeldet"},
    404: {"description": "unbekannt — fremd, unbekannt, abgeschlossen, ohne Gespräch oder der "
                         "des aktuellen Gesprächs"},
}


@public_router.post("/loeschen", responses=_LOESCH_ANTWORTEN)
@public_rate_limit
async def loeschen(anfrage: LoeschAnfrage, request: Request, response: Response,
                   session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str, bool]:
    uebernimm_llm_schluessel(request, pflicht=False)
    kennung, hier = await _angemeldet(request, session, anfrage.session_id)
    vid = anfrage.vorgang.lower()
    # Review AS-Ud, Befund 2: die Zeile bis zum Festschreiben sperren — ein Auftrag, den ein Zug
    # gerade anlegt (FK auf diese Zeile), wartet; einer, der schon steht, wird unten gelesen. Erst
    # sperren, dann lesen und prüfen (zweites Review, Z-9): sonst könnte ein Zug den Vorgang
    # dazwischen abschließen oder ins aktuelle Gespräch holen. Eine fremde Kennung sperrt nichts.
    await vorgaenge.sperren(session, vid, kennung)
    v = await vorgaenge.lesen(session, vid, kennung)
    # Ud-3 und Review AS-Ud, Kleinigkeit 9: nur, was die Liste zeigt — sonst wie Fremdes
    if (v is None or v.id == hier or v.session_id == anfrage.session_id
            or v.status in vorgaenge.ABGESCHLOSSEN or not v.session_id):
        raise _unbekannt()
    # Wie „Arbeitsstand löschen“: die Job-ID vorher lesen, den Auftrag erst nach dem Festschreiben
    # bei der b-api beenden (sonst liefe er dort weiter — Grenze von 20 je Schlüssel).
    offen = await auftraege_ablage.offen(session, v.id)
    job_id = offen.job_id if offen is not None else None
    await vorgaenge.loeschen(session, v.id, kennung)
    await session.commit()
    if job_id:
        bei_der_b_api_abbrechen(job_id)
    response.headers["Cache-Control"] = "private, no-store"
    # Q-6: ohne den Schlüssel der Person beendet die b-api den Job nicht (`bei_der_b_api_abbrechen`
    # tut dann nichts) — das Widget sagt es, statt „endet“ zu versprechen.
    return {"geloescht": True, "auftrag_laeuft_weiter": bool(job_id) and not hat_zug_schluessel()}
