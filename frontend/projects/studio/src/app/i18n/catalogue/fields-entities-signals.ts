/**
 * Feldtexte (ST-1) der Seite „Dimensionen", Bereiche Entitäten
 * (`04-entities/entities`) und Signale (`04-signals/signal-modulations`).
 *
 * Schlüsselschema wie in allen `fields-*.ts` (siehe `fields-layer-doc.ts`).
 * Entitäten und Signale liefert nur der Klassifikator der Muster-Engine
 * (`services/classify_prompt_blocks.py`, `services/classify_prompt.py`); die
 * Agent-Schleife hat keinen (`graph/nodes/assess.py`). Nicht ausgewertet werden
 * `type` und `examples` einer Entität, die Übernahme-Regeln (die Regeln je
 * Gesprächszug stehen fest in `graph/nodes/merge.py`) sowie Name, `show_more`
 * und `show_overview` eines Signals: `services/config_loader/classification.py`
 * reicht den Namen nicht weiter, die beiden Schalter liest niemand. Ein
 * gespeicherter Ton oder eine Länge ersetzt den Wert der Antwort auch dann,
 * wenn er leer ist (`domain/pattern_engine.phase3_modulate`).
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_ENTITIES_SIGNALS: CataloguePart = {
  de: {
    // ── Entitäten ───────────────────────────────────────────────────
    'feld.EntitiesArea.entities.label': 'Entitäten',
    'feld.EntitiesArea.entities.hint':
      'Die Angaben, die der Klassifikator aus Nachrichten herausliest, etwa Fach, Thema oder '
      + 'Bildungsstufe. Sie steuern Suche, Rückfragen und Materialerstellung. Nur Muster-Engine: '
      + 'die Agent-Schleife hat keinen Klassifikator.',
    'feld.EntitiesArea.accumulation_rules.label': 'Übernahme-Regeln',
    'feld.EntitiesArea.accumulation_rules.hint':
      'Wie erkannte Werte je Art des Gesprächszugs übernommen werden, etwa correction: '
      + 'overwrite. Nur beschreibend: diese Regeln stehen fest im Code.',
    'feld.EntityDef.id.label': 'Kennung',
    'feld.EntityDef.id.hint':
      'Name der Angabe, etwa thema oder fach. Unter ihm legt der Klassifikator den Wert ab; '
      + 'Code und Muster-Vorbedingungen lesen ihn. Umbenennen bricht diese Verweise.',
    'feld.EntityDef.label.label': 'Anzeigename',
    'feld.EntityDef.label.hint':
      'Lesbarer Name, etwa Bildungsstufe. Steht im Klassifikator-Prompt nur, wenn die '
      + 'Beschreibung leer ist; sonst dient er den Auswahllisten im Studio.',
    'feld.EntityDef.type.label': 'Datentyp',
    'feld.EntityDef.type.hint': 'Datentyp des Werts, meist string. Wird derzeit nicht ausgewertet.',
    'feld.EntityDef.description.label': 'Beschreibung',
    'feld.EntityDef.description.hint':
      'Was die Angabe meint und wie sie zu füllen ist, etwa „Klasse 5–10 = Sekundarstufe I". '
      + 'Steht einzeilig im Klassifikator-Prompt.',
    'feld.EntityDef.examples.label': 'Beispielwerte',
    'feld.EntityDef.examples.hint':
      'Typische Werte, etwa Mathematik oder Deutsch. Wird derzeit nicht ausgewertet: im Prompt '
      + 'stehen nur Positiv- und Negativbeispiele.',
    'feld.EntityDef.positive_examples.label': 'Positivbeispiele',
    'feld.EntityDef.positive_examples.hint':
      'Sätze mit erwartetem Wert, je text und value. Die ersten acht stehen im '
      + 'Klassifikator-Prompt; Einträge ohne beides fehlen dort.',
    'feld.EntityDef.negative_examples.label': 'Negativbeispiele',
    'feld.EntityDef.negative_examples.hint':
      'Sätze, in denen die Angabe leer bleiben muss, je text und rationale (Begründung). Die '
      + 'ersten zwölf stehen im Klassifikator-Prompt.',
    'feld.EntityDef.discriminators.label': 'Abgrenzungen',
    'feld.EntityDef.discriminators.hint':
      'Regeln gegen Verwechslung mit einer anderen Angabe: vs (deren Kennung) und rule '
      + '(Faustregel). Die ersten acht stehen im Klassifikator-Prompt; example_a und example_b '
      + 'nicht.',

    // ── Signale ─────────────────────────────────────────────────────
    'feld.SignalModulationsArea.signals.label': 'Signale',
    'feld.SignalModulationsArea.signals.hint':
      'Hinweise auf Lage und Haltung der Person, die der Klassifikator erkennen kann (Schlüssel '
      + '= Kennung, etwa zeitdruck), je mit Änderungen an der Antwort. Nur Muster-Engine: die '
      + 'Agent-Schleife erkennt keine.',
    'feld.SignalModulationsArea.reduce_items_signals.label': 'Signale für weniger Treffer',
    'feld.SignalModulationsArea.reduce_items_signals.hint':
      'Signal-Kennungen, etwa ungeduldig oder gestresst: wird eines erkannt, sind höchstens '
      + 'drei Ergebnisse vorgesehen statt des Gerätewerts.',
    'feld.SignalDef.dimension.label': 'Gruppe',
    'feld.SignalDef.dimension.hint':
      'Gruppe des Signals, etwa D1-Zeit. Der Klassifikator-Prompt listet die Kennungen nach '
      + 'Gruppen geordnet; darüber hinaus wirkt sie nicht.',
    'feld.SignalDef.label.label': 'Anzeigename',
    'feld.SignalDef.label.hint':
      'Lesbarer Name, etwa Zeitdruck. Nur beschreibend: der Klassifikator sieht allein die '
      + 'Kennung.',
    'feld.SignalDef.tone.label': 'Ton',
    'feld.SignalDef.tone.hint':
      'Ton der Antwort, wenn das Signal erkannt wird, etwa sachlich oder empathisch; ersetzt '
      + 'den Ton aus Persona und Muster. Achtung: auch ein leer gespeicherter Wert ersetzt ihn.',
    'feld.SignalDef.length.label': 'Länge',
    'feld.SignalDef.length.hint':
      'Länge der Antwort bei diesem Signal: kurz, mittel oder lang; ersetzt die Länge aus '
      + 'Muster und Persona. Achtung: auch ein leer gespeicherter Wert ersetzt sie.',
    'feld.SignalDef.skip_intro.label': 'Ohne Einleitung',
    'feld.SignalDef.skip_intro.hint':
      'An: der Antwort-Prompt bekommt die Regel „Keine Einleitung. Direkt zur Sache."',
    'feld.SignalDef.one_option.label': 'Nur eine Option',
    'feld.SignalDef.one_option.hint':
      'An: der Antwort-Prompt verlangt, nur eine Option anzubieten, um nicht zu überfordern.',
    'feld.SignalDef.show_more.label': 'Mehr zeigen',
    'feld.SignalDef.show_more.hint':
      'Wird derzeit nicht ausgewertet: der Wert gelangt in die Musterausgabe, aber kein Prompt '
      + 'und keine Anzeige liest ihn.',
    'feld.SignalDef.add_sources.label': 'Quellen nennen',
    'feld.SignalDef.add_sources.hint':
      'An: der Antwort-Prompt verlangt, Quellen und Herkunft ausdrücklich zu nennen.',
    'feld.SignalDef.show_overview.label': 'Überblick zeigen',
    'feld.SignalDef.show_overview.hint':
      'Wird derzeit nicht ausgewertet: der Wert gelangt in die Musterausgabe, aber kein Prompt '
      + 'und keine Anzeige liest ihn.',
  },
  en: {
    // ── Entities ────────────────────────────────────────────────────
    'feld.EntitiesArea.entities.label': 'Entities',
    'feld.EntitiesArea.entities.hint':
      'The details the classifier reads from messages, such as subject, topic or education '
      + 'level. They drive search, follow-up questions and material creation. Pattern engine '
      + 'only: the agent loop has no classifier.',
    'feld.EntitiesArea.accumulation_rules.label': 'Carry-over rules',
    'feld.EntitiesArea.accumulation_rules.hint':
      'How recognised values are carried over per kind of turn, such as correction: '
      + 'overwrite. Descriptive only: these rules are fixed in the code.',
    'feld.EntityDef.id.label': 'Identifier',
    'feld.EntityDef.id.hint':
      'Name of the detail, such as thema or fach. The classifier stores the value under it; '
      + 'code and pattern preconditions read it. Renaming breaks these references.',
    'feld.EntityDef.label.label': 'Display name',
    'feld.EntityDef.label.hint':
      'Readable name, such as Bildungsstufe. Goes into the classifier prompt only when the '
      + 'description is empty; otherwise it serves the selection lists in the Studio.',
    'feld.EntityDef.type.label': 'Data type',
    'feld.EntityDef.type.hint': 'Data type of the value, usually string. Currently not evaluated.',
    'feld.EntityDef.description.label': 'Description',
    'feld.EntityDef.description.hint':
      'What the detail means and how to fill it, such as "Klasse 5–10 = Sekundarstufe I". '
      + 'Goes into the classifier prompt as a single line.',
    'feld.EntityDef.examples.label': 'Example values',
    'feld.EntityDef.examples.hint':
      'Typical values, such as Mathematik or Deutsch. Currently not evaluated: only the '
      + 'positive and negative examples go into the prompt.',
    'feld.EntityDef.positive_examples.label': 'Positive examples',
    'feld.EntityDef.positive_examples.hint':
      'Sentences with the expected value, each with text and value. The first eight go into '
      + 'the classifier prompt; entries lacking either are left out.',
    'feld.EntityDef.negative_examples.label': 'Negative examples',
    'feld.EntityDef.negative_examples.hint':
      'Sentences in which the detail must stay empty, each with text and rationale (reason). '
      + 'The first twelve go into the classifier prompt.',
    'feld.EntityDef.discriminators.label': 'Distinctions',
    'feld.EntityDef.discriminators.hint':
      'Rules against confusion with another detail: vs (its identifier) and rule (rule of '
      + 'thumb). The first eight go into the classifier prompt; example_a and example_b do not.',

    // ── Signals ─────────────────────────────────────────────────────
    'feld.SignalModulationsArea.signals.label': 'Signals',
    'feld.SignalModulationsArea.signals.hint':
      'Hints about the situation and attitude of the person that the classifier can recognise '
      + '(key = identifier, such as zeitdruck), each with changes to the answer. Pattern engine '
      + 'only: the agent loop recognises none.',
    'feld.SignalModulationsArea.reduce_items_signals.label': 'Signals for fewer results',
    'feld.SignalModulationsArea.reduce_items_signals.hint':
      'Signal identifiers, such as ungeduldig or gestresst: if one is recognised, at most three '
      + 'results are intended instead of the device value.',
    'feld.SignalDef.dimension.label': 'Group',
    'feld.SignalDef.dimension.hint':
      'Group of the signal, such as D1-Zeit. The classifier prompt lists the identifiers '
      + 'grouped by it; beyond that it has no effect.',
    'feld.SignalDef.label.label': 'Display name',
    'feld.SignalDef.label.hint':
      'Readable name, such as Zeitdruck. Descriptive only: the classifier sees the identifier '
      + 'alone.',
    'feld.SignalDef.tone.label': 'Tone',
    'feld.SignalDef.tone.hint':
      'Tone of the answer when the signal is recognised, such as sachlich or empathisch; '
      + 'replaces the tone from persona and pattern. Note: a value saved as empty replaces it too.',
    'feld.SignalDef.length.label': 'Length',
    'feld.SignalDef.length.hint':
      'Length of the answer for this signal: kurz, mittel or lang; replaces the length from '
      + 'pattern and persona. Note: a value saved as empty replaces it too.',
    'feld.SignalDef.skip_intro.label': 'Skip introduction',
    'feld.SignalDef.skip_intro.hint':
      'On: the answer prompt gets a rule to skip the introduction and get straight to the point.',
    'feld.SignalDef.one_option.label': 'Single option',
    'feld.SignalDef.one_option.hint':
      'On: the answer prompt asks to offer only one option, so as not to overwhelm.',
    'feld.SignalDef.show_more.label': 'Show more',
    'feld.SignalDef.show_more.hint':
      'Currently not evaluated: the value reaches the pattern output, but no prompt and no '
      + 'display reads it.',
    'feld.SignalDef.add_sources.label': 'Cite sources',
    'feld.SignalDef.add_sources.hint':
      'On: the answer prompt asks to name sources and origin explicitly.',
    'feld.SignalDef.show_overview.label': 'Show overview',
    'feld.SignalDef.show_overview.hint':
      'Currently not evaluated: the value reaches the pattern output, but no prompt and no '
      + 'display reads it.',
  },
};
