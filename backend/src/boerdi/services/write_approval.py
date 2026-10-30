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
import time

from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.schemas import ChatRequest, ChatResponse, DebugInfo, PreparedWriteOut
from boerdi.domain.host_capabilities import erlaubt
from boerdi.domain.prepared_write import (
    VERLAUF_SCHLUESSEL,
    PreparedWrite,
    fuer_den_verlauf,
    single_prepared_write,
)
from boerdi.domain.write_confirm import confirmed_args, redact_confirm_token
from boerdi.i18n import Locale, bot_text, resolve_locale
from boerdi.obs.log_inhalt import inhalt, kennung
from boerdi.services import abnahme_hinweis, zustimmung_pruefen
from boerdi.services.agent_tools import verborgene_werkzeuge
from boerdi.services.db_sessions import save_message, update_session
from boerdi.services.mcp.auth import aufrufer_kennung
from boerdi.services.mcp.client import (
    call_mcp_tool_status,
    get_prepared_writes,
    is_mcp_error,
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


async def discard_stale_approval(
    session: AsyncSession | None,
    req: ChatRequest,
    session_state: dict,
    *,
    hintergrund: bool = False,
) -> bool:
    """Den offenen Vorgang verwerfen, wenn dieser Zug ihn nicht bestätigen kann.

    Bestätigen kann ihn nur die Antwort **direkt** auf die Vorschau (Audit
    2026-09-29). Bis dahin überdauerte er jeden Zwischenzug bis zum Fristende,
    und ein beliebiges späteres „Ja …" führte ihn aus — etwa der Chip „Ja, zeig
    mir mehr Videos" zwei Züge nach einer Vorschau, zu der die Person nie etwas
    gesagt hatte. Verworfen wird deshalb in jedem Zug, der eine Direkt-Aktion
    trägt oder keine Zustimmung ist (``zustimmung_pruefen.stimmt_zu``). Kommt das
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
    fremd = not _gehoert_dem_aufrufer(pending)
    # Paket 10, A-6: Liste, Veto, dann das Modell — einmal je Zug; Vorlauf und
    # Werkzeug-Schleife lesen das Urteil (``zustimmung_pruefen.zugestimmt``).
    zustimmung = not req.action and await zustimmung_pruefen.stimmt_zu(
        req.message, str(pending.get("tool") or "") if isinstance(pending, dict) else "")
    session_state[zustimmung_pruefen.MERKER] = zustimmung
    if not fremd and zustimmung:
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
    ``turn_persist``).
    """
    session_state.setdefault("entities", {})["_pending_write"] = merkposten
    session_state["_write_preview"] = vorschau


def _nicht_einloesbar(tool: str, req: ChatRequest) -> str:
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

    ``None`` ist der Normalfall und kein Fehler: die weit überwiegende Zahl der
    Züge hat keinen offenen Vorgang. Der Aufrufer (``graph/nodes/preflight``)
    lässt den Zug dann unverändert weiterlaufen.

    Eingelöst wird nur, wenn **alle drei** zutreffen: ein Vorgang liegt vor, der
    Mensch hat zugestimmt (``zustimmung_pruefen.zugestimmt`` — ein „ja, aber …" zählt
    nicht), und der Vorgang ist noch frisch und vollständig gemerkt
    (:func:`confirmed_args`). Fehlt eines, läuft der Zug normal weiter und zeigt
    eine neue Vorschau — der teurere, aber immer richtige Ausgang.
    """
    entities = session_state.setdefault("entities", {})
    pending = entities.get("_pending_write")
    if not pending or not zustimmung_pruefen.zugestimmt(session_state, req.message):
        return None
    if not _gehoert_dem_aufrufer(pending):
        # Im Graphen hat ``setup`` ihn schon verworfen; diese Wache gilt für
        # jeden Weg, der den Vorlauf ohne ``setup`` erreicht (Paket 4, A1).
        logger.warning("offener Vorgang eines anderen Aufrufers — nicht eingelöst")
        return None
    tool = str(pending.get("tool") or "")
    grund = _nicht_einloesbar(tool, req)
    if grund:
        # Paket 7 (S4): etwa das Gastkonto zwischen Vorschau und „ja“ im Studio
        # wieder abgeschaltet; seit Paket 9 auch ein dort verborgenes Werkzeug oder
        # eine nur lesende Einbettung (Review Paket 7, MAJOR 11). Einlösbar wird er
        # so nie mehr — verworfen, auch in der Datenbank; der Zug läuft normal weiter.
        logger.warning("offener Vorgang für %s verworfen (%s) — nicht eingelöst", tool, grund)
        entities.pop("_pending_write", None)
        await update_session(session, req.session_id, entities=entities)
        return None

    args = confirmed_args(pending, tool, now=time.time())
    if args is None:
        # Abgelaufen oder ohne gemerkte Argumente. Beides ist kein Fehler,
        # sondern der Fall, für den der Fingerabdruck-Weg im Tool-Loop bleibt.
        return None

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
        rohtext, fehlerart = await call_mcp_tool_status(tool, args)
    except Exception as err:
        # Der SELTENE Weg. ``transport.call_tool`` fängt jede Ausnahme ab, hier
        # kommt also nur an, was daran vorbeigeht. Trotzdem eine Wache: ein Zug
        # darf nicht ohne Antwort enden.
        #
        # Der Grund geht ins Protokoll, nicht in die Antwort: eine
        # Transportmeldung ist ein Interna-Auszug und gehört nicht vor den
        # Nutzer. Dieselbe Aufteilung wie beim Nachbarn ``content_text_action``.
        logger.error(
            "Abnahme für %s (Sitzung %s) warf eine Ausnahme: %s",
            tool, kennung(req.session_id), err)
        return await _unbestaetigt(session, req, session_state, lang, debug)

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
            content=bot_text(lang, "write.executeRejected"),
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
