/**
 * Die Architektur-Referenz (C1-d5a): die Prosa der Hülle.
 *
 * Ein Teilkatalog je ABSCHNITTS-KOMPONENTE, nicht je Referenz-Tab: die fünf
 * Abschnitte haben je einen eigenen Grund zur Änderung (so steht es schon im
 * Kopf von `architecture-reference.component.ts`), und 268 Texte in einer Datei
 * spränge die 300-Zeilen-Grenze um ein Mehrfaches.
 *
 * **Und innerhalb dieser Komponente noch einmal geteilt.** Hier steht ihre
 * Prosa; die 71 Texte ihrer Tabellenzeilen kommen mit C1-d5a2 in einen eigenen
 * Teil. Gemessen statt geschätzt: die 59 Schlüssel hier füllen die Datei schon
 * bis knapp unter die Grenze, mit den Zeilen wären es über 400. Die Teilung
 * kostet hier nichts, weil ein Tabellentext für sich steht und mit keinem Satz
 * dieser Datei einen Satz teilt — anders als bei einer Wortgruppe, die in einen
 * Satz eingesetzt wird.
 *
 * **Auszeichnung als Marker, nicht als Markup.** Neun Sätze tragen `<code>`
 * oder `<strong>` mitten im Satz; sie stehen hier mit `` `so` `` und `*so*` und
 * werden von `rich()` zerlegt (C1-d4b2). Ein Satz aus Bruchstücken wäre die
 * Alternative gewesen — und genau der Fehler, den C1-d3a abgestellt hat.
 *
 * Entwurf: `docs/plans/2026-08-02-c1-i18n.md`.
 */
import type { CataloguePart } from './catalogue-part';

export const REFERENCE: CataloguePart = {
  de: {
    'arch.title': 'Architektur-Referenz',
    'arch.intro':
      'Wie die Elemente zusammenspielen — vom Nutzer-Input bis zur Bot-Antwort. Die '
      + 'aktuellen Anzahlen (Patterns, Personas, Intents, States, Entities, Signale) '
      + 'stehen im Tab „Übersicht“; hier steht, was sie bewirken.',

    // ── Spaltenköpfe der vier Tabellen ──────────────────────────────
    // Vier Tabellen teilen sich sieben Köpfe, „Wirkung" steht in zwei davon.
    // Je Tabelle eigene Schlüssel könnten auseinanderlaufen, ohne dass es
    // jemandem auffällt.
    'arch.col.element': 'Element',
    'arch.col.desc': 'Beschreibung',
    'arch.col.effect': 'Wirkung',
    'arch.col.step': 'Schritt',
    'arch.col.source': 'Quelle',
    'arch.col.layer': 'Schicht',
    'arch.col.priority': 'Priorität',
    'arch.col.content': 'Inhalt',
    'arch.col.tokens': 'Token-Verhalten',

    // ── Verarbeitungs-Pipeline ──────────────────────────────────────
    'arch.pipeline.title': 'Die Verarbeitungs-Pipeline',
    'arch.pipeline.text':
      'Jede Nutzernachricht durchläuft sieben Phasen. Klassifikation und '
      + 'Pattern-Wahl laufen strukturiert — LLM-Hint plus deterministische Anker —, '
      + 'bevor die Antwort generiert wird.',

    // ── Input-Elemente ──────────────────────────────────────────────
    'arch.input.title': 'Input-Elemente (Klassifikation)',
    'arch.input.text':
      'In Phase 2 erkennt ein LLM-Aufruf sechs Dimensionen aus der Nachricht. Diese '
      + 'Input-Elemente steuern alles Weitere.',

    // ── Pattern-Engine ──────────────────────────────────────────────
    'arch.engine.title': 'Pattern-Engine und ihre Ausgabe',
    'arch.engine.text':
      'Aus allen Gesprächsmustern wird *genau eines* gewählt; nur das '
      + 'Gewinner-Pattern landet im Prompt. Danach justiert die Modulation Ton, Länge '
      + 'und Format — bei Konflikten gewinnt die kürzere Länge.',
    'arch.engine.style': 'Stil & Inhalt',
    'arch.engine.control': 'Steuerung & Flags',

    // ── Hard-Overrides ──────────────────────────────────────────────
    'arch.overrides.title': 'Hard-Overrides im Classifier',
    'arch.overrides.text1':
      'Die frühere Routing-Rule-Engine ist ausgebaut. Was sie an Mehrwert hatte — '
      + 'explizite Persona-Selbstauskunft („ich bin Lehrkraft“), Verb-Unterscheidung '
      + '(suchen gegen erstellen) und Phantom-Themen-Erkennung — steht jetzt in einer '
      + 'Datei: `01-base/classify-overrides.yaml`.',
    'arch.overrides.text2':
      'Der Classifier-System-Prompt rendert sie als Hint-Anker; das LLM bekommt sie '
      + 'als deterministische Trigger-Liste mit Erwartungswerten. Eine Schicht statt '
      + 'Pre-Route, Post-Route, Lookup-Gruppen und Shadow-Logs — und im Studio unter '
      + '„Alle Bereiche“ direkt editierbar, wirksam ab dem nächsten Turn.',

    // ── Pattern-Wahl ────────────────────────────────────────────────
    'arch.selection.title': 'Pattern-Wahl — wer entscheidet?',
    /** Der Stern in `signal_*_fit` steht INNERHALB eines Backtick-Paars.
     *  `splitRich` liest das Paar als Ganzes, der Stern bleibt damit Teil des
     *  Bezeichners — gepinnt in `architecture-reference.component.spec.ts`,
     *  weil ein verschwundener Stern einen still falschen Namen ergäbe. */
    'arch.selection.gone':
      '*Was es nicht mehr gibt:* `gate_personas`, `gate_states`, `gate_intents`, '
      + '`signal_*_fit`, `page_bonus` und Tie-Breaker. Pattern-Frontmatter braucht '
      + 'nur noch Antwort-Form, Tools und Inhalt-Regeln. `precondition_slots` bleibt, '
      + 'wirkt aber nur noch als Degradations-Flag in der Modulation, nicht als '
      + 'Pattern-Ausschluss.',
    'arch.selection.personaTitle': 'Wirkung der Persona',
    'arch.selection.personaText':
      'Die Persona steuert *Stil und Anrede*, nicht die Pattern-Wahl. Ihre fünf '
      + 'Frontmatter-Felder greifen in der Modulation, nachdem das Pattern feststeht. '
      + 'Eine ausdrückliche Selbstauskunft überstimmt den Klassifikator über '
      + '`persona_overrides` in `01-base/classify-overrides.yaml` — sie setzt die '
      + 'Persona, nicht das Pattern.',
    'arch.selection.note':
      'ALT nannte dafür die Routing-Regel `lookup_persona_self_id__*`, obwohl der '
      + 'Abschnitt darüber den Ausbau der Rule-Engine beschreibt. In NEU gibt es '
      + 'diese Regel nicht; der Mechanismus ist die Override-Liste im '
      + 'Classifier-Prompt.',

    // ── Die sechs Schichten ─────────────────────────────────────────
    'arch.layers.title': 'Die sechs Architektur-Schichten',
    'arch.layers.text':
      'Der System-Prompt wird aus Schichten zusammengesetzt. Jede hat eine '
      + 'Priorität: bei Token-Knappheit werden niedrig priorisierte zuerst entladen.',
    'arch.layers.assemblyTitle': 'Aufbau zur Laufzeit',
    // Acht Zeilen mit je zwei unabhängigen Angaben: WAS geladen wird und WANN.
    // Das ist kein Satz aus Bruchstücken — die Bedingung steht am Bildschirm in
    // ihrer eigenen, abgesetzten Spalte und gehört keinem Satz.
    'arch.assembly.1': 'Schicht 1: `base-persona.md`',
    'arch.assembly.1.when': 'immer',
    'arch.assembly.2': 'Schicht 2: `domain-rules.md` + Plattform-Wissen',
    'arch.assembly.2.when': 'immer',
    'arch.assembly.3': 'Schicht 4: Persona-Prompt, Intent, Signale',
    'arch.assembly.3.when': 'nur erkannte',
    'arch.assembly.4': 'Schicht 3: Pattern-Block',
    'arch.assembly.4.when': 'nur der Gewinner',
    'arch.assembly.5': 'Schicht 5: Material-Format-Struktur',
    'arch.assembly.5.when': 'nur bei I05/I06',
    'arch.assembly.6': 'Schicht 6: RAG-Kontext',
    'arch.assembly.6.when': 'always-on-Bereiche',
    'arch.assembly.7': 'Aktuelle Themenseite',
    'arch.assembly.7.when': 'wenn die node_id auflösbar ist',
    'arch.assembly.8': 'Schicht 1: `guardrails.md`',
    'arch.assembly.8.when': 'immer, und immer am Ende',

    // ── Material-Erstellung & Datenschutz ───────────────────────────
    'arch.material.title': 'Material-Erstellung & Datenschutz',
    'arch.material.intentsTitle': 'Material-Intents & -Formate',
    /** Verweist auf den Abschnitt der Kataloge, OHNE dessen Überschrift zu
     *  zitieren: die steht bis C1-d5c auf Deutsch da, und ein englischer Satz
     *  nannte damit eine Überschrift, die anders lautet (dieselbe Entscheidung
     *  wie bei `rag.areas.empty`). */
    'arch.material.text':
      'Welche Formate Schicht 5 führt, steht im Abschnitt zu den Material-Typen — '
      + 'dort aus der laufenden Konfiguration gelesen statt hier abgeschrieben.',
    'arch.material.i05':
      '*I05 Material-Erstellung* → M10 erzeugt das Material als Inline-Dokument im '
      + 'Verlauf.',
    'arch.material.i06':
      '*I06 Material-Bearbeitung* → verfeinert das letzte Dokument bei „mach es '
      + 'einfacher“ oder „Lösungen dazu“.',
    'arch.material.priority':
      '*Typ- und Themen-Priorität:* aktueller Turn vor Klassifikator vor gemerkter '
      + 'Session — sonst gewinnt ein alter Wert beim Klick auf einen Chip.',

    'arch.privacy.title': 'Datenschutz-Schalter',
    'arch.privacy.text':
      'Logging lässt sich in `01-base/privacy-config.yaml` einzeln abschalten '
      + '(Studio-Bereich „Datenschutz“):',
    'arch.privacy.messages': '`logging.messages` — Chatverläufe',
    'arch.privacy.memory': '`logging.memory` — Session-Gedächtnis',
    'arch.privacy.quality': '`logging.quality` — Quality-Analytics',
    'arch.privacy.safety': '`logging.safety` — *immer an* (Audit-Pflicht)',
    'arch.privacy.purge':
      'Dazu löschen die Purge-Endpunkte bestehende Daten, und Snapshots sichern die '
      + 'Konfiguration ohne Up- oder Download.',
  },

  en: {
    'arch.title': 'Architecture reference',
    'arch.intro':
      'How the elements work together — from the user input to the bot’s answer. '
      + 'The current counts (patterns, personas, intents, states, entities, signals) '
      + 'are in the “Overview” tab; what they do is here.',

    'arch.col.element': 'Element',
    'arch.col.desc': 'Description',
    'arch.col.effect': 'Effect',
    'arch.col.step': 'Step',
    'arch.col.source': 'Source',
    'arch.col.layer': 'Layer',
    'arch.col.priority': 'Priority',
    'arch.col.content': 'Content',
    'arch.col.tokens': 'Token behaviour',

    'arch.pipeline.title': 'The processing pipeline',
    'arch.pipeline.text':
      'Every user message passes through seven phases. Classification and pattern '
      + 'choice run in a structured way — an LLM hint plus deterministic anchors — '
      + 'before the answer is generated.',

    'arch.input.title': 'Input elements (classification)',
    'arch.input.text':
      'In phase 2 a single LLM call recognises six dimensions in the message. These '
      + 'input elements steer everything that follows.',

    'arch.engine.title': 'The pattern engine and its output',
    'arch.engine.text':
      'Out of all conversation patterns *exactly one* is chosen; only the winning '
      + 'pattern reaches the prompt. The modulation then adjusts tone, length and '
      + 'format — where they conflict, the shorter length wins.',
    'arch.engine.style': 'Style & content',
    'arch.engine.control': 'Control & flags',

    'arch.overrides.title': 'Hard overrides in the classifier',
    'arch.overrides.text1':
      'The former routing rule engine has been removed. What it did add — an '
      + 'explicit persona self-statement (“I am a teacher”), telling verbs apart '
      + '(searching versus creating) and phantom-topic detection — now lives in a '
      + 'single file: `01-base/classify-overrides.yaml`.',
    'arch.overrides.text2':
      'The classifier system prompt renders them as hint anchors; the LLM receives '
      + 'them as a deterministic list of triggers with expected values. One layer '
      + 'instead of pre-route, post-route, lookup groups and shadow logs — and '
      + 'editable directly in the studio under “All areas”, effective from the next '
      + 'turn.',

    'arch.selection.title': 'Pattern choice — who decides?',
    'arch.selection.gone':
      '*What no longer exists:* `gate_personas`, `gate_states`, `gate_intents`, '
      + '`signal_*_fit`, `page_bonus` and tie-breakers. Pattern frontmatter only '
      + 'needs the answer shape, tools and content rules. `precondition_slots` '
      + 'remains, but now acts only as a degradation flag in the modulation, not as '
      + 'a pattern exclusion.',
    'arch.selection.personaTitle': 'What the persona does',
    'arch.selection.personaText':
      'The persona steers *style and form of address*, not the pattern choice. Its '
      + 'five frontmatter fields take effect in the modulation, once the pattern is '
      + 'settled. An explicit self-statement overrules the classifier through '
      + '`persona_overrides` in `01-base/classify-overrides.yaml` — it sets the '
      + 'persona, not the pattern.',
    'arch.selection.note':
      'ALT named the routing rule `lookup_persona_self_id__*` for this, although the '
      + 'section above it describes the removal of that rule engine. NEU has no such '
      + 'rule; the mechanism is the override list in the classifier prompt.',

    'arch.layers.title': 'The six architecture layers',
    'arch.layers.text':
      'The system prompt is assembled from layers. Each one carries a priority: '
      + 'when tokens run short, the lower-priority ones are dropped first.',
    'arch.layers.assemblyTitle': 'Assembly at run time',
    'arch.assembly.1': 'Layer 1: `base-persona.md`',
    'arch.assembly.1.when': 'always',
    'arch.assembly.2': 'Layer 2: `domain-rules.md` + platform knowledge',
    'arch.assembly.2.when': 'always',
    'arch.assembly.3': 'Layer 4: persona prompt, intent, signals',
    'arch.assembly.3.when': 'only those recognised',
    'arch.assembly.4': 'Layer 3: pattern block',
    'arch.assembly.4.when': 'only the winner',
    'arch.assembly.5': 'Layer 5: material format structure',
    'arch.assembly.5.when': 'only for I05/I06',
    'arch.assembly.6': 'Layer 6: RAG context',
    'arch.assembly.6.when': 'always-on areas',
    'arch.assembly.7': 'Current topic page',
    'arch.assembly.7.when': 'if the node_id resolves',
    'arch.assembly.8': 'Layer 1: `guardrails.md`',
    'arch.assembly.8.when': 'always, and always last',

    'arch.material.title': 'Material creation & data protection',
    'arch.material.intentsTitle': 'Material intents & formats',
    'arch.material.text':
      'Which formats layer 5 carries is in the section on material types — read '
      + 'there from the running configuration instead of copied out here.',
    'arch.material.i05':
      '*I05 material creation* → M10 produces the material as an inline document in '
      + 'the conversation.',
    'arch.material.i06':
      '*I06 material editing* → refines the last document on “make it simpler” or '
      + '“add the solutions”.',
    'arch.material.priority':
      '*Type and topic priority:* the current turn before the classifier before the '
      + 'remembered session — otherwise an old value wins when a chip is clicked.',

    'arch.privacy.title': 'Data protection switches',
    'arch.privacy.text':
      'Logging can be switched off item by item in `01-base/privacy-config.yaml` '
      + '(studio area “Data protection”):',
    'arch.privacy.messages': '`logging.messages` — chat histories',
    'arch.privacy.memory': '`logging.memory` — session memory',
    'arch.privacy.quality': '`logging.quality` — quality analytics',
    'arch.privacy.safety': '`logging.safety` — *always on* (required for audits)',
    'arch.privacy.purge':
      'On top of that the purge endpoints delete existing data, and snapshots secure '
      + 'the configuration without any up- or download.',
  },
};
