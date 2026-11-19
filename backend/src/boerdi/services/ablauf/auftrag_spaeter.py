"""„Später weitermachen“ am gesperrten Auftragsschritt (Paket K7, Plan 2026-11-17, E16/E17).

Direktaktion ``ablauf_auftrag_spaeter {ablauf}`` — der dritte Knopf neben „Stand prüfen“ und
„Auftrag abbrechen“ (``auftrag_zug.knoepfe``), solange die Eingabe gesperrt ist:

- Der Lauf bleibt ``wartet_auftrag`` im Vorgang, der Auftrag läuft weiter — keine Abfrage, kein
  Abbruch, nichts am Vorgang wird geschrieben.
- Die Sperre ruht für diese Sitzung (``auftrag_zug.spaeter_merken``, Marke in ``entities``). Zurück
  führt „Stand prüfen“ — auch „Fortsetzen“ unter „Meine Vorgänge“ schickt es; dann greift die
  Sperre wieder, solange der Auftrag läuft (``auftrag_zug.pruefen``).
- Der Satz nennt die Frist (:func:`rueckkehr_frist`): die frühere von Aufbewahrung des Vorgangs
  (``verfaellt_am``, nach den Tagen aus dem Studio; der Aufbewahrungslauf löscht danach) und den
  30 Tagen, die die b-api einen Job hält (``client.JOB_TAGE``).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Final

from boerdi.api.schemas import ChatRequest, ChatResponse
from boerdi.i18n import bot_text, resolve_locale
from boerdi.services import arbeitsstand, vorgaenge
from boerdi.services.ablauf import auftrag_zug, treiber
from boerdi.services.ablauf import zug_basis as basis
from boerdi.services.ablauf.ausloeser import laden
from boerdi.services.auftraege import ablage, client

_MONATE_EN: Final = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
                     "Dec")


def _mit_zone(zeit: datetime) -> datetime:
    return zeit if zeit.tzinfo is not None else zeit.replace(tzinfo=UTC)


def rueckkehr_frist(verfaellt_am: datetime | None, erstellt: datetime | None) -> datetime | None:
    """Bis wann die Person zurückkehren kann: die frühere von Ablauf des Vorgangs und Start des
    Jobs + :data:`client.JOB_TAGE` — ``None`` ohne beides."""
    grenzen = [_mit_zone(verfaellt_am)] if verfaellt_am is not None else []
    if erstellt is not None:
        grenzen.append(_mit_zone(erstellt) + timedelta(days=client.JOB_TAGE))
    return min(grenzen) if grenzen else None


def datum(frist: datetime, lang: str, *, jetzt: datetime | None = None) -> str:
    """Der letzte sichere Tag vor ``frist`` (der Tag davor, UTC) — die Uhrzeit des Ablaufs kennt die
    Person nicht; nie vor heute (Review B7: bleibt weniger als ein Tag, wäre es sonst gestern).
    Deutsch ``02.12.2026``, Englisch ``2 Dec 2026``."""
    heute = _mit_zone(jetzt or datetime.now(UTC)).astimezone(UTC).date()
    tag = max((_mit_zone(frist).astimezone(UTC) - timedelta(days=1)).date(), heute)
    if lang == "en":
        return f"{tag.day} {_MONATE_EN[tag.month - 1]} {tag.year}"
    return tag.strftime("%d.%m.%Y")


async def spaeter(session: Any, req: ChatRequest, session_state: dict) -> ChatResponse:
    """Die Direktaktion: die Sperre ruht, der Lauf wartet weiter; der Satz nennt die Frist."""
    entities = session_state.setdefault("entities", {})
    aufrufer = arbeitsstand.aufrufer_fuer(req.session_id)
    vw = arbeitsstand.verweis(entities, aufrufer)
    v = await vorgaenge.lesen(session, vw["id"], aufrufer) if vw else None
    lauf = (v.akte or {}).get("lauf") if v is not None else None
    gewollt = (req.action_params or {}).get("ablauf")
    basis.verweis_auffrischen(entities, v, aufrufer)
    if (not isinstance(lauf, dict) or lauf.get("ablauf") != gewollt
            or lauf.get("status") != treiber.WARTET_AUFTRAG
            or not auftrag_zug.spaeter_merken(req.session_id, session_state)):
        # wie „Auftrag abbrechen“: ein alter Knopf nach dem Ende des Auftrags
        beendet = ((isinstance(lauf, dict) and lauf.get("ablauf") == gewollt)
                   or (v is None and isinstance(gewollt, str) and laden(gewollt) is not None))
        return await basis.nur_text(
            session, req, "action.ablauf.auftragSchonBeendet" if beendet
            else "action.ablauf.unbekannt", entities)
    lang = resolve_locale(req.environment.locale)
    offen = await ablage.offen(session, v.id)
    frist = rueckkehr_frist(getattr(v, "verfaellt_am", None), getattr(offen, "erstellt", None))
    # ohne beide Grenzen (kommt nicht vor: ``verfaellt_am`` ist Pflicht) das Mindeste eines
    # wartenden Vorgangs
    frist = frist or datetime.now(UTC) + timedelta(days=vorgaenge.WARTET_AUFTRAG_TAGE)
    text = bot_text(lang, "action.ablauf.auftragSpaeter", datum=datum(frist, lang))
    return await basis.fester_text(session, req, text, entities,
                                   knoepfe=[auftrag_zug.knopf(gewollt, lang)])
