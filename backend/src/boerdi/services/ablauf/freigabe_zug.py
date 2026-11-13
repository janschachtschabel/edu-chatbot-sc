"""Paket S (Plan 2026-11-08): der Zug eines schreibenden Ablaufschritts mit Freigabe.

Der Treiber legt eine Änderung nur **vor** (:func:`vorleger`: das Werkzeug ohne Schlüssel, FS-1).
Diese Datei macht daraus dieselbe offene Abnahme wie im Chat (:func:`merken`: ``_pending_write`` mit
Aufrufer und Vorschau, dazu die Marke :data:`MARKE`) — eingelöst wird sie vom Vorlauf
(``write_approval.redeem_write_approval``) nach derselben Zustimmungsprüfung. Danach gibt
:func:`nach_einloesen` das Ergebnis an den Treiber (``treiber.weiter_freigabe``):

- eingelöst → Teil ``schreibt``, der nächste Schritt (FS-9);
- vom Server abgelehnt → ``bei_fehler``, sonst Ende mit Fehler (FS-8);
- Ausgang offen (keine Antwort nach dem Ja) → Ende mit Fehler, nie ``bei_fehler`` (FS-7);
- neu vorgelegt (Schlüssel abgelaufen) → die neue Abnahme trägt die Marke weiter;
- liegen gelassen (ausgelastet, Anmeldung oder Zustimmung unklar) → nichts, der Lauf wartet;
- verbraucht ohne Schreiben → der Lauf wartet; „Vorschau erneut zeigen“ (FS-6).

Ein Nein verwirft die Abnahme wie im Chat (``discard_stale_approval``); der Lauf wartet, unter
jeder Antwort steht „Vorschau erneut zeigen“ (:func:`weiter_knopf`). Ein Modell sieht den Schlüssel
nie.

Review S2/S3:
- Vorgelegt wird nur, was auch eingelöst werden dürfte (``write_approval.nicht_einloesbar``:
  Schreibrecht, im Studio verborgen, lesende Einbettung) — sonst hinge der Lauf (Befund 2).
- WLO ausgelastet, keine Antwort oder Anmeldung abgewiesen beim Vorlegen: der Lauf wartet mit
  „Vorschau erneut zeigen“; eine Ablehnung der Vorschau nennt ihren Grund (Befunde 8, 9).
- Eine abgelaufene Abnahme eines Laufs fängt der Vorlauf ab (:func:`vor_einloesen`, Befund 3),
  ebenso eine, deren Lauf nicht mehr auf sie wartet (Gesamt-Review, Befund 4).
- Jede Vorlage hat eine Kennung (``lauf.freigabe_id`` = Marke ``id``): ein „ja“ zu einer alten
  Vorschau setzt keinen neu gestarteten Lauf fort (Befund 6).
- Erfolg nur bei ``reason == "eingeloest"`` (Befund 7); das Ergebnis ohne Schlüsselfelder
  (Befund 11).
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterable
from typing import Any, Final

from boerdi.api.schemas import ChatRequest, ChatResponse
from boerdi.api.schemas_ui import UiInfo
from boerdi.domain.inline_documents import als_inhaltsrahmen
from boerdi.domain.write_anzeige import merke_vorschau, preview_for_display
from boerdi.domain.write_confirm import (
    MAX_REMEMBERED_ARGS_BYTES,
    TOKEN_TTL_SECONDS,
    extract_confirm_token,
    is_expired,
    redact_confirm_token,
    remember_pending,
)
from boerdi.i18n import bot_text, resolve_locale
from boerdi.services import arbeitsstand, plan_fortsetzen, vorgaenge
from boerdi.services.ablauf import freigabe_ergebnis, treiber
from boerdi.services.ablauf import zug_basis as basis
from boerdi.services.ablauf.ausloeser import laden
from boerdi.services.db_sessions import (
    FESTER_TEXT_KEY,
    an_letzte_antwort_anhaengen,
    save_message,
    update_session,
)
from boerdi.services.mcp.auth import aufrufer_kennung
from boerdi.services.schreibrecht import schreiben_erlaubt

logger = logging.getLogger(__name__)

#: „Vorschau erneut zeigen“ und „Ablauf abbrechen“ am wartenden Freigabe-Schritt (FS-6).
AKTION_ERNEUT: Final = "ablauf_freigabe_erneut"
AKTION_ABBRECHEN: Final = "ablauf_freigabe_abbrechen"
#: In der offenen Abnahme: zu welchem Lauf sie gehört (``{ablauf, schritt, id}``).
MARKE: Final = "ablauf"
#: Vom Vorlauf gesetzt (``write_approval``): der strukturierte Teil einer eingelösten Antwort.
ERGEBNIS: Final = "_eingeloest_ergebnis"
_PENDING: Final = "_pending_write"
#: Gründe von ``redeem_write_approval``, nach denen die Abnahme (neu) bereitliegt.
_LIEGT_BEREIT: Final = frozenset({"busy", "anmeldung_unklar", "zustimmung_unklar",
                                  "confirm_renewed"})
#: Arten eines Fehlers beim Vorlegen, nach denen der Lauf wartet (nichts geschrieben, später neu).
_VORUEBERGEHEND: Final = frozenset({"busy", "transport", "timeout", "auth"})


# ── Vorlegen ──────────────────────────────────────────────────────────────────────────────────

def vorleger(req: ChatRequest) -> Any:
    """Die Naht ``Umgebung.vorlegen`` — ``None`` ohne Schreibrecht (FS-5: dann gibt es nichts
    vorzulegen, der Schritt geht zu ``bei_fehler``)."""
    if not schreiben_erlaubt():
        return None
    lang = resolve_locale(req.environment.locale)

    async def vorlegen(name: str, args: dict[str, Any]) -> treiber.Vorlage | None:
        return await _vorlegen(name, args, req, lang)

    return vorlegen


async def _vorlegen(name: str, args: dict[str, Any], req: ChatRequest, lang: str
                    ) -> treiber.Vorlage | None:
    from boerdi.services.mcp.client import call_mcp_tool_antwort, is_mcp_error, nimm_bestaetigung
    from boerdi.services.write_approval import abgelehnt_text, nicht_einloesbar

    if grund := nicht_einloesbar(name, req):
        logger.info("Ablauf: Freigabe für %s nicht vorgelegt (%s)", name, grund)
        return None
    if len(json.dumps(args, ensure_ascii=False, default=str)) > MAX_REMEMBERED_ARGS_BYTES:
        # Ohne gemerkte Angaben ließe sich die Freigabe nie einlösen (nur der Fingerabdruck-Weg
        # des Modells, das die Angaben nicht kennt) — lieber gar nicht vorlegen.
        logger.info("Ablauf: Freigabe für %s — Angaben zu groß zum Merken", name)
        return treiber.Vorlage(bot_text(lang, "write.planTooLarge"), None, ausfall="abgelehnt")
    antwort = await call_mcp_tool_antwort(name, args, use_cache=False)
    art, code = antwort.art, antwort.code
    if art in _VORUEBERGEHEND:
        logger.info("Ablauf: Vorschau für %s gerade nicht möglich (%s)", name, art)
        return treiber.Vorlage(bot_text(lang, "action.ablauf.freigabeSpaeter"), None,
                               ausfall="voruebergehend")
    if antwort.art or is_mcp_error(antwort.text):
        logger.info("Ablauf: Vorschau für %s abgelehnt (%s)", name, code or "fehler")
        return treiber.Vorlage(abgelehnt_text(lang, antwort), None, ausfall="abgelehnt")
    schluessel = nimm_bestaetigung(name, args)
    if schluessel is None:
        schluessel = extract_confirm_token(antwort.text)
    return treiber.Vorlage(text=redact_confirm_token(antwort.text), schluessel=schluessel or None)


def merken(entities: dict[str, Any], freigabe: dict[str, Any], ablauf_id: str, lang: str) -> Any:
    """Die vorgelegte Änderung als offene Abnahme merken; zurück kommt die Vorschau-Box."""
    from boerdi.api.schemas import InlineDocument

    text = str(freigabe.get("vorschau") or "")
    pending = merke_vorschau(remember_pending(
        str(freigabe["werkzeug"]), dict(freigabe["args"]), str(freigabe["schluessel"]),
        now=time.time(), caller=aufrufer_kennung()), text)
    pending[MARKE] = {"ablauf": ablauf_id, "schritt": str(freigabe.get("schritt") or ""),
                      "id": str(freigabe.get("id") or "")}
    entities[_PENDING] = pending
    box = InlineDocument(
        kind="schreib_vorschau",
        title=bot_text(lang, "inline.title.writePreview"),
        content=preview_for_display(text) + "\n\n" + bot_text(
            lang, "inline.writePreview.frist", minuten=TOKEN_TTL_SECONDS // 60) + " "
        + bot_text(lang, "inline.writePreview.ask"),
    )
    return als_inhaltsrahmen(box)


# ── Knöpfe ────────────────────────────────────────────────────────────────────────────────────

def _knopf(lang: str, schluessel: str, aktion: str, ablauf_id: str) -> str:
    label = bot_text(lang, schluessel).replace("|", "/")
    return f"__action__|{label}|{aktion}|" + json.dumps({"ablauf": ablauf_id}, ensure_ascii=False)


def knoepfe(ablauf_id: str, lang: str, *, vorgelegt: bool) -> list[str]:
    """Mit Vorschau: der Bestätigungs-Chip und „Ablauf abbrechen“; ohne: „Vorschau erneut
    zeigen“ und „Ablauf abbrechen“."""
    erst = (bot_text(lang, "action.write.confirmChip") if vorgelegt
            else _knopf(lang, "action.ablauf.freigabeErneutKnopf", AKTION_ERNEUT, ablauf_id))
    return [erst, _knopf(lang, "action.ablauf.freigabeAbbrechenKnopf", AKTION_ABBRECHEN,
                         ablauf_id)]


def _wartend(session_id: str, session_state: dict[str, Any]) -> Any:
    vw = arbeitsstand.verweis(session_state.get("entities") or {},
                              arbeitsstand.aufrufer_fuer(session_id))
    lauf = (vw or {}).get("lauf")
    if not isinstance(lauf, dict) or lauf.get("status") != treiber.WARTET_FREIGABE:
        return None
    ablauf = laden(lauf.get("ablauf"))
    if not treiber.gilt(ablauf, lauf):
        return None
    return ablauf


def weiter_knopf(session_id: str, session_state: dict[str, Any], lang: str) -> str | None:
    """„Vorschau erneut zeigen“ unter einer gewöhnlichen Antwort, solange ein Lauf auf eine
    Freigabe wartet, deren Abnahme nicht mehr bereitliegt (Nein, Frist) — sonst ``None``."""
    ablauf = _wartend(session_id, session_state)
    if ablauf is None:
        return None
    entities = session_state.get("entities") or {}
    offen = entities.get(_PENDING)
    if (isinstance(offen, dict) and (offen.get(MARKE) or {}).get("ablauf") == ablauf.id
            and not is_expired(offen, now=time.time())):
        return None
    if _plan_offen(entities, marke={"ablauf": ablauf.id}):
        return plan_fortsetzen.knopf(lang)                  # S4: der Plan des Laufs läuft
    return _knopf(lang, "action.ablauf.freigabeErneutKnopf", AKTION_ERNEUT, ablauf.id)


async def _lauf_wartet_noch(session: Any, req: ChatRequest, entities: dict[str, Any],
                           marke: dict[str, Any]) -> bool:
    """Wartet der Lauf der Marke noch auf genau diese Vorlage (``freigabe_id``)?"""
    aufrufer = arbeitsstand.aufrufer_fuer(req.session_id)
    vw = arbeitsstand.verweis(entities, aufrufer)
    v = await vorgaenge.lesen(session, vw["id"], aufrufer) if vw else None
    lauf = (v.akte or {}).get("lauf") if v is not None else None
    await basis.frei(session)           # M7: gleich danach ruft das Einlösen den MCP
    return (isinstance(lauf, dict) and lauf.get("status") == treiber.WARTET_FREIGABE
            and lauf.get("ablauf") == marke.get("ablauf")
            and lauf.get("schritt") == marke.get("schritt")
            and bool(marke.get("id")) and lauf.get("freigabe_id") == marke.get("id"))


async def vor_einloesen(session: Any, req: ChatRequest, session_state: dict
                        ) -> ChatResponse | None:
    """Vor dem Einlösen einer Abnahme, die zu einem Lauf gehört:

    - abgelaufen (Review S2/S3, Befund 3) → weg damit, sonst hielte sie den Knopf zurück; war die
      Nachricht ein Ja (das Urteil dieses Zugs, Gesamt-Review Befund 3), sagt der Zug es und
      bietet die Vorschau neu an;
    - ihr Lauf wartet nicht mehr auf genau diese Vorlage — abgebrochen, neu vorgelegt, fertig,
      etwa in einem anderen Gespräch (Gesamt-Review, Befund 4) → bei einem Ja nicht einlösen: ein
      Abbruch sagt „nichts geändert“, und das soll stimmen.

    ``None``: nichts davon, der Vorlauf löst wie gewohnt ein."""
    from boerdi.services import zustimmung_pruefen

    entities = session_state.setdefault("entities", {})
    offen = entities.get(_PENDING)
    marke = offen.get(MARKE) if isinstance(offen, dict) else None
    if not isinstance(marke, dict):
        return None
    ja = (zustimmung_pruefen.zugestimmt(session_state, req.message or "")
          or bool(session_state.get(zustimmung_pruefen.UNKLAR_MERKER)))
    if is_expired(offen, now=time.time()):
        schluessel = "action.ablauf.freigabeAbgelaufen"
    elif ja and not await _lauf_wartet_noch(session, req, entities, marke):
        schluessel = "action.ablauf.freigabeNichtMehrOffen"
    else:
        return None
    entities.pop(_PENDING, None)
    await update_session(session, req.session_id, entities=entities)
    if not ja:
        return None
    lang = resolve_locale(req.environment.locale)
    text = bot_text(lang, schluessel)
    # Review AS-Ua, Kleinigkeit 12: ein fester Hinweis wie alle des Ablaufs (``nur_text``)
    await save_message(session, req.session_id, "assistant", text, debug={FESTER_TEXT_KEY: True})
    knopf = (knoepfe(str(marke.get("ablauf") or ""), lang, vorgelegt=False)
             if schluessel == "action.ablauf.freigabeAbgelaufen" else [])
    return ChatResponse(session_id=req.session_id, content=text, quick_replies=knopf,
                        ui=UiInfo(fester_text=True))


# ── Direktaktionen ────────────────────────────────────────────────────────────────────────────

async def _laden(session: Any, req: ChatRequest, entities: dict[str, Any], gewollt: Any, *,
                 stumm: bool = False) -> Any:
    """Vorgang, Lauf und Ablauf, wenn ein Lauf dieser Person am Freigabe-Schritt des gewollten
    Ablaufs wartet — sonst die Antwort des Zugs (``stumm``: ``None`` bzw. ``"abgebrochen"``, ohne
    eine Nachricht zu speichern)."""
    aufrufer = arbeitsstand.aufrufer_fuer(req.session_id)
    vw = arbeitsstand.verweis(entities, aufrufer)
    v = await vorgaenge.lesen(session, vw["id"], aufrufer) if vw else None
    lauf = (v.akte or {}).get("lauf") if v is not None else None
    if (not isinstance(lauf, dict) or lauf.get("ablauf") != gewollt
            or lauf.get("status") != treiber.WARTET_FREIGABE):
        basis.verweis_auffrischen(entities, v, aufrufer)
        if stumm:
            await update_session(session, req.session_id, entities=entities)
            return None
        return await basis.nur_text(session, req, "action.ablauf.unbekannt", entities)
    ablauf = laden(gewollt)
    if not treiber.gilt(ablauf, lauf):
        await basis.abbrechen(session, v, lauf, entities, aufrufer)
        return "abgebrochen" if stumm else await basis.nur_text(
            session, req, "action.ablauf.unbekannt", entities)
    return v, lauf, ablauf, aufrufer


async def _festhalten(session: Any, req: ChatRequest, session_state: dict, v: Any,
                      aus: treiber.Ausgabe, ablauf: Any, aufrufer: str, *,
                      anhaengen: bool = False) -> ChatResponse | None:
    """Lauf und Teile festschreiben und antworten — ``None`` bei einem Konflikt (zurückgerollt)."""
    entities = session_state.setdefault("entities", {})
    try:
        v = await basis.festhalten(session, v, aus, session_id=req.session_id)
        await session.commit()
    except vorgaenge.FESTHALTEN_KONFLIKTE:
        await session.rollback()
        return None
    entities[arbeitsstand.VERWEIS] = arbeitsstand.verweis_fuer(v, aufrufer)
    return await basis.antwort(session, req, session_state, aus, ablauf, anhaengen=anhaengen)


async def erneut(session: Any, req: ChatRequest, session_state: dict, *,
                 blocked_tools: Iterable[str] = ()) -> ChatResponse:
    """„Vorschau erneut zeigen“ (FS-6): den Freigabe-Schritt mit den Teilen von jetzt neu
    vorlegen."""
    entities = session_state.setdefault("entities", {})
    geladen = await _laden(session, req, entities, (req.action_params or {}).get("ablauf"))
    if isinstance(geladen, ChatResponse):
        return geladen
    v, lauf, ablauf, aufrufer = geladen
    if not schreiben_erlaubt():
        return await basis.nur_text(session, req, "action.ablauf.freigabeOhneAnmeldung", entities)
    if _plan_offen(entities, marke={"ablauf": ablauf.id, "id": lauf.get("freigabe_id")}):
        # Review S4, Befund 1: der Plan des Laufs läuft noch — eine neue Vorschau ließe ihn ein
        # zweites Mal von vorn laufen. Erst zu Ende führen.
        lang = resolve_locale(req.environment.locale)
        text = bot_text(lang, "write.planStillOpen")
        await save_message(session, req.session_id, "assistant", text,
                           debug={FESTER_TEXT_KEY: True})
        return ChatResponse(session_id=req.session_id, content=text,
                            quick_replies=[plan_fortsetzen.knopf(lang)],
                            ui=UiInfo(fester_text=True))
    aus = await basis.rechne(session, ablauf, treiber.erneut_vorlegen(
        ablauf, dict(lauf), basis.umgebung(session, req, entities, blocked_tools)))
    if aus is None:
        return await basis.nur_text(session, req, "action.ablauf.fehler", entities)
    antwort = await _festhalten(session, req, session_state, v, aus, ablauf, aufrufer)
    return antwort or await basis.nur_text(session, req, "action.ablauf.konflikt", entities)


async def abbrechen(session: Any, req: ChatRequest, session_state: dict) -> ChatResponse:
    """„Ablauf abbrechen“ am Freigabe-Schritt — geschrieben wurde nichts; die offene Abnahme hat
    schon der Vorlauf verworfen (eine Direktaktion ist kein Ja)."""
    entities = session_state.setdefault("entities", {})
    geladen = await _laden(session, req, entities, (req.action_params or {}).get("ablauf"))
    if isinstance(geladen, ChatResponse):
        return geladen
    v, lauf, ablauf, aufrufer = geladen
    offen = _plan_offen(entities, marke={"ablauf": ablauf.id, "id": lauf.get("freigabe_id")})
    # Review S4, Befund 3: auch ein Plan, der schon weg ist (abgelaufen), hat geschrieben
    angelaufen = offen or bool(lauf.get("plan_angelaufen"))
    if not await basis.abbrechen(session, v, lauf, entities, aufrufer):
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    if offen:
        # S4: was der Plan schon erledigt hat, bleibt; fortgesetzt wird er nicht
        entities.pop(plan_fortsetzen.KEY, None)
    return await basis.nur_text(session, req, "action.ablauf.freigabeAbgebrochenPlan"
                                if angelaufen else "action.ablauf.freigabeAbgebrochen", entities)


# ── Nach dem Einlösen ─────────────────────────────────────────────────────────────────────────

def _zusammen(einloesung: ChatResponse, ablauf: ChatResponse | None = None, *,
              satz: str = "") -> ChatResponse:
    """Die Antwort des Einlösens, dahinter, was der Lauf danach sagt und zeigt."""
    texte = [t for t in (einloesung.content, ablauf.content if ablauf else "", satz) if t]
    update: dict[str, Any] = {"content": "\n\n".join(texte)}
    if ablauf is not None:
        bloecke = [*(einloesung.ui.ui_bloecke if einloesung.ui else []),
                   *(ablauf.ui.ui_bloecke if ablauf.ui else [])]
        update["quick_replies"] = ablauf.quick_replies or einloesung.quick_replies
        update["ui"] = (ablauf.ui.model_copy(update={"ui_bloecke": bloecke}) if ablauf.ui
                        else einloesung.ui)
    return einloesung.model_copy(update=update)


async def _satz(session: Any, req: ChatRequest, antwort: ChatResponse, satz: str) -> ChatResponse:
    """Review R2, Befund 5: ein Satz nach dem Einlösen steht live UND im Verlauf — an der eben
    gespeicherten Antwort (Paket R2-f), sonst als eigene Nachricht."""
    if not await an_letzte_antwort_anhaengen(session, req.session_id, satz,
                                             {FESTER_TEXT_KEY: True}):
        await save_message(session, req.session_id, "assistant", satz,
                           debug={FESTER_TEXT_KEY: True})
    return _zusammen(antwort, satz=satz)


_ohne_schluessel = freigabe_ergebnis.ohne_schluessel


async def _konflikt_nach_schreiben(session: Any, req: ChatRequest, entities: dict[str, Any],
                                   marke: dict[str, Any]) -> None:
    """Review S2/S3, Befund 4: geschrieben, aber der Lauf ließ sich nicht fortschreiben — er endet,
    damit „Vorschau erneut zeigen“ nicht ein zweites Mal schreibt."""
    aufrufer = arbeitsstand.aufrufer_fuer(req.session_id)
    vw = arbeitsstand.verweis(entities, aufrufer)
    try:
        v = await vorgaenge.lesen(session, vw["id"], aufrufer) if vw else None
        lauf = (v.akte or {}).get("lauf") if v is not None else None
        if (isinstance(lauf, dict) and lauf.get("status") == treiber.WARTET_FREIGABE
                and lauf.get("freigabe_id") == marke.get("id")):
            v = await vorgaenge.lauf_setzen(session, v, {**lauf, "status": "fehler"},
                                            status="aktiv", tage=arbeitsstand.tage())
            await session.commit()
            entities[arbeitsstand.VERWEIS] = arbeitsstand.verweis_fuer(v, aufrufer)
    except vorgaenge.VorgangKonflikt:
        await session.rollback()
        logger.warning("Ablauf: nach dem Schreiben zweimal Konflikt — Lauf bleibt stehen")


async def nach_einloesen(session: Any, req: ChatRequest, session_state: dict, vorher: Any,
                         einloesung: ChatResponse, *, blocked_tools: Iterable[str] = ()
                         ) -> ChatResponse:
    """Der Vorlauf hat eine Abnahme eingelöst (oder es versucht) — gehörte sie zu einem Lauf, geht
    er hier weiter. ``vorher`` ist die Abnahme vor dem Einlösen."""
    marke = vorher.get(MARKE) if isinstance(vorher, dict) else None
    ergebnis = session_state.pop(ERGEBNIS, None)
    if not isinstance(marke, dict):
        return einloesung
    entities = session_state.setdefault("entities", {})
    neu = entities.get(_PENDING)
    if (isinstance(neu, dict) and MARKE not in neu
            and neu.get("tool") == vorher.get("tool")):
        neu[MARKE] = marke                      # neu vorgelegt: die Marke reist mit
        await update_session(session, req.session_id, entities=entities)
    grund = (einloesung.debug.entities or {}).get("reason") if einloesung.debug else None
    if grund in _LIEGT_BEREIT:
        return einloesung
    lang = resolve_locale(req.environment.locale)
    plan_offen = ((grund == "eingeloest" and bool((einloesung.debug.entities or {}).get(
        "plan_offen"))) or grund == "plan_unklar") and _plan_offen(
        entities, tool=str(vorher.get("tool") or ""))
    if grund in ("eingeloest", "unchanged") and not plan_offen:
        weiter: dict[str, Any] | None = (
            {"unveraendert": True} if grund == "unchanged"
            else _ohne_schluessel(ergebnis) if isinstance(ergebnis, dict) and ergebnis
            else {"text": (einloesung.content or "")[:4000]})
        if _alle_gescheitert(weiter):
            weiter = None                                    # Review S4, Befund 7
    elif grund == "rejected":
        weiter = None
    elif grund != "mcp_error" and not plan_offen:
        # verbraucht, ohne dass geschrieben wurde (Frist, ``timeout_ohne_wirkung``) — der Lauf
        # wartet; die Person holt die Vorschau neu (FS-6). Knöpfe des Einlösens bleiben vorn
        # (Review S4, Befund 5: „Plan fortsetzen“ bei ``plan_offen``/``too_many_plans``).
        return einloesung.model_copy(update={"quick_replies": _mit(
            einloesung.quick_replies, knoepfe(str(marke.get("ablauf") or ""), lang,
                                             vorgelegt=False))})
    geladen = await _laden(session, req, entities, marke.get("ablauf"), stumm=True)
    if geladen == "abgebrochen":
        return await _satz(session, req, einloesung, bot_text(lang, "action.ablauf.unbekannt"))
    if geladen is None:
        return einloesung
    v, lauf, ablauf, aufrufer = geladen
    if lauf.get("schritt") != marke.get("schritt") or lauf.get("freigabe_id") != marke.get("id"):
        # eine alte Vorschau (der Lauf wurde seitdem neu gestartet) — geschrieben ist, was die
        # Person sah; den neuen Lauf setzt das nicht fort (Befund 6)
        return einloesung
    if plan_offen:
        # Paket S4: ein Plan, der nach dem ersten Abschnitt noch offen ist — er trägt die Marke,
        # der Lauf merkt, dass er angelaufen ist; „Plan fortsetzen“ führt ihn zu Ende, dann geht
        # der Lauf weiter (:func:`nach_plan`)
        entities[plan_fortsetzen.KEY][MARKE] = marke
        await _lauf_merken(session, req, entities, v, {**lauf, "plan_angelaufen": True},
                           aufrufer)
        return einloesung
    if grund == "eingeloest" and _nur_vorbereitet(einloesung):
        # Gesamt-Review, Befund 2 (E3): der Server beschreibt die Änderung nur, die Seite führt
        # sie danach aus — oder gar nicht. Kein Folgeschritt auf einer Änderung, die noch fehlt.
        logger.info("Ablauf %s: Änderung nur vorbereitet — der Lauf endet", ablauf.id)
        # Review R2, Befund 2: der Satz ist der Text des Laufs — im Verlauf steht dasselbe wie live
        satz = bot_text(lang, "action.ablauf.freigabeVorbereitet")
        aus_vorbereitet = treiber.Ausgabe(lauf={**lauf, "status": "fehler", "freigabe_id": None},
                                          texte=[satz])
        vorbereitet = await _festhalten(session, req, session_state, v, aus_vorbereitet, ablauf,
                                        aufrufer, anhaengen=True)
        return (_zusammen(einloesung, vorbereitet) if vorbereitet is not None
                else await _satz(session, req, einloesung, satz))
    if grund == "mcp_error":
        # FS-7: es KANN geschrieben sein — kein Folgeschritt auf dieser Annahme
        logger.warning("Ablauf %s: Ausgang der Freigabe offen — der Lauf endet", ablauf.id)
        aus: treiber.Ausgabe | None = treiber.Ausgabe(lauf={**lauf, "status": "fehler"},
                                                      fehler=str(lauf.get("schritt")))
    else:
        aus = await basis.rechne(session, ablauf, treiber.weiter_freigabe(
            ablauf, dict(lauf), weiter, basis.umgebung(session, req, entities, blocked_tools)))
    if aus is None:
        return einloesung
    # Paket R2-f: live EINE Blase — also auch im Verlauf eine Nachricht
    antwort = await _festhalten(session, req, session_state, v, aus, ablauf, aufrufer,
                                anhaengen=True)
    if antwort is None:
        if grund == "rejected":
            # nichts geschrieben — der Lauf wartet weiter (Gesamt-Review, Befund 1)
            return await _satz(session, req, einloesung, bot_text(lang, "action.ablauf.konflikt"))
        await _konflikt_nach_schreiben(session, req, entities, marke)
        satz = ("action.ablauf.fehler" if grund == "mcp_error"
                else "action.ablauf.freigabeKonflikt")
        return await _satz(session, req, einloesung, bot_text(lang, satz))
    return _zusammen(einloesung, antwort)


def _nur_vorbereitet(einloesung: ChatResponse) -> bool:
    """Hat der Server die Änderung nur beschrieben (E3, ``prepared_write``) — oder mehr als eine,
    von denen keine ausgeliefert wird?"""
    from boerdi.services.mcp.client import get_prepared_writes

    return einloesung.prepared_write is not None or bool(get_prepared_writes())


# ── Paket S4: ein Plan als Freigabe-Schritt ───────────────────────────────────────────────────

def _plan_offen(entities: dict[str, Any], *, tool: str | None = None,
                marke: dict[str, Any] | None = None) -> bool:
    """Liegt ein eigener, nicht abgelaufener Plan zum Fortsetzen bereit — dieses Werkzeugs bzw.
    mit dieser Marke (``ablauf``, und wenn angegeben ``id``)? Review S4, Befund 6: Aufrufer, Frist
    und Kennung zählen, nicht nur der Name."""
    if not plan_fortsetzen.offen_fuer(entities, aufrufer_kennung(), time.time()):
        return False
    plan = entities[plan_fortsetzen.KEY]
    if marke is not None:
        eigene = plan.get(MARKE) or {}
        return (eigene.get("ablauf") == marke.get("ablauf")
                and ("id" not in marke or eigene.get("id") == marke.get("id")))
    return plan.get("tool") == tool


def _mit(vorne: list[str] | None, dazu: list[str]) -> list[str]:
    return list(dict.fromkeys([*(vorne or []), *dazu]))


_alle_gescheitert = freigabe_ergebnis.alle_gescheitert


async def _lauf_merken(session: Any, req: ChatRequest, entities: dict[str, Any], v: Any,
                       lauf: dict[str, Any], aufrufer: str) -> None:
    try:
        v = await vorgaenge.lauf_setzen(session, v, lauf, status=basis.STATUS.get(
            lauf.get("status"), "aktiv"), tage=arbeitsstand.tage())
        await session.commit()
        entities[arbeitsstand.VERWEIS] = arbeitsstand.verweis_fuer(v, aufrufer)
    except vorgaenge.VorgangKonflikt:
        await session.rollback()
        logger.info("Ablauf: angelaufener Plan nicht am Lauf vermerkt (Konflikt)")
    await update_session(session, req.session_id, entities=entities)


async def nach_plan(session: Any, req: ChatRequest, session_state: dict, vorher: Any,
                    antwort: ChatResponse, *, blocked_tools: Iterable[str] = ()) -> ChatResponse:
    """Nach „Plan fortsetzen“: gehörte der Plan zu einem Lauf (Marke) und ist er jetzt fertig, geht
    der Lauf weiter (Ergebnis → Teil ``schreibt``). Lehnt der Server ab (``plan_aus: fehler``),
    geht er zu ``bei_fehler``; ist der Plan weg, ohne fertig zu sein (Frist, ``plan_expired``),
    wartet er mit „Vorschau erneut zeigen“; ist er noch offen, nichts."""
    marke = vorher.get(MARKE) if isinstance(vorher, dict) else None
    fertig = session_state.pop(plan_fortsetzen.FERTIG, None)
    entities = session_state.setdefault("entities", {})
    lang = resolve_locale(req.environment.locale)
    if not isinstance(marke, dict):
        # Review S4, Befund 4: zu Zugbeginn abgelaufen (``abgelaufen_weg``) — der Knopf des
        # wartenden Laufs, sonst stünde „kein offener Plan“ ohne Weg weiter da
        knopf = weiter_knopf(req.session_id, session_state, lang)
        if knopf and not antwort.quick_replies:
            return antwort.model_copy(update={"quick_replies": [knopf]})
        return antwort
    aus_grund = (antwort.debug.entities or {}).get("plan_aus") if antwort.debug else None
    if fertig is None and aus_grund != "fehler":
        if _plan_offen(entities, marke=marke):
            return antwort
        return antwort.model_copy(update={"quick_replies": _mit(antwort.quick_replies, knoepfe(
            str(marke.get("ablauf") or ""), lang, vorgelegt=False))})
    geladen = await _laden(session, req, entities, marke.get("ablauf"), stumm=True)
    if geladen == "abgebrochen":
        return await _satz(session, req, antwort, bot_text(lang, "action.ablauf.unbekannt"))
    if geladen is None:
        return antwort
    v, lauf, ablauf, aufrufer = geladen
    if lauf.get("schritt") != marke.get("schritt") or lauf.get("freigabe_id") != marke.get("id"):
        return antwort
    ergebnis: dict[str, Any] | None = None
    if aus_grund != "fehler":
        ergebnis = _ohne_schluessel(fertig) if isinstance(fertig, dict) and fertig else {
            "complete": True}
        if _alle_gescheitert(ergebnis):
            ergebnis = None
    aus = await basis.rechne(session, ablauf, treiber.weiter_freigabe(
        ablauf, dict(lauf), ergebnis, basis.umgebung(session, req, entities, blocked_tools)))
    if aus is None:
        return antwort
    # Paket R2-f: auch nach „Plan fortsetzen“ EINE Blase im Verlauf
    weiter = await _festhalten(session, req, session_state, v, aus, ablauf, aufrufer,
                               anhaengen=True)
    if weiter is None:
        await _konflikt_nach_schreiben(session, req, entities, marke)
        return await _satz(session, req, antwort,
                           bot_text(lang, "action.ablauf.freigabeKonflikt"))
    return _zusammen(antwort, weiter)


# Öffentlich für ``abbruch_zug`` (zweites Review AS-U, Kleinigkeit 8).
plan_offen = _plan_offen
