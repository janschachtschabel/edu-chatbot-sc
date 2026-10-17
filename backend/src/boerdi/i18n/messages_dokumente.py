"""Meldungen der Ordner-Dokumente und des Wissens-Imports (Paket 6).

Aus ``messages.py`` gelöst, das sonst über 300 Zeilen gewachsen wäre; beide
Sprachen stehen nebeneinander wie in den Katalogteilen des Studios.
``messages.MESSAGES`` führt die Teile zusammen, ``msg`` kennt nur das Ganze.
"""

from typing import Final

from boerdi.i18n.locale import Locale

DOKUMENTE: Final[dict[Locale, dict[str, str]]] = {
    "de": {
        # ── Ordner-Dokumente: anlegen, duplizieren, löschen (Paket 6, S1) ──
        "documents.groupInvalid": (
            "Unbekannter Ordner {group} — anlegen geht in 03-patterns und 04-personas."
        ),
        "documents.idInvalid": (
            "Die Kennung {id} ist ungültig: Buchstaben, Ziffern, - und _, ohne "
            "Leerzeichen, höchstens 64 Zeichen."
        ),
        "documents.labelMissing": "Der Name fehlt oder ist länger als {max} Zeichen.",
        "documents.idTaken": (
            "Die Kennung {id} gibt es in diesem Ordner schon ({other} in {area})."
        ),
        "documents.personaKey": (
            "Die Persona {id} wird unter {expected} gesucht, liegt aber unter {area}. "
            "Bitte die Kennung lassen oder die Persona neu anlegen."
        ),
        "documents.sourceMissing": "Die Vorlage {source} gibt es in diesem Ordner nicht.",
        "documents.deleteOnly": (
            "{path} gehört zur festen Konfiguration und lässt sich nicht löschen — "
            "zurücksetzen geht über den Auslieferungsstand. Löschen lassen sich "
            "Muster, Personas und Bereiche ohne Modell."
        ),
        "documents.notFound": "{path} gibt es nicht.",
        "documents.deleteSafety": (
            "{id} antwortet bei Krise oder Bedrohung (Sicherheit) und lässt sich "
            "nicht löschen."
        ),
        "documents.idSafety": (
            "Die Kennung {id} bleibt: Das Muster antwortet bei Krise oder Bedrohung "
            "(Sicherheit)."
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
        # Paket 4, C5; seit Paket 7 (P6) liest das Image auch PDF und Office.
        "ingest.convertFailed": "Die Datei ließ sich nicht umwandeln ({detail}).",
        "ingest.serverMissing": (
            "Auf dem Server fehlt ein Baustein für die Umwandlung (markitdown). "
            "Bitte das Image prüfen."
        ),
        # Paket 9: der Grund kommt aus ``url_safety.UnsafeUrlError.grund`` — bis
        # dahin stand der englische Text des Wächters im Satz. Auch der MCP-Weg
        # nutzt die beiden (``api/config_guards.url_einwand``).
        "url.notAllowed": "Diese Adresse ist nicht erlaubt — nur öffentliche http(s)-Adressen.",
        "url.unknownHost": (
            "Der Name {detail} lässt sich nicht auflösen — ist die Adresse richtig geschrieben?"
        ),
        "ingest.fetchFailed": "Die Seite ließ sich nicht laden ({detail}).",
        "ingest.fetchTooLarge": "Die Seite ist größer als {wert} MB.",
        "ingest.fetchTooSlow": "Die Seite lieferte nicht binnen {wert} s.",
        "ingest.unpackedTooLarge": (
            "Die Datei ist entpackt größer als {wert} MB oder enthält zu viele Teile."),
        "ingest.tooManyPages": "Das PDF hat mehr als {wert} Seiten.",
        "ingest.convertTooSlow": "Die Umwandlung dauerte länger als {wert} s.",
        "ingest.convertTooBig": "Die Umwandlung brauchte zu viel Speicher.",
        "ingest.textTooLong": "Der umgewandelte Text ist länger als {wert} Millionen Zeichen.",
        "ingest.formatUnsupported": (
            "Dieses Dateiformat kann der Server nicht lesen. Möglich sind PDF, "
            "Word (DOCX), PowerPoint (PPTX), Excel (XLSX), HTML, Markdown, Text, "
            "CSV und JSON."
        ),
    },
    "en": {
        "documents.groupInvalid": (
            "Unknown folder {group} — documents can be created in 03-patterns and 04-personas."
        ),
        "documents.idInvalid": (
            "The id {id} is invalid: letters, digits, - and _, no spaces, at most "
            "64 characters."
        ),
        "documents.labelMissing": "The name is missing or longer than {max} characters.",
        "documents.idTaken": "The id {id} already exists in this folder ({other} in {area}).",
        "documents.personaKey": (
            "The persona {id} is looked up under {expected} but stored under {area}. "
            "Keep the id or create the persona anew."
        ),
        "documents.sourceMissing": "The template {source} does not exist in this folder.",
        "documents.deleteOnly": (
            "{path} belongs to the fixed configuration and cannot be deleted — reset "
            "it via the shipped state. Patterns, personas and areas without a model "
            "can be deleted."
        ),
        "documents.notFound": "{path} does not exist.",
        "documents.deleteSafety": (
            "{id} answers in a crisis or under threat (safety) and cannot be deleted."
        ),
        "documents.idSafety": (
            "The id {id} stays: this pattern answers in a crisis or under threat (safety)."
        ),
        "ingest.tooLarge": "File too large: {size} MB > {max} MB limit.",
        "ingest.raiseLimit": (
            "If the server has enough RAM, raise BOERDI_MAX_INGEST_MB "
            "(or set it to 0 for no limit)."
        ),
        "ingest.convertFailed": "The file could not be converted ({detail}).",
        "ingest.serverMissing": (
            "The server is missing a component for the conversion (markitdown). "
            "Please check the image."
        ),
        "url.notAllowed": "This address is not allowed — public http(s) addresses only.",
        "url.unknownHost": (
            "The name {detail} cannot be resolved — is the address spelled correctly?"
        ),
        "ingest.fetchFailed": "The page could not be loaded ({detail}).",
        "ingest.fetchTooLarge": "The page is larger than {wert} MB.",
        "ingest.fetchTooSlow": "The page did not arrive within {wert} s.",
        "ingest.unpackedTooLarge": (
            "Unpacked, the file is larger than {wert} MB or has too many parts."),
        "ingest.tooManyPages": "The PDF has more than {wert} pages.",
        "ingest.convertTooSlow": "The conversion took longer than {wert} s.",
        "ingest.convertTooBig": "The conversion needed too much memory.",
        "ingest.textTooLong": "The converted text is longer than {wert} million characters.",
        "ingest.formatUnsupported": (
            "The server cannot read this file format. Possible are PDF, "
            "Word (DOCX), PowerPoint (PPTX), Excel (XLSX), HTML, Markdown, text, "
            "CSV and JSON."
        ),
    },
}
