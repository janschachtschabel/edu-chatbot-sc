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

**Was hier bewusst NICHT geprüft wird:** ob der Aufrufer schreiben darf. Das
entscheidet der MCP-Server anhand des Zugangsblocks (``services/mcp/auth``), und
zwar bei jedem Aufruf — auch bei der Vorschau. Wer keine Vorschau bekam, hat
hier nichts einzulösen. Eine zweite Rechteprüfung an dieser Stelle wäre eine
Kopie mit eigener Driftgefahr.

Tests patchen die drei Aussenkanten (MCP, Sitzung, Nachricht) auf DIESEM Modul.
"""

from __future__ import annotations

import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.schemas import ChatRequest, ChatResponse, DebugInfo, PreparedWriteOut
from boerdi.domain.prepared_write import single_prepared_write
from boerdi.domain.write_confirm import (
    confirmed_args,
    is_affirmation,
    redact_confirm_token,
)
from boerdi.i18n import Locale, bot_text, resolve_locale
from boerdi.services.db_sessions import save_message, update_session
from boerdi.services.mcp.client import (
    call_mcp_tool_status,
    get_prepared_writes,
    is_mcp_error,
)

logger = logging.getLogger(__name__)

# Der Zug gehört fachlich zu M18 (Kuration) — er ist dessen zweite Hälfte.
# Das Muster hat ihn nur nicht ausgewählt, weil ein „ja" für sich genommen
# nichts über den Bestand aussagt.
_PATTERN_ID = "M18"


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
    Mensch hat glatt zugestimmt (:func:`is_affirmation` — ein „ja, aber …" zählt
    nicht), und der Vorgang ist noch frisch und vollständig gemerkt
    (:func:`confirmed_args`). Fehlt eines, läuft der Zug normal weiter und zeigt
    eine neue Vorschau — der teurere, aber immer richtige Ausgang.
    """
    entities = session_state.setdefault("entities", {})
    pending = entities.get("_pending_write")
    if not pending or not is_affirmation(req.message):
        return None

    tool = str(pending.get("tool") or "")
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
    entities.pop("_pending_write", None)

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
            tool, req.session_id, err)
        return await _unbestaetigt(session, req, session_state, lang, debug)

    if is_mcp_error(rohtext) and fehlerart == "tool":
        # Der Server hat GEANTWORTET und abgelehnt — damit steht fest, dass er
        # nichts geschrieben hat. Diese Person auf Verdacht in WLO nachsehen zu
        # schicken wäre unnötig; sie kann direkt nachbessern.
        logger.error(
            "Abnahme für %s (Sitzung %s) vom Server abgelehnt: %s",
            tool, req.session_id, rohtext)
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
            tool, req.session_id, rohtext)
        return await _unbestaetigt(session, req, session_state, lang, debug)

    # Tiefenstaffelung, wie auf dem Rückweg im Tool-Loop: nennt der Server in
    # seiner Erfolgsmeldung einen Schlüssel, geht er hier nicht weiter.
    text = redact_confirm_token(rohtext)
    logger.info(
        "Abnahme für %s (Sitzung %s) eingelöst — es galten die gezeigten Argumente",
        tool, req.session_id)

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
    await _persist(session, req, session_state, text, debug)
    return antwort


async def _unbestaetigt(
    session: AsyncSession | None,
    req: ChatRequest,
    session_state: dict,
    lang: Locale,
    debug: DebugInfo,
) -> ChatResponse:
    """Die ehrliche Antwort, wenn keine Bestätigung zurückkam.

    **Warum genau ein Text für beide Fehlerwege.** Von hier aus sind „der
    Server hat abgelehnt" und „die Antwort kam nie an" nicht zu unterscheiden:
    ``transport.call_tool`` macht aus einer Zeitüberschreitung dieselbe
    Fehler-Antwort wie aus einem Werkzeug-Fehler. Ein Satz, der „es wurde
    nichts geändert" behauptet, wäre im Zeitüberschreitungs-Fall falsch — und
    zwar in der teuren Richtung: die Person legt dieselbe Sache erneut an, und
    der kuratierte Bestand trägt eine Dublette.

    Also sagt der Text nur, was feststeht, und nennt den Schritt, der die
    Unsicherheit auflöst. Wer die beiden Fälle wirklich trennen will, muss
    zuerst den Transport dazu bringen, sie zu unterscheiden — der Text ist die
    Folge dieser Grenze, nicht ihre Ursache.
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
) -> None:
    """Verbrauchten Vorgang und Antwort festschreiben.

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
    try:
        await save_message(
            session, req.session_id, "assistant", text, debug=debug.model_dump(),
        )
    except Exception:
        logger.debug("Persistieren der Ausführungs-Antwort fehlgeschlagen", exc_info=True)
