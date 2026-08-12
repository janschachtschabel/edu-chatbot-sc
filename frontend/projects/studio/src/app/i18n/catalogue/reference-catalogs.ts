/**
 * Die beiden Referenz-Kataloge (C1-d5c2): Signal-Modulationen und
 * Material-Typen.
 *
 * **Was hier NICHT steht, ist der Punkt.** Beide Tabellen kommen aus der
 * laufenden Konfiguration. Übersetzt wird ausschliesslich, was diese Ansicht
 * selbst sagt; `effizient`, `kurz`, `sachlich`, `D1-Zeit` sind gepflegte Werte
 * und bleiben, wie sie gepflegt sind.
 *
 * **Die Flag-Wörter tragen den dokumentierten Durchfall weiter.**
 * `reference-catalogs.ts` verspricht: „a flag added to the config must show up
 * here without a code change". Bis C1-d5c2 hielt das eine Abbildung
 * `FLAG_LABELS[key] ?? key`; jetzt hält es dieselbe Abbildung auf
 * Katalog-Schlüssel — und `createTranslator` gibt einen unbekannten Schlüssel
 * als sich selbst zurück (`active[key] ?? fallback[key] ?? key`). Das Versprechen
 * überlebt die Umstellung ohne eine Zeile Zusatzcode; gepinnt in beiden
 * Sprachen, weil es sonst an der Vorgabesprache hinge.
 */
import type { CataloguePart } from './catalogue-part';

export const REFERENCE_CATALOGS: CataloguePart = {
  de: {
    'rc.signals.title': 'Signal-Dimensionen im Detail',
    'rc.signals.text':
      'Signale erkennen die situative Lage der Nutzerin; mehrere können '
      + 'gleichzeitig aktiv sein. Diese Tabelle kommt aus der laufenden '
      + 'Konfiguration (`04-signals/signal-modulations.yaml`) — sie ist keine '
      + 'Beschreibung der Konfiguration, sondern die Konfiguration.',
    'rc.signals.empty':
      'Die Signale stehen hier, sobald die Übersicht sie aus der Konfiguration '
      + 'geladen hat.',
    'rc.signals.combine':
      '*Wie mehrere Signale zusammenwirken:* die Modulationen werden der Reihe '
      + 'nach angewendet — bei widersprüchlichen Angaben gewinnt schlicht das '
      + '*letzte* Signal der Liste (`pattern_engine.py`, „Apply signal '
      + 'modulations"). Eine Regel „kürzere Länge gewinnt" gibt es nicht. Richtig '
      + 'ist die andere Hälfte: Signale überschreiben die Pattern-Defaults, nicht '
      + 'umgekehrt. Und `reduce_items_signals` *deckelt* `max_items` auf 3 — es '
      + 'halbiert nicht.',

    // Die Wörter für die Flags, die die Engine heute kennt. Ein neues Flag in
    // der Konfiguration erscheint ohne Code-Änderung als sein eigener
    // Schlüssel — siehe Dateikopf.
    'rc.flag.skipIntro': 'ohne Einleitung',
    'rc.flag.oneOption': 'nur ein Vorschlag',
    'rc.flag.addSources': 'mit Quellen',
    'rc.flag.showMore': 'ohne Rückfrage-Vorschlag',
    'rc.flag.showOverview': 'mit Überblick',

    'rc.mat.title': 'Material-Typen',
    'rc.mat.text':
      'Schicht 5 (`{area}`) legt fest, welche Ausgabeformate die '
      + 'Material-Erstellung anbietet. Bei `auto` wählt das Modell selbst — der '
      + 'Eintrag ist ein Selektor, kein Typ, und wird deshalb hier getrennt '
      + 'gezählt.',
    'rc.mat.loading': 'Material-Typen werden geladen …',
    /** Zwei fertige Wortgruppen, kein Satz — wie `ltRun.totals`. */
    'rc.mat.caption': '{entries} · {types}',
    'rc.mat.entries.one': '{count} Eintrag',
    'rc.mat.entries.other': '{count} Einträge',
    'rc.mat.types.one': '{count} Typ',
    'rc.mat.types.other': '{count} Typen',
    'rc.mat.col.category': 'Kategorie',
    'rc.mat.col.id': 'ID',
    'rc.mat.col.label': 'Bezeichnung',
    /** Die beiden Kategorien, die der Code kennt: sie sind hier Anzeigetext,
     *  in `splitMaterialTypes` aber Filterwert. Übersetzt wird nur die Anzeige
     *  — der Vergleich läuft weiter gegen den Konfigurationswert. */
    'rc.cat.didaktisch': 'didaktisch',
    'rc.cat.analytisch': 'analytisch',
    /** Die beiden Beispiele bleiben deutsch, auch im englischen Satz: es SIND
     *  die deutschen Auslöser aus der Konfiguration, keine Übersetzung. */
    'rc.mat.aliases':
      'Aliase („Lernblatt" → `arbeitsblatt`) stehen in '
      + '`05-canvas/create-triggers.yaml`, Bearbeitungs-Auslöser („mach es '
      + 'kürzer") in `05-canvas/edit-triggers.yaml`.',
  },

  en: {
    'rc.signals.title': 'The signal dimensions in detail',
    'rc.signals.text':
      'Signals recognise the situation a user is in; several can be active at '
      + 'once. This table comes from the running configuration '
      + '(`04-signals/signal-modulations.yaml`) — it is not a description of the '
      + 'configuration, it is the configuration.',
    'rc.signals.empty':
      'The signals appear here as soon as the overview has loaded them from the '
      + 'configuration.',
    'rc.signals.combine':
      '*How several signals interact:* the modulations are applied in order — '
      + 'where they contradict each other, the *last* signal in the list simply '
      + 'wins (`pattern_engine.py`, “Apply signal modulations”). There is no rule '
      + 'that the shorter length wins. The other half is true: signals override '
      + 'the pattern defaults, not the other way round. And '
      + '`reduce_items_signals` *caps* `max_items` at 3 — it does not halve it.',

    'rc.flag.skipIntro': 'without an introduction',
    'rc.flag.oneOption': 'one suggestion only',
    'rc.flag.addSources': 'with sources',
    'rc.flag.showMore': 'without a follow-up suggestion',
    'rc.flag.showOverview': 'with an overview',

    'rc.mat.title': 'Material types',
    'rc.mat.text':
      'Layer 5 (`{area}`) determines which output formats the material creation '
      + 'offers. With `auto` the model chooses for itself — that entry is a '
      + 'selector rather than a type, and is therefore counted separately here.',
    'rc.mat.loading': 'Loading the material types …',
    'rc.mat.caption': '{entries} · {types}',
    'rc.mat.entries.one': '{count} entry',
    'rc.mat.entries.other': '{count} entries',
    'rc.mat.types.one': '{count} type',
    'rc.mat.types.other': '{count} types',
    'rc.mat.col.category': 'Category',
    'rc.mat.col.id': 'ID',
    'rc.mat.col.label': 'Label',
    'rc.cat.didaktisch': 'didactic',
    'rc.cat.analytisch': 'analytic',
    /** Die beiden Beispiele sind deutsche Auslöser aus der Konfiguration und
     *  bleiben es auch hier — übersetzt wären sie schlicht falsch. Der
     *  englische Satz zitiert `knapper` statt `mach es kürzer`: beides steht
     *  wörtlich in `edit-triggers.yaml`, aber der Umlaut-Wächter dieses
     *  Katalogs kennt keine Ausnahmen, und ihn für ein Beispiel aufzuweichen
     *  wäre teurer als ein zweites, gleichwertiges Beispiel. */
    'rc.mat.aliases':
      'Aliases (“Lernblatt” → `arbeitsblatt`) are in '
      + '`05-canvas/create-triggers.yaml`, editing triggers (“knapper”) in '
      + '`05-canvas/edit-triggers.yaml`.',
  },
};
