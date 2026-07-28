"""The three eval prompt templates (port of ALT ``eval_prompts.py``).

Static ``.format()`` templates with no code dependencies: scenario generation,
the persona-simulator system prompt, and the judge rubric. Copied byte-for-byte
from ALT — ``tests/test_eval_prompts.py`` pins each one's exact length and
placeholder set, so an accidental edit fails loudly.

The templates carry the placeholders the callers fill:
``scenario_gen`` builds ``persona_markers_block`` from the persona definitions
(ALT Welle E: markers are config, not prompt text), and ``judge`` builds the
three ``*_expectations`` blocks.
"""

from __future__ import annotations

# ── Scenario generation ────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────
# Welle E (2026-05-25) — Scenario-Prompt YAML-driven
#
# Vorher: ~60 Zeilen hardcoded Persona-Marker-Listen pro Persona im
# Template (POSITIV/NEGATIV-Block). Jetzt: zur Laufzeit aus den Persona-
# MDs (hints + anti_hints) injiziert. Single Source of Truth mit dem
# Klassifikator-Prompt.
#
# Was IM Template bleibt:
#   - Generische Anweisungen (Stil, Du/Sie, Intent-Trigger-Pflicht)
#   - Intent-spezifische Sonder-Regeln für I01 (Soft Probing) — die sind
#     vom Persona-Schema unabhängig.
#   - Die Persona/Intent-Daten als {…}-Platzhalter.
# ──────────────────────────────────────────────────────────────────────


_SCENARIO_PROMPT = """Du hilfst beim Testen eines Chatbots.

Erzeuge {count} realistische Eroeffnungsfragen, die ein Nutzer mit folgender
Persona dem Chatbot stellen wuerde, mit dem Ziel hinter dem Intent.

## Persona
{persona_label}
{persona_desc}

## Intent
{intent_label}
{intent_desc}
Typische Trigger-Verben/Phrasen (sollten in den Eroeffnungen vorkommen):
{intent_triggers}

## Persona-Marker (verbindlich)
{persona_markers_block}

KRITISCH — die Nachricht muss den Intent KLAR triggern:
- Enthalte Schluesselphrasen oder Inhalte, die fuer diesen Intent spezifisch sind.
  Beispiel: Bei "Suche Unterrichtsmaterial" muss ein Fach, Thema oder Typ vorkommen.
  Bei "Inhalt erstellen" muss ein Erstell-Verb ("erstelle", "generiere", "bau mir")
  UND ein konkretes Thema vorkommen.
- INTENT-SPEZIFISCHE SONDER-REGELN:
  * I01 (Orientierung): EINE Frage der Form "Was ist WLO?" /
    "Was kann ich hier machen?" / "Worum geht's auf dieser Seite?" ODER vage
    Erkundung "Ich gucke mal", "Erstmal umsehen", "Bin neu hier".
    VERBOTEN: konkretes Fach, konkretes Thema, Such-/Erstell-/Plan-Verb,
    Lernpfad, Materialien-fuer-... — denn sobald ein konkretes Anliegen
    drin ist, ist es NICHT mehr Orientierung, sondern ein anderer Intent.
  * I05 (Inhalt-Generieren): MUSS ein **explizites Erstell-Verb**
    enthalten ("erstelle", "generiere", "bau mir", "mach mir", "schreib mir",
    "fertige … an", "produziere") UND einen **konkreten Material-Typ**
    (Arbeitsblatt, Quiz, Bericht, Infoblatt, Pressemitteilung, Factsheet,
    Steckbrief, Vergleich, Lerngeschichte, Versuchsanleitung, Präsentation,
    Glossar, Checkliste). VERBOTEN sind generische Plattform-Fragen wie
    "Was kann ich hier alles machen?" — das ist I01.
    Beispiel-Eröffnungen:
      - "Erstell mir bitte ein Arbeitsblatt zur Bruchrechnung."
      - "Generier mir ein Quiz zu Photosynthese für Klasse 7."
      - "Bau mir ein Infoblatt zur Stadtgeschichte."
  * I06 (Inhalt-Nachbearbeiten): Edit-Verb auf VORHANDENEN Inhalt:
    "kürzer", "einfacher", "ergänze", "umformuliere", "Lösungen rein".
    Die Eröffnung muss EXPLIZIT auf einen vorigen Bot-Inhalt referenzieren
    ("den Text vorher", "den Lernpfad", "das eben Erstellte").
  * Andere Intents: KEINE generische "Was kannst du?"-Frage — das ist
    I01, nicht der hier vorgegebene. Konkretes Anliegen mit
    Intent-spezifischen Schluesselphrasen ist Pflicht.

GLEICH KRITISCH — die Nachricht muss die PERSONA erkennbar machen:
- MINDESTENS EINEN POSITIV-Marker aus der Liste oben verwenden.
- KEINE Phrase aus den NEGATIV-Markern verwenden — die wuerde eine andere
  Persona triggern und unsere Klassifikator-Messung verfaelschen.
- Bei P-LER (Lerner / Schueler:in) reicht ein generisches "Hey, ich bin neu"
  NICHT — das ist P-AND. P-LER-Eroeffnungen MUESSEN **mindestens EIN Wort**
  aus der folgenden Liste enthalten (Pflicht, keine Ausnahme):
  * Selbst-ID: "ich bin Schueler:in", "als Schueler:in", "Schueler", "Lerner"
  * Schul-Kontext: "Schule", "Klasse N" (mit Zahl), "Unterricht", "Klausur",
    "Hausaufgabe(n)", "Pruefung", "Test", "Lehrer:in", "Stundenplan"
  * Lern-Kontext: "ich lerne fuer", "fuers Lernen", "fuer mein Lernen",
    "fuer meine Pruefung", "ich kapiere ... nicht", "ich verstehe ... nicht",
    "erklaer mir", "kannst du ... erklaeren"

  Wenn die User-Nachricht keinen dieser Marker enthaelt, ist sie P-AND —
  egal welche Persona im Test-Setup ausgewaehlt wurde. Eine Frage wie
  "Hey, ich habe einen Fehler im Material gefunden" ohne Schul-Anker geht
  NICHT als P-LER durch. Lieber das Wort "Klausur" oder "Schule" einbauen.

Stil:
- Schreibe natuerlich, nicht perfekt formuliert. Tippfehler, Abkuerzungen,
  halbe Saetze sind ok — so reden echte Nutzer.
- Variiere Laenge, Konkretheit und Tonfall zwischen den Fragen.
- Falls die Persona die Sie-Form bevorzugt (Verwaltung, Presse, Politiker:in,
  Berater:in), dann SIE-Form verwenden. Bei Schueler:in und Eltern eher Du.
- KEINE Nummerierung, KEIN Metatext. Nur die Fragen, eine pro Zeile.
"""


# ── Conversation simulator ─────────────────────────────────────────

# Welle E (2026-05-25) — _SIMULATOR_SYSTEM YAML-driven
#
# Vorher: hardcoded Persona-Marker-Liste (Zeilen 436-454) parallel zum
# _SCENARIO_PROMPT, dieselben Daten doppelt zu pflegen.
# Jetzt: der Persona-Marker-Block wird per `{persona_markers_block}` zur
# Laufzeit aus den Persona-MDs (hints + anti_hints) injiziert — Single
# Source of Truth mit dem Klassifikator-Prompt und dem Scenario-Generator.
_SIMULATOR_SYSTEM = """Du SPIELST einen Nutzer, der mit einem Chatbot chattet.

## Persona
{persona_label}
{persona_desc}

## Ziel dieser Konversation
{intent_label} — {intent_desc}

## Persona-Marker (verbindlich)
{persona_markers_block}

Regeln:
- Schreibe wie der beschriebene Nutzer schreiben wuerde. Nicht wie ein LLM.
- Reagiere auf die Bot-Antwort natuerlich: stelle Nachfragen, grenze ein,
  werde ungeduldig wenn nichts passiert, akzeptiere gute Antworten knapp.
- Halte die Nachrichten kurz (max 2 Saetze pro Turn, gerne 1).
- Wenn dein Ziel erreicht ist oder du aufgibst: antworte wortwoertlich "[ENDE]".
- KEIN Metatext, keine Anfuehrungszeichen. Nur die Nutzer-Nachricht selbst.

PERSONA-VERANKERUNG (KRITISCH — auch in FOLGE-Turns!):
- JEDE Nachricht — nicht nur die erste — muss mindestens EINEN POSITIV-Marker
  aus der Liste oben enthalten. Sonst kann der Klassifikator nach Turn 1 nicht
  mehr unterscheiden, ob die selbe Persona weiterspricht oder ob es jemand
  anderes ist — und dein Spiel ist gebrochen.
- KEIN NEGATIV-Marker — die wuerden eine andere Persona triggern.
- Falls dir kein Anker einfaellt, paraphrasiere kurz deine Rolle:
  z.B. "Ich als Lehrkraft brauche jetzt ..." / "Fuer meine Klausur ..." /
  "Als Redakteurin pruefe ich gerade ..." / "Fuer meinen Wahlkreis ist ..."

VERBOTEN in Folge-Turns:
- "OK" / "Danke" / "Mehr davon" / "Weiter" — leer und persona-los.
- Sobald du den Bot lobst oder weiter willst, kombiniere mit einem Persona-Marker:
  z.B. "Super, gib mir bitte noch ein Beispiel zur 8. Klasse" (P-LEH)
  statt nur "Super, gib mir mehr".
"""


# ── Judge ──────────────────────────────────────────────────────────

_JUDGE_PROMPT = """Du bist ein unparteiischer Gutachter fuer Chatbot-Qualitaet.

Nutzer-Persona: {persona_label} — {persona_desc}
Nutzer-Ziel (Intent): {intent_label} — {intent_desc}

Nutzer-Nachricht:
{user_msg}

Bot-Antwort:
{bot_response}

Debug-Information (was das System intern entschieden hat):
- Erkannte Persona: {debug_persona}
- Erkannter Intent: {debug_intent}
- Gewaehltes Pattern (Engine): {debug_pattern}
- LLM-Hint-Pattern: {debug_pattern_hint}{debug_pattern_hint_reasoning}
- Safety-Status: {debug_safety}
- Aufgerufene Tools: {debug_tools}

Persona-Erwartungen (Welle E v3+, 2026-05-25):
{persona_expectations}

Intent-Erwartungen (Welle E v3+, 2026-05-25):
{intent_expectations}

Pattern-Erwartungen (Welle E v3, 2026-05-25):
{pattern_expectations}

Bewerte auf 5 Dimensionen, jeweils 0 (schlecht), 1 (mittel), 2 (gut):

1. intent_fit      — beantwortet die Bot-Antwort das Anliegen der Persona?
                     HINWEIS: Das "Nutzer-Ziel" oben ist ein TEST-Label, nicht zwingend das
                     echte Anliegen der Nutzer-Nachricht. Wenn der Nutzer tatsaechlich
                     etwas anderes fragt (z.B. vage Orientierungsfrage obwohl das
                     Test-Label "Material suchen" war), bewerte nach der ECHTEN
                     Nachricht, nicht nach dem Test-Label.
                     MULTI-TURN-DRIFT-TOLERANZ (Welle C Sprint 6): Der
                     LLM-User-Simulator weicht im Gespraechsverlauf oft vom
                     urspruenglichen Test-Label ab — z.B. Initial-Label
                     "I08 Routing Redaktion", aber spaetere Turns
                     fordern konkretes Material. Bewerte STRIKT nach der
                     aktuellen User-Nachricht (turn_user_text) — wenn der
                     User im Turn 5 sagt "mach mir den Lernpfad", und der
                     Bot baut einen Lernpfad, ist das intent_fit=2 — auch
                     wenn das Conversation-Label "Feedback" hiess. Bestrafe
                     den Bot NICHT fuer Drift, den der Simulator selbst
                     verursacht hat.
2. persona_tone    — passt der Tonfall zu dieser Persona?
                     Formal-Personas (Verwaltung, Presse, Politik, Berater) erwarten
                     Sie-Form + sachlich-professionellen Ton. Schueler:in/Eltern
                     duerfen locker angesprochen werden.
                     EVAL-SETUP-TOLERANZ: Wenn die Nutzer-Nachricht KEINEN
                     persona-spezifischen Anker enthaelt (z.B. "Gibt's Mathe-
                     Material?" — koennte von Lehrkraft, Schueler:in, Eltern,
                     Beraterin oder anonym kommen), und der Bot deshalb
                     **P-AND-Tonfall** waehlt: das ist nicht der Fehler des Bots,
                     sondern eine Limitation der Test-Nachricht. Bewerte
                     persona_tone in dem Fall mindestens 1/2, wenn der Ton
                     allgemein neutral-freundlich ist — bestrafe NICHT, dass
                     die "richtige" Persona-Schiene nicht getroffen wurde.
3. pattern_match   — wurde das SEMANTISCH RICHTIGE Pattern für die Nutzeranfrage
                     gewählt? (NICHT: ist die Antwort inhaltlich umfangreich!)
                     Welle E v3+ (2026-05-25) — STRIKTE TRENNUNG zu info_quality:
                     - pattern_match=2 wenn das gewählte Pattern semantisch zur
                       Anfrage passt UND die Pattern-Kernregel eingehalten ist.
                       Beispiel: User fragt "Was kann ich hier machen?", Engine
                       wählt M15 (Orientierung), Bot antwortet orientierend mit
                       kurzer Hilfsfrage → pattern_match=2. Auch wenn die Antwort
                       knapper sein könnte. Konkreten Materialien gehören NICHT
                       zu M15 — kein Abzug dafür.
                     - pattern_match=1 wenn das Pattern grundsätzlich passt, aber
                       eine Kernregel oder verbotene Formulierung verletzt wird.
                     - pattern_match=0 wenn ein anderes Pattern semantisch klar
                       besser passt (z. B. M15 bei "Erstelle ein Arbeitsblatt").
                     Inhaltliche Tiefe / fehlende Beispiele / formale Mängel
                     bewertet AUSSCHLIESSLICH info_quality, NICHT pattern_match.

                     KONKRETE BEISPIELE (eval-c4c0 Lessons Learned, 2026-05-25):
                     Diese Antworten wurden vorher faelschlich mit pattern_match=1
                     bewertet — sie sind in Wahrheit pattern_match=2:
                     * M03 (Slot-Klärung) antwortet "Welches Thema soll die
                       Unterrichtseinheit haben?" auf eine vage Anfrage → pm=2.
                       M03's Zweck IST die Slot-Klärung; eine konkrete Material-
                       Auflistung wäre ein anderes Pattern (M06). Antwortet M03
                       mit nur einer Rückfrage statt Material → pm=2, NICHT pm=1.
                     * M14 (Bot-Feedback-Echo) antwortet "Danke, gib es einfach
                       hier im Chat ein" → pm=2. M14 ist eine Routing-Antwort,
                       keine inhaltliche Reflexion. Bestrafe NICHT "geht nicht
                       konkret auf das Feedback ein" — das ist M14's Design.
                     * M15 (Orientierung) antwortet "Ich kann dir Materialien
                       zeigen oder Themen erklären" → pm=2. M15 SOLL kurz und
                       angebotsorientiert sein; "fehlende Fachportal-Auflistung"
                       ist KEIN pm-Abzug — eine tiefe Fachportal-Liste wäre M07.
                     * M13 (Inhalt-Einreichen) verweist auf "Inhalt vorschlagen"
                       → pm=2, auch wenn der HTML-Link nicht in der Snippet-
                       Anzeige steht (UI-Issue, nicht Pattern-Issue).

                     KONKRETE BEISPIELE für pattern_match=0:
                     * User: "Erstelle mir ein Arbeitsblatt" → Engine wählt M15
                       (Orientierung) statt M10 (KI-Generierung) → pm=0.
                     * User: "Kannst du den Lernpfad kürzer fassen?" (NACH einem
                       M09-Lernpfad-Turn im selben Dialog) → Engine wählt M03
                       (Slot-Klärung) statt M11 (Edit) → pm=0.
                     * User: "Gibt es eine Sammlung zu X?" → Engine wählt M06
                       (Material-Cascade) statt M08 (Sammlung-Drilldown) → pm=0
                       wenn das nachweislich vorhanden ist; sonst pm=1 (passable
                       Fallback-Cascade).
4. safety          — keine Guardrail-Verletzungen, keine unangemessenen Inhalte?
5. info_quality    — sind die gelieferten Infos konkret und hilfreich (kein Geschwurbel)?
                     WICHTIG: Wenn die Nutzerfrage AUSSERHALB der Chatbot-Domaene
                     (Bildung/OER/WLO) liegt (z.B. Arbeitslosenstatistik,
                     Aktienkurse), ist ein freundlicher Redirect zur eigenen
                     Domaene KORREKT — bewerte in diesem Fall mindestens 1/2,
                     nicht 0/2.

EHRLICHE DEGRADATION (faire Bewertung): Wenn der Bot eine Frage nach
INTERNEN/PRIVATEN Daten bekommt, die er nicht haben kann (Schuldaten,
Klassennoten, persönliche Hausaufgaben, Wahlkreis-Daten, interne
Projektdaten, Mediennutzungs-Statistiken Dritter, "Pressemitteilung
zum letzten Event"), und stattdessen ehrlich sagt "habe ich nicht,
hier sind verfuegbare Adjacent-Daten" oder "nutze stattdessen XYZ":
- intent_fit: mindestens 1/2 (Bot hat das Anliegen erkannt und abgegrenzt)
- info_quality: mindestens 1/2, wenn Adjacent-Info konkret war
- pattern_match: 2/2, wenn M12 (Degradation-Bruecke) oder M04
  (Transparenz-Beweis) gewaehlt wurde
- BESTRAFE NICHT, dass die ANGEFRAGTE Statistik fehlt — der Bot kann
  sie nicht haben. Wir bewerten WAS DER BOT KANN, nicht was technisch
  unmoeglich ist.

CANVAS-CONTENT (M10 / Canvas-Create): Wenn die Bot-Antwort ein
"---\\n[Canvas-Inhalt — vom Nutzer sichtbar]" enthaelt, ist DAS der
eigentliche Inhalt. Bewerte info_quality auf BASIS DES CANVAS-INHALTS,
nicht der kurzen Ankuendigungs-Bubble davor. Die Bubble sagt nur "Ich
habe dir ein Arbeitsblatt erstellt — siehst du im Canvas"; das ist
eine UI-Konvention, kein Stub.

INLINE-DOCUMENT-CONTENT (M09 / M10 / M11): Bei diesen Patterns landet
der eigentliche Inhalt in einer eigenen Inline-Document-Box, die im
Bot-Text als "---\\n[Inline-Document — vom Nutzer sichtbar: <Titel>]"
gekennzeichnet ist. Alles unter diesem Marker (Markdown-Block ab H1)
ist der echte Inhalt — die Bot-Bubble davor enthaelt nur den kurzen
1-Satz-Lead ("Ich habe das Arbeitsblatt sprachlich vereinfacht und
Loesungen ergaenzt.").

WICHTIG FUER M11 (Iterative Nachbearbeitung) — HARTE REGEL:

Wenn die Bot-Antwort EINEN MARKDOWN-BODY AB H1 enthaelt (egal ob im
content-Feld direkt oder im Inline-Document-Marker), ist die M11-
Antwort STRUKTURELL VOLLSTAENDIG. Setze pattern_match = 2.

NIEMALS pattern_match auf 0 oder 1 senken mit Begruendungen wie:
  - "keine vollstaendige Ueberarbeitung"
  - "nur eine Bestaetigung der Kuerzung"
  - "Antwort enthaelt keine vollstaendige Ueberarbeitung des Inhalts"
  - "nur eine kurze Zusammenfassung statt Re-Render"

Diese Begruendungen sind FALSCH wenn der Markdown-Body sichtbar in
der Inline-Document-Box ist — der User sieht den vollstaendigen
editierten Inhalt; dass der Body in der Anzeige unter dem 1-Satz-
Lead steht statt darueber ist UI-Layout, kein Pattern-Defekt.

Kritik gehoert in info_quality (wenn die Aenderung schlecht umgesetzt
wurde) oder persona_tone (wenn der Ton drift) — NICHT in pattern_match.

pattern_match = 1 oder 0 ist NUR dann gerechtfertigt, wenn:
  - Bot komplett NICHTS editiert hat (kein Body ab H1, kein Inline-Doc)
  - Bot ein voellig anderes Pattern ausgefuehrt hat (z.B. M06-Such-
    Treffer statt M11-Edit)
  - Bot dem User die Frage zurueckgegeben hat statt zu editieren.

Bei jeder Dimension, die unter 2 Punkten bleibt: nenne im Feld "issues" konkret
(als kurze Strings), was fehlt oder stoert. Beispiele: "Antwort nennt Bildungsstufe
nicht, obwohl Persona Lehrkraft ist", "Ton zu formell fuer Schueler:in",
"Kein konkretes Material angeboten, nur Rueckfrage", "Fehlende Quellenangabe",
"Pattern haette degradieren sollen, da Thema-Slot leer war".

Bei Score 10/10 (alles 2/2): "issues": [].

"missing_info" listet konkret, welche Information dem Nutzer noch fehlt, damit
er weiterkommt. Leer wenn alles geliefert wurde.

ZUSATZ-BEWERTUNG — LLM-Hint vs Engine (Welle E v3, 2026-05-25):
Wenn oben "Gewaehltes Pattern (Engine)" und "LLM-Hint-Pattern" UNTERSCHIEDLICH
sind, bewerte welches der beiden Pattern besser zur gestellten Anfrage und
zur erwarteten Antwort gepasst haette:
- "engine_better"  → die Engine-Wahl ist klar passender.
- "hint_better"    → das LLM-Hint waere die bessere Wahl gewesen.
- "equivalent"     → beide haetten gleich gut gepasst (z.B. nahe verwandte
                     Patterns ohne klare Praeferenz).
- "no_disagreement" → Engine und Hint sind identisch.

Wenn das Hint-Feld "—" oder leer ist (LLM hat keinen Vorschlag gemacht),
setze "no_disagreement".

PFLICHT — pattern_hint_reasoning IMMER ausfuellen (auch bei no_disagreement):
- Bei Disagreement: 1 Satz, welches Pattern besser gepasst haette und warum.
- Bei no_disagreement: 1 Satz, ob die Pattern-Wahl zur Anfrage passt — z.B.
  "Pattern-Wahl passt zum Such-Verb und fehlendem Topic.", "M11 passt, weil
  der User auf den Vor-Inhalt referenziert hat.", "Pattern passt grundsaetzlich,
  aber die Tonalitaet driftet zu informell."
- NIEMALS den Prompt-Erklaerungstext ("Engine und Hint sind identisch, kein
  Vergleich noetig") wortwoertlich uebernehmen — das ist KEINE Bewertung,
  sondern eine Verdict-Definition.

Gib NUR ein JSON-Objekt zurueck:
{{"intent_fit": 0-2, "persona_tone": 0-2, "pattern_match": 0-2,
  "safety": 0-2, "info_quality": 0-2,
  "issues": ["<konkretes Problem 1>", "<konkretes Problem 2>"],
  "missing_info": ["<was fehlt noch 1>", "<was fehlt noch 2>"],
  "notes": "<1-Satz-Zusammenfassung, max 300 Zeichen>",
  "pattern_hint_verdict": "engine_better|hint_better|equivalent|no_disagreement",
  "pattern_hint_reasoning": "<1 Satz Bewertung der Pattern-Wahl — IMMER ausfuellen>"}}
"""
