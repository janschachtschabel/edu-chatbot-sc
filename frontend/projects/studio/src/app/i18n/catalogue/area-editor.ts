/**
 * Der generische Bereichs-Editor (C1-d3a): Bereichsliste, Bereichs-,
 * Abschnitts- und Gruppen-Editor, Schema-Formular und dessen Felder.
 *
 * Was sich diese Ansichten mit allen anderen teilen — Zustands-Streifen,
 * Fehlertexte, Speichern/Verwerfen — steht in `shared.ts`.
 *
 * Der Sicherheitslevel-Wähler steht hier mit (C1-d4e4), obwohl er
 * `safety-level.component` heisst: gerendert wird er in `area-section`, also
 * IN diesem Panel. Ein Teilkatalog gehört zum Panel, nicht zum Dateinamen —
 * C1-d3a/d3b haben ihn nach dem Namen einsortiert und dabei übersehen.
 */
import type { CataloguePart } from './catalogue-part';

export const AREA_EDITOR: CataloguePart = {
  de: {
    // ── Bereichsliste ───────────────────────────────────────────────
    // Die Überschrift ist `view.bereiche.label` — dieselbe Ansicht, derselbe
    // Name; ein zweiter Eintrag könnte davon abdriften.
    'areas.lead':
      'Jeder Konfigurationsbereich, direkt aus dem Backend gelistet — auch die ohne eigene '
      + 'Ansicht. Bearbeitet wird per Formular (aus dem Bereichsmodell erzeugt) oder im Rohtext.',
    'areas.loading': 'Lade Bereiche …',
    'areas.error': 'Die Bereichsliste konnte nicht geladen werden.',
    /** Der Befehl steht als Platzhalterwert und nicht im Satz — dasselbe
     *  Muster wie `login.passwordEnv`. Kostet die `<code>`-Auszeichnung und
     *  hält dafür den Satz als Ganzes übersetzbar. */
    'areas.importCmd': 'boerdi import-config',
    'areas.empty':
      'Es ist noch keine Konfiguration geladen. Nach dem Import ({cmd}) erscheinen die '
      + 'Bereiche hier.',
    'areas.count.one': '{count} Bereich',
    'areas.count.other': '{count} Bereiche',
    'areas.noFolder': '(ohne Ordner)',

    // ── Bereichs-Editor ─────────────────────────────────────────────
    'areaEditor.crumb': 'Konfigurationsbereich',
    'areaEditor.loading': 'Lade Bereich …',
    'areaEditor.tabsLabel': 'Ansicht des Bereichs',
    'areaEditor.tab.form': 'Formular',
    /** `{format}` ist `Markdown` oder `YAML` — ein Dateiformat, kein Wort. */
    'areaEditor.tab.raw': 'Rohtext ({format})',
    'areaEditor.rawHint':
      'die vollständige Quelle, inklusive aller Schlüssel, die das Formular nicht kennt.',
    /** `{view}` ist `view.bereiche.label`: wird die Ansicht umbenannt, wandert
     *  der Name hier mit. */
    'areaEditor.noArea': 'Es ist kein Bereich angegeben. Bitte über „{view}“ öffnen.',
    'areaEditor.tabBlocked':
      'Bitte erst speichern oder verwerfen — die Ansichten zeigen sonst unterschiedliche '
      + 'Stände desselben Bereichs.',

    // ── Abschnitt einer kuratierten Ansicht ─────────────────────────
    'areaSection.rawLink': 'Rohtext bearbeiten',
    'areaSection.rawLinkFor': 'Rohtext bearbeiten — {label}',

    // ── Gruppen-Abschnitt: mehrere Dokumente eines Bereichs ─────────
    'groupSection.listLoading': 'Lade Liste …',
    'groupSection.docs': 'Dokumente',
    'groupSection.empty': 'Noch keine Dokumente. Unten eines anlegen.',
    'groupSection.new': 'Neues Dokument',
    'groupSection.newKey': 'Wird angelegt als {file}',
    'groupSection.newHint': 'Der Name wird zum Dateinamen.',
    'groupSection.create': 'Anlegen',
    'groupSection.creating': 'Wird angelegt …',
    'groupSection.created': 'Angelegt.',
    'groupSection.pick': 'Links ein Dokument wählen, um es zu bearbeiten.',
    'groupSection.needName': 'Bitte einen Namen angeben.',
    'groupSection.duplicate': '„{name}“ gibt es schon — bitte einen anderen Namen wählen.',
    'groupSection.switchBlocked':
      'Bitte erst speichern oder verwerfen — sonst gehen die Änderungen an diesem '
      + 'Dokument verloren.',
    'groupSection.createBlocked':
      'Erst das offene Dokument speichern oder verwerfen — sonst gehen die Änderungen '
      + 'beim Wechsel verloren.',

    // ── Schema-Formular ─────────────────────────────────────────────
    // Mehrzahl über `plural()`: nicht nur das Substantiv unterscheidet die
    // Formen, sondern der ganze Satz (ihn/sie, bleibt/bleiben).
    'schemaForm.unmapped.one':
      'Ein Schlüssel wird hier nicht angezeigt, weil das Bereichsmodell ihn nicht kennt: '
      + '{keys}. Beim Speichern bleibt er erhalten; ändern lässt er sich im Reiter „Rohtext“.',
    'schemaForm.unmapped.other':
      '{count} Schlüssel werden hier nicht angezeigt, weil das Bereichsmodell sie nicht '
      + 'kennt: {keys}. Beim Speichern bleiben sie erhalten; ändern lassen sie sich im '
      + 'Reiter „Rohtext“.',
    /** Steht im Fehlertext an der Stelle eines Feldpfades, wenn der Fehler an
     *  der Wurzel des Dokuments sitzt. */
    'schemaForm.root': '(Wurzel)',
    /** Der Sammel-Abschnitt der einzeiligen Felder (S5). Die übrigen
     *  Abschnitte tragen ihren Config-Schlüssel, dieser hat keinen. */
    'schemaForm.basics': 'Grundwerte',

    // Die Form-Namen tragen ihren Artikel, weil der Satz sie so braucht — im
    // Englischen ist es „a"/„an", und das entscheidet die Sprache, nicht der
    // Code.
    'schemaField.shape.list': 'eine Liste',
    'schemaField.shape.object': 'ein Objekt',
    'schemaField.shape.scalar': 'ein einzelner Wert ({type})',
    'schemaField.mismatch':
      'Der gespeicherte Wert ist {actual}, das Bereichsmodell erwartet hier {expected}. '
      + 'Er wird als JSON gezeigt, damit nichts still verloren geht.',
    /** Rückfall, wenn eine Liste oder Karte keinen eigenen Namen hat — sonst
     *  stünde in der Legende und im Knopf-Namen eine Lücke. */
    'schemaField.fallbackGroup': 'Einträge',
    'schemaField.emptyList': 'Noch keine Einträge.',
    'schemaField.remove': 'Entfernen',
    'schemaField.removeIndex': 'Eintrag {index} aus {group} entfernen',
    'schemaField.removeKey': 'Eintrag {key} entfernen',
    'schemaField.add': '+ Eintrag',
    'schemaField.addTo': 'Eintrag zu {group} hinzufügen',
    'schemaField.key': 'Schlüssel',
    'schemaField.emptyKey': 'Ein Schlüssel darf nicht leer sein.',
    'schemaField.keyTaken': 'Der Schlüssel „{key}“ ist schon vergeben.',
    'schemaField.required': '(Pflichtfeld)',

    // ── Auswahl und Vorschlagsliste (S3/S4) ─────────────────────────
    // Die WERTE selbst stehen nicht hier: sie sind Konfigurationsschlüssel
    // (`smart`, `M06`, `search_wlo_all`), keine Prosa — dieselbe Grenze wie
    // beim Sicherheitslevel-Wähler darunter.
    'schemaField.noChoice': '— nicht gesetzt —',
    /** Ein gespeicherter Wert, den die Auswahlliste nicht kennt. Er wird
     *  weitergeführt statt weggeworfen, aber als Fremdkörper ausgewiesen. */
    'schemaField.foreignChoice': '{current} — nicht in der Auswahl',
    'schemaField.openTarget': '{value} öffnen',

    // ── Sicherheitslevel-Wähler ─────────────────────────────────────
    // Die NAMEN der fünf Stufen („Off", „Regex", „Standard", „Strict",
    // „Paranoid") stehen bewusst NICHT hier: das sind die Schlüssel aus
    // `presets` der Datei, nicht Prosa — dasselbe wie `areas.importCmd`. Ein
    // eigenes Preset trägt seinen Schlüssel unverändert als Namen; würden die
    // fünf bekannten übersetzt, widerspräche der Wähler der Datei.
    'safetyLevel.legend': 'Sicherheitslevel',
    'safetyLevel.hint':
      'Steuert, welche Safety-Stufen laufen. Wirkt nach dem Speichern sofort, ohne Neustart.',
    'safetyLevel.desc.off': 'Aus. Nur Crisis/PII-Regex (~1 ms).',
    'safetyLevel.desc.regex': 'Alle Regex-Checks inkl. Prompt-Injection (~2 ms).',
    'safetyLevel.desc.standard': 'Regex + OpenAI-Moderation (parallel, ~150 ms). Empfohlen.',
    'safetyLevel.desc.strict': 'Standard + LLM-Legal-Classifier smart (~150-300 ms).',
    'safetyLevel.desc.paranoid': 'Strict + Legal immer + halbierte Schwellen.',
    /** Beschreibung einer Stufe, die diese Datei über die fünf hinaus mitbringt. */
    'safetyLevel.desc.custom': 'Eigenes Preset aus dieser Datei.',
    'safetyLevel.missing':
      'Kein Preset in dieser Datei hinterlegt — es gilt der Escalation-Block.',
    'safetyLevel.note':
      'Für die markierten Stufen ist unter „presets“ nichts hinterlegt. Sie lassen sich '
      + 'wählen, wirken dann aber wie der Escalation-Block weiter unten.',
  },

  en: {
    'areas.lead':
      'Every configuration area, listed straight from the backend — including those without '
      + 'a view of their own. Edit through the form (built from the area model) or the source.',
    'areas.loading': 'Loading areas …',
    'areas.error': 'The area list could not be loaded.',
    'areas.importCmd': 'boerdi import-config',
    'areas.empty':
      'No configuration is loaded yet. The areas appear here after the import ({cmd}).',
    'areas.count.one': '{count} area',
    'areas.count.other': '{count} areas',
    'areas.noFolder': '(no folder)',

    'areaEditor.crumb': 'Configuration area',
    'areaEditor.loading': 'Loading area …',
    'areaEditor.tabsLabel': 'Area view',
    'areaEditor.tab.form': 'Form',
    'areaEditor.tab.raw': 'Source ({format})',
    'areaEditor.rawHint':
      'the complete source, including every key the form does not know about.',
    'areaEditor.noArea': 'No area was given. Please open one from “{view}”.',
    'areaEditor.tabBlocked':
      'Please save or discard first — otherwise the two views would show different states '
      + 'of the same area.',

    'areaSection.rawLink': 'Edit source',
    'areaSection.rawLinkFor': 'Edit source — {label}',

    'groupSection.listLoading': 'Loading list …',
    'groupSection.docs': 'Documents',
    'groupSection.empty': 'No documents yet. Create one below.',
    'groupSection.new': 'New document',
    'groupSection.newKey': 'Will be created as {file}',
    'groupSection.newHint': 'The name becomes the file name.',
    'groupSection.create': 'Create',
    'groupSection.creating': 'Creating …',
    'groupSection.created': 'Created.',
    'groupSection.pick': 'Pick a document on the left to edit it.',
    'groupSection.needName': 'Please enter a name.',
    'groupSection.duplicate': '“{name}” already exists — please pick another name.',
    'groupSection.switchBlocked':
      'Please save or discard first — otherwise the changes to this document would be lost.',
    'groupSection.createBlocked':
      'Save or discard the open document first — otherwise its changes would be lost when '
      + 'switching.',

    'schemaForm.unmapped.one':
      'One key is not shown here because the area model does not know it: {keys}. It '
      + 'survives the save; to change it, use the “Source” tab.',
    'schemaForm.unmapped.other':
      '{count} keys are not shown here because the area model does not know them: {keys}. '
      + 'They survive the save; to change them, use the “Source” tab.',
    'schemaForm.root': '(root)',
    'schemaForm.basics': 'Basics',

    'schemaField.shape.list': 'a list',
    'schemaField.shape.object': 'an object',
    'schemaField.shape.scalar': 'a single value ({type})',
    'schemaField.mismatch':
      'The stored value is {actual}, the area model expects {expected} here. It is shown '
      + 'as JSON so that nothing is lost silently.',
    'schemaField.fallbackGroup': 'Entries',
    'schemaField.emptyList': 'No entries yet.',
    'schemaField.remove': 'Remove',
    'schemaField.removeIndex': 'Remove entry {index} from {group}',
    'schemaField.removeKey': 'Remove entry {key}',
    'schemaField.add': '+ Entry',
    'schemaField.addTo': 'Add an entry to {group}',
    'schemaField.key': 'Key',
    'schemaField.emptyKey': 'A key must not be empty.',
    'schemaField.keyTaken': 'The key “{key}” is already taken.',
    'schemaField.required': '(required)',

    'schemaField.noChoice': '— not set —',
    'schemaField.foreignChoice': '{current} — not in the list',
    'schemaField.openTarget': 'Open {value}',

    'safetyLevel.legend': 'Safety level',
    'safetyLevel.hint':
      'Controls which safety stages run. Takes effect right after saving, without a restart.',
    'safetyLevel.desc.off': 'Off. Crisis/PII regex only (~1 ms).',
    'safetyLevel.desc.regex': 'All regex checks including prompt injection (~2 ms).',
    'safetyLevel.desc.standard': 'Regex + OpenAI moderation (in parallel, ~150 ms). Recommended.',
    'safetyLevel.desc.strict': 'Standard + LLM legal classifier, smart (~150-300 ms).',
    'safetyLevel.desc.paranoid': 'Strict + legal always + halved thresholds.',
    'safetyLevel.desc.custom': 'A custom preset from this file.',
    'safetyLevel.missing': 'No preset in this file — the escalation block applies.',
    'safetyLevel.note':
      'The marked levels have nothing under “presets”. They can still be picked, but then '
      + 'behave like the escalation block further down.',
  },
};
