"""The messages the API sends to a person (C1-e).

Only what an editor reads in the studio: the ``detail`` of an HTTP error, and
the one warning that a partial save produces. Deliberately NOT in here:

* ``Field(description=…)`` — those describe the API in ``/docs``, and the API
  is documented in one language like any other technical reference;
* operator messages at startup (``studio_static``) — read by whoever deploys,
  in the log, not in an interface;
* the demo pages under ``/widget/`` — German on purpose, they are the German
  integration example.

A second catalogue beside the studio's is a real cost, and it was weighed: the
alternative was a machine-readable error code that the studio translates, which
would have changed the error contract of eight routers and the frozen OpenAPI
document. The header costs nothing on the wire and keeps the values where the
sentence is formatted.

**One key, several call sites** where the sentence is the same and only the
field differs — ``field.empty`` covers four. Same rule as the studio catalogue:
two entries for one sentence are two places to translate it.
"""

from typing import Final

from boerdi.i18n.catalogue import render
from boerdi.i18n.locale import Locale

MESSAGES: Final[dict[Locale, dict[str, str]]] = {
    "de": {
        # ── Bereichs-Editor: Begrüßung ─────────────────────────────────
        "field.empty": "{field} darf nicht leer sein",
        "welcome.noReplies": "mindestens eine Quick-Reply nötig",
        "welcome.tourReplyUnknown": "tour_reply muss exakt einer der quick_replies sein",
        # ── Bereichs-Editor: Kontext-Aktionen ──────────────────────────
        "pills.labelEmpty": "{field}: label darf nicht leer sein",
        "pills.badKind": "{field}: kind muss action|text|report sein",
        "pills.actionMissing": "{field}: action-Pill braucht eine action",
        "pills.none": "{field} braucht mindestens eine Pill",
        # ── Bereichs-Editor: Tonfall ───────────────────────────────────
        "tone.partial": "Tone-Modifier teilweise gespeichert — fehlgeschlagen für: {failed}",
        # ── Rohtext-Editor + MCP-Registry (C1-e2) ──────────────────────
        "file.unreadable": "Inhalt nicht lesbar: {error}",
        "mcp.serverRejected": "MCP-Server '{id}': {error}",
        "mcp.connectFailed": "Verbindung fehlgeschlagen: {error}",
        "mcp.urlRequired": "Bitte eine Server-URL angeben.",
        # ── Element-Editoren (C1-e2) ───────────────────────────────────
        # `{label}` ist der Gattungsname, den die Route mitgibt („Pattern",
        # „Persona"): ein Bezeichner aus dem Aufrufer, kein Satzteil.
        "entries.invalid": "Ungültige {label}-Daten.",
        "patterns.qrModeInvalid": "quick_replies_mode ungültig: {value}",
        # ── Sicherung: Snapshots + Werksstand (C1-e2) ──────────────────
        "upload.tooLarge": "Datei zu groß (max {mb} MB).",
        "snapshots.notFound": "Snapshot nicht gefunden.",
        "snapshots.limitReached": "Snapshot-Limit erreicht (max {max}) — alte Snapshots löschen.",
        "factory.missing": "Kein Factory-Stand gesetzt",
        # ── Lasttest (C1-e2) ───────────────────────────────────────────
        "loadtest.disabled": (
            "Lasttest ist auf dieser Instanz deaktiviert (BOERDI_ALLOW_LOADTEST). "
            "Er würde die echte /api/chat-Pipeline mit Live-Nutzern um LLM-Kapazität "
            "konkurrieren lassen — bitte auf einer Staging-Instanz ausführen."
        ),
        "loadtest.alreadyRunning": "Lasttest {id} läuft bereits — bitte abwarten.",
        "loadtest.runMissing": "Run nicht gefunden.",
        "loadtest.runIsRunning": "Laufender Run kann nicht gelöscht werden.",
        # ── Qualitäts-Logs (C1-e2) ─────────────────────────────────────
        # „wuerde"/„loeschen" ohne Umlaut ist ALT-Wortlaut (`app/routers/
        # quality.py:78`) und bleibt es — der Port ist byte-nah, nicht schöner.
        "quality.logNotFound": "Log nicht gefunden.",
        "quality.bulkDeleteNeedsConfirm": (
            "Bulk-delete ohne Filter und ohne Scope verlangt ?confirm=true — "
            "das wuerde ALLE Quality-Logs loeschen."
        ),
        # ── Kostenschau (K4) ───────────────────────────────────────────
        "usage.periodReversed": "'from' liegt nach 'to' — der Zeitraum ist leer.",
        "usage.periodTooLong": (
            "Der Zeitraum umfasst mehr als {max} Tage. Bitte enger fassen."
        ),
        # ── RAG-Ingest (C1-e2) ─────────────────────────────────────────
        # Zwei Sätze statt eines langen: dieselbe Grenze meldet der schnelle
        # Vorab-Check (mit Hinweis) und die Prüfung nach dem Lesen (ohne).
        # Getrennt, damit der Katalog denselben Satz nicht zweimal trägt;
        # zusammengesetzt wird an der Satzgrenze, nie im Satz.
        "ingest.tooLarge": "Datei zu groß: {size} MB > {max} MB Limit.",
        "ingest.raiseLimit": (
            "Wenn der Server genug RAM hat, setze BOERDI_MAX_INGEST_MB höher "
            "(oder 0 für unbegrenzt)."
        ),
        # ── Sitzungen: Purge + Kompaktieren (C1-e2) ────────────────────
        # „Bestaetigung" ohne Umlaut: ALT-Wortlaut (`app/routers/sessions.py:112`).
        "sessions.purgeNeedsConfirm": (
            "Purge verlangt ?confirm=true als Schutz gegen versehentliche Nukes. "
            "Das Studio schickt den Parameter nach der Doppel-Bestaetigung automatisch."
        ),
        "sessions.optimizeFailed": (
            "Kompaktieren fehlgeschlagen — die Datenbank ist evtl. gerade unter Last "
            "gesperrt. Bitte in einer ruhigen Phase erneut versuchen. ({error})"
        ),
    },
    "en": {
        "field.empty": "{field} must not be empty",
        "welcome.noReplies": "at least one quick reply is required",
        "welcome.tourReplyUnknown": "tour_reply must be exactly one of the quick_replies",
        "pills.labelEmpty": "{field}: label must not be empty",
        "pills.badKind": "{field}: kind must be action|text|report",
        "pills.actionMissing": "{field}: an action pill needs an action",
        "pills.none": "{field} needs at least one pill",
        "tone.partial": "Tone modifiers partly saved — failed for: {failed}",
        "file.unreadable": "Content is not readable: {error}",
        "mcp.serverRejected": "MCP server '{id}': {error}",
        "mcp.connectFailed": "Connection failed: {error}",
        "mcp.urlRequired": "Please provide a server URL.",
        "entries.invalid": "Invalid {label} data.",
        "patterns.qrModeInvalid": "quick_replies_mode is invalid: {value}",
        "upload.tooLarge": "File too large (max {mb} MB).",
        "snapshots.notFound": "Snapshot not found.",
        "snapshots.limitReached": "Snapshot limit reached (max {max}) — delete old snapshots.",
        "factory.missing": "No factory state has been saved",
        "loadtest.disabled": (
            "The load test is disabled on this instance (BOERDI_ALLOW_LOADTEST). "
            "It would make the real /api/chat pipeline compete with live users for LLM "
            "capacity — please run it on a staging instance."
        ),
        "loadtest.alreadyRunning": "Load test {id} is already running — please wait.",
        "loadtest.runMissing": "Run not found.",
        "loadtest.runIsRunning": "A running run cannot be deleted.",
        "quality.logNotFound": "Log not found.",
        "quality.bulkDeleteNeedsConfirm": (
            "A bulk delete with neither a filter nor a scope requires ?confirm=true — "
            "it would delete ALL quality logs."
        ),
        "usage.periodReversed": "'from' is later than 'to' — the period is empty.",
        "usage.periodTooLong": (
            "The period spans more than {max} days. Please narrow it."
        ),
        "ingest.tooLarge": "File too large: {size} MB > {max} MB limit.",
        "ingest.raiseLimit": (
            "If the server has enough RAM, raise BOERDI_MAX_INGEST_MB "
            "(or set it to 0 for no limit)."
        ),
        "sessions.purgeNeedsConfirm": (
            "Purging requires ?confirm=true as a guard against accidental nukes. "
            "The studio sends the parameter automatically after the double confirmation."
        ),
        "sessions.optimizeFailed": (
            "Compacting failed — the database may currently be locked under load. "
            "Please try again in a quiet period. ({error})"
        ),
    },
}


def msg(locale: Locale, key: str, **params: object) -> str:
    """The message for ``key`` in ``locale``, with ``params`` substituted.

    Lookup and substitution moved to ``i18n/catalogue`` when the bot got its own
    catalogue (C1-f2b) — a formatting bug should have one home, not two. The
    behaviour is unchanged: unknown key → the key, missing parameter → its
    placeholder, never a raise on the error path.
    """
    return render(MESSAGES, locale, key, **params)
