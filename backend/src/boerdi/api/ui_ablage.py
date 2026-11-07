"""``POST /api/ui/ablage/{vorbereiten,datei,abschluss}`` — Ablage im persönlichen Bereich (U3-3a).

Das Modul ``ui_upload`` überträgt einen erfassten Ordner, nachdem die Person die Vorschau gesehen
und „Jetzt übertragen“ gewählt hat. Kein Zug und keine KI — das Backend reicht an das MCP durch
(``services/ablage/mcp_ablage``, MA-1…MA-4):

1. ``vorbereiten`` (JSON: Ordnername, je Datei Titel, sha256, Größe, Art) → Vorschau des Servers
   (normalisierte Namen, Ordner oder flach) und der Freigabe-Schlüssel. Die Vorschau wird Teil
   ``ablage`` im Vorgang (``services/ablage/vorgang_teil``; nur ein Prüf-Kürzel des Schlüssels).
2. ``datei`` (multipart: Schlüssel, Index, Datei — **nacheinander**, eine Datei zur Zeit) → die
   Bytes als Strom in einen Upload-Platz des MCP, dann als Eintrag ``index`` ablegen; der Stand geht
   in den Teil. Ein Index mit endgültigem Stand (auch ``failed``) gibt ihn zurück, ohne das MCP zu
   rufen; ein Grund des MCP ohne Anlegen (``erneut``, ``passt_nicht``, ``neu_vorbereiten``) lässt
   ihn offen; ohne Antwort wird er ``unverified`` (es KANN abgelegt sein).
3. ``abschluss`` → ``vorgang.json`` (baut der MCP-Server) und Teil ``abgeschlossen``.

Paket M6 (MCP-Stand 2026-11-07): ``vorbereiten`` bringt die eigenen letzten Ablagen mit
(``letzte``, ``wlo_list_my_batches``) — neben der Vorschau, damit dieselbe Auswahl nicht zweimal
landet. Parallel zur Freigabe und danach höchstens ``_LETZTE_REST_S`` länger; scheitert oder dauert
die Liste, bleibt sie leer und hält nichts auf.

Bremsen wie beim Dokument (``ui_dokumente``): Sitzung, nur mit **bestätigter Anmeldung** (403
``nur_angemeldet`` vor jedem MCP-Aufruf), Studio-Schalter ``ablage_in_wlo`` (403 ``aus``), Größe je
Datei = ``max_mb`` des Studios (413, schon beim Vorbereiten). ``vorbereiten`` verlangt die **offene
Frage von ui_upload** (409) und läuft über die Fenster der Redaktion (``check_rate_limit``, vor der
Anmeldungs-Bestätigung); ``datei``/``abschluss`` gehören dagegen zum Stapel im Teil ``ablage``
(Prüf-Kürzel und Block, 409 ``fremder_stapel``) — ein Zug mitten im Stapel schließt die Frage, der
Stapel läuft weiter (Querschnitts-Review 2026-11-06, M2). Ein offener Stapel mit abgelegten Dateien
wird nicht ersetzt, solange seine Freigabe gilt (409 ``stapel_offen``). Fehler als Codes, nie
Servertext; der Dateiname wird nicht geloggt.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.deps import get_session
from boerdi.api.ratelimit import peer_ip, public_rate_limit
from boerdi.api.schemas import SITZUNGSKENNUNG
from boerdi.api.turn_auth import adopt_turn_auth_block, pruefe_oeffentliche_kennung
from boerdi.db.verbindung import verbindung_freigeben
from boerdi.domain.repo_links import render_url
from boerdi.i18n import resolve_locale
from boerdi.obs.quality_events import log_safety_event
from boerdi.services import arbeitsstand
from boerdi.services.ablage import mcp_ablage, vorgang_teil
from boerdi.services.config_loader import get_repo_base_url
from boerdi.services.config_loader.upload import load_upload_config
from boerdi.services.db_sessions import (
    sitzung_entities,
    sitzung_entities_frisch,
    update_session,
)
from boerdi.services.mcp.anmeldung import bestaetige_anmeldung
from boerdi.services.mcp.auth import has_personal_auth
from boerdi.services.rate_limits import check_rate_limit
from boerdi.ui_module.antwort import OFFENE_FRAGE
from boerdi.ui_module.namen import UPLOAD

logger = logging.getLogger(__name__)
public_router = APIRouter(prefix="/api/ui/ablage", tags=["ui"])

_MIB = 1024 * 1024
_STUECK = _MIB
_BLOCK = r"^[a-z0-9]{8,32}$"
_TOKEN = r"^[A-Za-z0-9_.\-]{10,200}$"
_ART = r"^(pdf|docx|pptx|xlsx|odt|ods|odp|png|jpg|gif|webp|mp3|mp4|txt|md)$"
#: Codes von ``mcp_ablage`` → Status.
_STATUS = {"nur_angemeldet": 403, "kein_recht": 403, "abgewiesen": 422, "nicht_erreichbar": 503,
           "zu_gross": 413, "art": 415, "voll": 429, "zu_langsam": 504, "fehler": 502,
           "anmeldungen": 503, "erneut": 409, "passt_nicht": 422, "neu_vorbereiten": 409,
           "nichts_abgelegt": 409, "nicht_gespeichert": 503, "groesse": 400,
           "stapel_offen": 409}
#: Stände, die endgültig sind — ein zweiter Versuch schickt nichts mehr (Review, Befund 1).
_ENDGUELTIG = frozenset({"stored", "dropped", "unverified", "failed"})


class Eintrag(BaseModel):
    titel: str = Field(min_length=1, max_length=200)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    groesse: int = Field(gt=0)
    art: str = Field(pattern=_ART)


class Vorbereiten(BaseModel):
    session_id: str = Field(pattern=f"^{SITZUNGSKENNUNG}$")
    block_id: str = Field(pattern=_BLOCK)
    ordner: str = Field(min_length=1, max_length=120)
    eintraege: list[Eintrag] = Field(min_length=1, max_length=200)


class Abschluss(BaseModel):
    session_id: str = Field(pattern=f"^{SITZUNGSKENNUNG}$")
    block_id: str = Field(pattern=_BLOCK)
    batch_token: str = Field(pattern=_TOKEN)


async def _sitzung(request: Request, session: AsyncSession, session_id: str, block_id: str, *,
                   frage: bool) -> dict[str, Any]:
    """Sitzung und — für ``vorbereiten`` — die offene Frage von ui_upload. Gibt die Entities
    zurück."""
    pruefe_oeffentliche_kennung(request, session_id)
    entities = await sitzung_entities(session, session_id)
    if entities is None:
        raise HTTPException(status_code=404, detail="sitzung_unbekannt")
    offen = entities.get(OFFENE_FRAGE)
    if frage and not (isinstance(offen, dict) and offen.get("modul") == UPLOAD
                      and offen.get("block_id") == block_id):
        raise HTTPException(status_code=409, detail="keine_anfrage")
    await verbindung_freigeben(session)
    return entities


async def _anmeldung(request: Request) -> None:
    """Anmeldung und Schalter — vor jedem MCP-Aufruf."""
    adopt_turn_auth_block(request)
    await bestaetige_anmeldung()
    if not has_personal_auth():
        raise HTTPException(status_code=403, detail="nur_angemeldet")
    if not load_upload_config().ablage_in_wlo:
        raise HTTPException(status_code=403, detail="aus")


def _link(node_id: Any) -> str | None:
    """Der Link zum Ansehen eines abgelegten Knotens (U3-3b) — das Modul baut keine Adressen."""
    if not (isinstance(node_id, str) and node_id):
        return None
    return render_url(node_id, get_repo_base_url())


def _fehler(code: str) -> HTTPException:
    return HTTPException(status_code=_STATUS.get(code, 502), detail=code)


async def _verweis_zurueckschreiben(session: AsyncSession, session_id: str,
                                    entities: dict[str, Any]) -> None:
    """Nur den Verweis auf den Vorgang zurück in die Sitzung — auf einem FRISCH gelesenen Stand
    (Review, Befund 3): zwischen Lesen und Schreiben lag ein MCP-Aufruf von Sekunden, und ein Zug in
    der Zeit schrieb seine Entities sonst still zurück."""
    if arbeitsstand.VERWEIS not in entities:
        return
    frisch = await sitzung_entities_frisch(session, session_id)
    if frisch is None:
        await session.rollback()      # die Sperre nicht bis zum Ende der Anfrage halten
        return
    frisch[arbeitsstand.VERWEIS] = entities[arbeitsstand.VERWEIS]
    await update_session(session, session_id, entities=frisch)


async def _teil_zum_schluessel(session: AsyncSession, session_id: str, entities: dict[str, Any],
                               batch_token: str, block_id: str) -> dict[str, Any]:
    teil = await vorgang_teil.lesen(session, session_id, entities)
    if (teil is None or teil.get("token_kuerzel") != vorgang_teil.kuerzel(batch_token)
            or teil.get("block_id") != block_id):
        raise HTTPException(status_code=409, detail="fremder_stapel")
    return teil


@public_router.post("/vorbereiten")
@public_rate_limit
async def vorbereiten(anfrage: Vorbereiten, request: Request, response: Response,
                      session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str, Any]:
    entities = await _sitzung(request, session, anfrage.session_id, anfrage.block_id, frage=True)
    ip = peer_ip(request)
    urteil = await check_rate_limit(anfrage.session_id, ip,
                                    resolve_locale(request.headers.get("accept-language")))
    if not urteil.allowed:
        await log_safety_event(session, anfrage.session_id, "",
                               decision={"reasons": [f"rate_limit:{urteil.reason}"]},
                               ip=ip, rate_limited=True)
        raise HTTPException(status_code=429, detail=urteil.blocked_message)
    await _anmeldung(request)
    if any(e.groesse > load_upload_config().max_mb * _MIB for e in anfrage.eintraege):
        raise HTTPException(status_code=413, detail="zu_gross")
    vorher = await vorgang_teil.lesen(session, anfrage.session_id, entities)
    if vorgang_teil.haelt_noch(vorher):
        raise _fehler("stapel_offen")
    await verbindung_freigeben(session)
    # Paket M6: die Liste läuft neben der Freigabe — und hält sie nicht auf (Review M6, Befund 1):
    # danach bekommt sie nur noch :data:`_LETZTE_REST_S`; scheitert die Freigabe, wird sie
    # abgebrochen.
    liste = asyncio.create_task(_letzte_oder_leer())
    try:
        plan = await mcp_ablage.vorbereiten(anfrage.ordner,
                                            [e.model_dump() for e in anfrage.eintraege])
    except BaseException as fehler:
        liste.cancel()
        if isinstance(fehler, mcp_ablage.AblageFehler):
            raise _fehler(fehler.code) from None
        raise
    letzte = await _letzte_abwarten(liste)
    token = str(plan["batchToken"])
    teil = vorgang_teil.aus_plan(plan, token, anfrage.block_id, vorher)

    dazwischen = False

    async def neu() -> dict[str, Any] | None:
        nonlocal dazwischen
        # Review Q1, Befund 2: zwischen der Prüfung und hier lag der MCP-Aufruf — hat inzwischen ein
        # anderer Stapel abgelegt, wird er nicht überschrieben.
        frisch = await vorgang_teil.lesen(session, anfrage.session_id, entities)
        if vorgang_teil.haelt_noch(frisch):
            dazwischen = True
            return None
        return vorgang_teil.aus_plan(plan, token, anfrage.block_id, frisch)

    if not await vorgang_teil.speichern(session, anfrage.session_id, entities, teil, neu=neu):
        # Der wahre Grund statt „noch einmal versuchen“ (Review 2026-11-07, UI-Backend Befund 6).
        if dazwischen:
            raise _fehler("stapel_offen")
        # Ohne den Teil scheiterte jede Datei an ``fremder_stapel`` (Review, Befund 4).
        raise _fehler("nicht_gespeichert")
    await _verweis_zurueckschreiben(session, anfrage.session_id, entities)
    return {"batch_token": token, "layout": teil["layout"], "ordner": teil["ordner"],
            "gesamt": int(plan.get("totalBytes") or 0),
            "eintraege": [{k: e[k] for k in ("index", "titel", "art", "groesse", "name")}
                          for e in teil["inhalte"]],
            "letzte": letzte}


#: Paket M6: so lange wartet ``vorbereiten`` nach der Freigabe noch auf die Liste der letzten
#: Ablagen.
_LETZTE_REST_S = 3.0
_LEER: dict[str, Any] = {"ablagen": [], "gekappt": False}


async def _letzte_abwarten(liste: asyncio.Task[dict[str, Any]]) -> dict[str, Any]:
    try:
        fertig, _ = await asyncio.wait({liste}, timeout=_LETZTE_REST_S)
    finally:
        # Auch wenn die Anfrage selbst abbricht (Client weg, Herunterfahren): kein verwaister
        # Aufruf.
        if not liste.done():
            liste.cancel()
    if not fertig:
        logger.info("Ablage: letzte Ablagen zu langsam — ohne Liste weiter")
        return dict(_LEER)
    return liste.result()


async def _letzte_oder_leer() -> dict[str, Any]:
    """Paket M6: die letzten Ablagen — eine Orientierung, kein Teil der Freigabe. Ein Fehler (auch
    ein Server ohne das Werkzeug) gibt eine leere Liste, nie einen Fehler der Vorbereitung."""
    try:
        return await mcp_ablage.letzte_ablagen()
    except mcp_ablage.AblageFehler as f:
        logger.info("Ablage: letzte Ablagen nicht lesbar (%s)", f.code)
    except Exception:  # noqa: BLE001 — siehe Docstring
        logger.warning("Ablage: letzte Ablagen nicht lesbar", exc_info=True)
    return dict(_LEER)


async def _stuecke(datei: UploadFile) -> AsyncIterator[bytes]:
    while stueck := await datei.read(_STUECK):
        yield stueck


@public_router.post("/datei")
@public_rate_limit
async def datei(request: Request, response: Response,
                session: Annotated[AsyncSession, Depends(get_session)],
                session_id: Annotated[str, Form(pattern=f"^{SITZUNGSKENNUNG}$")],
                block_id: Annotated[str, Form(pattern=_BLOCK)],
                batch_token: Annotated[str, Form(pattern=_TOKEN)],
                index: Annotated[int, Form(ge=0, le=199)],
                datei: Annotated[UploadFile, File()]) -> dict[str, Any]:
    entities = await _sitzung(request, session, session_id, block_id, frage=False)
    await _anmeldung(request)
    teil = await _teil_zum_schluessel(session, session_id, entities, batch_token, block_id)
    eintrag = next((e for e in teil["inhalte"] if e["index"] == index), None)
    if eintrag is None:
        raise HTTPException(status_code=400, detail="index")
    # Querschnitts-Review, M3: ein selbst gesetztes „ohne Antwort“ ist nicht endgültig — das MCP
    # ist je Index idempotent und nennt beim zweiten Einlösen den wahren Stand.
    if eintrag["stand"] in _ENDGUELTIG and not eintrag.get("ohne_antwort"):
        return {"index": index, "stand": eintrag["stand"], "node_id": eintrag.get("node_id"),
                "link": _link(eintrag.get("node_id")),
                "ordner_verweigert": bool(teil.get("ordner_verweigert")), "bereits": True}
    groesse = datei.size or 0
    if groesse <= 0 or groesse > load_upload_config().max_mb * _MIB:
        raise HTTPException(status_code=413, detail="zu_gross")
    if groesse != eintrag["groesse"]:
        # Die Größe stand in der Freigabe — eine andere Datei geht gar nicht erst hin (Befund 8).
        raise _fehler("groesse")
    await verbindung_freigeben(session)
    try:
        slot = await mcp_ablage.datei_hochladen(_stuecke(datei), groesse, datei.filename or "")
    except mcp_ablage.AblageFehler as f:
        raise _fehler(f.code) from None
    try:
        ergebnis = await mcp_ablage.datei_ablegen(batch_token, index, str(slot["ref"]))
    except mcp_ablage.AblageFehler as f:
        if f.code in ("zu_langsam", "nicht_erreichbar"):
            # Keine Antwort: die Datei KANN abgelegt sein — „unklar“, nicht „offen“ (T2, Befund 2).
            await _stand_festhalten(session, session_id, entities, index,
                                    {"status": "unverified", "ohne_antwort": True},
                                    kuerzel=teil["token_kuerzel"], eintrag=eintrag)
        raise _fehler(f.code) from None
    if (code := mcp_ablage.grund(ergebnis)) is not None:
        raise _fehler(code)           # nichts angelegt — der Eintrag bleibt offen
    neu = await _stand_festhalten(session, session_id, entities, index, ergebnis,
                                  kuerzel=teil["token_kuerzel"], eintrag=eintrag)
    return {"index": index, "stand": neu["stand"], "node_id": neu.get("node_id"),
            "link": _link(neu.get("node_id")),
            "ordner_verweigert": bool(ergebnis.get("folderDenied")),
            "bereits": bool(ergebnis.get("already"))}


async def _stand_festhalten(session: AsyncSession, session_id: str, entities: dict[str, Any],
                            index: int, ergebnis: dict[str, Any], *, kuerzel: str,
                            eintrag: dict[str, Any]) -> dict[str, Any]:
    """Den Stand eines Eintrags in den FRISCH gelesenen Teil schreiben (Befund 5 — die Dateien
    eines Stapels kommen nacheinander; so überschreibt auch ein zweiter Aufruf nichts Älteres).

    ``kuerzel``/``eintrag``: der Stapel und Eintrag DIESER Anfrage — nicht der frisch gelesene
    Teil, der inzwischen einem anderen Stapel gehören kann (Review Q1, Befund 2)."""
    eigener = {"index": index, "stand": str(ergebnis.get("status") or "unverified"),
               "node_id": ergebnis.get("nodeId")}
    teil = await vorgang_teil.lesen(session, session_id, entities)
    if teil is None:
        logger.warning("Ablage: Teil des Vorgangs nicht lesbar — Stand nicht festgehalten")
        return eigener

    async def neu() -> dict[str, Any] | None:
        # Unter der Sperre frisch gelesen (V-3). Gehört der Teil inzwischen einem anderen Stapel
        # (zweiter Tab hat neu vorbereitet), kommt ein Abgelegtes nach ``frueher`` statt in dessen
        # Eintrag gleichen Indexes (Review Q1, Befund 2).
        frisch = await vorgang_teil.lesen(session, session_id, entities)
        if frisch is None:
            return None
        if frisch.get("token_kuerzel") != kuerzel:
            return vorgang_teil.mit_frueher(frisch, eintrag, ergebnis)
        return vorgang_teil.mit_ergebnis(frisch, index, ergebnis)

    if not await vorgang_teil.speichern(session, session_id, entities, teil, neu=neu,
                                        nur_dieser=True):
        logger.warning("Ablage: Stand einer Datei nicht im Vorgang gespeichert")
    await _verweis_zurueckschreiben(session, session_id, entities)
    if teil.get("token_kuerzel") != kuerzel:
        return eigener
    return next(e for e in vorgang_teil.mit_ergebnis(teil, index, ergebnis)["inhalte"]
                if e["index"] == index)


@public_router.post("/abschluss")
@public_rate_limit
async def abschluss(anfrage: Abschluss, request: Request, response: Response,
                    session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str, Any]:
    entities = await _sitzung(request, session, anfrage.session_id, anfrage.block_id, frage=False)
    await _anmeldung(request)
    teil = await _teil_zum_schluessel(session, anfrage.session_id, entities, anfrage.batch_token,
                                      anfrage.block_id)
    if teil.get("abgeschlossen"):
        return {"stand": "stored", "bereits": True}
    try:
        ergebnis = await mcp_ablage.abschliessen(anfrage.batch_token)
    except mcp_ablage.AblageFehler as f:
        raise _fehler(f.code) from None
    if (code := mcp_ablage.grund(ergebnis)) is not None:
        raise _fehler(code)
    def abgeschlossen(t: dict[str, Any]) -> dict[str, Any]:
        neu_t = {**t, "abgeschlossen": ergebnis.get("status") == "stored"}
        if isinstance(ergebnis.get("nodeId"), str):
            neu_t["vorgang_node_id"] = ergebnis["nodeId"]
        return neu_t

    async def neu() -> dict[str, Any] | None:
        frisch = await vorgang_teil.lesen(session, anfrage.session_id, entities)
        # Review Q1, Befund 2: nur der eigene Stapel wird abgeschlossen.
        if frisch is None or frisch.get("token_kuerzel") != teil.get("token_kuerzel"):
            return None
        return abgeschlossen(frisch)

    teil = abgeschlossen(teil)
    if not await vorgang_teil.speichern(session, anfrage.session_id, entities, teil, neu=neu,
                                        nur_dieser=True):
        logger.warning("Ablage: Abschluss nicht im Vorgang gespeichert")
    await _verweis_zurueckschreiben(session, anfrage.session_id, entities)
    return {"stand": str(ergebnis.get("status") or "unverified"), "bereits": False}
