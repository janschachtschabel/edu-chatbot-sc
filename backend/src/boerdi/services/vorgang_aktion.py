"""Direktaktionen zum Arbeitsstand (Querschnitts-Review 2026-11-06, M6 und Datenschutz).

- ``vorgang_neu`` („neues Vorhaben“): schließt den aktiven Vorgang (Status ``fertig``; ein wartender
  Lauf wird ``abgebrochen``, sein Auftrag ebenso). Neue Teile landen danach in einem neuen Vorgang.
- ``vorgang_loeschen`` („Arbeitsstand löschen“): fragt erst nach; mit ``{"bestaetigt": true}``
  löscht er **alle** Vorgänge der Person samt Ablage und Aufträgen (Kaskade), auch abgeschlossene,
  dazu die anonymen Vorgänge dieser Sitzung und ihr hochgeladenes Dokument — der Löschweg für eine
  angemeldete Person, deren Vorgänge sonst erst mit der Frist gehen. Einen laufenden Auftrag bei
  der b-api bricht er nicht ab (keine Schnittstelle, K21); dessen Ergebnis liegt dort bis zu 30
  Tage, abgeholt wird es nicht mehr.

Beide räumen auch den gemerkten Entwurf der Sitzung (``strukturentwurf_merken``) ab. Nur für die
eigenen Vorgänge (``aufrufer``), ohne Modell, hinter der Sicherheitsprüfung des Preflights wie jede
Direktaktion. Den Einstieg setzt das Backend: Knöpfe unter einem fertigen Ablauf (:func:`knoepfe`,
``zug_basis.antwort``) — das Modell schreibt keine ``__action__``-Knöpfe. simplify: ein Einstieg
außerhalb eines Ablaufs (Menü im Widget) ist eine offene Entscheidung.
"""

from __future__ import annotations

import json
from typing import Any, Final

from boerdi.api.schemas import ChatRequest, ChatResponse
from boerdi.i18n import bot_text, resolve_locale
from boerdi.services import arbeitsstand, vorgaenge
from boerdi.services.ablauf import zug_basis as basis
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
    try:
        await basis.schliessen(session, v)
        await session.commit()
    except vorgaenge.VorgangKonflikt:
        await session.rollback()
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    arbeitsstand.verweis_weg(entities, aufrufer)
    entities.pop(strukturentwurf_merken.KEY, None)
    return await basis.nur_text(session, req, "action.vorgang.neu", entities)


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
    zahl = await vorgaenge.alle_loeschen(session, aufrufer)
    # Nachprüfung, Befund 11: auch die anonymen Vorgänge dieser Sitzung (vor der Anmeldung) und ihr
    # hochgeladenes Dokument — die Rückfrage nennt beides.
    zahl += await vorgaenge.anonyme_der_sitzung_loeschen(session, req.session_id)
    zahl += await dokumente.der_sitzung_loeschen(session, req.session_id)
    await session.commit()
    arbeitsstand.verweis_weg(entities, aufrufer)
    entities.pop(strukturentwurf_merken.KEY, None)
    schluessel = "action.vorgang.geloescht" if zahl or hatte else "action.vorgang.keiner"
    return await basis.nur_text(session, req, schluessel, entities)
