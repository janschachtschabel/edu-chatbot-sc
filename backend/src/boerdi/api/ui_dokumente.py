"""``POST /api/ui/dokumente`` — ein Dokument aus dem Auswahlfeld lesen (Paket U3-2a, Plan §16.6).

Öffentlich wie der Zweig des Themenbaums: das Widget lädt hoch, wenn die Person in ``ui_upload``
ein Dokument verwerten will (etwa „Themenbaum aus dem Strukturdokument“). Kein Zug und keine KI —
nur Umwandlung, Gliederung und Moderation; das Ergebnis bleibt an der Sitzung liegen
(``dokument_uploads``), bis der nächste Zug es serverseitig liest. Die Bremsen:

- außen ``@public_rate_limit`` (je IP-Netz), innen die Fenster der Redaktion (``check_rate_limit``),
- die Sitzung muss existieren und eine **offene Frage von ui_upload** mit dieser ``block_id``
  tragen (409 ``keine_anfrage``) — ohne Auswahlfeld kein Hochladen,
- Studio-Schalter (``01-base/upload-config``): ``dokument_im_chat`` (403 ``aus``), ohne Anmeldung
  nur mit ``dokument_ohne_anmeldung`` (403 ``nur_angemeldet``), Größe (413 ``zu_gross``; die
  Rumpf-Grenze des Pfads deckelt vorher hart, ``api/body_limit``),
- Fehlercodes des Dienstes ``services/dokumente/aufnahme`` — ``detail`` nie mit Servertext.

Plan 2026-11-16, TG-3e: Das Modul lässt mehrere Dokumente nacheinander lesen, jedes mit einem
eigenen Aufruf hier. Die Bremsen gelten je Aufruf (Vorgabe 30 je Minute und Sitzung). Die offene
Frage bleibt bis zur Antwort offen, darum gelingen alle mit derselben ``block_id``.

Plan 2026-11-17, Paket U („Hier im Chat“): Feld ``rolle`` — ``struktur`` (Vorgabe, wie vorher) oder
``inhalt``. Ein Inhalt bekommt nach Umwandlung und Moderation Kurzangaben aus einem LLM-Aufruf
(``dokumente/inhalt_angaben``), gespeichert am Upload; die Antwort trägt Befund, ``rolle`` und
``angaben`` — nie den Text. Grenzen je Sitzung (Studio ``lokal_max_dateien``,
``lokal_max_mb_gesamt``): 409 ``grenze_anzahl`` bzw. 413 ``grenze_gesamt`` — vorab ohne Sperre
(spart Umwandlung und LLM), verbindlich unter der Sperre in ``ablage.speichern``; es wird nichts
mehr verdrängt.

Plan 2026-11-19, Paket C: eine gescannte PDF liest die Texterkennung über das Chat-Modell
(``dokumente/ocr``), wenn sie an ist (Studio ``ocr``, Umgebung ``DOCUMENT_OCR`` nicht ``off``,
Anbieter mit Bildeingang) — höchstens ``ocr_max_seiten`` Seiten binnen :func:`ocr_frist`. Ihr
Verbrauch wird für die Sitzung gebucht (Quelle ``dokument_ocr``), auch wenn das Dokument danach
abgewiesen wird oder eine Ausnahme folgt (Review 14). Review 3: je Sitzung höchstens
``lokal_max_dateien × ocr_max_seiten`` Seiten (``ocr_sitzung``), danach 429 ``grenze_ocr``.

Datenschutz: die Rohdatei wird nicht gespeichert (``umwandlung``: Temp-Verzeichnis, gelöscht),
der Dateiname nie geloggt. Wie beim Zweig geht die Verbindung vor Anmeldung und Umwandlung in den
Pool zurück (``verbindung_freigeben``) — beides dauert, und „idle in transaction“ sperrt.
"""

from __future__ import annotations

import functools
import time
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.deps import get_session
from boerdi.api.ratelimit import peer_ip, public_rate_limit
from boerdi.api.schemas import SITZUNGSKENNUNG
from boerdi.api.turn_auth import (
    adopt_turn_auth_block,
    pruefe_oeffentliche_kennung,
    uebernimm_llm_schluessel,
)
from boerdi.db.verbindung import verbindung_freigeben
from boerdi.i18n import resolve_locale
from boerdi.obs.quality_events import log_safety_event
from boerdi.obs.usage import new_accumulator
from boerdi.services.config_loader.upload import load_upload_config
from boerdi.services.db_sessions import sitzung_entities, sitzung_vorhanden
from boerdi.services.dokumente import ablage, inhalt_angaben, ocr, ocr_sitzung
from boerdi.services.dokumente.aufnahme import Abweisung, aufbereiten, sauberer_name
from boerdi.services.dokumente.inhalt_angaben import ermitteln as inhalt_angaben_ermitteln
from boerdi.services.dokumente.ocr import OcrLesen
from boerdi.services.dokumente.ocr import aktiv as ocr_aktiv
from boerdi.services.mcp.anmeldung import bestaetige_anmeldung
from boerdi.services.mcp.auth import aufrufer_kennung, has_personal_auth
from boerdi.services.rate_limits import check_rate_limit
from boerdi.services.safety.moderation import moderate
from boerdi.services.usage_store import record_turn_usage
from boerdi.ui_module import upload_bereitgestellt as bereit
from boerdi.ui_module.antwort import OFFENE_FRAGE
from boerdi.ui_module.namen import UPLOAD
from boerdi.ui_module.rollen import ist_material

public_router = APIRouter(prefix="/api/ui", tags=["ui"])

_MIB = 1024 * 1024
#: So lange wartet die Person höchstens auf die Umwandlung (der Kindprozess hat seine eigene).
FRIST_S = 60.0
#: Frist der Texterkennung (Paket C), ab dem Beginn der Aufbereitung: 20 Seiten zu je 8 zugleich
#: sind drei Runden à 4–11 s (gemessen 39 s für 18 Seiten). Mit Moderation und Speichern unter der
#: Frist des Widgets (120 s ab dem Ende des Hochladens, ``dokument-transport.ANTWORT_FRIST_MS``) und
#: der Lesefrist des Ingress (120 s); was danach fehlt, ist ``gekuerzt``. Bei ``inhalt`` kürzer
#: (:func:`ocr_frist`).
OCR_FRIST_S = 80.0
_BLOCK = r"^[a-z0-9]{8,32}$"
_UPLOAD_ID = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
#: Paket U1: Grenzen der Sitzung (``ablage.GrenzeErreicht``) → Status.
_GRENZE_STATUS = {"grenze_anzahl": 409, "grenze_gesamt": 413}


class DokumentAntwort(BaseModel):
    """Was das Modul anzeigt und in seiner Antwort mitschickt — kein Text des Dokuments."""

    upload_id: str
    name: str
    format: str
    befund: dict[str, Any]
    ueberschriften_vorschau: list[str]
    #: Paket U2: ``inhalt`` (Material) oder ``struktur`` (Strukturdokument, Vorgabe wie vor U).
    rolle: Literal["inhalt", "struktur", "beides"] = "struktur"
    #: Paket U2: nur bei ``inhalt`` — ``{titel, beschreibung, schlagworte[, fach, stufe]}``; fehlt,
    #: wenn das LLM keine lieferte (der Titel entsteht dann aus dem Dateinamen).
    angaben: dict[str, Any] | None = None


class DokumentLoeschen(BaseModel):
    session_id: str = Field(pattern=f"^{SITZUNGSKENNUNG}$")
    upload_id: str = Field(pattern=_UPLOAD_ID)


async def _drosseln(request: Request, session: AsyncSession, session_id: str) -> str:
    ip = peer_ip(request)
    urteil = await check_rate_limit(session_id, ip,
                                    resolve_locale(request.headers.get("accept-language")))
    if not urteil.allowed:
        await log_safety_event(session, session_id, "",
                               decision={"reasons": [f"rate_limit:{urteil.reason}"]},
                               ip=ip, rate_limited=True)
        raise HTTPException(status_code=429, detail=urteil.blocked_message)
    return ip


def _offene_upload_frage(entities: dict[str, Any], block_id: str) -> bool:
    frage = entities.get(OFFENE_FRAGE)
    return (isinstance(frage, dict) and frage.get("modul") == UPLOAD
            and frage.get("block_id") == block_id)


def ocr_frist(rolle: str) -> float:
    """Review 4: bei ``inhalt`` folgen noch die Kurzangaben (``inhalt_angaben.FRIST_S``) — die
    Texterkennung bekommt um so viel weniger, damit alles unter der Frist des Widgets bleibt."""
    return OCR_FRIST_S - (inhalt_angaben.FRIST_S if ist_material(rolle) else 0.0)


def _ocr_lesen(session: AsyncSession, session_id: str, cfg: Any, rolle: str) -> OcrLesen | None:
    """Die Texterkennung für ``aufbereiten`` — ``None``, wenn sie aus ist (Paket C). Den Rest des
    Seitenbudgets liest und den Verbrauch bucht ``ocr_sitzung`` unter der Sperre der Sitzung
    (Review 3, zweites Review 2) — auch, wenn das Dokument danach abgewiesen wird oder eine
    Ausnahme folgt (Review 14); die Quelle ``dokument_ocr`` zählt das Budget."""
    if not ocr_aktiv(cfg):
        return None

    async def gebucht() -> int:
        return await ocr_sitzung.seiten_gebucht(session, session_id)

    async def buchen(verbrauch: dict[str, Any]) -> None:
        if await record_turn_usage(session, session_id, verbrauch, quelle=ocr.PHASE):
            await session.commit()

    return ocr_sitzung.leser(session_id=session_id,
                             budget=cfg.lokal_max_dateien * cfg.ocr_max_seiten,
                             seiten_max=cfg.ocr_max_seiten, gebucht=gebucht, buchen=buchen,
                             frist_ende=time.monotonic() + ocr_frist(rolle))


@public_router.post("/dokumente", response_model=DokumentAntwort,
                    response_model_exclude_none=True)
@public_rate_limit
async def dokument_hochladen(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    session_id: Annotated[str, Form(pattern=f"^{SITZUNGSKENNUNG}$")],
    block_id: Annotated[str, Form(pattern=_BLOCK)],
    datei: Annotated[UploadFile, File()],
    rolle: Annotated[Literal["inhalt", "struktur", "beides"], Form()] = "struktur",
) -> DokumentAntwort:
    """Liest das Dokument, legt Markdown und Gliederung an der Sitzung ab, gibt den Befund.

    ``response`` braucht der Decorator der Drosselung für seine Kopfzeilen (wie beim Zweig)."""
    pruefe_oeffentliche_kennung(request, session_id)
    ip = await _drosseln(request, session, session_id)
    entities = await sitzung_entities(session, session_id)
    if entities is None:
        raise HTTPException(status_code=404, detail="sitzung_unbekannt")
    if not _offene_upload_frage(entities, block_id):
        raise HTTPException(status_code=409, detail="keine_anfrage")
    if not bereit.ort_erlaubt(entities.get(OFFENE_FRAGE), "chat"):
        # Review Paket U, MINOR 4: der Ablauf lässt „Hier im Chat“ nicht zu (nicht nur die
        # Oberfläche sperrt den Ort)
        raise HTTPException(status_code=403, detail="ort_nicht_erlaubt")
    await verbindung_freigeben(session)
    # Die Moderation rechnet über den Schlüssel des Zuges ab (Paket 17), keine Pflicht.
    uebernimm_llm_schluessel(request, pflicht=False)
    adopt_turn_auth_block(request)
    await bestaetige_anmeldung()
    cfg = load_upload_config()
    if not cfg.dokument_im_chat:
        raise HTTPException(status_code=403, detail="aus")
    person = has_personal_auth()
    if not (person or cfg.dokument_ohne_anmeldung):
        raise HTTPException(status_code=403, detail="nur_angemeldet")
    rumpf = await datei.read(cfg.max_mb * _MIB + 1)
    if len(rumpf) > cfg.max_mb * _MIB:
        raise HTTPException(status_code=413, detail="zu_gross")
    name = sauberer_name(datei.filename or "")
    # Paket U1: über den Grenzen der Sitzung erst gar nicht umwandeln (verbindlich in ``speichern``)
    if code := await ablage.grenze_vorab(session, session_id, block_id=block_id, name=name,
                                         groesse=len(rumpf)):
        raise HTTPException(status_code=_GRENZE_STATUS[code], detail=code)
    await verbindung_freigeben(session)
    erg = await aufbereiten(rumpf, datei.filename or "", max_seiten=cfg.max_seiten,
                            frist_s=FRIST_S,
                            # Eigene Stufe (Nachprüfung Q4): nicht im Alarm der Chat-Züge.
                            moderieren=functools.partial(moderate, stufe="dokument_aufnahme"),
                            ocr_lesen=_ocr_lesen(session, session_id, cfg, rolle))
    if isinstance(erg, Abweisung):
        if erg.code == "abgewiesen":
            await log_safety_event(session, session_id, "",
                                   decision={"reasons": ["upload:moderation"]}, ip=ip)
        raise HTTPException(status_code=erg.status, detail=erg.code)
    # Paket U2: Kurzangaben nur für Inhalte, nach Umwandlung und Moderation (der Anfang, den das
    # LLM sieht, ist der moderierte, ``inhalt_angaben``)
    angaben = None
    # P1 (Plan 2026-11-20): ``beides`` ist auch ein Inhalt
    if ist_material(rolle):
        verbrauch = new_accumulator()
        angaben = await inhalt_angaben_ermitteln(erg.markdown, name, usage_acc=verbrauch)
        # Kosten sichtbar (Wächter ``test_usage_coverage``): für die Sitzung gebucht, gleich hier —
        # auch wenn das Speichern danach an der Grenze scheitert, war der Aufruf bezahlt
        if await record_turn_usage(session, session_id, verbrauch):
            await session.commit()
    try:
        kennung = await ablage.speichern(
            session, session_id=session_id, block_id=block_id,
            aufrufer=aufrufer_kennung() if person else None, name=name, format=erg.format,
            groesse=len(rumpf), befund=erg.befund, gliederung=erg.gliederung,
            markdown=erg.markdown, ttl_h=cfg.aufbewahrung_h, rolle=rolle, angaben=angaben)
        await session.commit()
    except ablage.GrenzeErreicht as grenze:
        await session.rollback()
        raise HTTPException(status_code=_GRENZE_STATUS[grenze.code], detail=grenze.code) from None
    except IntegrityError:
        # Wurde die Sitzung inzwischen gelöscht (Fremdschlüssel), ist das 404 (Review U3-2,
        # Befund 17). Plan 2026-11-16, TG-3e: zwei Uploads derselben Sitzung zugleich sind kein
        # Konflikt mehr (bis zu fünf Dokumente, ``ablage.speichern`` zählt sie nacheinander) — ein
        # anderer Schlüsselkonflikt bleibt 409.
        await session.rollback()
        if not await sitzung_vorhanden(session, session_id):
            raise HTTPException(status_code=404, detail="sitzung_unbekannt") from None
        raise HTTPException(status_code=409, detail="laeuft_schon") from None
    return DokumentAntwort(upload_id=kennung, name=name, format=erg.format, befund=erg.befund,
                           ueberschriften_vorschau=erg.vorschau, rolle=rolle, angaben=angaben)


@public_router.post("/dokumente/loeschen", status_code=204)
@public_rate_limit
async def dokument_loeschen(
    anfrage: DokumentLoeschen,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Löscht das Dokument — 204 auch für fremde oder unbekannte Kennungen (verrät nichts)."""
    pruefe_oeffentliche_kennung(request, anfrage.session_id)
    await ablage.loeschen(session, anfrage.session_id, anfrage.upload_id)
    await session.commit()
    return Response(status_code=204)
