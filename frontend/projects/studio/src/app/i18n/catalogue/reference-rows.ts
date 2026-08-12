/**
 * Die Tabellenzeilen der Architektur-Referenz (C1-d5a2).
 *
 * Eigene Datei neben `reference.ts` — nicht weil die Zeilen woanders hingehören,
 * sondern weil beides zusammen über 400 Zeilen ergäbe (gemessen in C1-d5a1). Die
 * Teilung ist harmlos: eine Zelle steht für sich und teilt mit keinem Satz der
 * Nachbardatei einen Satz.
 *
 * **Die Regel dieser Scheibe: was im `<code>` steht, ist ein Bezeichner und
 * bleibt Daten.** Die Feldnamen der Modulation (`tone`, `max_items`, …) stehen
 * deshalb weiter in `views/reference-data.ts` und nicht hier. Die Ausnahme ist
 * die Quellen-Spalte der Pattern-Wahl: zwei ihrer vier Zellen sind Prosa, die
 * ALT ins `<code>` gesetzt hat. Damit die Spalte einen Weg nimmt statt zwei,
 * gehen alle vier durch den Katalog — die beiden echten Bezeichner stehen in
 * beiden Sprachen wortgleich da und sind in `en.spec.ts` als solche benannt.
 *
 * Entwurf: `docs/plans/2026-08-02-c1-i18n.md`.
 */
import type { CataloguePart } from './catalogue-part';

export const REFERENCE_ROWS: CataloguePart = {
  de: {
    // ── Die sieben Phasen ───────────────────────────────────────────
    'arch.row.pipe.1.label': 'Safety-Check',
    'arch.row.pipe.1.desc':
      'Regex, Moderation und Legal-Klassifikator prüfen die Nachricht; '
      + 'Crisis-/Threat-Marker erzwingen M01 bzw. M02.',
    'arch.row.pipe.2.label': 'Klassifikation (LLM)',
    'arch.row.pipe.2.desc':
      'Persona, Intent, Pattern-Hint, Signale, Entities, State und Turn-Type '
      + 'erkennen — classify-overrides.yaml liefert die Hard-Override-Anker.',
    'arch.row.pipe.3.label': 'Policy-Prüfung',
    'arch.row.pipe.3.desc': 'Tool-Blockaden und Disclaimer anhand von Persona und Intent.',
    'arch.row.pipe.4.label': 'Pattern-Wahl',
    'arch.row.pipe.4.desc':
      'Safety vor LLM-Hint vor Fallback (M15). Eine Quelle, keine Rule-Engine.',
    'arch.row.pipe.5.label': 'Prompt-Zusammensetzung',
    'arch.row.pipe.5.desc': 'Die Schichten werden zum System-Prompt kombiniert.',
    'arch.row.pipe.6.label': 'LLM-Aufruf + MCP-Tools',
    'arch.row.pipe.6.desc': 'Das LLM antwortet und ruft bei Bedarf externe Tools auf.',
    'arch.row.pipe.7.label': 'Nachbereitung',
    'arch.row.pipe.7.desc': 'Karten extrahieren, Quality-Log schreiben, State speichern.',

    // ── Die sechs Input-Dimensionen ─────────────────────────────────
    // Vier der sechs Namen sind Lehnwörter, die auch das deutsche Studio
    // englisch führt; sie stehen deshalb in der Erlaubnisliste von `en.spec.ts`.
    'arch.row.dim.persona.name': 'Persona',
    'arch.row.dim.persona.desc': 'Wer spricht? (Lehrkraft, Lernende, Eltern, Presse …)',
    'arch.row.dim.persona.effect': 'Anrede, Tonalität, Policy-Regeln, Tool-Zugang',
    'arch.row.dim.intent.name': 'Intent',
    'arch.row.dim.intent.desc':
      'Was will die Person? (Inhalte abrufen, Fakten, Material erstellen oder '
      + 'bearbeiten, Feedback …)',
    'arch.row.dim.intent.effect':
      'Pattern-Wahl, MCP-Tool-Präferenz, spekulative Vorab-Abfragen',
    'arch.row.dim.signals.name': 'Signale',
    'arch.row.dim.signals.desc': 'Emotionale und situative Hinweise in vier Dimensionen',
    'arch.row.dim.signals.effect':
      'Modulieren Ton, Länge und skip_intro — überschreiben Pattern-Defaults',
    'arch.row.dim.entities.name': 'Entities',
    'arch.row.dim.entities.desc':
      'Extrahierte Parameter: Fach, Stufe, Thema, Medientyp, Lizenz',
    'arch.row.dim.entities.effect':
      'MCP-Suchparameter, Pattern-Preconditions, Entity-Memory über Turns',
    'arch.row.dim.state.name': 'State',
    'arch.row.dim.state.desc': 'Gesprächszustand: Orientierung → Suche → Kuratierung',
    'arch.row.dim.state.effect': 'Pattern-Wahl, zustandsabhängiges Verhalten',
    'arch.row.dim.turnType.name': 'Turn-Type',
    /** Eine Aufzählung der Enum-Werte, keine Beschreibung — in beiden Sprachen
     *  dieselben fünf Bezeichner. */
    'arch.row.dim.turnType.desc': 'initial, follow_up, clarification, correction, topic_switch',
    'arch.row.dim.turnType.effect':
      'Entity-Akkumulation (behalten, ergänzen, überschreiben, zurücksetzen)',

    // ── Modulation: Stil & Inhalt ───────────────────────────────────
    'arch.row.style.tone': 'Ton der Antwort (sachlich, empathisch, spielerisch …)',
    'arch.row.style.formality': 'Formalitätsgrad',
    'arch.row.style.length': 'Antwortlänge (kurz, mittel, lang)',
    'arch.row.style.detailLevel': 'Detailgrad (standard, ausführlich)',
    'arch.row.style.responseType': 'Antworttyp (answer, question, redirect …)',
    'arch.row.style.formatPrimary': 'Primärformat (text, list, cards …)',
    'arch.row.style.formatFollowUp': 'Follow-up-Format',
    'arch.row.style.sources': 'Wissensquellen (mcp, rag oder leer)',

    // ── Modulation: Steuerung & Flags ───────────────────────────────
    'arch.row.ctl.maxItems': 'Höchstzahl der Ergebniskarten',
    'arch.row.ctl.cardTextMode': 'Kartentext (minimal, detailed)',
    'arch.row.ctl.tools': 'Erzwungene MCP-Tools',
    'arch.row.ctl.ragAreas': 'RAG-Wissensbereiche',
    'arch.row.ctl.coreRule': 'Kern-Anweisung für das LLM',
    'arch.row.ctl.skipIntro': 'Einleitung weglassen',
    'arch.row.ctl.oneOption': 'Nur einen Vorschlag zeigen',
    'arch.row.ctl.addSources': 'Quellenangaben erzwingen',
    'arch.row.ctl.degradation': 'Degradation aktiv?',
    'arch.row.ctl.missingSlots': 'Fehlende Precondition-Slots',
    'arch.row.ctl.blockedPatterns': 'Eliminierte Pattern-IDs',

    // ── Die vier Schritte der Pattern-Wahl ──────────────────────────
    'arch.row.sel.1.step': '1. Safety-Override',
    'arch.row.sel.1.source': 'safety.enforced_pattern',
    'arch.row.sel.1.effect': 'M01 bei Selbstgefährdung, M02 bei Drohungen — gewinnt immer.',
    'arch.row.sel.2.step': '2. LLM-Hint',
    'arch.row.sel.2.source': 'classification.pattern_id_hint',
    'arch.row.sel.2.effect':
      'Der primäre Pfad in praktisch jedem Turn, geleitet von den Hint-Ankern aus '
      + '01-base/classify-overrides.yaml.',
    'arch.row.sel.3.step': '3. Fallback',
    'arch.row.sel.3.source': 'defensiv hartkodiert',
    'arch.row.sel.3.effect':
      'M15 (Orientierung), wenn weder Safety noch Hint ein gültiges Pattern liefern.',
    'arch.row.sel.4.step': '4. Modulation',
    'arch.row.sel.4.source': 'Persona-Modifier + Pattern-Defaults + Signale',
    'arch.row.sel.4.effect':
      'Stil, Tonalität, Tool-Liste, Slot-Degradation. Die Persona greift hier — '
      + 'nicht bei der Pattern-Wahl.',

    // ── Die sechs Prompt-Schichten ──────────────────────────────────
    'arch.row.layer.1.name': '1 — Identität & Schutz',
    'arch.row.layer.1.content': 'Persona-Definition, Guardrails, Safety-Config, Policy-Regeln',
    'arch.row.layer.1.tokens': 'Wird nie entladen. Guardrails stehen immer am Ende.',
    'arch.row.layer.2.name': '2 — Domain & Regeln',
    'arch.row.layer.2.content': 'Plattform-Regeln, WLO-Fachwissen',
    'arch.row.layer.2.tokens': 'Wird nie entladen.',
    'arch.row.layer.3.name': '3 — Patterns',
    'arch.row.layer.3.content': 'Das gewählte Gesprächsmuster (genau eines)',
    'arch.row.layer.3.tokens': 'Kann auf M12 (Degradation) zurückfallen.',
    'arch.row.layer.4.name': '4 — Dimensionen',
    'arch.row.layer.4.content': 'Nur erkannte Persona, aktiver Intent und aktive Signale',
    'arch.row.layer.4.tokens': 'Kann teilweise entladen werden.',
    'arch.row.layer.5.name': '5 — Material-Formate',
    'arch.row.layer.5.content': 'Struktur-Vorgabe des Material-Typs, Alias-Mapping, Trigger',
    'arch.row.layer.5.tokens': 'Nur bei I05/I06 geladen, sonst nicht im Prompt.',
    'arch.row.layer.6.name': '6 — Wissen',
    'arch.row.layer.6.content': 'RAG-Kontext (always-on + on-demand), MCP-Tools',
    'arch.row.layer.6.tokens': 'Wird als erstes entladen.',
  },

  en: {
    'arch.row.pipe.1.label': 'Safety check',
    'arch.row.pipe.1.desc':
      'Regex, moderation and the legal classifier check the message; crisis and '
      + 'threat markers force M01 or M02.',
    'arch.row.pipe.2.label': 'Classification (LLM)',
    'arch.row.pipe.2.desc':
      'Recognise persona, intent, pattern hint, signals, entities, state and turn '
      + 'type — classify-overrides.yaml supplies the hard-override anchors.',
    'arch.row.pipe.3.label': 'Policy check',
    'arch.row.pipe.3.desc': 'Tool blocks and disclaimers based on persona and intent.',
    'arch.row.pipe.4.label': 'Pattern choice',
    'arch.row.pipe.4.desc':
      'Safety before the LLM hint before the fallback (M15). One source, no rule engine.',
    'arch.row.pipe.5.label': 'Prompt assembly',
    'arch.row.pipe.5.desc': 'The layers are combined into the system prompt.',
    'arch.row.pipe.6.label': 'LLM call + MCP tools',
    'arch.row.pipe.6.desc': 'The LLM answers and calls external tools where needed.',
    'arch.row.pipe.7.label': 'Post-processing',
    'arch.row.pipe.7.desc': 'Extract cards, write the quality log, store the state.',

    'arch.row.dim.persona.name': 'Persona',
    'arch.row.dim.persona.desc': 'Who is speaking? (teacher, learner, parent, press …)',
    'arch.row.dim.persona.effect': 'Form of address, tone, policy rules, tool access',
    'arch.row.dim.intent.name': 'Intent',
    'arch.row.dim.intent.desc':
      'What does the person want? (retrieve content, facts, create or edit '
      + 'material, feedback …)',
    'arch.row.dim.intent.effect':
      'Pattern choice, MCP tool preference, speculative prefetches',
    'arch.row.dim.signals.name': 'Signals',
    'arch.row.dim.signals.desc': 'Emotional and situational cues in four dimensions',
    'arch.row.dim.signals.effect':
      'They modulate tone, length and skip_intro — and override the pattern defaults',
    'arch.row.dim.entities.name': 'Entities',
    'arch.row.dim.entities.desc':
      'Extracted parameters: subject, level, topic, media type, licence',
    'arch.row.dim.entities.effect':
      'MCP search parameters, pattern preconditions, entity memory across turns',
    'arch.row.dim.state.name': 'State',
    'arch.row.dim.state.desc': 'Conversation state: orientation → search → curation',
    'arch.row.dim.state.effect': 'Pattern choice, state-dependent behaviour',
    'arch.row.dim.turnType.name': 'Turn type',
    'arch.row.dim.turnType.desc': 'initial, follow_up, clarification, correction, topic_switch',
    'arch.row.dim.turnType.effect':
      'Entity accumulation (keep, extend, overwrite, reset)',

    'arch.row.style.tone': 'Tone of the answer (factual, empathetic, playful …)',
    'arch.row.style.formality': 'Degree of formality',
    'arch.row.style.length': 'Length of the answer (short, medium, long)',
    'arch.row.style.detailLevel': 'Level of detail (standard, detailed)',
    'arch.row.style.responseType': 'Type of answer (answer, question, redirect …)',
    'arch.row.style.formatPrimary': 'Primary format (text, list, cards …)',
    'arch.row.style.formatFollowUp': 'Follow-up format',
    'arch.row.style.sources': 'Knowledge sources (mcp, rag or empty)',

    'arch.row.ctl.maxItems': 'Maximum number of result cards',
    'arch.row.ctl.cardTextMode': 'Card text (minimal, detailed)',
    'arch.row.ctl.tools': 'Enforced MCP tools',
    'arch.row.ctl.ragAreas': 'RAG knowledge areas',
    'arch.row.ctl.coreRule': 'Core instruction for the LLM',
    'arch.row.ctl.skipIntro': 'Leave out the introduction',
    'arch.row.ctl.oneOption': 'Show only one suggestion',
    'arch.row.ctl.addSources': 'Enforce source references',
    'arch.row.ctl.degradation': 'Degradation active?',
    'arch.row.ctl.missingSlots': 'Missing precondition slots',
    'arch.row.ctl.blockedPatterns': 'Eliminated pattern ids',

    'arch.row.sel.1.step': '1. Safety override',
    'arch.row.sel.1.source': 'safety.enforced_pattern',
    'arch.row.sel.1.effect':
      'M01 for self-harm, M02 for threats — it always wins.',
    'arch.row.sel.2.step': '2. LLM hint',
    'arch.row.sel.2.source': 'classification.pattern_id_hint',
    'arch.row.sel.2.effect':
      'The primary path in practically every turn, guided by the hint anchors from '
      + '01-base/classify-overrides.yaml.',
    'arch.row.sel.3.step': '3. Fallback',
    'arch.row.sel.3.source': 'defensively hard-coded',
    'arch.row.sel.3.effect':
      'M15 (orientation), when neither safety nor the hint yields a valid pattern.',
    'arch.row.sel.4.step': '4. Modulation',
    'arch.row.sel.4.source': 'persona modifiers + pattern defaults + signals',
    'arch.row.sel.4.effect':
      'Style, tone, tool list, slot degradation. The persona takes effect here — '
      + 'not in the pattern choice.',

    'arch.row.layer.1.name': '1 — Identity & protection',
    'arch.row.layer.1.content': 'Persona definition, guardrails, safety config, policy rules',
    'arch.row.layer.1.tokens': 'Never unloaded. Guardrails always come last.',
    'arch.row.layer.2.name': '2 — Domain & rules',
    'arch.row.layer.2.content': 'Platform rules, WLO domain knowledge',
    'arch.row.layer.2.tokens': 'Never unloaded.',
    'arch.row.layer.3.name': '3 — Patterns',
    'arch.row.layer.3.content': 'The chosen conversation pattern (exactly one)',
    'arch.row.layer.3.tokens': 'Can fall back to M12 (degradation).',
    'arch.row.layer.4.name': '4 — Dimensions',
    'arch.row.layer.4.content': 'Only the recognised persona, the active intent and signals',
    'arch.row.layer.4.tokens': 'Can be partly unloaded.',
    'arch.row.layer.5.name': '5 — Material formats',
    'arch.row.layer.5.content': 'Structure of the material type, alias mapping, triggers',
    'arch.row.layer.5.tokens': 'Loaded only for I05/I06, otherwise absent from the prompt.',
    'arch.row.layer.6.name': '6 — Knowledge',
    'arch.row.layer.6.content': 'RAG context (always-on + on-demand), MCP tools',
    'arch.row.layer.6.tokens': 'The first to be unloaded.',
  },
};
