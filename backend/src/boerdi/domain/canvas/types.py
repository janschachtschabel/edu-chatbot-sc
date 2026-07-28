"""Canvas material-type registry — ported 1:1 from ALT
``app/services/canvas_types.py``: the ``_DEFAULT_*`` in-code fallback data
(material types, aliases, triggers, personas, LRT mapping) + the 8
config-driven getters (``get_material_types`` ... ``get_analytical_personas``).
Each getter reads the ``config_loader.load_canvas_*`` studio-editable
read-facade and falls back to its ``_DEFAULT_*`` block on empty/failed load.
Pure config-driven logic (only the config_loader read-facade + stdlib) ->
``domain/``. Tests patch ``types.config_loader``.
"""
from __future__ import annotations

import copy
import logging

from boerdi.services import config_loader

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Material-Typ-Definitionen
# ---------------------------------------------------------------------------
#
# Die kanonische Quelle aller Canvas-Definitionen ist
# `chatbots/wlo/v1/05-canvas/*.yaml`. Der hier folgende `_DEFAULT_*`-Block
# ist nur ein Fallback, falls eine YAML-Datei fehlt oder defekt ist.
# Runtime-Code nutzt die `get_*()`-Wrapper, die pro Aufruf die YAML-Datei
# lesen (mtime-gecacht) — so wirken Studio-Edits live.


_DEFAULT_MATERIAL_TYPES: dict[str, dict[str, str]] = {
    "auto": {
        "label": "Automatisch",
        "emoji": "🤖",
        "structure": (
            "Wähle einen für das Thema und die Lernenden passenden Material-Typ "
            "(Arbeitsblatt, Infoblatt, Quiz, Präsentation, Checkliste, Glossar, "
            "Strukturübersicht, Übungsaufgaben, Lerngeschichte, Versuchsanleitung, "
            "Diskussionskarten oder Rollenspielkarten). Beginne den Inhalt mit einer "
            "H1-Überschrift in der Form '# [Typ]: [Thema]'. Gestalte das Material "
            "didaktisch sinnvoll."
        ),
    },
    "arbeitsblatt": {
        "label": "Arbeitsblatt",
        "emoji": "📝",
        "structure": (
            "Erstelle ein Arbeitsblatt mit:\n"
            "1. H1-Überschrift '# Arbeitsblatt: [Thema]'\n"
            "2. Kurzer Einleitung (2-3 Sätze, was die Lernenden lernen)\n"
            "3. 4-7 nummerierte Aufgaben, gemischt zwischen Reproduktion und Anwendung\n"
            "4. Abschnitt '## Lösungen' am Ende mit Musterlösungen zu jeder Aufgabe\n"
            "5. Optionalem Hinweis für Lehrkräfte (Differenzierung)"
        ),
    },
    "infoblatt": {
        "label": "Infoblatt",
        "emoji": "📄",
        "structure": (
            "Erstelle ein Infoblatt mit:\n"
            "1. H1-Überschrift '# Infoblatt: [Thema]'\n"
            "2. Kurzem Einstieg (worum geht es?)\n"
            "3. 3-5 thematischen Abschnitten als H2-Überschriften\n"
            "4. Bullet-Listen und Fließtext, keine Aufgaben\n"
            "5. Abschnitt '## Wichtige Begriffe' mit 3-6 Begriffserklärungen\n"
            "6. Abschnitt '## Weiterführende Fragen' (3-4 Denkanstöße)"
        ),
    },
    "praesentation": {
        "label": "Präsentation",
        "emoji": "📊",
        "structure": (
            "Erstelle eine Foliensatz-Struktur mit 6-10 Folien als H2-Abschnitte:\n"
            "1. H1 '# Präsentation: [Thema]'\n"
            "2. Pro Folie: H2-Überschrift '## Folie N: [Titel]', darunter 3-5 "
            "Bullet-Points (kurz, nicht mehr als 12 Wörter je Bullet).\n"
            "3. Zwischendurch 1-2 Folien mit Reflexionsfragen ('## Folie N: Diskussion')\n"
            "4. Letzte Folie '## Folie X: Zusammenfassung' mit 3-4 Kernpunkten"
        ),
    },
    "quiz": {
        "label": "Quiz/Test",
        "emoji": "❓",
        "structure": (
            "Erstelle ein Quiz mit:\n"
            "1. H1 '# Quiz: [Thema]'\n"
            "2. Kurzem Einstieg (Thema, Anzahl Fragen, geschätzte Bearbeitungszeit)\n"
            "3. 6-10 Fragen, gemischte Typen: Multiple-Choice (A/B/C/D), Wahr/Falsch, "
            "offene Fragen. Nummeriere durchgehend.\n"
            "4. Bei MC-Fragen: alle Optionen angeben.\n"
            "5. Abschnitt '## Lösungen' mit richtiger Antwort und 1 Satz Begründung je Frage"
        ),
    },
    "checkliste": {
        "label": "Checkliste",
        "emoji": "✅",
        "structure": (
            "Erstelle eine Schritt-für-Schritt-Checkliste mit:\n"
            "1. H1 '# Checkliste: [Thema]'\n"
            "2. Kurzer Einleitung (wann/wofür?)\n"
            "3. 5-12 Checklisten-Punkten als '- [ ] Beschreibung' (Markdown-Task-Syntax)\n"
            "4. Gruppiere bei Bedarf in H2-Phasen ('## Vorbereitung', '## Durchführung', '## Nachbereitung')\n"
            "5. Abschließend: '## Häufige Fehler' (3-5 Stolperfallen)"
        ),
    },
    "glossar": {
        "label": "Glossar",
        "emoji": "📖",
        "structure": (
            "Erstelle ein Glossar mit:\n"
            "1. H1 '# Glossar: [Thema]'\n"
            "2. Kurzer Einführung\n"
            "3. 8-15 Begriffen, alphabetisch sortiert, als Definitionsliste:\n"
            "   **Begriff**\n"
            "   : Definition (1-3 Sätze, präzise)\n"
            "4. Querverweise zwischen verwandten Begriffen (z.B. 'siehe auch: ...')"
        ),
    },
    "struktur": {
        "label": "Strukturübersicht",
        "emoji": "🗺️",
        "structure": (
            "Erstelle eine Text-Mindmap / Themenübersicht:\n"
            "1. H1 '# Strukturübersicht: [Thema]'\n"
            "2. Kurzer Einleitung\n"
            "3. Baumstruktur in verschachtelten Listen (3 Ebenen):\n"
            "   - Hauptast\n"
            "     - Unterast\n"
            "       - Detail\n"
            "4. 4-7 Hauptäste, jeweils mit 2-4 Unterästen\n"
            "5. Abschluss: '## Wie liest man diese Übersicht?' (1 Absatz)"
        ),
    },
    "uebung": {
        "label": "Übungsaufgaben",
        "emoji": "✏️",
        "structure": (
            "Erstelle differenzierte Übungsaufgaben:\n"
            "1. H1 '# Übungsaufgaben: [Thema]'\n"
            "2. Drei H2-Schwierigkeitsgrade: '## Basis (★)', '## Mittel (★★)', '## Fortgeschritten (★★★)'\n"
            "3. Pro Schwierigkeitsgrad 2-4 Aufgaben, nummeriert\n"
            "4. Abschnitt '## Lösungen' mit Musterlösungen nach Schwierigkeitsgrad gegliedert"
        ),
    },
    "lerngeschichte": {
        "label": "Lerngeschichte",
        "emoji": "📚",
        "structure": (
            "Erstelle eine narrative Lerngeschichte:\n"
            "1. H1 '# Lerngeschichte: [Thema]'\n"
            "2. Kurze Charakter- und Rahmen-Einführung (1 Absatz)\n"
            "3. Erzählung in 3-5 Kapiteln als H2 ('## Kapitel 1: ...')\n"
            "4. Pro Kapitel 2-4 Absätze Fließtext, eingestreute wörtliche Rede, "
            "fachliche Inhalte im Dialog\n"
            "5. Abschließend '## Was wir gelernt haben' mit 3-5 Bullet-Points"
        ),
    },
    "versuch": {
        "label": "Versuchsanleitung",
        "emoji": "🔬",
        "structure": (
            "Erstelle eine Experiment-/Versuchsanleitung:\n"
            "1. H1 '# Versuch: [Thema]'\n"
            "2. '## Lernziel' (1 Absatz)\n"
            "3. '## Material' (Bullet-Liste)\n"
            "4. '## Durchführung' (nummerierte Schritte)\n"
            "5. '## Beobachtung' (Platzhalter für Einträge der Lernenden)\n"
            "6. '## Erklärung' (fachliche Hintergründe, 1-3 Absätze)\n"
            "7. '## Sicherheitshinweise' (falls relevant)"
        ),
    },
    "diskussion": {
        "label": "Diskussionskarten",
        "emoji": "💬",
        "structure": (
            "Erstelle einen Satz Diskussionsimpulse als 'Karten':\n"
            "1. H1 '# Diskussionskarten: [Thema]'\n"
            "2. Kurzer Moderationshinweis (1 Absatz)\n"
            "3. 6-10 Karten als H3-Blöcke ('### Karte 1'), jede mit:\n"
            "   - Eine provokante/offene Frage in fetter Schrift\n"
            "   - 2-3 Leitfragen zur Vertiefung\n"
            "   - Mini-Hintergrund (1-2 Sätze) für die Moderation"
        ),
    },
    "rollenspiel": {
        "label": "Rollenspielkarten",
        "emoji": "🎭",
        "structure": (
            "Erstelle ein Rollenspiel-Set mit Szenario + Rollenkarten:\n"
            "1. H1 '# Rollenspiel: [Thema]'\n"
            "2. '## Szenario' mit Ausgangssituation und Ziel (1-3 Absätze)\n"
            "3. 4-6 Rollenkarten als H3 ('### Rolle: [Name/Funktion]'), jede mit:\n"
            "   - **Motivation:** Was will diese Rolle?\n"
            "   - **Hintergrund:** Kurze Charakterisierung\n"
            "   - **Argumente:** 2-3 typische Standpunkte/Sätze\n"
            "4. '## Ablauf' mit Phasen des Rollenspiels und Zeitangaben\n"
            "5. '## Nachbereitung' (3-4 Reflexionsfragen)"
        ),
    },

    # ───────────────────────────────────────────────────────────
    # Analytisch / organisatorisch (Politik, Verwaltung, Beratung, Presse)
    # ───────────────────────────────────────────────────────────

    "bericht": {
        "label": "Bericht",
        "emoji": "📊",
        "category": "analytisch",
        "structure": (
            "Erstelle einen strukturierten Management-Bericht:\n"
            "1. H1 '# Bericht: [Titel]' — klarer Titel mit Bezug zu Thema/Zeitraum\n"
            "2. **Kurzfassung** (3-5 Sätze als fette Aufmacher-Zeile, kein Blindtext)\n"
            "3. '## Ausgangslage' (1-2 Absätze: Kontext, warum ist das Thema relevant)\n"
            "4. '## Zahlen & Fakten' — wo immer möglich mit Tabelle (| Kennzahl | Wert | Stand |). "
            "Wenn keine belastbare Zahl vorliegt, schreibe [Zahl einsetzen] statt zu halluzinieren.\n"
            "5. '## Analyse' (2-4 Absätze: Muster, Auffälligkeiten, Einordnung)\n"
            "6. '## Schlussfolgerungen & Empfehlungen' (3-5 Bullet-Points)\n"
            "7. '## Quellen' — Liste der herangezogenen Seiten/Dokumente, jeweils als Markdown-Link.\n"
            "Tonalität: sachlich, faktenorientiert, siezend. Keine Didaktik-Sprache."
        ),
    },
    "factsheet": {
        "label": "Factsheet",
        "emoji": "📈",
        "category": "analytisch",
        "structure": (
            "Erstelle ein kompaktes Factsheet (eine DIN-A4-Seite):\n"
            "1. H1 '# Factsheet: [Thema]'\n"
            "2. 3-4 One-Liner-Kernaussagen direkt darunter (fett gesetzt, mit zentraler Zahl oder Aussage je Zeile). "
            "Nutze [Zahl einsetzen] bei Unsicherheit.\n"
            "3. '## Kennzahlen' — Tabelle mit 5-10 Zeilen: | Kennzahl | Wert | Stand | Quelle |\n"
            "4. '## Einordnung' (2-3 Absätze, jeweils max. 3 Sätze)\n"
            "5. '## Weiterführende Informationen' — Bulletliste mit Markdown-Links\n"
            "Tonalität: faktisch, zitierfähig, siezend. Keine werblichen Floskeln."
        ),
    },
    "steckbrief": {
        "label": "Projektsteckbrief",
        "emoji": "🗂️",
        "category": "analytisch",
        "structure": (
            "Erstelle einen Projektsteckbrief:\n"
            "1. H1 '# Projektsteckbrief: [Projektname]'\n"
            "2. Meta-Tabelle direkt am Anfang: | Träger | … | Laufzeit | … | Fördervolumen | … | Partner | … |\n"
            "3. '## Ziel & Mehrwert' (1-2 Absätze, was das Projekt erreichen will und für wen)\n"
            "4. '## Umsetzung' — Meilensteine als Bulletliste mit Jahres-/Quartalsangabe\n"
            "5. '## Ergebnisse / Outputs' — konkrete Produkte, Zahlen, Veröffentlichungen. "
            "Wenn noch keine Ergebnisse vorliegen: '[Zwischenstand: Projekt laufend]'.\n"
            "6. '## Beteiligte & Kontakt' — Ansprechpartner:innen (Platzhalter wenn unbekannt)\n"
            "Tonalität: sachlich-präzise, nachvollziehbar, siezend."
        ),
    },
    "pressemitteilung": {
        "label": "Pressemitteilung",
        "emoji": "📰",
        "category": "analytisch",
        "structure": (
            "Erstelle eine journalistisch sauber strukturierte Pressemitteilung:\n"
            "1. Dateline-Zeile: '[Ort], [Datum als heute ausformuliert]'\n"
            "2. H1 '# [Headline]' — aussagestark, News-Wert, max. 12 Wörter\n"
            "3. Subhead in *kursiv* direkt unter der H1 (ein Satz, ergänzt die Headline)\n"
            "4. **Lead-Absatz**: 5-W-Aufmacher (wer, was, wann, wo, warum) in ≤ 5 Sätzen, fett gesetzt\n"
            "5. 2-3 Fließtext-Absätze mit Kernbotschaften\n"
            "6. Zitat-Block: '> „[Zitat]“ — [Name, Funktion]' — Platzhalter, wenn nicht bekannt\n"
            "7. '## Über WirLernenOnline' — 2-Satz-Boilerplate\n"
            "8. '## Pressekontakt' — Ansprechpartner/E-Mail (Platzhalter)\n"
            "Tonalität: zitierfähig, präzise, ohne Werbesprech, siezend."
        ),
    },
    "vergleich": {
        "label": "Vergleichs-Analyse",
        "emoji": "⚖️",
        "category": "analytisch",
        "structure": (
            "Erstelle eine Vergleichs-Analyse:\n"
            "1. H1 '# Vergleich: [Option A] vs. [Option B] (ggf. vs. [Option C])'\n"
            "2. '## Fragestellung' (1 Absatz: worum geht es, welche Entscheidung steht an)\n"
            "3. '## Kriterien-Matrix' — Markdown-Tabelle: Spalten = Optionen, Zeilen = "
            "4-7 Kriterien. In jeder Zelle kurze Bewertung + ✓ / ○ / ✗ Symbol. Beispiel:\n"
            "   | Kriterium | Option A | Option B |\n"
            "   | --- | --- | --- |\n"
            "   | Reichweite | ✓ stark (10k+) | ○ mittel (3k) |\n"
            "4. '## Stärken & Schwächen' — pro Option 1 Absatz\n"
            "5. '## Empfehlung' — klare Handlungsempfehlung mit Begründung (1-2 Absätze)\n"
            "Tonalität: analytisch, ausgewogen, siezend."
        ),
    },
}


# Aliase für tolerante Material-Typ-Zuordnung (vom Classifier/User getippt)
_DEFAULT_TYPE_ALIASES: dict[str, str] = {
    "auto": "auto",
    "automatisch": "auto",
    "ki": "auto",
    "arbeitsblatt": "arbeitsblatt",
    "arbeitsblätter": "arbeitsblatt",
    "arbeitsblaetter": "arbeitsblatt",
    "aufgabenblatt": "arbeitsblatt",
    "aufgabenblätter": "arbeitsblatt",
    "aufgabenblaetter": "arbeitsblatt",
    "worksheet": "arbeitsblatt",
    "worksheets": "arbeitsblatt",
    "infoblatt": "infoblatt",
    "info": "infoblatt",
    "informationsblatt": "infoblatt",
    "zusammenfassung": "infoblatt",
    "praesentation": "praesentation",
    "präsentation": "praesentation",
    "folien": "praesentation",
    "vortrag": "praesentation",
    "quiz": "quiz",
    "quizfragen": "quiz",
    "quizze": "quiz",
    "test": "quiz",
    "tests": "quiz",
    "quiz/test": "quiz",
    "checkliste": "checkliste",
    "checklisten": "checkliste",
    "checklist": "checkliste",
    "checklists": "checkliste",
    "glossar": "glossar",
    "begriffe": "glossar",
    "strukturuebersicht": "struktur",
    "strukturübersicht": "struktur",
    "struktur": "struktur",
    "mindmap": "struktur",
    "themenuebersicht": "struktur",
    "themenübersicht": "struktur",
    "übersicht": "struktur",
    "uebung": "uebung",
    "übung": "uebung",
    "uebungen": "uebung",
    "übungen": "uebung",
    "uebungsaufgaben": "uebung",
    "übungsaufgaben": "uebung",
    "lerngeschichte": "lerngeschichte",
    "lerngeschichten": "lerngeschichte",
    # Welle E v4+11 (2026-05-26, eval-f6f56-Befund): "geschichte" und
    # "geschichten" als Aliase entfernt — kollidieren als Substring mit
    # dem Schulfach "Geschichte" (z.B. "Quiz zur europäischen Geschichte"
    # wurde fälschlich als Lerngeschichte erkannt). User muss explizit
    # "lerngeschichte" sagen.
    "story": "lerngeschichte",
    "stories": "lerngeschichte",
    "versuch": "versuch",
    "versuche": "versuch",
    "experiment": "versuch",
    "experimente": "versuch",
    "versuchsanleitung": "versuch",
    "versuchsanleitungen": "versuch",
    "diskussion": "diskussion",
    "diskussionskarten": "diskussion",
    "debatte": "diskussion",
    "rollenspiel": "rollenspiel",
    "rollenspielkarten": "rollenspiel",
    "rollen": "rollenspiel",

    # Analytisch / organisatorisch
    "bericht": "bericht",
    "report": "bericht",
    "reporting": "bericht",
    "managementbericht": "bericht",
    "jahresbericht": "bericht",
    "lagebericht": "bericht",
    "factsheet": "factsheet",
    "faktenblatt": "factsheet",
    "kennzahlen": "factsheet",
    "kpis": "factsheet",
    "kpi": "factsheet",
    "fakten": "factsheet",
    "uebersicht": "factsheet",
    "übersicht": "factsheet",
    "steckbrief": "steckbrief",
    "projektsteckbrief": "steckbrief",
    "projektinfo": "steckbrief",
    "projektprofil": "steckbrief",
    "pressemitteilung": "pressemitteilung",
    "presse": "pressemitteilung",
    "pm": "pressemitteilung",
    "pressetext": "pressemitteilung",
    "medienmitteilung": "pressemitteilung",
    "vergleich": "vergleich",
    "gegenueberstellung": "vergleich",
    "gegenüberstellung": "vergleich",
    "matrix": "vergleich",
    "vergleichsanalyse": "vergleich",
    "evaluation": "vergleich",
}


# Short aliases that are distinctive enough to match inside a free-text message
# even when they are under 6 chars. Avoids false positives like "info" in
# "Ich brauche Info zur Photosynthese" (ambiguous) while still catching "Quiz".
_DEFAULT_SHORT_ALIAS_WHITELIST = {"quiz", "test", "kpi", "pm"}


# Verbs that strongly indicate a "create me new material" intent. Checked at
# message start or early in the sentence as an override for classifier drift.
_DEFAULT_CREATE_TRIGGERS: tuple[str, ...] = (
    # Imperative
    "erstelle",
    "erstell ",
    "erstell mir",
    "generiere",
    "generier mir",
    "mach mir ein",
    "mach mir eine",
    "mach ein",
    "mach eine",
    "bau mir",
    "schreib mir ein",
    "schreib mir eine",
    "schreib ein",
    "schreib eine",
    "entwirf",
    "produziere",
    # Indikativ/Wunsch (Verwaltung, Politik, Presse formulieren oft so)
    "ich brauche ein",
    "ich brauche eine",
    "ich brauche einen",
    "brauche ein",
    "brauche eine",
    "brauche einen",
    "hätte gern ein",
    "hätte gern eine",
    "hätte gern einen",
    "hätte gerne ein",
    "hätte gerne eine",
    "hätte gerne einen",
    "ich möchte ein",
    "ich möchte eine",
    "ich möchte einen",
    "möchte ein",
    "möchte eine",
    "möchte einen",
    "gib mir ein",
    "gib mir eine",
    "gib mir einen",
    "kannst du mir ein",
    "kannst du mir eine",
    "kannst du mir einen",
    "kannst du einen",
    "kannst du ein",
    "fasse zusammen als",
    "wandle um in",
)


# Personas, die analytische Formate (Bericht / Factsheet / …) bevorzugen.
# Für diese wird die Quick-Reply-Auswahl im Canvas so sortiert, dass die
# analytischen Typen zuerst erscheinen.
_DEFAULT_ANALYTICAL_PERSONAS: frozenset[str] = frozenset({
    "P-ENT",       # Entscheider: Verwaltung + Politik + Beratung
    "P-RED",       # Redaktion & Medien (inkl. Presse / Journalismus)
})


# ---------------------------------------------------------------------------
# Learning-resource-type → canvas material type
# ---------------------------------------------------------------------------

# Mapping from WLO/edu-sharing `learning_resource_types` values to our
# canvas MATERIAL_TYPES keys. The LRT vocabulary is broader than our
# canvas types, so unmapped LRT falls back to 'auto'.
_DEFAULT_LRT_TO_MATERIAL_TYPE: dict[str, str] = {
    "arbeitsblatt": "arbeitsblatt",
    "aufgabe": "uebung",
    "unterrichtsbaustein": "arbeitsblatt",
    "unterrichtsplan": "arbeitsblatt",
    "unterrichtsplanung": "arbeitsblatt",
    "übungsmaterial": "uebung",
    "uebungsmaterial": "uebung",
    "uebungsaufgabe": "uebung",
    "übungsaufgabe": "uebung",
    "test": "quiz",
    "quiz": "quiz",
    "selbsttest": "quiz",
    "praesentation": "praesentation",
    "präsentation": "praesentation",
    "folie": "praesentation",
    "infoblatt": "infoblatt",
    "informationsblatt": "infoblatt",
    "lesetext": "infoblatt",
    "nachschlagewerk": "glossar",
    "glossar": "glossar",
    "begriffsdefinition": "glossar",
    "mindmap": "struktur",
    "concept map": "struktur",
    "themenübersicht": "struktur",
    "themenübersicht": "struktur",
    "rollenspiel": "rollenspiel",
    "debatte": "diskussion",
    "diskussion": "diskussion",
    "experiment": "versuch",
    "versuch": "versuch",
    "video": "infoblatt",              # Video can't be reproduced — infoblatt form
    "audio": "infoblatt",
    "webseite": "infoblatt",
    "lerngeschichte": "lerngeschichte",
    # Welle E v4+11 (2026-05-26): "geschichte" entfernt — Substring-Match
    # mit Schulfach Geschichte. User muss explizit "lerngeschichte" sagen.
    "erzählung": "lerngeschichte",
    "checkliste": "checkliste",
}


# ---------------------------------------------------------------------------
# YAML-backed Getter-Funktionen (Quelle der Wahrheit: 05-canvas/*.yaml)
# ---------------------------------------------------------------------------
#
# Jeder Getter ruft den config_loader (mtime-cached), merged Studio-Edits
# sofort ein, und fällt bei Fehlern auf den `_DEFAULT_*`-Block zurück.
# Runtime-Code benutzt IMMER diese Getter, nicht die `_DEFAULT_*`-Konstanten
# direkt — so wirken YAML-Änderungen live, ohne Backend-Restart.


def get_material_types() -> dict[str, dict[str, str]]:
    """Return the current material-type registry (YAML or default)."""
    try:
        items = config_loader.load_canvas_material_types()
    except Exception as e:  # noqa: BLE001 — defensive, defaults are safe
        logger.warning("material-types YAML load failed: %s (using defaults)", e)
        return copy.deepcopy(_DEFAULT_MATERIAL_TYPES)

    if not items:
        return copy.deepcopy(_DEFAULT_MATERIAL_TYPES)

    result: dict[str, dict[str, str]] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        mtid = (it.get("id") or "").strip()
        if not mtid:
            continue
        entry: dict[str, str] = {
            "label": it.get("label") or mtid,
            "emoji": it.get("emoji") or "📄",
            "structure": it.get("structure") or "",
        }
        cat = it.get("category")
        if cat:
            entry["category"] = cat
        result[mtid] = entry
    return result or copy.deepcopy(_DEFAULT_MATERIAL_TYPES)


def get_type_aliases() -> dict[str, str]:
    """Flat alias → canonical-type-id map. YAML merged on top of defaults."""
    try:
        bundle = config_loader.load_canvas_type_aliases()
    except Exception as e:  # noqa: BLE001
        logger.warning("type-aliases YAML load failed: %s (using defaults)", e)
        return dict(_DEFAULT_TYPE_ALIASES)

    yaml_map = bundle.get("aliases") or {}
    if not yaml_map:
        return dict(_DEFAULT_TYPE_ALIASES)
    # Start from defaults, let YAML override (studio-editable wins)
    merged: dict[str, str] = dict(_DEFAULT_TYPE_ALIASES)
    for k, v in yaml_map.items():
        if isinstance(k, str) and isinstance(v, str):
            merged[k.lower()] = v
    return merged


def get_short_alias_whitelist() -> set[str]:
    """Short (≤5-char) aliases that are allowed as substring matches."""
    try:
        bundle = config_loader.load_canvas_type_aliases()
    except Exception:
        return set(_DEFAULT_SHORT_ALIAS_WHITELIST)
    items = bundle.get("short_whitelist") or []
    if not items:
        return set(_DEFAULT_SHORT_ALIAS_WHITELIST)
    return {str(x).strip().lower() for x in items if x}


def get_lrt_mapping() -> dict[str, str]:
    """edu-sharing LRT → canvas material-type mapping (for remix flow)."""
    try:
        bundle = config_loader.load_canvas_type_aliases()
    except Exception:
        return dict(_DEFAULT_LRT_TO_MATERIAL_TYPE)
    yaml_map = bundle.get("lrt_to_type") or {}
    if not yaml_map:
        return dict(_DEFAULT_LRT_TO_MATERIAL_TYPE)
    merged: dict[str, str] = dict(_DEFAULT_LRT_TO_MATERIAL_TYPE)
    for k, v in yaml_map.items():
        if isinstance(k, str) and isinstance(v, str):
            merged[k.lower()] = v
    return merged


def get_create_triggers() -> tuple[str, ...]:
    """Verb phrases that flag a "create new material" intent."""
    try:
        bundle = config_loader.load_canvas_create_triggers()
    except Exception:
        return tuple(_DEFAULT_CREATE_TRIGGERS)
    items = bundle.get("create_triggers") or []
    if not items:
        return tuple(_DEFAULT_CREATE_TRIGGERS)
    return tuple(str(x) for x in items if x)


# (Der Getter ``get_search_verbs`` [Negative-Liste "Suche statt Create",
# las den ``search_verbs``-Key desselben YAML-Bundles] stand hier —
# entfernt 2026-07-09: 0 Produktions-Aufrufer in app/ + scripts/.)
_DEFAULT_EDIT_TRIGGERS: tuple[str, ...] = (
    "mach es einfacher", "mach das einfacher", "einfacher formulieren",
    "vereinfachen", "vereinfache", "kürzer", "kürzer fassen", "kürzer formulieren",
    "knapper", "ausführlicher", "detaillierter", "länger", "mehr details",
    "füge hinzu", "ergänze", "ergänze um", "nimm noch", "nimm zusätzlich",
    "zusätzlich", "dazu noch", "mehr übungen", "mehr aufgaben", "mehr beispiele",
    "füge lösungen", "füge eine lösung", "mit lösungen", "mit lösung",
    "streiche", "entferne", "lösche", "weg mit", "ohne",
    "formuliere um", "schreib um", "anders formulieren", "umformulieren",
    "neu formulieren", "stil anpassen", "förmlicher", "formeller", "lockerer",
    "persönlicher", "ändere", "ändere den titel", "ändere die überschrift",
    "ändere die reihenfolge", "sortiere um", "tausch", "ersetze",
    "pass es an", "passe es an", "überarbeite", "verbessere", "optimiere",
    "verfeinere",
)


_DEFAULT_EXPLICIT_CREATE_OVERRIDES: tuple[str, ...] = (
    "neues arbeitsblatt", "neues infoblatt", "neues quiz", "neuen bericht",
    "neues factsheet", "neue präsentation", "neuen steckbrief",
    "neue pressemitteilung", "neuen vergleich", "anderes thema",
    "zu einem anderen thema", "fang nochmal an", "fang von vorne",
)


def get_edit_triggers() -> tuple[str, ...]:
    """Verb phrases that flag a Canvas-EDIT (refinement) intent."""
    try:
        bundle = config_loader.load_canvas_edit_triggers()
    except Exception:
        return _DEFAULT_EDIT_TRIGGERS
    items = bundle.get("edit_triggers") or []
    if not items:
        return _DEFAULT_EDIT_TRIGGERS
    return tuple(str(x) for x in items if x)


def get_explicit_create_overrides() -> tuple[str, ...]:
    """Phrases that force CREATE even in S3 (e.g. 'neues Quiz')."""
    try:
        bundle = config_loader.load_canvas_edit_triggers()
    except Exception:
        return _DEFAULT_EXPLICIT_CREATE_OVERRIDES
    items = bundle.get("explicit_create_overrides") or []
    if not items:
        return _DEFAULT_EXPLICIT_CREATE_OVERRIDES
    return tuple(str(x) for x in items if x)


def get_analytical_personas() -> frozenset[str]:
    """Persona IDs that see analytical material-types first in quick replies."""
    try:
        bundle = config_loader.load_canvas_persona_priorities()
    except Exception:
        return _DEFAULT_ANALYTICAL_PERSONAS
    items = bundle.get("analytical_personas") or []
    if not items:
        return _DEFAULT_ANALYTICAL_PERSONAS
    return frozenset(str(x).strip() for x in items if x)
