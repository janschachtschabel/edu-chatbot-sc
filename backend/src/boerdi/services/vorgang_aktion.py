"""Direktaktionen zum Arbeitsstand (Querschnitts-Review 2026-11-06, M6 und Datenschutz).

- ``vorgang_neu`` („neues Vorhaben“): schließt den aktiven Vorgang (Status ``fertig``; ein wartender
  Lauf wird ``abgebrochen``, sein Auftrag ebenso). Neue Teile landen danach in einem neuen Vorgang.
  Wartet ein Lauf auf einen Auftrag, fragt es erst nach — wie „Auftrag abbrechen“ (K2b); die
  Bestätigung gilt nur für diesen Auftrag (Kürzel).
- ``vorgang_loeschen`` („Arbeitsstand löschen“): fragt erst nach; mit ``{"bestaetigt": true}``
  löscht er **alle** Vorgänge der Person samt Ablage und Aufträgen (Kaskade), auch abgeschlossene,
  dazu die anonymen Vorgänge dieser Sitzung und ihr hochgeladenes Dokument — der Löschweg für eine
  angemeldete Person, deren Vorgänge sonst erst mit der Frist gehen. Laufende Aufträge enden nach
  dem Festschreiben auch bei der b-api (``DELETE``, Job-Vertrag 2026-11-07) — nur mit dem
  Schlüssel der Person; ihre Ein- und Ausgaben liegen dort weiter bis zu 30 Tage.

Beide räumen auch den gemerkten Entwurf der Sitzung (``strukturentwurf_merken``) ab. Nur für die
eigenen Vorgänge (``aufrufer``), ohne Modell, hinter der Sicherheitsprüfung des Preflights wie jede
Direktaktion. Den Einstieg setzt das Backend: Knöpfe unter einem fertigen Ablauf (:func:`knoepfe`,
``zug_basis.antwort``) — das Modell schreibt keine ``__action__``-Knöpfe. Außerhalb eines Ablaufs
zeigt seit AS-Ud „Meine Vorgänge“ im Widget die Vorgänge anderer Gespräche und löscht sie einzeln
(``api/ui_vorgaenge.py``); „alle löschen“ bleibt diese Direktaktion.
"""

from __future__ import annotations

import json
from typing import Any, Final

from sqlalchemy.exc import DBAPIError

from boerdi.api.schemas import ChatRequest, ChatResponse
from boerdi.domain.write_confirm import OFFENER_PLAN_KEY
from boerdi.i18n import bot_text, resolve_locale
from boerdi.services import arbeitsstand, vorgaenge
from boerdi.services.ablauf import treiber
from boerdi.services.ablauf import zug_basis as basis
from boerdi.services.auftraege import ablage as auftraege_ablage
from boerdi.services.auftraege import client as auftraege_client
from boerdi.services.dokumente import ablage as dokumente
from boerdi.ui_module import strukturentwurf_merken

AKTION_NEU: Final = "vorgang_neu"
AKTION_LOESCHEN: Final = "vorgang_loeschen"


def _knopf(lang: str, schluessel: str, aktion: str, params: dict[str, Any] | None = None) -> str:
    label = bot_text(lang, schluessel).replace("|", "/")
    return f"__action__|{label}|{aktion}|" + json.dumps(params or {}, ensure_ascii=False)


def knoepfe(lang: str) -> list[str]:
    """„Neues Vorhaben“ und „Arbeitsstand löschen“ als Schnellantworten."""
    return [_knopf(lang, "action.vorgang.neuKnopf", AKTION_NEU),
            _knopf(lang, "action.vorgang.loeschenKnopf", AKTION_LOESCHEN)]


async def neu(session: Any, req: ChatRequest, session_state: dict) -> ChatResponse:
    entities = session_state.setdefault("entities", {})
    aufrufer = arbeitsstand.aufrufer_fuer(req.session_id)
    vw = arbeitsstand.verweis(entities, aufrufer)
    v = await vorgaenge.lesen(session, vw["id"], aufrufer) if vw else None
    if v is None or v.status in vorgaenge.ABGESCHLOSSEN:
        arbeitsstand.verweis_weg(entities, aufrufer)
        entities.pop(strukturentwurf_merken.KEY, None)
        return await basis.nur_text(session, req, "action.vorgang.keiner", entities)
    if (frage := await _neu_rueckfrage(session, req, v, entities)) is not None:
        return frage
    try:
        alter_job = await basis.schliessen(session, v)
        await session.commit()
    except vorgaenge.VorgangKonflikt:
        await session.rollback()
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    basis.bei_der_b_api_abbrechen(alter_job)
    arbeitsstand.verweis_weg(entities, aufrufer)
    entities.pop(strukturentwurf_merken.KEY, None)
    return await basis.nur_text(session, req, "action.vorgang.neu", entities)


async def _neu_rueckfrage(session: Any, req: ChatRequest, v: Any,
                          entities: dict[str, Any]) -> ChatResponse | None:
    """Zweites Review K2b, Befund 5: ein alter „Neues Vorhaben“-Knopf im Verlauf beendete sonst
    still einen laufenden Auftrag — die Rückfrage, die „Auftrag abbrechen“ stellt, fehlte hier."""
    lauf = (v.akte or {}).get("lauf")
    if not isinstance(lauf, dict) or lauf.get("status") != treiber.WARTET_AUFTRAG:
        return None
    offen = await auftraege_ablage.offen(session, v.id)
    jetzt = auftraege_client.kuerzel(offen.job_id) if offen is not None else ""
    params = req.action_params or {}
    if params.get("bestaetigt") is True and params.get("kuerzel") == jetzt:
        return None
    antwort = await basis.nur_text(session, req, "action.vorgang.neuFrage", entities)
    antwort.quick_replies = [_knopf(resolve_locale(req.environment.locale), "action.vorgang.neuJa",
                                    AKTION_NEU, {"bestaetigt": True, "kuerzel": jetzt})]
    return antwort


async def loeschen(session: Any, req: ChatRequest, session_state: dict) -> ChatResponse:
    entities = session_state.setdefault("entities", {})
    if (req.action_params or {}).get("bestaetigt") is not True:
        # Review Q3, Befund 4: Löschen lässt sich nicht zurücknehmen — erst nachfragen.
        antwort = await basis.nur_text(session, req, "action.vorgang.loeschenFrage", entities)
        antwort.quick_replies = [_knopf(resolve_locale(req.environment.locale),
                                        "action.vorgang.loeschenJa", AKTION_LOESCHEN,
                                        {"bestaetigt": True})]
        return antwort
    aufrufer = arbeitsstand.aufrufer_fuer(req.session_id)
    hatte = arbeitsstand.verweis(entities, aufrufer) is not None
    # Job-Vertrag 2026-11-07: offene Aufträge gingen per Kaskade mit, liefen bei der b-api aber
    # weiter (Grenze von 20 je Schlüssel) — die Job-IDs vorher lesen, nach dem Festschreiben enden.
    besitz = [aufrufer, f"sitzung:{req.session_id}"]
    try:
        # Querschnitts-Review AS-U/BU, Q-5: erst sperren — ein gleichzeitig eingetragener Auftrag
        # wartet bis zum Festschreiben, statt ungelesen per Kaskade mitzugehen
        await vorgaenge.alle_sperren(session, besitz)
        offene = await auftraege_ablage.offene_job_ids(session, besitz)
        zahl = await vorgaenge.alle_loeschen(session, aufrufer)
        # Nachprüfung, Befund 11: auch die anonymen Vorgänge dieser Sitzung (vor der Anmeldung) und
        # ihr hochgeladenes Dokument — die Rückfrage nennt beides.
        zahl += await vorgaenge.anonyme_der_sitzung_loeschen(session, req.session_id)
        zahl += await dokumente.der_sitzung_loeschen(session, req.session_id)
        await session.commit()
    except DBAPIError as fehler:
        # Zweites Review, Z-4: ein Deadlock (anderer Zug sperrte zugleich) ist ein Konflikt, kein
        # Fehler des Zugs — nichts gelöscht, die Person kann es noch einmal versuchen.
        if not vorgaenge.ist_deadlock(fehler):
            raise
        await session.rollback()
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    basis.bei_der_b_api_abbrechen(*offene)
    arbeitsstand.verweis_weg(entities, aufrufer)
    entities.pop(strukturentwurf_merken.KEY, None)
    entities.pop(OFFENER_PLAN_KEY, None)  # Paket M5 (Review, Befund 7)
    schluessel = "action.vorgang.geloescht" if zahl or hatte else "action.vorgang.keiner"
    return await basis.nur_text(session, req, schluessel, entities)
