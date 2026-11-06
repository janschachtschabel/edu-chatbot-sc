"""Der Schritt ``auftrag`` im Zug (Paket K1a, Plan 2026-11-05 §5/§9) — b-api-Aufträge (Kestra).

- :func:`starter`: die Naht der Treiber-Umgebung — nur in einer eingerichteten Anlage
  (``client.freigeschaltet``) und mit **bestätigter Anmeldung** (Plan V-3: der Gast-Schlüssel teilt
  sich 20 Jobs). Ein abgewiesener Start liefert ``None`` (``bei_fehler``).
- :func:`pruefen` (Direktaktion ``ablauf_auftrag_pruefen {ablauf}``, Knopf „Stand prüfen“): fragt im
  Zug der Person ab — der Schlüssel, mit dem der Auftrag lief, wird nie gespeichert, ein Wächter im
  Hintergrund könnte ihn nicht lesen. Läuft noch → Hinweis; fertig → Ausgaben werden Teil
  ``schreibt``, der Treiber setzt fort; Fehler → ``bei_fehler`` oder Ende mit Hinweis.
- :func:`knopf` / :func:`pruefen_knopf`: die Schnellantwort, solange ein Lauf auf einen Auftrag
  wartet.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, Final

from boerdi.api.schemas import ChatRequest, ChatResponse
from boerdi.i18n import bot_text, resolve_locale
from boerdi.services import arbeitsstand, vorgaenge
from boerdi.services.ablauf import treiber
from boerdi.services.ablauf import zug_basis as basis
from boerdi.services.ablauf.ausloeser import laden
from boerdi.services.auftraege import ablage, client
from boerdi.services.llm_auth import hat_zug_schluessel
from boerdi.services.mcp.auth import has_personal_auth

logger = logging.getLogger(__name__)

AKTION: Final = "ablauf_auftrag_pruefen"
#: Gründe des Clients, die kein neuer Versuch heilt — der Auftrag gilt als gescheitert
#: (``bei_fehler``), statt dass „Stand prüfen“ endlos wiederkommt (Querschnitts-Review).
ENDGUELTIG: Final = frozenset({"unbekannt", "aus"})


def starter() -> Callable[[str, dict[str, Any]], Awaitable[str | None]] | None:
    """Die Start-Naht für den Treiber — ``None`` ohne Einrichtung, ohne Anmeldung oder ohne den
    durchgereichten Schlüssel der Person: sonst teilten alle Angemeldeten die 20 Aufträge von
    ``B_API_KEY`` (Plan V-3, Review K1a, Befund 1)."""
    if not client.freigeschaltet() or not has_personal_auth() or not hat_zug_schluessel():
        return None

    async def starte(flow: str, eingaben: dict[str, Any]) -> str | None:
        try:
            return await client.starten(flow, eingaben)
        except client.AuftragFehler as fehler:
            logger.info("Auftrag nicht gestartet (%s)", fehler.grund)
            return None

    return starte


def knopf(ablauf_id: str, lang: str) -> str:
    label = bot_text(lang, "action.ablauf.auftragKnopf").replace("|", "/")
    return f"__action__|{label}|{AKTION}|" + json.dumps({"ablauf": ablauf_id}, ensure_ascii=False)


def pruefen_knopf(session_id: str, session_state: dict[str, Any], lang: str) -> str | None:
    """„Stand prüfen“, solange ein Lauf dieser Person auf einen Auftrag wartet (nur der Verweis)."""
    vw = arbeitsstand.verweis(session_state.get("entities") or {},
                              arbeitsstand.aufrufer_fuer(session_id))
    lauf = (vw or {}).get("lauf")
    if not isinstance(lauf, dict) or lauf.get("status") != treiber.WARTET_AUFTRAG:
        return None
    # Review K1a, Befund 11: wie ``ki_schritt.aktueller`` — nur, solange der Ablauf gilt.
    ablauf = laden(lauf.get("ablauf"))
    if ablauf is None or not ablauf.aktiv or lauf.get("fassung") != treiber.fassung(ablauf):
        return None
    return knopf(ablauf.id, lang)


async def _mit_knopf(session: Any, req: ChatRequest, schluessel: str,
                     ablauf_id: str) -> ChatResponse:
    antwort = await basis.nur_text(session, req, schluessel)
    antwort.quick_replies = [knopf(ablauf_id, resolve_locale(req.environment.locale))]
    return antwort


async def pruefen(session: Any, req: ChatRequest, session_state: dict, *,
                  blocked_tools: Iterable[str] = ()) -> ChatResponse:
    entities = session_state.setdefault("entities", {})
    aufrufer = arbeitsstand.aufrufer_fuer(req.session_id)
    vw = arbeitsstand.verweis(entities, aufrufer)
    v = await vorgaenge.lesen(session, vw["id"], aufrufer) if vw else None
    lauf = (v.akte or {}).get("lauf") if v is not None else None
    gewollt = (req.action_params or {}).get("ablauf")
    if (not isinstance(lauf, dict) or lauf.get("ablauf") != gewollt
            or lauf.get("status") != treiber.WARTET_AUFTRAG):
        # Querschnitts-Review M5: der Verweis folgt dem Vorgang (zweite Sitzung, verdrängt).
        basis.verweis_auffrischen(entities, v, aufrufer)
        return await basis.nur_text(session, req, "action.ablauf.unbekannt", entities)
    ablauf = laden(gewollt)
    auftrag = await ablage.offen(session, v.id)
    if (ablauf is None or not ablauf.aktiv or lauf.get("fassung") != treiber.fassung(ablauf)
            or auftrag is None or auftrag.schritt != lauf.get("schritt")):
        await basis.abbrechen(session, v, lauf, entities, aufrufer)
        return await basis.nur_text(session, req, "action.ablauf.unbekannt", entities)
    if not hat_zug_schluessel():
        # Mit ``B_API_KEY`` sähe der Chatbot den Auftrag der Person nicht (K22) — und fragte nicht.
        return await _mit_knopf(session, req, "action.ablauf.auftragNichtAbrufbar", ablauf.id)
    await basis.frei(session)             # M7: die b-api-Abfrage hält keine DB-Verbindung
    try:
        stand = await client.stand(auftrag.job_id)
    except client.AuftragFehler as fehler:
        logger.info("Auftrag: Stand nicht abrufbar (%s)", fehler.grund)
        if fehler.grund == "abgewiesen":
            # Ein abgewiesener Schlüssel heilt kein zweiter Klick — der Lauf endet, damit ein
            # Neustart (Wendung, Modul) nicht am wartenden Lauf hängt (Review Q2, Befund 1).
            await basis.abbrechen(session, v, lauf, entities, aufrufer)
            return await basis.nur_text(session, req, "action.ablauf.auftragAbgewiesen", entities)
        if fehler.grund not in ENDGUELTIG:
            return await _mit_knopf(session, req, "action.ablauf.auftragNichtAbrufbar", ablauf.id)
        stand = client.Stand("fehler")    # Auftrag weg (30 Tage) oder Aufträge aus: gescheitert
    if stand.status == "laeuft":
        return await _mit_knopf(session, req, "action.ablauf.auftragLaeuft", ablauf.id)
    ergebnis = ({"outputs": stand.outputs, "dateien": stand.dateien}
                if stand.status == "fertig" else None)
    aus = await basis.rechne(session, ablauf, treiber.weiter_auftrag(
        ablauf, dict(lauf), ergebnis, basis.umgebung(session, req, entities, blocked_tools)))
    if aus is None:
        return await basis.nur_text(session, req, "action.ablauf.fehler", entities)
    try:
        await ablage.abschliessen(session, auftrag, stand.status)
        v = await basis.festhalten(session, v, aus)
        await session.commit()
    except vorgaenge.VorgangKonflikt:
        await session.rollback()
        basis.nicht_festgehalten(aus)
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    entities[arbeitsstand.VERWEIS] = arbeitsstand.verweis_fuer(v, aufrufer)
    return await basis.antwort(session, req, session_state, aus, ablauf)
