"""S5 — die abgenommene Änderung einlösen, ohne das Modell zu fragen (2026-08-15).

Der Bestätigungs-Wall (``domain/write_confirm``) legt jede Änderung einem
Menschen vor und merkt sich den offenen Vorgang: Werkzeug, Argumente, Schlüssel.
Was danach fehlte, war der Weg zurück. Der Merkposten wurde **nur** in
``services/tool_loop`` gelesen, und damit hing die Einlösung an zwei
Entscheidungen, die nichts garantiert:

1. **Der Klassifikator musste auf ein „ja" hin M18 wählen.** Nur dieses Muster
   nennt die schreibenden Werkzeuge, und ``_select_active_tools`` bietet dem
   Modell ausschliesslich genannte an. Fiel die Wahl anders aus, war die
   Einlösung in diesem Zug nicht bloss unwahrscheinlich, sondern unmöglich.
2. **Das Modell musste dasselbe Werkzeug erneut rufen** — mit Argumenten, die
   es nicht kennen kann. Die Historie trägt nur die gespeicherten Texte
   (``_assemble_messages`` → ``history[-10:]``); die Vorschau steht als
   Inline-Dokument daneben und die Argumente des ersten Aufrufs standen nie
   darin. Bei einem Upload ist die Nutzlast grundsätzlich nicht wiederholbar.

Beides zusammen ist die Schleife, die der Nutzer meldete: jedes „ja" erzeugte
eine neue Frage statt einer Ausführung.

**Die Abnahme ist ein bestimmter Zustand, kein Sprachverstehensproblem.**
Werkzeug, Argumente und Schlüssel liegen fertig im Merkposten; die Zustimmung
steht in der Nachricht des Menschen. Beides zusammen ergibt genau einen Aufruf.
Ihn hier abzusetzen ist deshalb nicht nur robuster, sondern auch **ehrlicher**:
ausgeführt wird, was in der Abnahme-Box stand, Zeichen für Zeichen — und nicht,
was ein Modell im Folgezug daraus rekonstruiert. Dieselbe Begründung wie bei der
Volltext-Aktion (``content_text_action``): wo der Wortlaut zählt, hat das Modell
nichts zu suchen.

**Die Zug-Regel des Walls gilt hier stärker, nicht schwächer.** Der Tool-Loop
musste sich den offenen Vorgang beim Zug-Eintritt als Schnappschuss merken, um
eine im selben Zug erzeugte Vorschau nicht sofort bestätigen zu können. Dieser
Weg braucht den Schnappschuss nicht: ``session_state`` kommt aus der Datenbank
(``graph/nodes/setup``), enthält also ausschliesslich Vorgänge **früherer**
Züge. Ein in diesem Zug entstandener kann hier gar nicht auftauchen.

**Was hier bewusst NICHT geprüft wird:** welche Rechte der Block beim Server
hat. Das entscheidet der MCP-Server bei jedem Aufruf — auch bei der Vorschau.
Eine zweite Rechteprüfung an dieser Stelle wäre eine Kopie mit eigener
Driftgefahr.

**Was seit Paket 7 (S4) geprüft wird: ob hier überhaupt geschrieben werden
darf** — die Produktregel, nicht die Serverrechte: nur mit persönlicher
Anmeldung, oder mit dem Dienst-Block, wenn das Studio das Gastkonto erlaubt
(``services/schreibrecht``). Bis dahin löste ein „ja“ im Muster-Modus mit dem
Dienst-Block ein (Audit 2026-09-29, B-H3).

**Was dagegen geprüft wird: ob es DERSELBE Aufrufer ist** (Paket 4, A1). Der
Schlüssel des Servers ist an keine Identität gebunden. Eine Vorschau, die unter
einer Anmeldung entstand, löste ein „ja“ ohne diese Anmeldung sonst mit dem
Dienst-Block der Anlage ein — der Server prüfte dann die Rechte des
Dienstkontos, nicht die der Person, der die Vorschau galt. Der Merkposten trägt
deshalb das Kennzeichen seines Aufrufers (:func:`_gehoert_dem_aufrufer`).

Tests patchen die drei Aussenkanten (MCP, Sitzung, Nachricht) auf DIESEM Modul.
"""

from __future__ import annotations

import logging
import re
import time

from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.schemas import (
    ChatRequest,
    ChatResponse,
    DebugInfo,
    InlineDocument,
    PreparedWriteOut,
)
from boerdi.api.schemas_ui import UiInfo
from boerdi.domain.host_capabilities import erlaubt
from boerdi.domain.inline_documents import als_inhaltsrahmen
from boerdi.domain.prepared_write import (
    VERLAUF_SCHLUESSEL,
    PreparedWrite,
    fuer_den_verlauf,
    single_prepared_write,
)
from boerdi.domain.write_anzeige import VORSCHAU_KOPIE, merke_vorschau, preview_for_display
from boerdi.domain.write_confirm import (
    CONFIRM_TOKEN_FIELD,
    TOKEN_TTL_SECONDS,
    confirmed_args,
    extract_confirm_token,
    is_expired,
    redact_confirm_token,
    remember_pending,
)
from boerdi.i18n import Locale, bot_text, resolve_locale
from boerdi.obs.log_inhalt import inhalt, kennung
from boerdi.services import abnahme_hinweis, plan_fortsetzen, zustimmung_pruefen
from boerdi.services.agent_tools import verborgene_werkzeuge
from boerdi.services.db_sessions import save_message, update_session
from boerdi.services.fehlertext import ausgelastet_text
from boerdi.services.mcp.auth import aufrufer_kennung, has_personal_auth, zug_anmeldung_unklar
from boerdi.services.mcp.client import (
    McpAntwort,
    call_mcp_tool_antwort,
    get_prepared_writes,
    is_mcp_error,
    nimm_bestaetigung,
)
from boerdi.services.schreibrecht import schreiben_erlaubt

logger = logging.getLogger(__name__)

# Der Zug gehört fachlich zu M18 (Kuration) — er ist dessen zweite Hälfte.
# Das Muster hat ihn nur nicht ausgewählt, weil ein „ja" für sich genommen
# nichts über den Bestand aussagt.
_PATTERN_ID = "M18"


def _gehoert_dem_aufrufer(pending: object) -> bool:
    """Stammt der offene Vorgang vom Aufrufer DIESES Zugs?

    Ein Merkposten ohne Kennzeichen (vor Paket 4 gemerkt) gilt als fremd: Er
    verfällt, statt unter unbekannter Identität eingelöst zu werden.
    """
    return isinstance(pending, dict) and pending.get("caller") == aufrufer_kennung()


def _anmeldung_unpruefbar(pending: object) -> bool:
    """Plan 2026-11-07 (CB-4): der Server konnte die Anmeldung dieses Zugs nicht prüfen, und es
    gab keine frühere Bestätigung (etwa nach einem Neustart). Dann ist „fremd“ nicht feststellbar
    — ein Vorgang einer Person bleibt liegen, eingelöst wird er erst nach einer Prüfung."""
    return (zug_anmeldung_unklar() and not has_personal_auth() and isinstance(pending, dict)
            and str(pending.get("caller") or "").startswith("p:"))


async def discard_stale_approval(
    session: AsyncSession | None,
    req: ChatRequest,
    session_state: dict,
    *,
    hintergrund: bool = False,
    modul_antwort: bool = False,
) -> bool:
    """Den offenen Vorgang verwerfen, wenn dieser Zug ihn nicht bestätigen kann.

    Bestätigen kann ihn nur die Antwort **direkt** auf die Vorschau (Audit
    2026-09-29). Bis dahin überdauerte er jeden Zwischenzug bis zum Fristende,
    und ein beliebiges späteres „Ja …" führte ihn aus — etwa der Chip „Ja, zeig
    mir mehr Videos" zwei Züge nach einer Vorschau, zu der die Person nie etwas
    gesagt hatte. Verworfen wird deshalb in jedem Zug, der eine Direkt-Aktion
    trägt oder keine Zustimmung ist (``zustimmung_pruefen.urteil``). Kommt das
    Anliegen wieder, zeigt das Modell eine neue Vorschau: der Preis ist eine
    zweite Frage, nicht eine Änderung ohne Zustimmung.

    Eine glatte Zustimmung lässt den Vorgang stehen — ihn löst
    :func:`redeem_write_approval` ein oder, ohne gemerkte Argumente, der
    Fingerabdruck-Weg im Tool-Loop. Gerufen wird im ersten Knoten
    (``graph/nodes/setup``), vor jedem frühen Ausgang — Tour und Kontext-Gruß
    beenden den Zug vor dem Vorlauf. So sieht jeder Weg nur Vorgänge des direkt
    vorigen Zugs der Person (stumme Hintergrund-Züge zählen nicht, siehe unten).

    Gespeichert wird sofort: nicht jeder Weg nach dem Vorlauf schreibt
    ``entities`` zurück (die Direkt-Aktionen nicht), und ein nur im Speicher
    verworfener Vorgang stünde beim nächsten Zug wieder in der Datenbank.
    Gibt zurück, ob verworfen wurde.

    Verworfen wird auch der Vorgang eines ANDEREN Aufrufers (Paket 4, A1) —
    hier, damit ihn keiner der beiden Einlöse-Wege (Vorlauf, Fingerabdruck-Weg
    im Tool-Loop) je zu sehen bekommt.

    **Ein Hintergrund-Zug verwirft nur im Speicher** (``hintergrund``, Befund
    2026-10-08). Kontext-Ping und Tour-Tick schickt das Widget von sich aus und
    zeigt ihre Antwort nur, wenn sie Inhalt hat. Bis hier verwarf schon ein
    stummer Ping den Vorgang in der Datenbank: Die Person sah zwischen Vorschau
    und ihrem „bestätigen“ nichts, und doch kam statt der Ausführung eine neue
    Vorschau. Einlösen kann diesen Zug nichts; im Speicher fällt der Vorgang
    deshalb immer. Sichtbar endet ein Hintergrund-Zug nur mit einer
    gespeicherten Begrüßung, und die schreibt ``entities`` samt Verfall zurück;
    Fehler und ein ungespeicherter Gruß enden stumm (``api/chat``,
    ``graph/nodes/context_greeting``). Bleibt er stumm, schreibt niemand, und
    die Antwort der Person trifft den Vorgang an — längstens bis zur Frist.
    """
    entities = session_state.setdefault("entities", {})
    pending = entities.get("_pending_write")
    if not pending:
        return False
    if hintergrund:
        entities.pop("_pending_write", None)
        logger.info(
            "offener Vorgang für %s ruht — Hintergrund-Zug, nur im Speicher verworfen",
            pending.get("tool") if isinstance(pending, dict) else "?")
        return True
    fremd = not _gehoert_dem_aufrufer(pending) and not _anmeldung_unpruefbar(pending)
    # Paket 10, A-6: Liste, Veto, dann das Modell — einmal je Zug; Vorlauf und
    # Werkzeug-Schleife lesen das Urteil (``zustimmung_pruefen.zugestimmt``).
    # Eine Modul-Antwort (U1-d1) zählt wie eine Direkt-Aktion als NEIN — sonst würde eine gewählte
    # Option „Ja“ zur Zustimmung. Auch eine verworfene (Review U1-d1, Befund 2: zweites Fenster,
    # alte Frage): ``setup`` setzt sie vorher auf ``None`` und meldet sie als ``modul_antwort``.
    nein = bool(req.action) or modul_antwort or req.ui_antwort is not None
    urteil = zustimmung_pruefen.NEIN if nein else await zustimmung_pruefen.urteil(
        req.message, str(pending.get("tool") or "") if isinstance(pending, dict) else "")
    zustimmung = urteil == zustimmung_pruefen.JA
    session_state[zustimmung_pruefen.MERKER] = zustimmung
    if not fremd and zustimmung:
        return False
    if not fremd and urteil == zustimmung_pruefen.UNKLAR:
        # Paket 19, M-2: kein Urteil ist keine Absage. Der Vorgang bleibt — aber nur im
        # Speicher (Review 19-5, 1): endet der Zug vor dem Vorlauf (Tour, Drosselung), löste
        # sonst ein späteres „ok“ zu etwas anderem den alten Vorgang ein (Audit 2026-09-29).
        # In die Datenbank zurück schreibt ihn erst :func:`_zustimmung_unklar`, wenn die
        # Vorschau samt Chip wirklich gezeigt wird. Eingelöst wird so nie — ``MERKER``
        # steht auf ``False``.
        session_state[zustimmung_pruefen.UNKLAR_MERKER] = True
        logger.info("offener Vorgang für %s ruht — Zustimmung unklar",
                    pending.get("tool") if isinstance(pending, dict) else "?")
        await update_session(session, req.session_id, entities={
            k: v for k, v in entities.items() if k != "_pending_write"})
        return False
    if fremd and zustimmung:
        # Paket 10 (Kurzaudit S-1/S-3/S-4): die Person meint diese Vorschau, hat
        # aber nicht die Anmeldung, unter der sie entstand — der Vorlauf sagt es ihr.
        session_state[abnahme_hinweis.MERKER] = True
    entities.pop("_pending_write", None)
    logger.info(
        "offener Vorgang für %s verworfen — %s",
        pending.get("tool") if isinstance(pending, dict) else "?",
        "anderer Aufrufer als bei der Vorschau" if fremd
        else "dieser Zug ist keine Antwort auf die Vorschau")
    await update_session(session, req.session_id, entities=entities)
    return True


def merke_abnahme(session_state: dict, merkposten: dict, vorschau: str) -> None:
    """Eine offene Abnahme der Agent-Schleife ablegen (Paket 2, Runde-2-Plan).

    An dieselben zwei Stellen, die ``services/tool_loop`` setzt: der Merkposten
    in ``entities`` überdauert den Zug und wird hier im nächsten eingelöst, die
    Vorschau auf oberster Ebene gilt nur für diesen Zug (Box und Knopf in
    ``turn_persist``). Eine Kopie der Vorschau reist im Merkposten mit (Paket 19,
    Review 19-5: erneute Anzeige bei unklarer Zustimmung).
    """
    session_state.setdefault("entities", {})["_pending_write"] = merke_vorschau(
        merkposten, vorschau)
    session_state["_write_preview"] = vorschau


def nicht_einloesbar(tool: str, req: ChatRequest) -> str:
    """Warum ein offener Vorgang nicht mehr eingelöst werden darf — ``""``, wenn er darf."""
    if not schreiben_erlaubt():
        return "ohne Schreibrecht"
    if tool in verborgene_werkzeuge():
        return "Werkzeug im Studio verborgen"
    if not erlaubt(tool, req.environment.tool_mode):
        return f"Einbettung erlaubt es nicht ({req.environment.tool_mode})"
    return ""


async def redeem_write_approval(
    session: AsyncSession | None,
    req: ChatRequest,
    session_state: dict,
) -> ChatResponse | None:
    """Die offene Abnahme einlösen — oder ``None``, wenn keine ansteht.

    Paket M2 (MCP-Stand 2026-11-07): verzweigt über ``error.code``. Gilt der Schlüssel nicht
    mehr (``confirm_*``, ``plan_*``), legt sie dieselben Angaben OHNE Schlüssel neu vor — eine
    Vorschau, die nichts schreibt — und zeigt sie mit Bestätigungs-Chip.

    ``None`` ist der Normalfall und kein Fehler: die weit überwiegende Zahl der
    Züge hat keinen offenen Vorgang. Der Aufrufer (``graph/nodes/preflight``)
    lässt den Zug dann unverändert weiterlaufen.

    Eingelöst wird nur, wenn **alle drei** zutreffen: ein Vorgang liegt vor, der
    Mensch hat zugestimmt (``zustimmung_pruefen.zugestimmt`` — ein „ja, aber …" zählt
    nicht), und der Vorgang ist noch frisch und vollständig gemerkt
    (:func:`confirmed_args`). Fehlt eines, läuft der Zug normal weiter und zeigt
    eine neue Vorschau — der teurere, aber immer richtige Ausgang.

    War die Zustimmung **unklar** (Paket 19, M-2: Frist, kein LLM-Platz, vorübergehender
    Anbieterfehler), endet der Zug hier mit der „ausgelastet“-Blase, der erneut gezeigten
    Vorschau und dem Bestätigungs-Chip — ohne Aufruf, der Vorgang bleibt für den
    Folgezug. Erst nach den Prüfungen unten: ein Vorgang, der ohnehin nicht mehr
    eingelöst werden darf (fremd, ohne Schreibrecht, abgelaufen), bekommt keinen Chip.
    """
    entities = session_state.setdefault("entities", {})
    pending = entities.get("_pending_write")
    unklar = bool(session_state.get(zustimmung_pruefen.UNKLAR_MERKER))
    if not pending or not (
            unklar or zustimmung_pruefen.zugestimmt(session_state, req.message)):
        return None
    tool = str(pending.get("tool") or "")
    if _anmeldung_unpruefbar(pending):
        # Plan 2026-11-07 (CB-4): ohne Prüfung kein Schreibrecht — aber auch kein Grund, die
        # Abnahme zu verwerfen. Sie bleibt; das nächste „ja“ löst sie nach einer Prüfung ein.
        # Auch bei unklarer Zustimmung (Review 2026-11-07, Befund 2): sonst liefe der Zug weiter,
        # und der Fingerabdruck-Weg der Werkzeug-Schleife fände den Schlüssel ohne ein Ja.
        lang = resolve_locale(req.environment.locale)
        debug = DebugInfo(pattern=_PATTERN_ID, tools_called=[], entities={"tool": tool})
        return await _liegen_lassen(session, req, session_state, pending, lang, debug,
                                    "write.authUnclear", "anmeldung_unklar")
    if not _gehoert_dem_aufrufer(pending):
        # Im Graphen hat ``setup`` ihn schon verworfen; diese Wache gilt für
        # jeden Weg, der den Vorlauf ohne ``setup`` erreicht (Paket 4, A1).
        logger.warning("offener Vorgang eines anderen Aufrufers — nicht eingelöst")
        return None
    grund = nicht_einloesbar(tool, req)
    if grund:
        # Paket 7 (S4): etwa das Gastkonto zwischen Vorschau und „ja“ im Studio
        # wieder abgeschaltet; seit Paket 9 auch ein dort verborgenes Werkzeug oder
        # eine nur lesende Einbettung (Review Paket 7, MAJOR 11). Einlösbar wird er
        # so nie mehr — verworfen, auch in der Datenbank; der Zug läuft normal weiter.
        logger.warning("offener Vorgang für %s verworfen (%s) — nicht eingelöst", tool, grund)
        entities.pop("_pending_write", None)
        await update_session(session, req.session_id, entities=entities)
        return None
    if unklar:
        if is_expired(pending, now=time.time()):
            # Review 19-5 (3): nach der Frist löste der Chip nichts mehr ein — und der Server
            # kennte den Schlüssel nicht mehr. Verworfen; der Zug läuft normal weiter.
            logger.info("offener Vorgang für %s abgelaufen — kein Bestätigungs-Chip", tool)
            entities.pop("_pending_write", None)
            await update_session(session, req.session_id, entities=entities)
            return None
        return await _zustimmung_unklar(session, req, session_state, tool)

    args = confirmed_args(pending, tool, now=time.time())
    if args is None and plan_fortsetzen.ist_plan(tool) and not is_expired(pending, now=time.time()):
        # Review M6 (Befund 6): ein Plan, dessen Angaben zu groß zum Merken waren. Den
        # Fingerabdruck-Weg gibt es für Pläne nicht — jedes „ja“ ergäbe wortlos eine neue Vorschau.
        entities.pop("_pending_write", None)
        lang = resolve_locale(req.environment.locale)
        debug = DebugInfo(pattern=_PATTERN_ID, tools_called=[], entities={"tool": tool,
                                                                            "reason": "zu_gross"})
        antwort = ChatResponse(session_id=req.session_id,
                               content=bot_text(lang, "write.planTooLarge"), debug=debug)
        await _persist(session, req, session_state, antwort.content, debug)
        return antwort
    if args is None:
        # Abgelaufen oder ohne gemerkte Argumente. Beides ist kein Fehler,
        # sondern der Fall, für den der Fingerabdruck-Weg im Tool-Loop bleibt.
        return None
    if plan_fortsetzen.ist_plan(tool) and plan_fortsetzen.anderer_plan_offen(
            entities, tool, args, caller=aufrufer_kennung(), now=time.time()):
        # Review 2026-11-07: es gibt einen Platz für den offenen Plan. Ein zweiter, der ebenfalls
        # offen bliebe, nähme dem ersten Schlüssel und Knopf — auf dem Server bliebe er bis zur
        # Frist liegen und zählte gegen die fünf Pläne je Anmeldung. Erst den ersten zu Ende führen.
        entities.pop("_pending_write", None)
        lang = resolve_locale(req.environment.locale)
        debug = DebugInfo(pattern=_PATTERN_ID, tools_called=[], entities={"tool": tool,
                                                                            "reason": "plan_offen"})
        antwort = ChatResponse(session_id=req.session_id,
                               content=bot_text(lang, "write.planStillOpen"),
                               quick_replies=[plan_fortsetzen.knopf(lang)], debug=debug)
        await _persist(session, req, session_state, antwort.content, debug)
        return antwort

    # Verbraucht, BEVOR gerufen wird. Der Schlüssel gilt serverseitig genau
    # einmal; ob ein fehlgeschlagener Aufruf den Server erreicht hat, ist von
    # hier aus nicht feststellbar. Ihn liegen zu lassen hiesse, ein zweites „ja"
    # könnte dieselbe Änderung erneut absetzen — die Richtung, in der ein Irrtum
    # teuer wird. Eine verworfene Abnahme kostet eine Wiederholung.
    #
    # Und zwar in der Datenbank, nicht nur hier im Speicher (Audit 2026-09-29,
    # B-M3): Bricht der Zug während des Aufrufs ab, stünde der Merkposten sonst
    # beim nächsten „ja" wieder bereit. Ein Schreibfehler hier bricht ab, bevor
    # etwas geändert wurde.
    entities.pop("_pending_write", None)
    await update_session(session, req.session_id, entities=entities)

    lang = resolve_locale(req.environment.locale)
    debug = DebugInfo(pattern=_PATTERN_ID, tools_called=[tool], entities={"tool": tool})

    try:
        antwort_mcp = await call_mcp_tool_antwort(tool, args)
        if antwort_mcp.art == "busy":
            # Plan 2026-11-07 (CB-2): ausgelastet — kein Werkzeug lief, der Schlüssel ist nicht
            # eingelöst. Die Abnahme kommt zurück; der Chip löst sie gleich noch einmal ein.
            return await _liegen_lassen(session, req, session_state, pending, lang, debug,
                                        "write.busy", "busy",
                                        warte_s=antwort_mcp.warte_s)
        if is_mcp_error(antwort_mcp.text) and _neu_vorlegen(antwort_mcp):
            # Paket M2: der Schlüssel galt nicht mehr (abgelaufen, schon benutzt, andere
            # Änderung, Plan weg) — geschrieben wurde nichts. Dieselben Angaben ohne Schlüssel
            # neu vorlegen: eine frische Vorschau statt „abgelehnt“.
            erneut = await call_mcp_tool_antwort(
                tool, {k: v for k, v in args.items() if k != CONFIRM_TOKEN_FIELD})
            if not erneut.art and not is_mcp_error(erneut.text):
                return await _neu_vorgelegt(session, req, session_state, tool, args, erneut)
            if erneut.art not in ("tool", "auth"):
                # Review M2, Befund 2: der Server HAT geantwortet (Schlüssel ungültig) — dass die
                # neue Vorschau danach ausblieb, macht daraus kein „vielleicht angekommen“.
                debug.entities["reason"] = "confirm_expired"
                antwort = ChatResponse(session_id=req.session_id,
                                       content=bot_text(lang, "write.confirmExpired"),
                                       debug=debug)
                await _persist(session, req, session_state, antwort.content, debug)
                return antwort
            antwort_mcp = erneut
        rohtext, fehlerart = antwort_mcp.text, antwort_mcp.art
    except Exception as err:
        # Der SELTENE Weg. ``transport.call_tool`` fängt jede Ausnahme ab, hier
        # kommt also nur an, was daran vorbeigeht. Trotzdem eine Wache: ein Zug
        # darf nicht ohne Antwort enden.
        #
        # Der Grund geht ins Protokoll, nicht in die Antwort: eine
        # Transportmeldung ist ein Interna-Auszug und gehört nicht vor den
        # Nutzer. Dieselbe Aufteilung wie beim Nachbarn ``content_text_action``.
        logger.exception(
            "Abnahme für %s (Sitzung %s) warf eine Ausnahme (%s)",
            tool, kennung(req.session_id), type(err).__name__)
        return await _unbestaetigt(session, req, session_state, lang, debug)

    if (is_mcp_error(rohtext) and antwort_mcp.code == "timeout"
            and (antwort_mcp.fehler or {}).get("outcomeOpen") is False):
        # Review 2026-11-07: der Server sagt ausdrücklich, dass nichts geschah — keine Ablehnung,
        # an der die Person etwas ändern müsste. Die Abnahme ist verbraucht; neu bitten genügt.
        debug.entities["reason"] = "timeout_ohne_wirkung"
        antwort = ChatResponse(session_id=req.session_id,
                               content=bot_text(lang, "write.timeoutNothingDone"), debug=debug)
        await _persist(session, req, session_state, antwort.content, debug)
        return antwort

    if is_mcp_error(rohtext) and antwort_mcp.code == "too_many_plans":
        # Paket M5: nichts geschrieben. Der Merkposten bleibt verbraucht (Review M5, Befund 2):
        # jeder Folgezug, auch „Plan fortsetzen“, verwürfe ihn ohnehin — der Text sagt deshalb, dass
        # danach eine neue Vorschau kommt. Liegt ein eigener Plan offen, steht sein Knopf da.
        debug.entities["reason"] = "too_many_plans"
        antwort = ChatResponse(
            session_id=req.session_id, content=bot_text(lang, "write.tooManyPlans"),
            quick_replies=([plan_fortsetzen.knopf(lang)] if plan_fortsetzen.offen_fuer(
                entities, aufrufer_kennung(), time.time()) else []),
            debug=debug)
        await _persist(session, req, session_state, antwort.content, debug)
        return antwort

    if (is_mcp_error(rohtext) and plan_fortsetzen.ist_plan(tool)
            and fehlerart in ("timeout", "transport")
            and plan_fortsetzen.merke_unklar(entities, tool, args, caller=aufrufer_kennung(),
                                             now=time.time())):
        # Review M5, Befund 3: der erste Abschnitt ist der längste. Ohne Antwort KANN der Plan
        # laufen — der Bestätigungsschlüssel setzt ihn fort (oder der Server sagt ``plan_expired``).
        logger.warning("Abnahme für Plan %s (Sitzung %s) ohne Antwort — Fortsetzen angeboten",
                       tool, kennung(req.session_id))
        debug.entities["reason"] = "plan_unklar"
        antwort = ChatResponse(session_id=req.session_id,
                               content=bot_text(lang, "write.planUnclearStart"),
                               quick_replies=[plan_fortsetzen.knopf(lang)], debug=debug)
        await _persist(session, req, session_state, antwort.content, debug)
        return antwort

    if is_mcp_error(rohtext) and (antwort_mcp.fehler or {}).get("recordExists") is True:
        # MCP-Stand nach dem Audit (Plan 2026-11-13, C2): der Datensatz IST angelegt, ein Schritt
        # danach blieb ohne Antwort. Weder „abgelehnt, nichts geändert“ noch „ob es ankam, weiß
        # ich nicht“ — beides lüde zu einer Dublette ein.
        # nur der Code des Servers (eine feste Kennung), nie der Text der Antwort
        fehlercode = antwort_mcp.code or "ohne Code"
        logger.warning("Abnahme für %s (Sitzung %s): angelegt, aber unvollständig (%s)",
                       tool, kennung(req.session_id), fehlercode)
        return await _angelegt_unvollstaendig(session, req, session_state, lang, debug,
                                              antwort_mcp.fehler or {})

    if is_mcp_error(rohtext) and fehlerart in ("tool", "auth"):
        # Der Server hat GEANTWORTET und abgelehnt — damit steht fest, dass er
        # nichts geschrieben hat (``auth``: den Zugang schon vor dem Werkzeug).
        # Diese Person auf Verdacht in WLO nachsehen zu schicken wäre unnötig;
        # sie kann direkt nachbessern.
        logger.error(
            "Abnahme für %s (Sitzung %s) vom Server abgelehnt: %s",
            tool, kennung(req.session_id), inhalt(rohtext))
        debug.entities["reason"] = "rejected"
        antwort = ChatResponse(
            session_id=req.session_id,
            content=abgelehnt_text(lang, antwort_mcp),
            debug=debug,
        )
        await _persist(session, req, session_state, antwort.content, debug)
        return antwort

    if is_mcp_error(rohtext):
        # Der HÄUFIGE Weg — und der, den dieser Pfad bis zum Review als Erfolg
        # verbucht hat. ``call_mcp_tool`` meldet jeden Fehlschlag als
        # gewöhnlichen Rückgabewert (``services/mcp/client.is_mcp_error``):
        # abgelehnter Schlüssel, fehlende Rechte, Zeitüberschreitung, Server
        # weg. Ohne diese Abfrage stünde die rohe Servermeldung als Bot-Antwort
        # im Chat und das Protokoll meldete Vollzug.
        #
        # Der Text selbst bleibt im Protokoll: er nennt den Grund, den der
        # Betreiber braucht, und ist zugleich das Interna, das der Nutzer
        # nicht bekommt.
        logger.error(
            "Abnahme für %s (Sitzung %s) nicht bestätigt: %s",
            tool, kennung(req.session_id), inhalt(rohtext))
        return await _unbestaetigt(session, req, session_state, lang, debug)

    # Tiefenstaffelung, wie auf dem Rückweg im Tool-Loop: nennt der Server in
    # seiner Erfolgsmeldung einen Schlüssel, geht er hier nicht weiter.
    text = redact_confirm_token(rohtext)
    # Paket S: gehört die Abnahme zu einem Ablauf, wird der strukturierte Teil der Antwort dessen
    # Ergebnis (``ablauf/freigabe_zug.nach_einloesen`` nimmt ihn im selben Zug wieder heraus).
    session_state["_eingeloest_ergebnis"] = antwort_mcp.strukturiert
    # Review S2/S3, Befund 7: Erfolg ausdrücklich — der Nachlauf eines Ablaufs zählt nur ihn.
    debug.entities["reason"] = "eingeloest"
    knoepfe: list[str] = []
    if plan_fortsetzen.ist_plan(tool):
        # Paket M5: ein Plan, der noch nicht fertig ist, wird gemerkt und per Knopf fortgesetzt —
        # ohne neue Bestätigung, nur von dieser Person (``services/plan_fortsetzen``).
        offen = plan_fortsetzen.merke(entities, tool, args, antwort_mcp,
                                      caller=aufrufer_kennung(), now=time.time())
        text = plan_fortsetzen.anzeige(rohtext, lang, offen=offen)
        knoepfe = [plan_fortsetzen.knopf(lang)] if offen else []
        debug.entities["plan_offen"] = offen          # Paket S4: für den Nachlauf eines Ablaufs
    logger.info(
        "Abnahme für %s (Sitzung %s) eingelöst — es galten die gezeigten Argumente",
        tool, kennung(req.session_id))

    # E3: im eingebetteten Betrieb schreibt der Server nicht selbst, sondern
    # beschreibt die Änderung. Sie muss mit — dieser Zug ist der einzige, in dem
    # sie entstehen kann.
    _writes = get_prepared_writes()
    prepared = single_prepared_write(_writes)
    if prepared is None and _writes:
        # Wortgleich zum Nachbarn ``turn_persist``: mehr als eine Vorbereitung
        # heisst, es ist nicht feststellbar, welcher Änderung zugestimmt wurde.
        # Ausgeliefert wird keine — ohne diese Zeile sähe der Nutzer eine
        # Erfolgsmeldung, und im Repositorium passierte nichts.
        logger.warning(
            "%d vorbereitete Schreibzugriffe in einem Zug — keiner wird "
            "ausgeliefert, weil nicht feststellbar ist, welchem zugestimmt wurde",
            len(_writes))

    antwort = ChatResponse(
        session_id=req.session_id,
        content=text,
        quick_replies=knoepfe,
        debug=debug,
        prepared_write=(
            PreparedWriteOut(
                method=prepared.method,
                path=prepared.path,
                body=prepared.body,
                done_message=prepared.done_message,
            )
            if prepared is not None
            else None
        ),
    )
    await _persist(session, req, session_state, text, debug, vorbereitet=prepared)
    return antwort


#: Paket M2: Codes, bei denen der Schlüssel nicht mehr gilt — nichts geschrieben, neu vorlegen.
def _neu_vorlegen(antwort: McpAntwort) -> bool:
    """Gilt der Schlüssel nicht mehr, ohne dass etwas geschrieben sein kann? Dann dieselben
    Angaben ohne Schlüssel neu vorlegen.

    ``requiresNewPreview`` allein genügt NICHT (Review 2026-11-07, Befund 1): der Server setzt es
    an JEDEN Fehler nach der Einlösung, auch an ``not_visible``/``unverified`` („angenommen, aber
    nicht nachweisbar“). Neu vorgelegt wird nur, wenn der Server geantwortet hat (``tool``) und
    der Code sagt, dass der Schlüssel nicht galt — oder er ausdrücklich ``outcomeOpen: false``
    meldet. Jede andere Ablehnung zeigt ihren Grund, ein offener Ausgang „bitte nachsehen“."""
    if antwort.art != "tool":
        return False
    fehler = antwort.fehler or {}
    # ``exists`` (Dublette) trägt nach der Einlösung ``outcomeOpen: false`` — eine neue Vorschau
    # träfe dieselbe Dublette; die Ablehnung nennt dafür den vorhandenen Datensatz (Paket M2).
    return antwort.code in _NEU_VORLEGEN or (
        bool(fehler.get("requiresNewPreview")) and fehler.get("outcomeOpen") is False
        and antwort.code != "exists")


async def _liegen_lassen(session: AsyncSession | None, req: ChatRequest, session_state: dict,
                         pending: dict, lang: Locale, debug: DebugInfo, schluessel: str,
                         grund: str, *, warte_s: int | None = None) -> ChatResponse:
    """Die Abnahme wurde nicht ausgeführt und bleibt liegen (Plan 2026-11-07, CB-2/CB-4): zurück
    in die Sitzung, ein Satz dazu und der Bestätigungs-Chip — der Folgezug löst ohne Modell ein.
    ``warte_s``: die Wartezeit, die der Server nennt — sie steht im Satz."""
    session_state.setdefault("entities", {})["_pending_write"] = pending
    debug.entities["reason"] = grund
    text = bot_text(lang, schluessel)
    if warte_s is not None:
        text += " " + bot_text(lang, "write.busyWait", s=warte_s)
    antwort = ChatResponse(session_id=req.session_id, content=text,
                           quick_replies=[bot_text(lang, "action.write.confirmChip")],
                           debug=debug)
    await _persist(session, req, session_state, antwort.content, debug)
    logger.info("Abnahme für %s (Sitzung %s) nicht ausgeführt (%s) — sie bleibt liegen",
                pending.get("tool"), kennung(req.session_id), grund)
    return antwort


_NEU_VORLEGEN = frozenset({"confirm_expired", "confirm_unknown", "confirm_mismatch",
                           "plan_expired", "plan_mismatch"})
_ANMELDUNG = frozenset({"login_required", "login_rejected"})
#: Nur fachliche Gründe erreichen die Person (Review M2, Befund 1): ``upstream_error`` und
#: ``forbidden`` tragen Text des Repositoriums — der gehört ins Protokoll.
_GRUND_ZEIGEN = frozenset({"refused", "invalid_input", "not_found", "not_a_collection",
                           "not_checked",
                           # Paket K2d-3 (Review, Befund 6): Volltexte — der Grund sagt, warum
                           "would_replace_file", "link_record", "exists"})
#: MCP-Stand nach dem Audit (Plan 2026-11-13, C2): Gründe mit EIGENEM Satz. Der Text des Servers
#: ist an die KI gerichtet und nennt Werkzeuge und Status-Kennungen („ist wlo_update_content das
#: Werkzeug“, „Status 200_tocheck“) — das gehört nicht vor die Person (Review C2). So gibt es den
#: Grund auch auf Englisch. ``suggestion_not_marked`` fehlt bewusst: es kommt nur nach der
#: Einlösung und wird dort neu vorgelegt oder „bitte nachsehen“.
_EIGENER_GRUND = {"already_decided": "write.grund.alreadyDecided",
                  "already_submitted": "write.grund.alreadySubmitted",
                  "is_a_folder": "write.grund.isAFolder",
                  "is_a_collection": "write.grund.isACollection",
                  "not_a_record": "write.grund.notARecord"}
#: Eine Knoten-Kennung, wie sie in einen Satz an die Person darf — ohne Satz- und
#: Markdown-Zeichen.
_KENNUNG = re.compile(r"[A-Za-z0-9-]{8,64}")
_GRUND_ZEICHEN = 300


def abgelehnt_text(lang: Locale, antwort: McpAntwort) -> str:
    """Die Ablehnung — mit dem Grund des Servers (``error.message``), bei fehlender Anmeldung
    der Hinweis dazu, bei einer Dublette der vorhandene Datensatz (Paket M2)."""
    if antwort.code in _ANMELDUNG:
        return bot_text(lang, "write.loginNeeded")
    text = bot_text(lang, "write.executeRejected")
    fehler = antwort.fehler or {}
    vorhanden = fehler.get("existing") if isinstance(fehler.get("existing"), dict) else None
    if antwort.code == "exists" and vorhanden and str(vorhanden.get("title") or "").strip():
        # Mit Kennung (Review M2, Befund 6): die Rückfrage braucht etwas, woran sie anknüpft.
        return f"{text}\n\n" + bot_text(lang, "write.existsHint",
                                         titel=str(vorhanden["title"]).strip()[:200],
                                         kennung=str(vorhanden.get("nodeId") or "")[:80])
    if antwort.code in _EIGENER_GRUND:
        return f"{text}\n\n" + bot_text(lang, "write.rejectedReason",
                                         grund=bot_text(lang, _EIGENER_GRUND[antwort.code]))
    if antwort.code not in _GRUND_ZEIGEN or lang != "de":
        return text           # der Grund des Servers ist deutsch — in EN nur der Satz
    grund = " ".join(redact_confirm_token(str(fehler.get("message") or "")).split())
    if len(grund) > _GRUND_ZEICHEN:
        grund = grund[:_GRUND_ZEICHEN - 1].rstrip() + "…"
    return f"{text}\n\n" + bot_text(lang, "write.rejectedReason", grund=grund) if grund else text


async def _neu_vorgelegt(
    session: AsyncSession | None,
    req: ChatRequest,
    session_state: dict,
    tool: str,
    args: dict,
    erneut: McpAntwort,
) -> ChatResponse:
    """Die frische Vorschau nach einem verbrauchten Schlüssel (Paket M2): merken wie im
    Werkzeug-Zug und mit Bestätigungs-Chip zeigen. Ohne Schlüssel (``unchanged``: nichts zu
    ändern) nur der Text des Servers."""
    lang = resolve_locale(req.environment.locale)
    entities = session_state.setdefault("entities", {})
    debug = DebugInfo(pattern=_PATTERN_ID, tools_called=[tool],
                      entities={"tool": tool, "reason": "confirm_renewed"})
    ohne = {k: v for k, v in args.items() if k != CONFIRM_TOKEN_FIELD}
    schluessel = nimm_bestaetigung(tool, ohne)
    if schluessel is None:
        schluessel = extract_confirm_token(erneut.text)
    text = redact_confirm_token(erneut.text)
    if not schluessel:
        # Nichts zu ändern (``unchanged``) — ein eigener Satz statt des Servertexts (Befund 5).
        debug.entities["reason"] = "unchanged"
        unveraendert = bool((erneut.strukturiert or {}).get("unchanged"))
        antwort = ChatResponse(
            session_id=req.session_id,
            content=bot_text(lang, "write.nothingToChange") if unveraendert else text,
            debug=debug)
        await _persist(session, req, session_state, antwort.content, debug)
        return antwort
    entities["_pending_write"] = merke_vorschau(remember_pending(
        tool, ohne, schluessel, now=time.time(), caller=aufrufer_kennung()), text)
    box = InlineDocument(
        kind="schreib_vorschau",
        title=bot_text(lang, "inline.title.writePreview"),
        # Die ganze Vorschau wie im Werkzeug-Zug, nicht die gekürzte Kopie (Befund 3).
        content=preview_for_display(text) + "\n\n" + bot_text(
            lang, "inline.writePreview.frist", minuten=TOKEN_TTL_SECONDS // 60) + " "
        + bot_text(lang, "inline.writePreview.ask"),
    )
    antwort = ChatResponse(
        session_id=req.session_id,
        content=bot_text(lang, "write.confirmRenewed"),
        quick_replies=[bot_text(lang, "action.write.confirmChip")],
        ui=UiInfo(ui_bloecke=[als_inhaltsrahmen(box)]),
        debug=debug,
    )
    await _persist(session, req, session_state, antwort.content, debug)
    return antwort


async def _zustimmung_unklar(
    session: AsyncSession | None,
    req: ChatRequest,
    session_state: dict,
    tool: str,
) -> ChatResponse:
    """Die Antwort, wenn das Modell die freie Antwort auf die Vorschau nicht beurteilen
    konnte (Paket 19, M-2): die „ausgelastet“-Blase, die Vorschau erneut und der
    Bestätigungs-Chip.

    Die Vorschau steht wieder darunter (Review 19-5, 2): die unbeurteilte Nachricht kann
    eine Änderung gewesen sein („bitte noch Schlagwort Mathe ergänzen“) — der Chip führt
    sichtbar die GEZEIGTE Fassung aus, und der Text sagt es. Ohne gemerkte Kopie (ein
    Vorgang von vor diesem Stand) gibt es keinen Chip: dann fällt der Vorgang.

    Der Chip ist ein Wort der Erlaubnisliste — der Folgezug löst ohne Modell ein, also
    auch unter Last. „Nochmal versuchen“ steht bewusst NICHT daneben: das Modell läse es
    im Folgezug womöglich als Zustimmung zu einer Nachricht, die es nie beurteilt hat.
    ``_persist`` schreibt den Vorgang wieder in die Datenbank (``setup`` hatte ihn dort
    verworfen) — nur hier, wo der Chip wirklich gezeigt wird.
    """
    lang = resolve_locale(req.environment.locale)
    entities = session_state.setdefault("entities", {})
    vorschau = str((entities.get("_pending_write") or {}).get(VORSCHAU_KOPIE) or "").strip()
    debug = DebugInfo(pattern=_PATTERN_ID, tools_called=["error"],
                      entities={"tool": tool, "reason": "zustimmung_unklar"})
    if not vorschau:
        entities.pop("_pending_write", None)
        logger.info("offener Vorgang für %s ohne gemerkte Vorschau verworfen — kein Chip", tool)
        antwort = ChatResponse(session_id=req.session_id, content=ausgelastet_text(lang),
                               debug=debug)
        await _persist(session, req, session_state, antwort.content, debug)
        return antwort
    box = InlineDocument(
        kind="schreib_vorschau",
        title=bot_text(lang, "inline.title.writePreview"),
        content=f"{vorschau}\n\n" + bot_text(
            lang, "inline.writePreview.frist", minuten=TOKEN_TTL_SECONDS // 60),
    )
    antwort = ChatResponse(
        session_id=req.session_id,
        # Beginnt mit dem „ausgelastet“-Satz (setzt den Blasen-Merker des Zugs; Lasttest und
        # Golden zählen die Blase über ihren Anfang, ``eval/run_profile.fallback_kind``).
        content=f"{ausgelastet_text(lang)}\n\n{bot_text(lang, 'write.consentUnclear')}",
        quick_replies=[bot_text(lang, "action.write.confirmChip")],
        ui=UiInfo(ui_bloecke=[als_inhaltsrahmen(box)]),
        debug=debug,
    )
    await _persist(session, req, session_state, antwort.content, debug)
    return antwort


async def _angelegt_unvollstaendig(
    session: AsyncSession | None, req: ChatRequest, session_state: dict, lang: Locale,
    debug: DebugInfo, fehler: dict,
) -> ChatResponse:
    """Der Datensatz existiert, ein Schritt nach dem Anlegen ist offen (``recordExists``): der
    Satz nennt die Kennung (``error.nodeId``), damit die Person oder der Folgezug nachträgt statt
    neu anzulegen. Für einen Ablauf bleibt es ein offener Ausgang (``reason: mcp_error``)."""
    debug.entities["reason"] = "mcp_error"
    debug.entities["record_exists"] = True
    roh = fehler.get("nodeId")
    node_id = roh if isinstance(roh, str) and _KENNUNG.fullmatch(roh) else None
    text = (bot_text(lang, "write.recordExists", kennung=node_id) if node_id
            else bot_text(lang, "write.recordExistsOhneKennung"))
    antwort = ChatResponse(session_id=req.session_id, content=text, debug=debug)
    await _persist(session, req, session_state, antwort.content, debug)
    return antwort


async def _unbestaetigt(
    session: AsyncSession | None,
    req: ChatRequest,
    session_state: dict,
    lang: Locale,
    debug: DebugInfo,
) -> ChatResponse:
    """Die ehrliche Antwort, wenn keine Bestätigung zurückkam.

    **Wann dieser Text kommt.** Seit ``kind`` unterscheidet der Transport „der
    Server hat abgelehnt" (``tool`` — dann antwortet ``write.executeRejected``
    oben) von „die Antwort kam nie an" (``transport``). Hier landen nur noch
    dieser zweite Fall und Ausnahmen: der Aufruf kann angekommen und ausgeführt
    sein. Ein Satz, der „es wurde nichts geändert" behauptet, wäre dann falsch —
    und zwar in der teuren Richtung: die Person legt dieselbe Sache erneut an,
    und der kuratierte Bestand trägt eine Dublette. (Bestätigte Aufrufe
    wiederholt der Client deshalb auch nicht mehr, ``services/mcp/client``.)

    Also sagt der Text nur, was feststeht, und nennt den Schritt, der die
    Unsicherheit auflöst: in WLO nachsehen.
    """
    debug.entities["reason"] = "mcp_error"
    antwort = ChatResponse(
        session_id=req.session_id,
        content=bot_text(lang, "write.executeUnconfirmed"),
        debug=debug,
    )
    await _persist(session, req, session_state, antwort.content, debug)
    return antwort


async def _persist(
    session: AsyncSession | None,
    req: ChatRequest,
    session_state: dict,
    text: str,
    debug: DebugInfo,
    *,
    vorbereitet: PreparedWrite | None = None,
) -> None:
    """Verbrauchten Vorgang und Antwort festschreiben — mit der ausgelieferten
    Anfrage (``vorbereitet``), damit die Nachfrage aus dem Verlauf sie findet
    (Paket 9, ``domain/prepared_write.VERLAUF_SCHLUESSEL``).

    Beides gehört zusammen und beides ist Pflicht: dieser Weg beendet den Zug
    vor dem ``persist``-Knoten, also schreibt sonst niemand mehr. Bliebe der
    Vorgang in der Datenbank stehen, wäre er beim nächsten „ja" wieder da.

    Der Sitzungs-Schreibfehler wird **nicht** verschluckt, der Nachrichten-
    Schreibfehler schon: ohne den ersten wäre der Vorgang doppelt auslösbar,
    ohne den zweiten fehlt nur eine Zeile im Verlauf.

    ``turn_count`` bleibt bewusst stehen. Die drei Direkt-Aktionen schreiben den
    Sitzungszustand überhaupt nicht fort; hier wird genau das eine geschrieben,
    was geschrieben werden MUSS. Den Zähler mitzuziehen wäre eine Nebenwirkung,
    die dieser Weg nicht braucht — und die Zahl trägt keine Entscheidung, die
    von einem Abnahme-Zug abhinge.
    """
    await update_session(session, req.session_id, entities=session_state["entities"])
    daten = debug.model_dump()
    if vorbereitet is not None:
        daten[VERLAUF_SCHLUESSEL] = fuer_den_verlauf(vorbereitet)
    try:
        await save_message(session, req.session_id, "assistant", text, debug=daten)
    except Exception:
        # WARNING (Paket 10, Audit A-10): ohne diese Zeile fehlt im Verlauf auch die
        # vorbereitete Änderung — die Nachfrage nach einem Strom-Abbruch fände sie nie.
        logger.warning("Persistieren der Ausführungs-Antwort fehlgeschlagen", exc_info=True)
