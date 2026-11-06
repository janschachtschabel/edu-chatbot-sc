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

Datenschutz: die Rohdatei wird nicht gespeichert (``umwandlung``: Temp-Verzeichnis, gelöscht),
der Dateiname nie geloggt. Wie beim Zweig geht die Verbindung vor Anmeldung und Umwandlung in den
Pool zurück (``verbindung_freigeben``) — beides dauert, und „idle in transaction“ sperrt.
"""

from __future__ import annotations

import functools
from typing import Annotated, Any

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
from boerdi.services.config_loader.upload import load_upload_config
from boerdi.services.db_sessions import sitzung_entities, sitzung_vorhanden
from boerdi.services.dokumente import ablage
from boerdi.services.dokumente.aufnahme import Abweisung, aufbereiten, sauberer_name
from boerdi.services.mcp.anmeldung import bestaetige_anmeldung
from boerdi.services.mcp.auth import aufrufer_kennung, has_personal_auth
from boerdi.services.rate_limits import check_rate_limit
from boerdi.services.safety.moderation import moderate
from boerdi.ui_module.antwort import OFFENE_FRAGE
from boerdi.ui_module.namen import UPLOAD

public_router = APIRouter(prefix="/api/ui", tags=["ui"])

_MIB = 1024 * 1024
#: So lange wartet die Person höchstens auf die Umwandlung (der Kindprozess hat seine eigene).
FRIST_S = 60.0
_BLOCK = r"^[a-z0-9]{8,32}$"
_UPLOAD_ID = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"


class DokumentAntwort(BaseModel):
    """Was das Modul anzeigt und in seiner Antwort mitschickt — kein Text des Dokuments."""

    upload_id: str
    name: str
    format: str
    befund: dict[str, Any]
    ueberschriften_vorschau: list[str]


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


@public_router.post("/dokumente", response_model=DokumentAntwort)
@public_rate_limit
async def dokument_hochladen(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    session_id: Annotated[str, Form(pattern=f"^{SITZUNGSKENNUNG}$")],
    block_id: Annotated[str, Form(pattern=_BLOCK)],
    datei: Annotated[UploadFile, File()],
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
    erg = await aufbereiten(rumpf, datei.filename or "", max_seiten=cfg.max_seiten,
                            frist_s=FRIST_S,
                            # Eigene Stufe (Nachprüfung Q4): nicht im Alarm der Chat-Züge.
                            moderieren=functools.partial(moderate, stufe="dokument_aufnahme"))
    if isinstance(erg, Abweisung):
        if erg.code == "abgewiesen":
            await log_safety_event(session, session_id, "",
                                   decision={"reasons": ["upload:moderation"]}, ip=ip)
        raise HTTPException(status_code=erg.status, detail=erg.code)
    name = sauberer_name(datei.filename or "")
    try:
        kennung = await ablage.speichern(
            session, session_id=session_id, block_id=block_id,
            aufrufer=aufrufer_kennung() if person else None, name=name, format=erg.format,
            groesse=len(rumpf), befund=erg.befund, gliederung=erg.gliederung,
            markdown=erg.markdown, ttl_h=cfg.aufbewahrung_h)
        await session.commit()
    except IntegrityError:
        # Zwei Uploads derselben Sitzung zugleich (eindeutige Sitzung): einer gewinnt, der andere
        # erfährt es. Wurde die Sitzung inzwischen gelöscht (Fremdschlüssel), ist das 404
        # (Review U3-2, Befund 17).
        await session.rollback()
        if not await sitzung_vorhanden(session, session_id):
            raise HTTPException(status_code=404, detail="sitzung_unbekannt") from None
        raise HTTPException(status_code=409, detail="laeuft_schon") from None
    return DokumentAntwort(upload_id=kennung, name=name, format=erg.format, befund=erg.befund,
                           ueberschriften_vorschau=erg.vorschau)


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
