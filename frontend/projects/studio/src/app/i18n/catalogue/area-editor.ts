/**
 * Der generische Bereichs-Editor (C1-d3a): Bereichsliste, Bereichs- und
 * Abschnitts-Editor, Schema-Formular und dessen Felder. Der Gruppen-Abschnitt
 * (Muster, Personas) steht seit Paket 6 in `group-section.ts`.
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
    'areaEditor.zurueckNav': 'Zurück',
    'areaEditor.zurueckZu': '← Zurück zu „{seite}“',
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
    // Paket 4c, B2: Listen, bei denen „nicht gesetzt“ die Vorgabe heißt (`x-vorgabe`).
    'schemaField.unset': 'Nicht gesetzt – es gilt die Vorgabe.',
    'schemaField.restoreDefault': 'Vorgabe wiederherstellen',
    'schemaField.vorgabe': 'Vorgabe',
    'schemaField.nurBei': '„{feld}“ wirkt beim gewählten Wert von „{nachbar}“ nicht – der Wert bleibt gespeichert.',
    'schemaField.nurBeiEntfernen': 'Wert entfernen',
    'schemaField.nurBeiLeer': '„{feld}“ wirkt beim gewählten Wert von „{nachbar}“ nicht.',
    'jsonValue.ungueltig': 'Kein gültiges JSON — noch nicht übernommen.',
    // Paket K2c-4: „Ablauf prüfen“ und die Schrittfolge unter einem Ablauf
    'ablaufPruefen.titel': 'Prüfen und Schrittfolge',
    'ablaufPruefen.knopf': 'Ablauf prüfen',
    'ablaufPruefen.erneut': 'Erneut prüfen',
    'ablaufPruefen.laeuft': 'Wird geprüft …',
    'ablaufPruefen.ok': 'Keine Befunde.',
    'ablaufPruefen.befunde.one': '{count} Befund — an den Schritten markiert.',
    'ablaufPruefen.befunde.other': '{count} Befunde — an den Schritten markiert.',
    'ablaufPruefen.form.one': 'Der Entwurf passt noch nicht zum Modell — {count} Stelle (hier genannt und am Feld markiert):',
    'ablaufPruefen.form.other': 'Der Entwurf passt noch nicht zum Modell — {count} Stellen (hier genannt und am Feld markiert):',
    'ablaufPruefen.fehler': 'Prüfen ging nicht: {detail}',
    'ablaufPruefen.veraltet': 'Geändert seit der Prüfung — bitte erneut prüfen.',
    'ablaufPruefen.folge': 'Schrittfolge (aus dem Entwurf, nur lesend):',
    'ablaufPruefen.keineSchritte': 'Noch keine Schritte.',
    'ablaufPruefen.ohneKennung': '(ohne Kennung)',
    'ablaufPruefen.endetHier': 'Endet hier.',
    'ablaufPruefen.weiter': '→ {ziel}',
    'ablaufPruefen.beiFehler': 'bei Fehler → {ziel}',
    'ablaufPruefen.sonst': 'sonst → {ziel}',
    'ablaufPruefen.regel': 'wenn {wenn} → {ziel}',
    'ablaufPruefen.wennTeil': 'Teil „{teil}“ da',
    'ablaufPruefen.wennGewaehlt': '„{wahl}“ gewählt',
    'ablaufPruefen.ohneBedingung': '(keine Bedingung)',
    'ablaufPruefen.keineGreift': 'greift keine Regel → {ziel}',
    'ablaufPruefen.laeuftAus': '(Ende ohne „ende“-Schritt)',
    'ablaufPruefen.unbekannt': '— diesen Schritt gibt es nicht',
    'teilWerte.leer': 'Noch keine Einträge.',
    'teilWerte.pfadHinweis':
      'Ein Teil kann eine Stelle darin meinen: Name und Pfad mit Punkt, etwa volltext.outputs.markdown.',
    'teilWerte.name': 'Name {n}',
    'teilWerte.art': 'Art von Zeile {n}',
    'teilWerte.art.text': 'Text',
    'teilWerte.art.teil': 'Teil',
    'teilWerte.art.json': 'JSON',
    'teilWerte.wert': 'Wert {n}',
    'teilWerte.teil': 'Teil für Zeile {n}',
    'teilWerte.weg': 'Entfernen',
    'teilWerte.entfernen': 'Zeile {n} ({name}) entfernen',
    'teilWerte.entfernenOhneName': 'Zeile {n} entfernen',
    'teilWerte.spalte.name': 'Name',
    'teilWerte.spalte.art': 'Art',
    'teilWerte.spalte.wert': 'Wert',
    'teilWerte.neu': 'Eintrag hinzufügen',
    'teilWerte.alsJson': 'Als JSON bearbeiten',
    'teilWerte.alsTabelle': 'Als Tabelle bearbeiten',
    'teilWerte.fehler.name_leer': 'Zeile {zeile}: Name fehlt — noch nicht übernommen.',
    'teilWerte.fehler.name_doppelt': 'Zeile {zeile}: „{name}“ gibt es schon — noch nicht übernommen.',
    'teilWerte.fehler.teil_leer': 'Zeile {zeile}: Welcher Teil? — noch nicht übernommen.',
    'teilWerte.fehler.json': 'Zeile {zeile}: kein gültiges JSON — noch nicht übernommen.',
    'schemaForm.weitere': 'Weitere Einstellungen',
    'schemaField.wirkung.nurMuster': 'wirkt nur im Muster-Modus',
    'schemaField.wirkung.nurAgent': 'wirkt nur im Agent-Modus',
    'schemaField.wirkung.nurKrise': 'im Agent-Modus nur bei Krise',
    'schemaField.wirkung.nurExtern': 'nur externer Auftrag (/api/agent)',
    'schemaField.wirkung.ohneWirkung': 'ohne Wirkung',
    'schemaField.zurueck': 'Auf Vorgabe zurück',
    'schemaField.zurueckFuer': '{label} auf die Vorgabe zurücksetzen',
    'schemaField.restoreDefaultFor': 'Vorgabe wiederherstellen: {group}',
    'schemaField.remove': 'Entfernen',
    'schemaField.removeIndex': 'Eintrag {index} aus {group} entfernen',
    'schemaField.removeKey': 'Eintrag {key} entfernen',
    'schemaField.add': '+ Eintrag',
    'schemaField.addTo': 'Eintrag zu {group} hinzufügen',
    'schemaField.key': 'Schlüssel',
    'schemaField.markerVerwaist':
      'Als {label} ist „{wert}“ gespeichert — das passt zu keinem Eintrag. Einen Eintrag '
      + 'wählen oder „ohne“.',
    'schemaField.wert': 'Wert',
    'schemaField.aktion': 'Aktion',
    'schemaField.keyOf': 'Schlüssel von {key}',
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
    // ST-2c: die Grenzen eines Zahlfelds aus dem Schema, sichtbar am Feld.
    'schemaField.range': 'Erlaubt: {min} bis {max}',
    'schemaField.rangeMin': 'Erlaubt: ab {min}',
    'schemaField.rangeMax': 'Erlaubt: bis {max}',
    // ST-2i: EIN Eintrag einer Liste ist hervorgehoben (Tour-Chip). „Ohne"
    // statt „Kein/Keine": der Name des Nachbarfelds hat ein Geschlecht.
    'schemaField.markAs': 'Als {label}',
    'schemaField.markItemAs': '„{value}“ als {label}',
    'schemaField.markNone': 'Ohne {label}',
    // ST-2h: ein Regler ohne Wert (`| None`) — die Vorgabe greift.
    'schemaField.sliderUnset': 'nicht gesetzt — es gilt die Vorgabe',
    'schemaField.sliderClear': 'Leeren',
    // ST-2g: Katalog-Namen als Chips.
    'schemaField.removeChip': '„{value}“ aus {group} entfernen',
    'schemaField.chipTaken': '„{value}“ steht schon in {group}.',
    // ST-6: vom Code festgesetzt — der gesperrte Schalter zeigt, was wirkt.
    'schemaField.fixedOn': 'fest aktiv',
    // ST-3: Listen und Maps von Objekten als Liste│Editor
    'objectList.count.one': '{count} Eintrag',
    'objectList.count.other': '{count} Einträge',
    'objectList.countFiltered': '{shown} von {count}',
    'objectList.search': 'Suchen',
    'objectList.searchIn': 'In {group} suchen',
    'objectList.entries': 'Einträge in {group}',
    'objectList.noMatch': 'Kein Eintrag passt zur Suche.',
    'objectList.entry': 'Eintrag {index}',
    'objectList.hasProblem': 'enthält einen Fehler',
    'objectList.new': 'Neu',
    'objectList.newIn': 'Neu in {group}',
    'objectList.duplicate': 'Duplizieren',
    'objectList.duplicateEntry': 'Duplizieren: {title}',
    'objectList.remove': 'Löschen',
    'objectList.removeEntry': 'Löschen: {title}',

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
    'areaEditor.zurueckNav': 'Back',
    'areaEditor.zurueckZu': '← Back to “{seite}”',
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
    'schemaField.unset': 'Not set – the default applies.',
    'schemaField.restoreDefault': 'Restore default',
    'schemaField.vorgabe': 'Default',
    'schemaField.nurBei': '“{feld}” has no effect with the selected value of “{nachbar}” – the value stays saved.',
    'schemaField.nurBeiEntfernen': 'Remove value',
    'schemaField.nurBeiLeer': '“{feld}” has no effect with the selected value of “{nachbar}”.',
    'jsonValue.ungueltig': 'Not valid JSON — not applied yet.',
    'ablaufPruefen.titel': 'Check and step sequence',
    'ablaufPruefen.knopf': 'Check workflow',
    'ablaufPruefen.erneut': 'Check again',
    'ablaufPruefen.laeuft': 'Checking …',
    'ablaufPruefen.ok': 'No findings.',
    'ablaufPruefen.befunde.one': '{count} finding — marked at the steps.',
    'ablaufPruefen.befunde.other': '{count} findings — marked at the steps.',
    'ablaufPruefen.form.one': 'The draft does not fit the model yet — {count} place (listed here and marked at its field):',
    'ablaufPruefen.form.other': 'The draft does not fit the model yet — {count} places (listed here and marked at their fields):',
    'ablaufPruefen.fehler': 'Checking failed: {detail}',
    'ablaufPruefen.veraltet': 'Changed since the check — please check again.',
    'ablaufPruefen.folge': 'Step sequence (from the draft, read-only):',
    'ablaufPruefen.keineSchritte': 'No steps yet.',
    'ablaufPruefen.ohneKennung': '(no id)',
    'ablaufPruefen.endetHier': 'Ends here.',
    'ablaufPruefen.weiter': '→ {ziel}',
    'ablaufPruefen.beiFehler': 'on error → {ziel}',
    'ablaufPruefen.sonst': 'otherwise → {ziel}',
    'ablaufPruefen.regel': 'if {wenn} → {ziel}',
    'ablaufPruefen.wennTeil': 'part “{teil}” present',
    'ablaufPruefen.wennGewaehlt': '“{wahl}” chosen',
    'ablaufPruefen.ohneBedingung': '(no condition)',
    'ablaufPruefen.keineGreift': 'no rule applies → {ziel}',
    'ablaufPruefen.laeuftAus': '(end without an “ende” step)',
    'ablaufPruefen.unbekannt': '— no such step',
    'teilWerte.leer': 'No entries yet.',
    'teilWerte.pfadHinweis':
      'A part can point to a place inside it: name and path with dots, e.g. volltext.outputs.markdown.',
    'teilWerte.name': 'Name {n}',
    'teilWerte.art': 'Kind of row {n}',
    'teilWerte.art.text': 'Text',
    'teilWerte.art.teil': 'Part',
    'teilWerte.art.json': 'JSON',
    'teilWerte.wert': 'Value {n}',
    'teilWerte.teil': 'Part for row {n}',
    'teilWerte.weg': 'Remove',
    'teilWerte.entfernen': 'Remove row {n} ({name})',
    'teilWerte.entfernenOhneName': 'Remove row {n}',
    'teilWerte.spalte.name': 'Name',
    'teilWerte.spalte.art': 'Kind',
    'teilWerte.spalte.wert': 'Value',
    'teilWerte.neu': 'Add entry',
    'teilWerte.alsJson': 'Edit as JSON',
    'teilWerte.alsTabelle': 'Edit as table',
    'teilWerte.fehler.name_leer': 'Row {zeile}: name missing — not applied yet.',
    'teilWerte.fehler.name_doppelt': 'Row {zeile}: “{name}” already exists — not applied yet.',
    'teilWerte.fehler.teil_leer': 'Row {zeile}: which part? — not applied yet.',
    'teilWerte.fehler.json': 'Row {zeile}: not valid JSON — not applied yet.',
    'schemaForm.weitere': 'Further settings',
    'schemaField.wirkung.nurMuster': 'pattern mode only',
    'schemaField.wirkung.nurAgent': 'agent mode only',
    'schemaField.wirkung.nurKrise': 'agent mode: crisis only',
    'schemaField.wirkung.nurExtern': 'external jobs only (/api/agent)',
    'schemaField.wirkung.ohneWirkung': 'no effect',
    'schemaField.zurueck': 'Back to default',
    'schemaField.zurueckFuer': 'Reset {label} to its default',
    'schemaField.restoreDefaultFor': 'Restore default: {group}',
    'schemaField.remove': 'Remove',
    'schemaField.removeIndex': 'Remove entry {index} from {group}',
    'schemaField.removeKey': 'Remove entry {key}',
    'schemaField.add': '+ Entry',
    'schemaField.addTo': 'Add an entry to {group}',
    'schemaField.key': 'Key',
    'schemaField.markerVerwaist':
      '“{wert}” is stored as {label} — it matches no entry. Pick an entry or “none”.',
    'schemaField.wert': 'Value',
    'schemaField.aktion': 'Action',
    'schemaField.keyOf': 'Key of {key}',
    'schemaField.emptyKey': 'A key must not be empty.',
    'schemaField.keyTaken': 'The key “{key}” is already taken.',
    'schemaField.required': '(required)',

    'schemaField.noChoice': '— not set —',
    'schemaField.foreignChoice': '{current} — not in the list',
    'schemaField.openTarget': 'Open {value}',
    'schemaField.range': 'Allowed: {min} to {max}',
    'schemaField.rangeMin': 'Allowed: {min} or more',
    'schemaField.rangeMax': 'Allowed: up to {max}',
    'schemaField.markAs': 'As {label}',
    'schemaField.markItemAs': '"{value}" as {label}',
    'schemaField.markNone': 'No {label}',
    'schemaField.sliderUnset': 'not set — the default applies',
    'schemaField.sliderClear': 'Clear',
    'schemaField.removeChip': 'Remove "{value}" from {group}',
    'schemaField.chipTaken': '"{value}" is already in {group}.',
    'schemaField.fixedOn': 'always on',
    'objectList.count.one': '{count} entry',
    'objectList.count.other': '{count} entries',
    'objectList.countFiltered': '{shown} of {count}',
    'objectList.search': 'Search',
    'objectList.searchIn': 'Search in {group}',
    'objectList.entries': 'Entries in {group}',
    'objectList.noMatch': 'No entry matches the search.',
    'objectList.entry': 'Entry {index}',
    'objectList.hasProblem': 'contains an error',
    'objectList.new': 'New',
    'objectList.newIn': 'New in {group}',
    'objectList.duplicate': 'Duplicate',
    'objectList.duplicateEntry': 'Duplicate: {title}',
    'objectList.remove': 'Delete',
    'objectList.removeEntry': 'Delete: {title}',

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
