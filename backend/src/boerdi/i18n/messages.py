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
from boerdi.i18n.messages_dokumente import DOKUMENTE

_GRUND: Final[dict[Locale, dict[str, str]]] = {
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
        # Paket 4, D5: Speichern mit Konfliktschutz
        "config.conflict": (
            "Dieser Bereich wurde inzwischen geändert (Version {version}, von {who}, "
            "{when} UTC). Neu laden oder trotzdem speichern."
        ),
        "config.conflictGone": "Dieser Bereich wurde inzwischen gelöscht.",
        "guide.patternInvalid": (
            "Lotsen-Regel {nr} ({label}): Das Muster ist kein gültiger regulärer "
            "Ausdruck ({error})."
        ),
        "policy.regexInvalid": (
            "Policy-Regel {nr} ({id}): message_regex ist kein gültiger regulärer "
            "Ausdruck ({error})."
        ),
        "config.exists": "Unter der Kennung {area} gibt es schon ein Dokument.",
        # Paket 4b, A4: ein Wert, den Postgres nicht speichert (etwa ein Nullzeichen).
        # Zwei Fassungen (Review 4b): Wiederherstellen und Seed schreiben alles in
        # einer Transaktion, die Sammel-Routen einen Bereich je Transaktion.
        "config.notStorable": (
            "Der Bereich {area} enthält einen Wert, den die Datenbank nicht speichern "
            "kann, etwa ein Nullzeichen oder ein Datum ohne Anführungszeichen. Dieser "
            "Bereich wurde nicht gespeichert."
        ),
        "config.notStorableAll": (
            "Der Bereich {area} enthält einen Wert, den die Datenbank nicht speichern "
            "kann, etwa ein Nullzeichen oder ein Datum ohne Anführungszeichen. Der ganze "
            "Vorgang wurde verworfen, geschrieben wurde nichts."
        ),
        "mcp.serverRejected": "MCP-Server '{id}': {error}",
        "mcp.connectFailed": "Verbindung fehlgeschlagen: {error}",
        "mcp.urlRequired": "Bitte eine Server-URL angeben.",
        # Paket 7 (P1): ein anderer Zug derselben Sitzung läuft noch.
        "chat.sessionBusy": "Sitzung beschäftigt — die vorige Nachricht wird noch beantwortet.",
        # ── Element-Editoren (C1-e2) ───────────────────────────────────
        # `{label}` ist der Gattungsname, den die Route mitgibt („Pattern",
        # „Persona"): ein Bezeichner aus dem Aufrufer, kein Satzteil.
        "entries.invalid": "Ungültige {label}-Daten.",
        "patterns.qrModeInvalid": "quick_replies_mode ungültig: {value}",
        "patterns.idReserved": (
            "Die Muster-Kennung {value} ist reserviert: Sie kennzeichnet die Züge "
            "der Agent-Schleife."
        ),
        # Paket 8 (A): der Lauf läuft schon — auf dieser oder einer anderen Kopie.
        "retention.busy": "Die Bereinigung läuft gerade schon. Gleich noch einmal versuchen.",
        # ── Sicherung: Snapshots + Werksstand (C1-e2) ──────────────────
        "upload.tooLarge": "Datei zu groß (max {mb} MB).",
        "snapshots.notFound": "Snapshot nicht gefunden.",
        "snapshots.limitReached": "Snapshot-Limit erreicht (max {max}) — alte Snapshots löschen.",
        "snapshots.exactEmpty": (
            "Die Sicherung enthält keinen Konfigurationsbereich — „exakt“ würde alles "
            "löschen. Nichts wurde geändert."
        ),
        # Etiketten der Schnappschüsse, die der Server selbst anlegt (Review
        # Paket 7, C-11) — in der Sprache der Person, die den Lauf auslöst.
        "snapshots.invalidFile": (
            "Die Sicherung lässt sich nicht lesen: {file} ist kein gültiges YAML in "
            "UTF-8 oder verwendet YAML-Verweise (Anker/Aliasse). Nichts wurde geändert."
        ),
        "snapshots.label.exactRestore": "vor Wiederherstellen (exakt)",
        "snapshots.label.seedApply": "vor Werksfassung",
        "factory.missing": "Kein eigener Grundstand gesichert",
        "seed.missing": (
            "Dieses Abbild bringt keine Werksfassung mit "
            "(CONFIG_SEED_DIR zeigt auf kein Verzeichnis)."
        ),
        # ── Werk und eigene Fassung (Paket 12) ─────────────────────────
        "fassung.keinWerk": "Für {area} gibt es keine Werksfassung.",
        "fassung.keineEigene": (
            "Für {area} ist keine eigene Fassung stillgelegt — es gibt nichts zurückzuholen."
        ),
        "fassung.versionFehlt": (
            "Die Version fehlt — bitte die Ansicht neu laden und noch einmal umschalten."
        ),
        "fassung.unbekannt": "Den Bereich {area} gibt es weder im Werk noch in der Datenbank.",
        "fassung.zweiEigene": (
            "Für {area} liegt schon eine eigene Fassung still, und die gelebte ist ebenfalls "
            "angepasst — mit der Werksfassung ginge eine verloren. Erst „Eigene Fassung "
            "verwenden“ (tauscht beide) oder eine der beiden von Hand zusammenführen."
        ),
        "fassung.inzwischenDa": (
            "{area} wurde inzwischen angelegt — bitte die Ansicht neu laden."
        ),
        "fassung.nichtsZuPruefen": (
            "{area} ist nicht angepasst oder steht schon auf der aktuellen Werksfassung."
        ),
        "fassung.loeschenMitEigener": (
            "{area} trägt eine stillgelegte eigene Fassung, die beim Löschen verloren ginge — "
            "erst unter Sicherung → „Werk und eigene Fassung“ zurückholen."
        ),
        # ── Lasttest (C1-e2) ───────────────────────────────────────────
        "loadtest.disabled": (
            "Lasttest ist auf dieser Instanz deaktiviert (BOERDI_ALLOW_LOADTEST). "
            "Er würde die echte /api/chat-Pipeline mit Live-Nutzern um LLM-Kapazität "
            "konkurrieren lassen — bitte auf einer Staging-Instanz ausführen."
        ),
        "loadtest.alreadyRunning": (
            "Lasttest {id} läuft bereits — bitte abwarten oder stoppen."
        ),
        "loadtest.runMissing": "Run nicht gefunden.",
        "loadtest.runIsRunning": "Laufender Run kann nicht gelöscht werden.",
        "loadtest.notRunning": (
            "Lasttest {id} läuft nicht (Status: {status}) — nichts zu stoppen."
        ),
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
        # ── Evaluation: Läufe vergleichen (ST-7c) ──────────────────────
        "eval.compareTooFew": "Ein Vergleich braucht mindestens zwei verschiedene Läufe.",
        # ── Agent-Steuerzentrale: Skill-Verzeichnis (ST-8c) ─────────────
        "agentCenter.registryFailed": (
            "Das Repositorium hat das Skill-Verzeichnis nicht geliefert ({error})."
        ),
        "agentCenter.registryUnreadable": "Das Repositorium hat eine unlesbare Antwort geliefert.",
        "agentCenter.searchFailed": (
            "Das Repositorium hat die Skill-Suche nicht beantwortet ({error})."
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
        "config.conflict": (
            "This area was changed in the meantime (version {version}, by {who}, "
            "{when} UTC). Reload or save anyway."
        ),
        "config.conflictGone": "This area was deleted in the meantime.",
        "guide.patternInvalid": (
            "Guide rule {nr} ({label}): the pattern is not a valid regular "
            "expression ({error})."
        ),
        "policy.regexInvalid": (
            "Policy rule {nr} ({id}): message_regex is not a valid regular "
            "expression ({error})."
        ),
        "config.exists": "A document with the id {area} already exists.",
        "config.notStorable": (
            "Area {area} holds a value the database cannot store, such as a NUL "
            "character or an unquoted date. This area was not saved."
        ),
        "config.notStorableAll": (
            "Area {area} holds a value the database cannot store, such as a NUL "
            "character or an unquoted date. The whole operation was discarded; "
            "nothing was written."
        ),
        "mcp.serverRejected": "MCP server '{id}': {error}",
        "mcp.connectFailed": "Connection failed: {error}",
        "mcp.urlRequired": "Please provide a server URL.",
        "chat.sessionBusy": "Session busy — the previous message is still being answered.",
        "entries.invalid": "Invalid {label} data.",
        "patterns.qrModeInvalid": "quick_replies_mode is invalid: {value}",
        "patterns.idReserved": (
            "The pattern id {value} is reserved: it marks the turns of the agent loop."
        ),
        "retention.busy": "Cleanup is already running. Try again in a moment.",
        "upload.tooLarge": "File too large (max {mb} MB).",
        "snapshots.notFound": "Snapshot not found.",
        "snapshots.limitReached": "Snapshot limit reached (max {max}) — delete old snapshots.",
        "snapshots.exactEmpty": (
            "The backup contains no configuration area — “exact” would delete "
            "everything. Nothing was changed."
        ),
        "snapshots.invalidFile": (
            "The backup cannot be read: {file} is not valid UTF-8 YAML or uses YAML "
            "references (anchors/aliases). Nothing was changed."
        ),
        "snapshots.label.exactRestore": "before restore (exact)",
        "snapshots.label.seedApply": "before factory version",
        "factory.missing": "No baseline has been saved",
        "seed.missing": (
            "This image ships no factory config tree "
            "(CONFIG_SEED_DIR points to no directory)."
        ),
        "fassung.keinWerk": "There is no factory version of {area}.",
        "fassung.keineEigene": (
            "No own version of {area} is set aside — there is nothing to bring back."
        ),
        "fassung.versionFehlt": "The version is missing — please reload the view and switch again.",
        "fassung.unbekannt": (
            "The area {area} exists neither in the factory set nor in the database."
        ),
        "fassung.zweiEigene": (
            "An own version of {area} is already set aside and the live one is customized too — "
            "switching to the factory version would lose one. Use “Use own version” first (it "
            "swaps both) or merge them by hand."
        ),
        "fassung.inzwischenDa": "{area} was created meanwhile — please reload the view.",
        "fassung.nichtsZuPruefen": (
            "{area} is not customized or is already based on the current factory version."
        ),
        "fassung.loeschenMitEigener": (
            "{area} has an own version set aside that deleting would lose — bring it back first "
            "under Backup → “Factory and own version”."
        ),
        "loadtest.disabled": (
            "The load test is disabled on this instance (BOERDI_ALLOW_LOADTEST). "
            "It would make the real /api/chat pipeline compete with live users for LLM "
            "capacity — please run it on a staging instance."
        ),
        "loadtest.alreadyRunning": (
            "Load test {id} is already running — please wait or stop it."
        ),
        "loadtest.runMissing": "Run not found.",
        "loadtest.runIsRunning": "A running run cannot be deleted.",
        "loadtest.notRunning": (
            "Load test {id} is not running (status: {status}) — nothing to stop."
        ),
        "quality.logNotFound": "Log not found.",
        "quality.bulkDeleteNeedsConfirm": (
            "A bulk delete with neither a filter nor a scope requires ?confirm=true — "
            "it would delete ALL quality logs."
        ),
        "usage.periodReversed": "'from' is later than 'to' — the period is empty.",
        "usage.periodTooLong": (
            "The period spans more than {max} days. Please narrow it."
        ),
        "sessions.purgeNeedsConfirm": (
            "Purging requires ?confirm=true as a guard against accidental nukes. "
            "The studio sends the parameter automatically after the double confirmation."
        ),
        "sessions.optimizeFailed": (
            "Compacting failed — the database may currently be locked under load. "
            "Please try again in a quiet period. ({error})"
        ),
        "eval.compareTooFew": "A comparison needs at least two different runs.",
        "agentCenter.registryFailed": (
            "The repository did not deliver the skill directory ({error})."
        ),
        "agentCenter.registryUnreadable": "The repository returned an unreadable answer.",
        "agentCenter.searchFailed": (
            "The repository did not answer the skill search ({error})."
        ),
    },
}

# Paket 6: die Meldungen der Ordner-Dokumente und des Wissens-Imports stehen in
# ``messages_dokumente.py`` (die Datei wuchs sonst über 300 Zeilen). Ein Schlüssel
# darf nur in einem Teil stehen — sonst gewönne still der spätere
# (``test_i18n_messages.py`` prüft das).
MESSAGES: Final[dict[Locale, dict[str, str]]] = {
    sprache: {**_GRUND[sprache], **DOKUMENTE[sprache]} for sprache in _GRUND
}


def msg(locale: Locale, key: str, **params: object) -> str:
    """The message for ``key`` in ``locale``, with ``params`` substituted.

    Lookup and substitution moved to ``i18n/catalogue`` when the bot got its own
    catalogue (C1-f2b) — a formatting bug should have one home, not two. The
    behaviour is unchanged: unknown key → the key, missing parameter → its
    placeholder, never a raise on the error path.
    """
    return render(MESSAGES, locale, key, **params)
