"""LLM learning-path generator (P5-6a, port of ALT llm_learning_path.py):
``generate_learning_path_text`` — a pedagogically structured learning path
from collection contents, one LLM call.

NEU-deviation (documented): transport goes through ``llm.chat_completion``
(routing/semaphore/usage) instead of ALT's module-level ``client``/``MODEL``
singletons (LiteLLM has no persistent client). The prompt-building is verbatim
ALT — it carries the pedagogical logic (step-count rules, fach/stufe inference
hint, no-LaTeX formatting). Precedent: quick_replies_llm.py.
"""

from __future__ import annotations

from boerdi.domain.reasoning_filters import strip_reasoning_markers
from boerdi.services import llm


async def generate_learning_path_text(
    collection_title: str,
    contents_text: str,
    session_state: dict,
) -> str:
    """Generate a pedagogically structured learning path from collection contents."""
    persona_id = session_state.get("persona_id", "P-AND")
    entities = session_state.get("entities", {})

    learner_info = []
    if entities.get("fach"):
        learner_info.append(f"Fach: {entities['fach']}")
    if entities.get("stufe"):
        learner_info.append(f"Bildungsstufe: {entities['stufe']}")
    learner_ctx = " | ".join(learner_info) if learner_info else "allgemeine Lernende"

    # If fach/stufe are missing, the LLM should infer plausible defaults
    # from the topic (e.g. "Photosynthese" → Biologie, Sek I) AND state
    # this assumption transparently in the response. Eval-Befund Run 10:
    # ohne dieses Hinzunehmen liefert M09 leere Schritt 1/2/3-Templates.
    has_fach = bool(entities.get("fach"))
    has_stufe = bool(entities.get("stufe"))
    default_hint = ""
    if not has_fach or not has_stufe:
        default_hint = (
            "\n\n**WICHTIG — Fach/Stufe ableiten und transparent nennen:**\n"
            f"- Fach{'' if has_fach else ' (NICHT genannt — leite plausible Annahme aus dem Thema ab)'}: "
            f"{entities.get('fach') or '— leite ab'}\n"
            f"- Stufe{'' if has_stufe else ' (NICHT genannt — leite plausible Annahme aus dem Thema ab)'}: "
            f"{entities.get('stufe') or '— leite ab'}\n"
            "Beispiele: 'Photosynthese' → Biologie / Sek I; 'Bruchrechnung' → "
            "Mathematik / Sek I; 'Mittelalter' → Geschichte / Sek I.\n"
            "Im ersten Satz des Lernpfad-Titels die Annahme transparent benennen, "
            "z.B. 'Lernpfad zu *X* (Annahme: Biologie / Sek I — bei Bedarf "
            "anpassen).'"
        )

    system = f"""Du bist BOERDi, ein paedagogischer Assistent fuer WirLernenOnline.de.
Erstelle einen strukturierten Lernpfad aus den gegebenen Inhalten.
Persona: {persona_id}
Kontext: {learner_ctx}{default_hint}

FORMATIERUNGS-REGELN — WICHTIG:
- KEINE LaTeX-Syntax verwenden. Kein \\frac{{}}{{}}, kein \\sqrt{{}}, keine $...$-Delimiter.
- Brueche als Unicode darstellen wo moeglich: 1/2, 1/3, 3/4 — oder ausgeschrieben
  ("ein Drittel", "drei Viertel"). NIEMALS \\frac12 oder ( \\frac12 ).
- Mathematische Ausdruecke als einfacher Text: x^2 statt x^{{2}}, sqrt(2) statt
  \\sqrt{{2}}.
- Markdown wird zu HTML gerendert (marked.js + DOMPurify) — alles, was nicht
  Standard-Markdown ist, kommt beim User als Rohtext an."""

    prompt = f"""Erstelle einen paedagogisch strukturierten **Lernpfad** zum Thema \"{collection_title}\".

Verfuegbare Inhalte:

{contents_text}

**Aufgabe:** Waehle die geeignetsten Inhalte aus und ordne sie in einem sinnvollen Lernpfad an.
Bringe die Materialien in eine didaktisch sinnvolle Reihenfolge (vom Einfachen zum Komplexen).

**HARTE REGELN — nicht verhandelbar:**
1. **Jeder Inhalt darf maximal EINMAL verwendet werden.** Verlinke nie dasselbe
   Material in zwei verschiedenen Schritten. Wiederholungen sind ein Fehler.
2. **Die Anzahl der Schritte richtet sich nach den verfuegbaren Materialien:**
   - Bei 1 Material → 1 Schritt (plus Hinweis, dass der Pfad so kurz ist, weil nur
     ein passendes Material gefunden wurde). Schreibe keinen mehrstufigen Pfad mit
     einem einzigen wiederholten Material.
   - Bei 2-3 Materialien → 2-3 Schritte.
   - Bei 4+ Materialien → 3-5 Schritte, klassisch Einstieg / Erarbeitung / Sicherung.
3. **Das Thema des Lernpfads ist \"{collection_title}\" — nicht der Titel einer
   Sammlung oder eines einzelnen Inhalts.** Wenn die Materialien thematisch nur
   am Rand passen, weise darauf explizit hin (z.B. \"Ein direkt zu '{collection_title}'
   passendes Material war nicht verfuegbar — die folgenden Inhalte streifen das
   Thema.\"). Kapere das Thema nicht.
4. **Jeder Schritt MUSS sein Material beim Namen nennen** — als eigene Zeile
   exakt im Format \"- Material: [exakter Titel](URL)\". Ein Schritt ohne diese
   Zeile ist unvollstaendig. Verwende den Titel WOERTLICH aus der Liste oben
   (nicht umformulieren oder kuerzen), damit die Lernenden jeden Schritt dem
   passenden Inhalt in der Material-Box darunter zuordnen koennen.

**Format (Markdown, auf Deutsch):**

Beginne mit einem kurzen Ueberblick:
> **Lernpfad: {collection_title}**
> Kurze Beschreibung des Lernziels (1-2 Saetze).
> Geschaetzte Gesamtdauer: X Minuten

Dann die einzelnen Schritte als nummerierte Abschnitte:
### Schritt 1: Einstieg (ca. X Min.)
- *Lernziel: ...*
- Material: [exakter Titel aus der Liste](URL)
- Aktivitaet: Was sollen die Lernenden konkret tun?
- Begruendung warum dieser Inhalt hier passt

### Schritt 2: Erarbeitung (ca. X Min.)
...usw.

### Schritt N: Sicherung / Vertiefung
...

Schliesse mit:
- **Differenzierung:** Tipps fuer schnellere / langsamere Lernende
- **Tipp fuer Lehrende:** Praktische Hinweise zur Durchfuehrung

Nutze ausschliesslich Inhalte aus der obigen Liste. Verlinke alle verwendeten Inhalte.
Wenn wenige Materialien vorhanden sind, schlage konkret vor, welche Materialtypen
zur Ergaenzung gesucht werden koennten (z.B. \"ein kurzes Erklaervideo\",
\"ein Arbeitsblatt mit Aufgaben\") — aber verwende niemals dasselbe Material mehrfach,
um Luecken zu fuellen."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    try:
        resp = await llm.chat_completion(
            messages=messages,
            temperature=0.7,
            max_tokens=2000,
        )
        return strip_reasoning_markers(resp.choices[0].message.content or "") or "Lernpfad konnte nicht erstellt werden."
    except Exception as e:
        return f"Fehler beim Erstellen des Lernpfads: {e}"
