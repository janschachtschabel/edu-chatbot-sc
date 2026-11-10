/**
 * Paket U1-f: Texte der Seite „UI-Module“ (`views/ui-module.component.*`,
 * `views/ui-modul-vorschau.component.*`) — Liste, Schalter, Angaben aus dem Manifest, Vorschau.
 */
import type { CataloguePart } from './catalogue-part';

export const UI_MODULE: CataloguePart = {
  de: {
    'view.ui-module.label': 'UI-Module',
    'view.ui-module.desc': 'Bausteine im Chat: Vorschau, an/aus',
    'curated.uiModule.intro':
      'UI-Module sind die Bausteine, die der Chat unter einer Antwort zeigt — Dokumente, Treffer, '
      + 'Webseiten, Auswahlfragen, Themenbäume. Hier siehst du, was jedes Modul erwartet, wie es '
      + 'aussieht, und schaltest es für beide Modi an oder aus. Abläufe aus diesen Modulen baust '
      + 'du auf der Seite „Abläufe“.',
    'curated.uiModule.panel.label': 'Module',
    'curated.uiModule.panel.hint':
      'Alle Module aus dem Katalog mit ihren Beispielen. Schalter gelten ab der nächsten Antwort.',

    'uiModule.laedt': 'UI-Module werden geladen …',
    'uiModule.leer': 'Der Katalog enthält keine UI-Module.',
    'uiModule.liste': 'UI-Module',
    'uiModule.geltung':
      'Schalter gelten ab der nächsten Antwort, in Muster- und Agent-Modus. Frühere Antworten im '
      + 'Verlauf bleiben, wie sie gezeigt wurden.',
    'uiModule.zustand.an': 'an',
    'uiModule.zustand.aus': 'aus',
    'uiModule.zustand.ohneAgent': 'an, nicht für den Agenten',
    'uiModule.zustand.fest': 'fest',
    'uiModule.zustand.geaendert': 'geändert',
    'uiModule.art.anzeigen': 'zeigt an',
    'uiModule.art.abfragen': 'fragt ab',

    'uiModule.schalter.legend': 'An und aus',
    'uiModule.schalter.aktiv': 'Aktiv',
    'uiModule.schalter.aktiv.hint':
      'Aus: neue Antworten zeigen das Modul nicht. Die KI bekommt es in keinem Modus als Werkzeug.',
    'uiModule.schalter.aktiv.hintAbgeleitet':
      'Aus: neue Antworten zeigen das Modul nicht; an seiner Stelle stehen die bisherigen '
      + 'Trefferboxen. Auch ein Muster mit „ui_module“ bekommt es dann nicht.',
    'uiModule.schalter.aktiv.fest':
      'Fest — lässt sich nicht abschalten. Es trägt die Volltext-Anzeige und die Vorschau einer '
      + 'Änderung an WLO vor der Freigabe. Ob Dokumente als Box erscheinen, regelt „Anzeige“ › '
      + 'Dokument-Boxen.',
    'uiModule.schalter.agent': 'Für den Agenten',
    'uiModule.schalter.agent.hint':
      'Aus: der Agent-Modus bietet das Modul nicht als Werkzeug an. Ein Muster, das es unter '
      + '„tools“ nennt, bietet es weiter an.',
    'uiModule.schalter.agent.erstAktiv': 'Gilt erst, wenn das Modul aktiv ist.',
    'uiModule.schalter.agent.keins':
      'Kein eigenes Werkzeug — das Modul entsteht ohne Aufruf aus der fertigen Antwort.',
    'uiModule.schalter.agent.festText':
      'Kein Schalter — das Dokument-Werkzeug bekommt der Agent immer.',
    'uiModule.schalter.erstSpeichern': 'Ungespeicherte Änderungen — speichern oder verwerfen.',
    'uiModule.gespeichert': 'Gespeichert. Gilt ab der nächsten Antwort.',

    'uiModule.angaben': 'Angaben aus dem Manifest',
    'uiModule.angabe.name': 'Name',
    'uiModule.angabe.version': 'Hauptversion',
    'uiModule.angabe.art': 'Art',
    'uiModule.angabe.agent': 'Als Werkzeug für die KI',
    'uiModule.angabe.agent.ja': 'ja',
    'uiModule.angabe.agent.abgeleitet': 'nein — entsteht aus der Antwort',
    'uiModule.angabe.agent.nein': 'nein',
    'uiModule.angabe.datenquelle': 'Datenquelle',
    'uiModule.angabe.datenquelle.keine': 'keine — die KI liefert die Daten',
    'uiModule.angabe.datenquelle.wert': '{werkzeug}, die KI nennt {argumente}',
    'uiModule.angabe.faehigkeiten': 'Fähigkeiten',
    'uiModule.angabe.faehigkeiten.keine': 'keine',
    'uiModule.angabe.textfassung': 'Textfassung für ältere Widgets',
    'uiModule.angabe.platz': 'Platz unter der Antwort',
    'uiModule.angabe.platz.oben': 'vor den Trefferboxen',
    'uiModule.angabe.platz.unten': 'nach den Trefferboxen',
    'uiModule.faehigkeit.antworten': 'antworten',
    'uiModule.faehigkeit.drucken': 'drucken',
    'uiModule.faehigkeit.herunterladen': 'herunterladen',
    'uiModule.faehigkeit.oeffnen': 'Links und Aktionen öffnen',
    'uiModule.faehigkeit.nachladen': 'Daten nachladen (ohne Zug)',
    'uiModule.faehigkeit.hochladen': 'Dateien hochladen und ablegen (ohne Zug)',
    'uiModule.faehigkeit.auftrag': 'Stand eines Ablauf-Auftrags abfragen und abholen',
    'uiModule.wann': 'Wann die KI es nutzt',
    'uiModule.nichtWann': 'Wann nicht',
    'uiModule.eingabe': 'Eingabe',
    'uiModule.eingabe.datenquelle':
      'Die Daten des Blocks; die KI nennt nur die Argumente der Datenquelle, das Backend holt den Rest.',
    'uiModule.antwort': 'Antwort der Person',
    'uiModule.feld.name': 'Feld',
    'uiModule.feld.typ': 'Typ',
    'uiModule.feld.pflicht': 'Pflicht',
    'uiModule.feld.pflicht.ja': 'ja',
    'uiModule.feld.pflicht.nein': 'nein',
    'uiModule.feld.beschreibung': 'Beschreibung',
    'uiModule.feld.werte': 'Werte: {werte}',
    'uiModule.feld.nurSystem': 'Nur vom System gesetzt: {werte}',

    'uiModule.vorschau': 'Vorschau',
    'uiModule.vorschau.hint':
      'Die echte Komponente aus dem Widget mit den Beispielen des Manifests. Nichts verlässt die '
      + 'Seite: Links, Downloads, Druck und Antworten werden nur angesagt.',
    'uiModule.vorschau.beispiel': 'Beispiel',
    'uiModule.vorschau.laedt': 'Vorschau wird geladen …',
    'uiModule.vorschau.ladeFehler':
      'Die Vorschau ließ sich nicht laden — die Verbindung war unterbrochen oder das Studio wurde '
      + 'inzwischen neu ausgeliefert. „Seite neu laden“ holt sie neu.',
    'uiModule.vorschau.neuLaden': 'Seite neu laden',
    'uiModule.vorschau.beantwortet': 'Beantwortet zeigen (mit der Antwort des Beispiels)',
    'uiModule.vorschau.kacheln': 'Als Kacheln zeigen (wie im breiten Widget)',
    'uiModule.vorschau.daten': 'Beispieldaten (JSON)',
    'uiModule.vorschau.unbekannt':
      'Dieses Studio kennt das Modul in Hauptversion {version} nicht — es wurde mit einem anderen '
      + 'Widget-Stand gebaut. Hier stehen die Beispieldaten.',
    'uiModule.vorschau.keineBeispiele': 'Das Manifest enthält keine Beispiele.',
    'uiModule.vorschau.link': 'In der Vorschau öffnet sich kein Link: {url}',
    'uiModule.vorschau.herunterladen': 'In der Vorschau wird nichts heruntergeladen: {datei}',
    'uiModule.vorschau.drucken': 'In der Vorschau wird nicht gedruckt: {titel}',
    'uiModule.vorschau.aktion': 'In der Vorschau läuft keine Aktion ({aktion}).',
    'uiModule.vorschau.antworten': 'In der Vorschau wird nichts gesendet. Antwort: {text}',
    'uiModule.vorschau.zweig': 'In der Vorschau wird nichts geladen ({knoten}) — es stehen Beispiel-Unterthemen da.',
    'uiModule.vorschau.hochladen': 'In der Vorschau wird nichts hochgeladen ({datei}) — es steht ein Beispiel-Befund da.',
    'uiModule.vorschau.ablegen': 'In der Vorschau wird nichts in WLO abgelegt (Schritt {schritt}) — es steht ein Beispiel-Ergebnis da.',
    'uiModule.vorschau.auftrag': 'In der Vorschau läuft kein Auftrag — im Chat holte das Modul jetzt das Ergebnis ab.',
  },
  en: {
    'view.ui-module.label': 'UI modules',
    'view.ui-module.desc': 'Building blocks in the chat: preview, on/off',
    'curated.uiModule.intro':
      'UI modules are the building blocks the chat shows below an answer — documents, results, '
      + 'web pages, choice questions, topic trees. Here you see what each module expects, what it '
      + 'looks like, and switch it on or off for both modes.',
    'curated.uiModule.panel.label': 'Modules',
    'curated.uiModule.panel.hint':
      'All modules in the catalogue with their examples. Switches apply from the next answer.',

    'uiModule.laedt': 'Loading UI modules …',
    'uiModule.leer': 'The catalogue holds no UI modules.',
    'uiModule.liste': 'UI modules',
    'uiModule.geltung':
      'Switches apply from the next answer, in pattern and agent mode. Earlier answers in the '
      + 'history stay as they were shown.',
    'uiModule.zustand.an': 'on',
    'uiModule.zustand.aus': 'off',
    'uiModule.zustand.ohneAgent': 'on, not for the agent',
    'uiModule.zustand.fest': 'fixed',
    'uiModule.zustand.geaendert': 'changed',
    'uiModule.art.anzeigen': 'displays',
    'uiModule.art.abfragen': 'asks',

    'uiModule.schalter.legend': 'On and off',
    'uiModule.schalter.aktiv': 'Active',
    'uiModule.schalter.aktiv.hint':
      'Off: new answers do not show the module. The AI gets it as a tool in neither mode.',
    'uiModule.schalter.aktiv.hintAbgeleitet':
      'Off: new answers do not show the module; the previous result boxes stand in its place. A '
      + 'pattern with “ui_module” does not get it either.',
    'uiModule.schalter.aktiv.fest':
      'Fixed — cannot be switched off. It carries the full-text view and the preview of a change '
      + 'to WLO before approval. Whether documents appear as a box is set under “Display” › '
      + 'document boxes.',
    'uiModule.schalter.agent': 'For the agent',
    'uiModule.schalter.agent.hint':
      'Off: agent mode does not offer the module as a tool. A pattern that lists it under “tools” '
      + 'still offers it.',
    'uiModule.schalter.agent.erstAktiv': 'Applies only while the module is active.',
    'uiModule.schalter.agent.keins':
      'No tool of its own — the module is derived from the finished answer without a call.',
    'uiModule.schalter.agent.festText': 'No switch — the agent always gets the document tool.',
    'uiModule.schalter.erstSpeichern': 'Unsaved changes — save or discard them.',
    'uiModule.gespeichert': 'Saved. Applies from the next answer.',

    'uiModule.angaben': 'From the manifest',
    'uiModule.angabe.name': 'Module name',
    'uiModule.angabe.version': 'Major version',
    'uiModule.angabe.art': 'Kind',
    'uiModule.angabe.agent': 'Tool for the AI',
    'uiModule.angabe.agent.ja': 'yes',
    'uiModule.angabe.agent.abgeleitet': 'no — derived from the answer',
    'uiModule.angabe.agent.nein': 'no',
    'uiModule.angabe.datenquelle': 'Data source',
    'uiModule.angabe.datenquelle.keine': 'none — the AI supplies the data',
    'uiModule.angabe.datenquelle.wert': '{werkzeug}, the AI names {argumente}',
    'uiModule.angabe.faehigkeiten': 'Capabilities',
    'uiModule.angabe.faehigkeiten.keine': 'none',
    'uiModule.angabe.textfassung': 'Text version for older widgets',
    'uiModule.angabe.platz': 'Place below the answer',
    'uiModule.angabe.platz.oben': 'before the result boxes',
    'uiModule.angabe.platz.unten': 'after the result boxes',
    'uiModule.faehigkeit.antworten': 'answer',
    'uiModule.faehigkeit.drucken': 'print',
    'uiModule.faehigkeit.herunterladen': 'download',
    'uiModule.faehigkeit.oeffnen': 'open links and actions',
    'uiModule.faehigkeit.nachladen': 'load more data (without a turn)',
    'uiModule.faehigkeit.hochladen': 'upload and store files (without a turn)',
    'uiModule.faehigkeit.auftrag': 'check and fetch a workflow job',
    'uiModule.wann': 'When the AI uses it',
    'uiModule.nichtWann': 'When not',
    'uiModule.eingabe': 'Input',
    'uiModule.eingabe.datenquelle':
      'The block data; the AI only names the data source arguments, the backend fetches the rest.',
    'uiModule.antwort': 'Answer of the person',
    'uiModule.feld.name': 'Field',
    'uiModule.feld.typ': 'Type',
    'uiModule.feld.pflicht': 'Required',
    'uiModule.feld.pflicht.ja': 'yes',
    'uiModule.feld.pflicht.nein': 'no',
    'uiModule.feld.beschreibung': 'Description',
    'uiModule.feld.werte': 'Values: {werte}',
    'uiModule.feld.nurSystem': 'Set by the system only: {werte}',

    'uiModule.vorschau': 'Preview',
    'uiModule.vorschau.hint':
      'The real component from the widget with the examples of the manifest. Nothing leaves the '
      + 'page: links, downloads, printing and answers are only announced.',
    'uiModule.vorschau.beispiel': 'Example',
    'uiModule.vorschau.laedt': 'Loading preview …',
    'uiModule.vorschau.ladeFehler':
      'The preview could not be loaded — the connection was interrupted or the Studio has been '
      + 'redeployed in the meantime. “Reload page” fetches it again.',
    'uiModule.vorschau.neuLaden': 'Reload page',
    'uiModule.vorschau.beantwortet': 'Show as answered (with the example answer)',
    'uiModule.vorschau.kacheln': 'Show as tiles (as in the wide widget)',
    'uiModule.vorschau.daten': 'Example data (JSON)',
    'uiModule.vorschau.unbekannt':
      'This Studio does not know the module in major version {version} — it was built with a '
      + 'different widget version. The example data is shown here.',
    'uiModule.vorschau.keineBeispiele': 'The manifest has no examples.',
    'uiModule.vorschau.link': 'No link opens in the preview: {url}',
    'uiModule.vorschau.herunterladen': 'Nothing is downloaded in the preview: {datei}',
    'uiModule.vorschau.drucken': 'Nothing is printed in the preview: {titel}',
    'uiModule.vorschau.aktion': 'No action runs in the preview ({aktion}).',
    'uiModule.vorschau.antworten': 'Nothing is sent in the preview. Answer: {text}',
    'uiModule.vorschau.zweig': 'Nothing is loaded in the preview ({knoten}) — example subtopics are shown.',
    'uiModule.vorschau.hochladen': 'Nothing is uploaded in the preview ({datei}) — an example result is shown.',
    'uiModule.vorschau.ablegen': 'Nothing is stored in WLO in the preview (step {schritt}) — an example result is shown.',
    'uiModule.vorschau.auftrag': 'No job runs in the preview — in the chat the module would now fetch the result.',
  },
};
