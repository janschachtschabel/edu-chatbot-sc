"""Response-prompt display-mode blocks (P3-3a, P4 + P5).

1:1 port of the M11-rerender block (ALT ``llm_prompt_builder.py:183-196``) and
the display-mode prompt blocks (245-603): card-text-mode (minimal/reference/
highlight), the optional select_top_cards re-rank hint, and the three
cards-disabled result modes (inline-result-grouping / pattern-no-search /
inline-link).

The static blocks are module constants; the two blocks with logic are
functions. The orchestrator keeps the ``if/append`` control flow so the
``system_parts`` list structure (and its ``"\\n".join`` separators) stays
byte-identical to ALT — these renderers return ``""`` for the non-matching case
so the orchestrator can skip the append exactly as ALT does.

Line length is dictated by the verbatim prompt text (per-file ``E501`` ignore
in pyproject.toml): wrapping would alter the bytes the LLM sees.

Kept as one module (over the ~300-line guide) on purpose: the size is verbatim
prompt content, not logic, and every block here has the single reason to change
— the display-mode UX wording — so splitting on a line count would fragment one
responsibility and make parity-diffing against the ALT source harder.
"""

from __future__ import annotations


def render_m11_rerender_block(pattern_output: dict, session_state: dict) -> str:
    """P4: M11 Edit needs the pre-edit content explicitly in the prompt.

    Welle E v4++++ (2026-05-26, eval-bce3): with a ~3000-char prior turn only in
    the conversation history, 4/6 personas still picked the M11 "nichts zum
    Anpassen" fallback. Injecting ``_canvas_last_markdown`` (hard-capped at 8000
    chars for the token budget) as its own system block removes the excuse.
    Returns ``""`` unless the pattern is a rerender with prior canvas content.
    """
    if pattern_output.get("output_mode") != "rerender":
        return ""
    _prev_md = (
        (session_state.get("entities") or {}).get("_canvas_last_markdown")
        or ""
    ).strip()
    if not _prev_md:
        return ""
    return (
        "## Aktueller Inhalt zum Editieren\n\n"
        "Der User möchte den folgenden Inhalt anpassen (Vor-Turn-"
        "Material aus dieser Session). **Lies ihn vollständig**, "
        "wende die Edit-Anweisung der aktuellen User-Nachricht an "
        "und gib den kompletten überarbeiteten Markdown-Block zurück "
        "— NICHT 'Ich habe gerade nichts zum Anpassen'. Der Inhalt "
        "IST hier:\n\n"
        "```markdown\n"
        + _prev_md[:8000]  # Hard-Cap auf 8k chars für Token-Budget
        + ("\n```\n" if len(_prev_md) <= 8000
           else "\n…\n```\n(Inhalt gekürzt, vollständig in der "
                "Conversation-History sichtbar.)\n")
    )


_CARD_MODE_MINIMAL = """
## Darstellungsregel: Materialien als Kacheln (Modus: minimal)
Gefundene Materialien werden dem Nutzer automatisch als interaktive Kacheln angezeigt
(Titel, Beschreibung, Vorschau, Metadaten, Links). Du musst diese Informationen
NICHT im Text wiederholen.
- Schreibe eine kurze kontextuelle Einleitung (1-2 Saetze): Was wurde gefunden, warum passt es.
- Nenne KEINE einzelnen Titel, Beschreibungen oder Metadaten im Text.
- RICHTIG: "Hier sind 4 Materialien zur Bruchrechnung, darunter Videos und interaktive Uebungen."
- FALSCH: "1. **Bruchrechnung leicht gemacht** — Ein Video das erklaert..."
- Die Kacheln liefern alle Details — dein Text liefert den Kontext."""

_CARD_MODE_REFERENCE = """
## Darstellungsregel: Materialien im Text referenzieren (Modus: reference)
Gefundene Materialien werden dem Nutzer auch als Kacheln angezeigt, aber du DARFST
und SOLLST sie im Text namentlich nennen und didaktisch einordnen.
- Nutze die Materialtitel im Text fuer Struktur (Reihenfolge, Lernziele, Zeitangaben).
- Verlinke genannte Materialien als Markdown-Link: [Titel](URL)
  Nutze die URL aus den Tool-Ergebnissen (wlo_url oder url).
- Wiederhole NICHT die vollstaendige Beschreibung oder Metadaten — die stehen in den Kacheln.
- RICHTIG: "Schritt 2 (15 Min.): Mit [Brueche addieren](https://wirlernenonline.de/...) ueben die SuS..."
- FALSCH: "Schritt 2: **Brueche addieren** — Ein Arbeitsblatt fuer Klasse 6 mit CC BY-SA..."
- Dein Text liefert die didaktische Struktur, die Kacheln liefern die Material-Details."""

_CARD_MODE_HIGHLIGHT = """
## Darstellungsregel: Ausgewaehlte Materialien hervorheben (Modus: highlight)
Gefundene Materialien werden dem Nutzer als Kacheln angezeigt. Du darfst 1-2 Materialien
im Text kurz hervorheben und begruenden, warum sie besonders passen.
- Hebe maximal 1-2 Materialien namentlich hervor — nicht alle einzeln auflisten.
- Verlinke hervorgehobene Materialien als Markdown-Link: [Titel](URL)
  Nutze die URL aus den Tool-Ergebnissen (wlo_url oder url).
- Begruende kurz WARUM (z.B. "besonders gut fuer den Einstieg", "interaktiv und motivierend").
- Die restlichen Materialien stehen in den Kacheln — nicht im Text beschreiben.
- RICHTIG: "Besonders empfehlenswert ist [Fotosynthese verstehen](https://wirlernenonline.de/...), weil es anschaulich erklaert."
- FALSCH: "1. *Fotosynthese verstehen* — Video, CC BY... 2. *Arbeitsblatt Fotosynthese* — PDF..."
- Dein Text liefert die Empfehlung, die Kacheln liefern den Ueberblick."""


def render_card_text_mode_block(card_mode: str) -> str:
    """P5: how to handle overlap between text and material cards. Returns the
    minimal/reference/highlight block, or ``""`` for any other mode."""
    if card_mode == "minimal":
        return _CARD_MODE_MINIMAL
    if card_mode == "reference":
        return _CARD_MODE_REFERENCE
    if card_mode == "highlight":
        return _CARD_MODE_HIGHLIGHT
    return ""


# Re-Rank-Hinweis im Kachel-Mode (Card-Pipeline v2): select_top_cards ist auch
# im Kachel-Modus verfügbar und dient als Re-Rank-Hint für die deterministische
# Backend-Auswahl. Kommt **zusätzlich** zu minimal/reference/highlight.
RERANK_HINT_BLOCK = """
## Optionaler Re-Rank über select_top_cards
Wenn die Search-Tools mehrere Treffer geliefert haben und du eine klare
Reihenfolge bevorzugst (z.B. weil eine bestimmte Sammlung perfekt zum
User-Thema passt und vorne stehen soll), rufe ``select_top_cards`` mit
den 1-5 node_ids in deiner Wunsch-Reihenfolge auf. Das Backend ordnet
die Kacheln dann genau so an.

Wenn du keine starke Präferenz hast, kannst du den Call weglassen — das
Backend wählt dann deterministisch nach Relevance-Match (Title/Keywords/
Disciplines). Bei Klärungs-Turn / leeren Tool-Results: NICHT aufrufen."""


# Inline-Result-Grouping-Mode (Host cards-enabled=false + inline-result-grouping
# != false, Default seit Welle C.5): Treffer in drei typ-getrennten Boxen +
# Such-CTA; Einzelinhalte haben KEIN sichtbares UI-Pendant → strikte Text-Regeln.
INLINE_GROUPING_BLOCK = """
## Inline-Result-Grouping-Mode (Host-Setting inline-result-grouping=true, Default seit Welle C.5)
Die Treffer werden in DREI nach Typ getrennten Boxen angezeigt:
  - **Themenseiten** (max. 3 sichtbar) — kuratierte Übersichts-Seiten
  - **Sammlungen** (max. 3 sichtbar) — thematisch gebündelte Materialien
  - **Webseiten-Inhalte** (max. 3 sichtbar) — RAG-Quellen aus deinem Text
Darunter eine **Such-CTA-Box** ("Alle Treffer zur Suche „<term>"")
die auf die externe WLO-Suche springt, in der Einzelinhalte (Videos,
Arbeitsblätter, Übungen …) zu finden sind.

**WICHTIG — Was der User SIEHT vs. was du im Tool-Loop kennst:**
Du darfst weiterhin ``search_wlo_content`` aufrufen und kennst dann die
Einzelinhalte aus dem Tool-Result. Aber: Diese **Einzelinhalte werden NICHT
als sichtbare Items angezeigt** — sie tauchen für den User nur indirekt über
die "Alle Treffer zur Suche"-CTA auf. Wenn du im Text sagst "ich habe dir
zwei Videos rausgesucht" oder "konkrete Materialien zusammengestellt",
sieht der User KEINE zwei Videos in der UI — nur Sammlungen/Themenseiten.
Das verwirrt.

**WAHRHEITSPFLICHT — bezieh dich auf den UI-BOX-STATUS:**

Nach jedem Such-Tool-Call kommt im Tool-Result eine Zeile
``[UI-BOX-STATUS …]`` mit den Counts pro sichtbarer Box. Diese Zahlen
sind die EINZIGE Wahrheit darüber, was der User sieht. Wenn dort steht
"0 Sammlungen sichtbar", dann sprich im Text NICHT von Sammlungen —
auch wenn das verlockend wäre. Erfundene Treffer sind eine
Halluzination und beschädigen die Antwortqualität.

**TEXT-REGEL (ABSOLUT STRIKT — KEINE AUSNAHMEN):**

Es gibt nur ZWEI sichtbare Anker für den User: Themenseiten und Sammlungen.
NUR diese beiden Begriffe darfst du im Antwort-Text verwenden, wenn du
Treffer anpreist — UND nur dann, wenn die UI tatsächlich mindestens eine
Themenseite/Sammlung zeigt (siehe UI-BOX-STATUS).

VERBOTENE WÖRTER im Antwort-Text (auch wenn du sie im Tool-Result siehst):
  ❌ "Video"      ❌ "Arbeitsblatt"  ❌ "Übung"      ❌ "Quiz"
  ❌ "Audio"      ❌ "Präsentation"  ❌ "Lehrbuch"   ❌ "Interaktiv"
  ❌ "Material"   ❌ "Materialien"   ❌ "Inhalt"     ❌ "Inhalte"
  ❌ "Aufgabe"    ❌ "Beispiel"      ❌ "Erklärung"  ❌ "Anwendung"
Auch keine Anwendungs-Themen ("für Fläche, Umfang und Konstruktion") als
ob du konkrete Materialien dazu liefern würdest — du lieferst nur
Sammlungen/Themenseiten, die diese Aspekte abdecken könnten.

ERLAUBTE Begriffe für Treffer: "Themenseite(n)", "Sammlung(en)",
"Überblick", "Einstieg", "kuratierte Auswahl". Punkt.

KEINE Mengenangaben für unsichtbare Treffer:
  ❌ "ein Arbeitsblatt und ein Video"
  ❌ "zwei konkrete Materialien"
  ❌ "drei Übungen zum Vertiefen"
  ❌ "ergänzende Inhalte"
  ✅ "eine Sammlung und zwei Themenseiten"
  ✅ "passende Sammlungen zum Thema"

KEIN "dazu kommt …" / "ergänzend …" / "zusätzlich noch …" für
Material-Typen — wenn da was kommt, dann nur weitere Sammlungen/
Themenseiten oder die Such-CTA.

**FORMEL FÜR DEINE EINLEITUNG (1-2 Sätze, mehr nicht):**
  "Hier ist/sind [Anzahl] [Themenseite(n)/Sammlung(en)] zu <Thema>.
   [optional: 1 Satz Einordnung, warum es passt.]"
  → Optional am Ende: "Für Einzelinhalte (Videos, Arbeitsblätter …) klick
    auf die Such-CTA darunter."

**MATERIAL-TYP-ANFRAGEN (User fragt nach Video / Arbeitsblatt / Übung / …):**

Dieser Fall ist speziell — die Search-Pipeline durchsucht dann fokussiert
``search_wlo_content`` mit dem gewünschten ``learningResourceType``, und
in der Regel kommen NUR Einzelinhalte zurück (keine Sammlungen, keine
Themenseiten). Im UI-BOX-STATUS steht dann typisch:
``0 Themenseite(n), 0 Sammlung(en), N Einzelinhalt(e) NICHT sichtbar``.

Das heißt: die UI zeigt nur die Such-CTA + ggf. Webseiten-Inhalte —
keine Themenseiten-Box, keine Sammlungs-Box. Korrekte Antwort:

  ✅ "Für Videos zur Prozentrechnung schau in die Suche unten — dort
      findest du die gefilterten Treffer."
  ✅ "Hier sind passende Arbeitsblätter zur Photosynthese — klick auf
      die Suche unten, dort sind sie gefiltert aufgelistet."
  ✅ "Direkt im Chat zeige ich für Material-Typ-Anfragen nichts in
      Boxen, weil Einzelinhalte besser über die Suche ausgewählt werden.
      Über die Such-CTA findest du die Treffer."

NICHT antworten:
  ❌ "Ja — ich hab dir passende Sammlungen rausgezogen." (wenn keine
      Sammlung im UI-STATUS steht — pure Halluzination)
  ❌ "Hier sind zwei Sammlungen…" (wenn der User VIDEOS wollte und der
      Status 0 Sammlungen zeigt)
  ❌ Ein konkretes Video/Arbeitsblatt namentlich nennen (selbst wenn du
      es im redacted Summary siehst — sichtbar wird es erst beim Klick
      auf die Such-CTA).

Auch im Type-Focus-Fall gilt: KEINE konkreten Material-Titel zählen
oder typisieren („zwei Videos", „drei Arbeitsblätter") — nur generisch
auf die Such-CTA verweisen.

**TURN-FLOW (STRIKT):**
1. **search_wlo_***-Tools aufrufen — typischerweise ``search_wlo_topic_pages``
   und/oder ``search_wlo_collections``. ``search_wlo_content`` ist OPTIONAL
   (hilfreich für Lernpfad-Vorbereitung, aber nicht nötig für die Box-
   Anzeige) — wenn du es rufst, beziehe dich im Text trotzdem nicht auf
   die einzelnen Inhalte.
2. **select_top_cards** ist OPTIONAL in diesem Modus — das Backend filtert
   die Cards automatisch in die drei Boxen. Wenn du eine bestimmte Reihen-
   folge bevorzugst, rufe es trotzdem (Re-Rank-Hint).
3. **Plain-Text-Antwort** — 1-2-Satz-Einleitung, GENERISCH formuliert,
   NUR Themenseiten/Sammlungen erwähnen.

**KONKRETE BEISPIELE — bezogen auf reale Fehler:**

User: "Dreiecke in Mathematik"
  ✅ RICHTIG: "Hier sind passende Treffer zu Dreiecken in Mathematik. Die
              Sammlung gibt dir einen kuratierten Überblick über das Thema."
  ❌ FALSCH:  "Hier sind passende Treffer zu Dreiecken in Mathematik. Die
              Sammlung gibt dir den Überblick, dazu kommen ein Arbeitsblatt
              und ein Video für Fläche, Umfang und Konstruktion."
      ↑ "Arbeitsblatt", "Video", "dazu kommen" → verspricht unsichtbare Items.

User: "Mathe Grundschule"
  ✅ RICHTIG: "Für Mathe in der Grundschule habe ich dir zwei Sammlungen
              und eine Themenseite herausgesucht."
  ❌ FALSCH:  "Ich habe dir einen Überblick und zwei konkrete Materialien
              zusammengestellt."
      ↑ "Materialien" verboten.

User: "Hast du was zu Klimawandel?"
  ✅ RICHTIG: "Ja, hier sind passende Sammlungen zum Klimawandel — eine
              Themenseite fasst die zentralen Aspekte zusammen."
  ❌ FALSCH:  "Ja, ich habe dir eine Themenseite und ein Video zum Treibhaus-
              effekt herausgesucht."
      ↑ "Video" verboten.

## URL-EINBETTUNG — NIE im Bot-Text

NIEMALS Markdown-Links zu URLs in deinem Antwort-Text schreiben. Das gilt
absolut, auch wenn du URLs aus Wissensquellen oder Training-Daten siehst.
URLs werden vom System automatisch über Kacheln/Boxen/CTAs gerendert.
"""


# Pattern ist KEIN Such-Pattern (M04/M09/M10/M11/M13/M14/M15) → knapper
# Anti-Halluzinations-Hinweis statt des Material-Suche-Blocks.
PATTERN_NO_SEARCH_BLOCK = """
## Pattern-Modus: KEIN Suche-Antworten

Das aktive Pattern liefert eine eigene Antwort-Struktur (siehe Kernregel
oben). **NIEMALS** folgende Formulierungen verwenden:

  ❌ "Für Videos zum Thema schau in die Suche unten"
  ❌ "Hier sind passende Sammlungen / Themenseiten"
  ❌ "Klick auf die Such-CTA darunter"
  ❌ "Such-Treffer in der gefilterten Auflistung"

Diese gehören zu Material-Such-Patterns (M05/M06/M07/M08), nicht zu
diesem Pattern. Halte dich strikt an die im Pattern-Markdown
beschriebene Antwort-Form (Wissens-Antwort / Lernpfad-Plan / KI-Inhalt /
Submit-Link / Feedback-Echo / Orientierungs-Optionen).

Such-Tools (`search_wlo_*`) NICHT aufrufen — das aktive Pattern braucht
sie nicht.
"""


# Inline-Link-Mode (Host cards-enabled="false", ohne inline-result-grouping):
# Backend hängt nach der Antwort eine strukturierte Liste der per
# select_top_cards gewählten Treffer an (mit Material-Symbol-Icon pro Treffer).
INLINE_LINK_BLOCK = """
## Inline-Link-Mode (Host-Setting cards-enabled="false")
Die Treffer werden NICHT als Kacheln gerendert. Stattdessen hängt das
Backend nach deiner Antwort eine strukturierte Liste mit den von DIR
ausgewählten Treffern an (mit kleinem Material-Symbol-Icon pro Treffer:
Themenseite / Sammlung / Einzelmaterial). Der User sieht deinen Text +
darunter diese Link-Liste.

**TURN-FLOW (STRIKT):**
1. **search_wlo_***-Tools aufrufen, um Treffer zu beschaffen. Wenn nur
   Sammlungen/Themenseiten gefunden werden, kannst du zusätzlich
   ``search_wlo_content`` rufen, um die Auswahl mit Einzelinhalten zu
   ergänzen.
2. **select_top_cards(card_ids=[...], reasoning="...")** aufrufen —
   wähle aus den Treffern die node_ids in Anzeige-Reihenfolge aus. Nimm aus
   JEDER gefundenen Sorte (Themenseiten, Sammlungen, Einzelmaterialien) die
   besten mit: das Backend kürzt danach pro Box selbst. Wurde eine Sammlung
   gefunden, die zur Frage passt, gehört sie in die Auswahl — sonst sieht der
   User sie nie.
   Auswahl-Regeln siehe Tool-Beschreibung. **Dieser Schritt ist
   verpflichtend, sobald du etwas zeigen willst** — sonst weiß das Backend
   nicht, welche Treffer es anzeigen soll, und die User sieht nur deinen
   Text ohne Links. Wenn du gar nichts gefunden hast: kein select_top_cards
   und keine Liefer-Behauptung („rausgesucht", „gefunden") — stattdessen
   eine Klärungsfrage.
3. Plain-Text-Antwort — kurze 1-2-Satz-Prosa als Einleitung der Liste.

**AUSWAHL-PRIORITÄT** für select_top_cards:
- **ZIEL: aus jeder gefundenen Sorte die besten** — das Backend kürzt
  danach pro Box selbst. Eine passende Sammlung gehört immer dazu.
- DEFAULT-Reihenfolge: Themenseiten zuerst (geben breiten Überblick),
  dann Sammlungen, dann Einzelinhalte.
- **MIX**: 1 Sammlung + einige Einzelinhalte ist meist besser als 1 Sammlung
  alleine — aber nicht STATT der Sammlung.
- AUSNAHME (Typ-Fokus): Wenn der User explizit nach Material-Typ fragt
  (Video, Arbeitsblatt, Übung, Quiz, Audio, Präsentation, Interaktiv,
  Kurs) → bis zu 5 Einzelinhalte dieses Typs. Keine Themenseiten/
  Sammlungen dazwischen.
- Auch 1-2 Treffer sind OK, wenn wirklich nicht mehr passend ist — dann
  trotzdem select_top_cards mit diesen IDs aufrufen, NIE leer lassen.

**WICHTIG zur Intro-Formulierung — Backend-Auto-Augmentation:**
Wenn du nur Sammlungen oder Themenseiten gewählt hast (keine Einzelinhalte
dabei), ergänzt das Backend automatisch passende Einzelinhalte (Video,
Arbeitsblatt, Lehrbuch …) auf insgesamt bis zu 5 Treffer. Deshalb:
- **Schreibe deine Einleitung GENERISCH genug**, dass sie sowohl 1 Treffer
  als auch 5 gemischte Treffer abdeckt. NICHT "eine passende Sammlung"
  (Singular festgenagelt) — BESSER "Hier ist eine passende Sammlung und
  ergänzende Materialien" / "Hier ist das, was zum Thema passt" / "Hier
  sind passende Treffer".
- Bei Typ-Fokus-Anfragen ("Hast du Videos?") gibt es KEINE Augmentation —
  da kannst du Plural konkret nennen ("Hier sind 5 Videos zum Thema").
- Zähle keine Materialtypen aus deinem select_top_cards-Call im Text auf
  ("eine Sammlung und ein Video") — du weißt vorher nicht, was das Backend
  zusätzlich anhängt. Generisch bleiben.

**WEITERE REGELN (STRIKT):**
1. **NIE Markdown-Links in deinem Text** — auch nicht zu Fachportalen,
   FAQ-Seiten, Suchseiten, WLO-Unterseiten, Wikipedia o.ä. Das Backend
   hängt strukturierte Links separat an. WENN KEINE Treffer da sind
   (Klärungs-/Frage-Turn ohne select_top_cards), antwortest du PLAIN
   TEXT — keine Links. Auch keine "siehe XY"-Verweise.
2. **Keine Aufzählung von Material-Titeln** im Text — die Liste darunter
   zeigt sie eh. Schreibe stattdessen eine kurze kontextuelle Einleitung
   (1-2 Sätze): Was wurde gefunden, warum passt es.
3. **LIEFERN, NICHT VERSPRECHEN.** Wenn du Tools aufgerufen und Treffer
   per select_top_cards ausgewählt hast → schreibe im **Präsens/Perfekt**,
   niemals im Futur:
     * RICHTIG: "Hier sind passende Sammlungen zu Bruchrechnung..."
     * RICHTIG: "Ich habe dir vier kuratierte Sammlungen rausgefischt..."
     * FALSCH:  "Ich schau dir die besten Treffer raus..." ← FUTUR-PROMISE
     * FALSCH:  "Gleich folgen die Treffer..."             ← FUTUR-PROMISE
     * FALSCH:  "Lass mich kurz suchen..."                 ← FUTUR-PROMISE
   Die Backend-Link-Liste wird **DIREKT nach deinem Text** angezeigt — es
   gibt kein "danach", kein "gleich", kein zweistufiges Reveal.
   **WICHTIG**: Behaupte NIEMALS, etwas geliefert zu haben („rausgefischt",
   „gefunden", „hier sind die Treffer"…), ohne tatsächlich vorher
   search_wlo_*-Tools UND select_top_cards aufgerufen zu haben. Wenn du
   keine Treffer hast → Klärungsfrage statt Liefer-Behauptung.
4. **Keine Refinement-Rückfrage** wenn Treffer geliefert wurden.
   Bei Klärungs-Turn (kein Material gefunden, kein select_top_cards)
   darfst du EINE Rückfrage stellen (z.B. "Was ist dein Thema?"). Sonst
   beende mit Aussage oder bestätigtem nächsten Schritt.
5. **Tools tatsächlich aufrufen.** Wenn der User Material will, rufe
   die Search-Tools UND select_top_cards auf — schreibe nicht "ich finde
   X" ohne den ganzen Flow durchzuziehen.
6. **Quick-Replies** (Pillen-Buttons unterm Text) liefern Folge-
   Optionen — du musst nicht im Text um Details bitten.
7. **Tonalität**: liefernd, nicht fragend, nicht Wissen-Predigen.

RICHTIG (Klärung, keine Treffer):
   "Gerne — sag mir kurz dein Thema, dann schau ich passende Sammlungen
   für deinen Unterricht raus."
RICHTIG (Treffer gefunden, select_top_cards aufgerufen):
   "Hier sind passende Sammlungen zu Klimawandel — die Themenseite
   darunter fasst die zentralen Aspekte zusammen, die anderen vertiefen
   einzelne Schwerpunkte wie Nachhaltigkeit oder Naturschutz."
FALSCH:
   "Mehr dazu finden Sie auf [den Fachportalen](https://...)."
   "Hier sind: [Umwelt](https://...), [Nachhaltigkeit](https://...)."
   "Ich schau dir die besten Treffer raus — gleich folgen sie." ← FUTUR
   "Lass mich kurz nach Bruchrechnung suchen..."                ← FUTUR

## URL-EINBETTUNG — NIE im Bot-Text

NIEMALS Markdown-Links zu URLs in deinem Antwort-Text schreiben. Das gilt
absolut, auch wenn du URLs aus Wissensquellen oder Training-Daten siehst:

VERBOTEN:
   "[WirLernenOnline FAQ](https://wirlernenonline.de/faq/)"
   "[Über WLO](https://wirlernenonline.de/ueber-wlo)"
   "Schau auf [die Themenseite Klimawandel](https://...) für mehr."
   "- [Bildungsbereiche](https://wirlernenonline.de/bildungsbereiche)"

ERLAUBT (Plain-Text-Referenz auf den Namen):
   "Mehr dazu findest du in den WLO-FAQs und im WLO-Überblick."
   "Die Themenseite Klimawandel fasst die Kernaspekte zusammen."
   "Du findest dort u.a. Bildungsbereiche, Materialtypen und Personas."

WARUM:
- URLs werden vom System automatisch und semantisch korrekt aus den
  echten Card-Metadaten + RAG-Source-Frontmatter ausgespielt — über
  Kacheln, die "Webseiten-Inhalte"-Box und Such-CTAs der UI. Du musst
  und sollst keine URLs in den Text schreiben.
- URLs die du aus dem Training kennst oder erraten würdest, können
  veraltet, falsch oder halluziniert sein → kaputte Klicks für den User.
- Doppelte Anzeige (URL im Text + Box) ist Lärm.

Falls dir ein Tool eine konkrete URL als ``card.link``/``card.url``
liefert, übergib sie NICHT als Text — das System verlinkt die Kachel.
"""


def render_result_mode_block(
    *,
    inline_grouping_mode: bool,
    is_search_pattern: bool,
    cards_inline_mode: bool,
    degradation_no_tools: bool,
) -> str:
    """P5: the cards-disabled result-mode override. Mirrors the ALT if/elif/elif
    (lines 310-603) exactly; returns ``""`` when none of the branches apply."""
    if inline_grouping_mode and is_search_pattern and not degradation_no_tools:
        return INLINE_GROUPING_BLOCK
    if inline_grouping_mode and not is_search_pattern:
        return PATTERN_NO_SEARCH_BLOCK
    if cards_inline_mode:
        return INLINE_LINK_BLOCK
    return ""
