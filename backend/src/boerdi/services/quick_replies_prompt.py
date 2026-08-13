"""Quick-reply system-prompt text (split out of ``quick_replies_llm``).

The LLM-facing half of the quick-reply generator: the two persona
capability-hint menus and ``build_system_prompt``. ``quick_replies_llm`` keeps
the transport, the parsing/dedupe and the ``max_chars`` filter — plus the config
seams the tests patch there (``get_state_directive``, ``_analytical_personas``,
``load_display_rules_config``), whose results come in as arguments; this module
reads no config itself. Precedent: ``classify_prompt`` /
``response_prompt_tools_text``. Line length is dictated by the verbatim prompt
text (per-file ``E501`` ignore in pyproject.toml): wrapping would alter the bytes
the LLM sees.
"""

from __future__ import annotations

import json
from typing import Any

from boerdi.i18n import Locale, template_hint

# ── Persona-abhaengige Quick-Reply-Menues (Capability-Hints) ──────────
# Diese Listen geben dem LLM einen konkreten Vorrat an plausiblen
# Vorschlaegen, ausgerichtet an dem, was der Bot TATSAECHLICH kann.
# Der LLM darf daraus ableiten oder abwandeln — NICHT woertlich kopieren.
_CAPABILITY_HINTS_DIDACTIC = [
    # Suche
    "Zeig mir mehr Material zu {thema}",
    "Hast du auch Videos/Audios dazu?",
    "Gibt es interaktive Uebungen dazu?",
    "Welche Sammlungen gibt es zu {thema}?",
    "Welche Themenseite passt dazu?",
    # Canvas-Create didaktisch
    "Erstelle mir ein Arbeitsblatt dazu",
    "Mach mir ein Quiz dazu",
    "Erstell mir eine Praesentation zu {thema}",
    "Bau mir einen Lernpfad daraus",
    # Canvas-Edit (wenn S3)
    "Mach es einfacher",
    "Fuege Loesungen hinzu",
    "Kuerzer fassen",
    "Mehr Beispiele bitte",
    # Vertiefung / Richtung
    "Was gibt es noch zu {fach}?",
    "Anderes Thema: ",
    "Fuer welche Klassenstufe ist das?",
]

_CAPABILITY_HINTS_ANALYTICAL = [
    # Projekt-/OER-Statistik / Plattforminfos
    "Welche Statistiken gibt es zu WLO?",
    "Wie viele Materialien hat WLO?",
    "Welche Faecher sind am besten abgedeckt?",
    "Wer steht hinter WLO?",
    "Welche Projekte laufen gerade?",
    # Canvas-Create analytisch
    "Erstell mir einen Bericht dazu",
    "Bau mir ein Factsheet zu {thema}",
    "Ich brauche einen Projektsteckbrief",
    "Entwirf eine Pressemitteilung dazu",
    "Erstell mir einen Vergleich zu {thema}",
    # Canvas-Edit
    "Formeller formulieren",
    "Kuerzer fassen",
    "Kennzahlen ergaenzen",
    "Foerderlogik hervorheben",
    # Suche / Kontext
    "Zeig mir Datengrundlagen dazu",
    "Welche Zielgruppen sind primaer?",
]


def select_capability_hints(
    persona_id: str, in_canvas: bool, has_topic: bool, analytical: frozenset[str],
) -> list[str]:
    """Return a focused subset of capability hints for the quick-reply LLM.
    ``analytical`` is the set of persona IDs that gets the analytical menu — the
    caller reads it from config."""
    base = (
        _CAPABILITY_HINTS_ANALYTICAL if persona_id in analytical
        else _CAPABILITY_HINTS_DIDACTIC
    )
    hints = [h for h in base if not (("{thema}" in h or "{fach}" in h) and not has_topic)]
    if not in_canvas:
        # Drop pure-edit hints — no canvas yet.
        hints = [h for h in hints if not any(
            w in h.lower() for w in (
                "einfacher", "loesungen", "kuerzer", "mehr beispiele",
                "formeller", "kennzahlen ergaenzen", "foerderlogik",
            )
        )]
    return hints[:14]


def fill_capability_hints(capability_hints: list[str], thema: str, fach: str) -> list[str]:
    """Fill the ``{thema}``/``{fach}`` placeholders with concrete session values
    so the LLM sees realistic example sentences. A hint whose placeholders do not
    resolve is kept as-is rather than dropped."""
    filled_hints = []
    for h in capability_hints:
        try:
            filled_hints.append(h.format(thema=thema or "dem Thema", fach=fach or "deinem Fach"))
        except (KeyError, IndexError, ValueError):
            filled_hints.append(h)
    return filled_hints


def build_system_prompt(
    *, count: int, persona_id: str, intent_id: str, state_id: str,
    in_canvas: bool, public_entities: dict[str, Any], state_meta: dict[str, Any],
    filled_hints: list[str], budget: int, lang: Locale,
) -> str:
    """Assemble the quick-reply system prompt. ``state_meta`` is the
    ``04-states`` directive entry — an unknown state ({}) yields an empty label
    plus the fallback directive. ``budget`` is the ``max_chars`` cap (``0`` =
    off): named in the prompt here, enforced by the caller's filter — one number
    from one source."""
    # simplify (P3-3): the semantic page-context line (page_context_service) is
    # deferred to its own package; the seam is here. Until then no page line.
    _page_line = ""

    # B8: Quick-Replies speak in the USER's voice to the bot, and the user
    # always duzt BOERDi (product rule, identical to the response prompt).
    persona_salute = "du"

    # State-specific QR directive (bot_directive from 04-states/states.yaml).
    # Unknown state → {} → empty label + fallback directive.
    _qr_state_label = state_meta.get("label", "")
    _qr_state_directive = state_meta.get("bot_directive", "")
    _len_rule = (
        f"hoechstens {budget} Zeichen lang (mit Leerzeichen)" if budget
        else "kurz — ein knapper Satz"
    )
    return f"""Du generierst genau {count} kurze Antwortvorschlaege fuer einen Chatbot-Nutzer.
Jeder Vorschlag ist {_len_rule}; laengere werden verworfen und gar nicht erst angezeigt.
Der Nutzer interagiert gerade mit BOERDi, dem Chatbot der Bildungsplattform
WirLernenOnline (WLO).

## Kontext
- Persona: {persona_id} (Anrede: {persona_salute})
- Intent: {intent_id}
- Gesprächs-Phase: {state_id} ({_qr_state_label}){" — Canvas-Arbeit aktiv" if in_canvas else ""}
- Erkannte Entities: {json.dumps(public_entities, ensure_ascii=False)}{_page_line}

## Phase-Direktive für die Quick-Reply-Auswahl
{_qr_state_directive or '— keine spezifische Direktive für diese Phase, biete generische Folgeschritte an.'}
Die {count} Vorschläge müssen zu dieser Phase passen — z.B. in der Ergebnis-Kuratierung Refinement-Optionen,
in der Bewertung & Feedback eine Probing-Frage, in der Slot-Erfassung wahrscheinliche Slot-Werte.

## Was BOERDi kann (die Vorschlaege MUESSEN sich daraus bedienen)
1. **Inhalte suchen** — einzelne Materialien (Video, Arbeitsblatt, Audio, interaktive
   Uebung, Bild, Text) mit Filtern auf Fach, Stufe, Medientyp, Lizenz.
2. **Sammlungen suchen** — kuratierte Material-Sammlungen.
3. **Themenseiten suchen** — didaktisch aufbereitete Einstiegsseiten zu einem Thema.
4. **Plattforminfos und OER-Projektinfos** — Fragen zu WLO, edu-sharing, Metaventis,
   Projekten, Zahlen/Statistiken zur Plattform.
5. **Canvas-Ausgaben (neue Inhalte erstellen)** — didaktisch: Arbeitsblatt, Infoblatt,
   Praesentation, Quiz, Checkliste, Glossar, Strukturuebersicht, Uebungen,
   Lerngeschichte, Versuchsanleitung, Diskussionskarten, Rollenspiel, **Lernpfad**.
   Analytisch: Bericht, Factsheet, Projektsteckbrief, Pressemitteilung, Vergleich.
6. **Canvas-Edits** — bestehenden Canvas-Inhalt verfeinern (einfacher, kuerzer,
   ausfuehrlicher, Loesungen ergaenzen, formeller, etc.) — NUR wenn State=S3.

## Realistische Vorschlag-Beispiele fuer diese Persona
(Inspiration — nicht woertlich uebernehmen, auf den konkreten Kontext anpassen.)
{chr(10).join(f"- {h}" for h in filled_hints)}

## Perspektive (STRIKT — wichtigste Regel)
Die 4 Vorschlaege sind **Saetze, die der NUTZER dem Bot sagt**, nicht der Bot
zum Nutzer. Schreib aus Ich-/Du-Perspektive des Users. Bot-imperative
("Mach", "Zeige", "Filtere"...) sind nur dann ok, wenn der NUTZER damit etwas
vom Bot verlangt ("Zeig mir nur Videos") — nicht als Bot-Selbstbefehl
("Material zeigen"). Faustregel: Jeder Vorschlag muss vor dem Wort
"Boerdi/Bot" stehen koennen wie ein User-Satz.
FALSCH (Bot-Perspektive / handlungslos):
  - "Weitere Materialien zeigen"
  - "Suche eingrenzen"
  - "Nur Arbeitsblaetter zeigen"   ← wirkt wie Bot-Selbstbefehl
RICHTIG (Nutzer-Perspektive):
  - "Zeig mir mehr davon"
  - "Ich will das auf Klasse 8 eingrenzen"
  - "Zeig mir nur Arbeitsblaetter"   ← Nutzer fordert vom Bot
  - "Hast du auch Videos dazu?"

## Standalone-Regel (KRITISCH — kein Kontext-Anhang moeglich)
Jeder Vorschlag wird als **alleinstehender Button** dargestellt. Der Nutzer
kann ihn NICHT bearbeiten oder ergaenzen — er klickt 1:1 wie er da steht.
Deshalb:
  - Jeder Vorschlag muss **fuer sich alleine sinnvoll** sein, ohne den
    vorherigen Bot-Satz mitzulesen.
  - KEINE Demonstrativa ohne Bezug: "Mehr davon", "Das genauer", "Mach es
    einfacher" sind nur OK wenn aus dem Thema-Kontext eindeutig ist, worauf
    sich "davon"/"das"/"es" bezieht. Im Zweifel das Thema konkret nennen:
      SCHLECHT: "Mehr davon zeigen"
      BESSER:   "Mehr zu Photosynthese zeigen"
  - KEINE Vorschlaege die ein ungesagtes Subjekt voraussetzen.

## Struktur ({count} verschiedene Typen — KEIN Duplikat)
Waehle {count} aus den folgenden Kategorien (mindestens {min(3, count)} unterschiedliche Kategorien):
  (a) **Vertiefung / Material-Typ-Filter** — mehr zum aktuellen Thema/Treffer,
      gerne mit konkretem Material-Typ-Filter (Video, Arbeitsblatt, Uebung,
      Audio, Praesentation, Interaktiv, Quiz, Bild, Text). Diese Filter sind
      ausdruecklich erwuenscht — sie propagieren in die Suche und werden
      als Such-Filter weitergereicht.
      z.B. "Hast du auch Videos dazu?", "Zeig mir nur Arbeitsblaetter",
           "Gibt es das fuer Klasse 8?", "Ich brauche interaktive Uebungen"
  (b) **Canvas-Ausgabe** — neues Material erstellen lassen (zieht den aktuellen
      Kontext als Thema heran)
      z.B. "Mach mir ein Quiz daraus", "Erstell mir einen Lernpfad"
  (c) **Canvas-Edit** — NUR wenn S3 aktiv: bestehenden Inhalt aendern
      z.B. "Mach es einfacher", "Fuege Loesungen hinzu"
  (d) **Richtungswechsel** — anderes Thema / andere Fachrichtung
      z.B. "Anderes Thema: Klimawandel", "Was gibt's zu Physik?"
  (e) **Plattforminfo** — KONKRETE, existierende Aspekte von WLO.
      ZULAESSIG (existieren wirklich):
        - "Welche Faecher deckt WLO ab?"
        - "Wie viele Materialien gibt es?"
        - "Wer steht hinter WLO?" / "Wer betreibt WLO?"
        - "Was ist OER?" / "Was bedeuten die Lizenzen?"
        - "Was ist eine Themenseite?" / "Was sind Fachportale?"
        - "Welche Bildungsstufen werden abgedeckt?"
        - "Kann ich eigene Materialien einreichen?"
      VERBOTEN (existieren NICHT als WLO-Konzept):
        - "Plattforminfrastruktur", "Architektur", "Backend", "API"
        - "Roadmap", "Strategie", "Datenmodell"
        - irgendein erfundener Tech-Begriff
      Wenn du dir unsicher bist ob ein Begriff existiert: lass die
      Plattforminfo-Kategorie weg und nimm eine andere.
  (f) **Konkrete Antwort auf Rueckfrage des Bots** — wenn der Bot eine Frage
      stellt (Thema? Fach? Stufe?), liefere KONKRETE Antworten als Vorschlaege,
      z.B. bei Mathe-Frage: "Bruchrechnung Klasse 6", "Geometrie Sek I".

## Regeln
1. Genau {count} Vorschlaege, einer pro Zeile, KEINE Nummerierung, KEINE Bullets.
2. **Laenge — HARTE Grenze**: jeder Vorschlag {_len_rule}. Zaehle die Zeichen,
   bevor du eine Zeile abgibst. Zu lange Vorschlaege werden VERWORFEN; der
   Nutzer sieht dann eine Pille weniger. Beim Lotsen-Format (Regel 11) zaehlt
   nur der Anzeigetext, nicht die URL.
   ZU LANG: "Erstelle ein Arbeitsblatt zu Kompetenzen geometrischer Optik" (60)
   GUT:     "Arbeitsblatt zur geometrischen Optik" (35)
3. Anrede strikt {persona_salute}.
4. Wenn Canvas aktiv (S3) ist: mindestens EIN Edit-Vorschlag (Kategorie c).
5. Wenn Themenseite bekannt: mindestens EIN Vorschlag der den Seiten-Kontext nutzt.
6. Wenn Persona analytisch ist (P-ENT/P-ENT/P-RED/P-ENT/P-RED):
   bevorzuge Bericht/Factsheet/Steckbrief/Pressemitteilung/Vergleich und
   Plattform-/Projekt-/Statistik-Fragen. Weniger klassische Lehrmaterialien.
7. Wenn Persona didaktisch (P-LEH/P-LER/P-ELT/P-AND): klassische Lehrmaterialien
   + Lernpfad + Medienvielfalt. Keine Berichte/Factsheets.
8. Wenn der Bot eine Rueckfrage stellt, liefere KONKRETE Antworten (Kategorie f) —
   KEINE generischen Phrasen wie "Was kannst du noch?".
9. NIEMALS erfundene oder vage Begriffe. Wenn du nicht 100% sicher bist
   dass etwas auf WLO existiert: nimm einen anderen Vorschlag. Lieber
   ein konkretes Fach-Beispiel ("Mathe Klasse 8") als ein abstraktes,
   nicht-existierendes Konzept.
10. Vorschlaege sollen **selbst-erklaerend** sein. Wenn man den Vorschlag
    aus dem Kontext reisst, muss klar bleiben was angefragt wird.
    SCHLECHT: "Mehr davon zeigen" (ohne Bezug)
    GUT: "Mehr Mathe-Videos zeigen" / "Anderes Thema waehlen"
11. **Bring-mich-hin-Vorschlag (Webseiten-Lotse — sehr oft nutzbar)**:
    Wenn die NUTZER-NACHRICHT zu einer dieser konkreten WLO-Seiten passt,
    MUSST du EINEN der 4 Vorschlaege als Spezialformat schreiben:

       ``__guide__|<kurzer Anzeigetext>|<vollstaendige URL>``

    Frontend rendert das als dunkelblauen Same-Tab-Navigations-Button.
    Die anderen 3 Vorschlaege bleiben normale Folgesaetze.

    NUTZER-FRAGE → ANZUBIETENDE WLO-URL (verlaesslich; erfinde KEINE
    weiteren Pfade ausserhalb dieser Liste):

    Frage zu Themenseiten / Konzept-Erklaerung „was ist eine Themenseite":
      __guide__|Themenseiten-Beispiel|https://wirlernenonline.de/themenseite/klimawandel
    Frage zu Fachportalen / „welche Faecher / fachportale" / Uebersicht:
      __guide__|Fachportal-Uebersicht|https://wirlernenonline.de/fachportale
    Frage zu Mitmachen / „wie kann ich beitragen / einreichen":
      __guide__|Mitmachen-Seite|https://wirlernenonline.de/mitmachen
    Frage zu „wer steht hinter / wer macht / ueber WLO":
      __guide__|Ueber WLO|https://wirlernenonline.de/ueber-uns
    Frage zu „WLO-Projekt / Hintergrund / Geschichte":
      __guide__|Hintergrund-Info|https://wirlernenonline.de/projekt
    Frage zu OER / Lizenzen (allgemein):
      __guide__|OER-Erklaerung|https://wirlernenonline.de/oer
    Frage zu konkretem Thema X (Themenseite gewuenscht):
      __guide__|Themenseite <X>|https://wirlernenonline.de/themenseite/<x-kleinbuchstaben>
    Frage zu Edu-Sharing / „edu-sharing.net":
      __guide__|Edu-Sharing|https://openeduhub.net/

    REGELN:
    - URL muss vollstaendig sein (https://...), kein relativer Pfad.
    - Maximal 1 Guide-QR pro Antwort. Insgesamt also {count} Zeilen davon 1 Guide.
    - Wenn KEINE der oben gelisteten Frage-Kategorien passt, KEINEN Guide-QR
      einbauen — dann {count} normale Vorschlaege.
    - Themenseiten-Slugs nur fuer Themen die der User EXPLIZIT genannt hat
      (z.B. „klimawandel", „photosynthese") — keine Slugs erfinden.
    - Anzeigetext kurz, konkret, deutsch. KEINE generische „Bring mich hin"
      ohne Kontext.

Gib NUR die {count} Zeilen zurueck, sonst nichts.""" + template_hint(lang)
