/**
 * Paket A1: Feldtexte des Bereichs `06-ablaeufe/katalog` (Abschnitt „Abläufe“ auf der Seite
 * „UI-Module“). Gelesen vom lokalen Treiber (`backend/src/boerdi/services/ablauf`); beim Speichern prüft
 * das Backend, ob jeder Ablauf sicher läuft (Ziele, Ende, Module, nur lesende Werkzeuge, Teilnamen).
 *
 * Schlüsselschema wie in `fields-layer-doc.ts`; Auswahlwerte `feld.<Modell>.<feld>.wahl.<wert>`.
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_ABLAEUFE: CataloguePart = {
  de: {
    'feld.AblaufKatalogArea.ablaeufe.label': 'Abläufe',
    'feld.AblaufKatalogArea.ablaeufe.hint': 'Je Eintrag ein Ablauf; die Kennung ist sein Schlüssel.',
    'feld.AblaufArea.id.label': 'Kennung',
    'feld.AblaufArea.id.hint': 'Kleinbuchstaben, Ziffern, Unterstrich — so startet ein Knopf ihn (ablauf_starten).',
    'feld.AblaufArea.titel.label': 'Titel',
    'feld.AblaufArea.titel.hint': 'Je Sprache (de, en).',
    'feld.AblaufArea.beschreibung.label': 'Beschreibung',
    'feld.AblaufArea.beschreibung.hint': 'Was der Ablauf tut, für die Redaktion.',
    'feld.AblaufArea.wann.label': 'Wann',
    'feld.AblaufArea.wann.hint': 'Wofür er gedacht ist (für spätere Vorschläge durch die KI).',
    'feld.AblaufArea.nicht_wann.label': 'Wann nicht',
    'feld.AblaufArea.nicht_wann.hint': 'Wofür er nicht gedacht ist.',
    'feld.AblaufArea.aktiv.label': 'Eingeschaltet',
    'feld.AblaufArea.aktiv.hint': 'Aus = startet nicht. Neue Abläufe sind aus.',
    'feld.AblaufArea.ausloeser.label': 'Auslöser',
    'feld.AblaufArea.ausloeser.hint': 'Womit der Ablauf startet: Knopf, Vorschlag der KI, Wendung oder Modul-Antwort.',
    'feld.AblaufArea.voraussetzungen.label': 'Voraussetzungen',
    'feld.AblaufArea.voraussetzungen.hint': 'Anmeldung: nur für angemeldete WLO-Personen.',
    'feld.AblaufArea.voraussetzungen.wahl.anmeldung': 'WLO-Anmeldung',
    'feld.AblaufArea.schritte.label': 'Schritte',
    'feld.AblaufArea.schritte.hint': '1 bis 40 Schritte, der Reihe nach, wenn kein „weiter“ etwas anderes sagt.',
    'feld.Ausloeser.art.label': 'Art',
    'feld.Ausloeser.art.hint':
      'Knopf (Direktaktion), KI (schlägt vor), Wendung (in der Nachricht) oder Modul (dessen Antwort startet).',
    'feld.Ausloeser.art.wahl.knopf': 'Knopf',
    'feld.Ausloeser.art.wahl.text': 'Wendung in der Nachricht',
    'feld.Ausloeser.wendungen.label': 'Wendungen',
    'feld.Ausloeser.wendungen.hint':
      'Bei „Wendung“: 1 bis 10 Wendungen, je 4 bis 80 Zeichen. Kommt eine in der Nachricht vor '
      + '(Groß-/Kleinschreibung egal), startet der Ablauf — ohne Platzhalter oder Muster.',
    'feld.Ausloeser.art.wahl.agent': 'KI schlägt vor',
    'feld.Ausloeser.art.wahl.modul': 'Antwort eines Moduls',
    'feld.Ausloeser.modus.label': 'Modus',
    'feld.Ausloeser.modus.hint': 'Bei „KI“: vorschlagen — unter der Antwort erscheint ein Knopf, die Person startet.',
    'feld.Ausloeser.modus.wahl.vorschlagen': 'vorschlagen',
    'feld.Ausloeser.modul.label': 'Modul',
    'feld.Ausloeser.modul.hint':
      'Bei „Modul“: dessen geprüfte Antwort startet den Ablauf nach seinem Schritt mit diesem Modul.',
    'feld.Ausloeser.wenn_teil.label': 'Wenn Teil vorhanden',
    'feld.Ausloeser.wenn_teil.hint': 'Nur starten, wenn dieser Teil danach im Vorgang liegt.',
    'feld.Schritt.id.label': 'Kennung',
    'feld.Schritt.id.hint': 'Eindeutig im Ablauf; Ziel von „weiter“ und „bei Fehler“.',
    'feld.Schritt.typ.label': 'Art',
    'feld.Schritt.typ.hint':
      'Nachricht, Modul, Werkzeug, Verzweigung, KI-Abschnitt, Auftrag (b-api/Kestra) oder Ende.',
    'feld.Schritt.typ.wahl.auftrag': 'Auftrag (b-api)',
    'feld.Schritt.flow.label': 'Flow',
    'feld.Schritt.flow.hint':
      'Bei „Auftrag“: der Kestra-Flow hinter der b-api — nur Flows, die der Betrieb freischaltet '
      + '(B_API_JOBS_FLOWS). Braucht die Voraussetzung Anmeldung; „Stand prüfen“ holt das Ergebnis.',
    'feld.Schritt.warten.label': 'Während der Auftrag läuft',
    'feld.Schritt.warten.hint':
      'Nur bei „Auftrag“. „Frei“: das Gespräch geht weiter. „Gesperrt“: bis der Auftrag fertig ist, '
      + 'nimmt das Widget nur „Stand prüfen“ und „Auftrag abbrechen“ an.',
    'feld.Schritt.warten.wahl.frei': 'Frei',
    'feld.Schritt.warten.wahl.gesperrt': 'Gesperrt',
    'feld.Schritt.typ.wahl.agent': 'KI-Abschnitt',
    'feld.Schritt.agent.label': 'KI-Abschnitt',
    'feld.Schritt.agent.hint':
      'Bei „KI-Abschnitt“: die KI arbeitet mit der Person, nur mit diesen Werkzeugen; „Weiter im Ablauf“ '
      + 'setzt fort.',
    'feld.AgentSchritt.werkzeuge.label': 'Werkzeuge',
    'feld.AgentSchritt.werkzeuge.hint':
      '1 bis 10: lesende WLO-Werkzeuge oder UI-Module, die die KI nutzen darf — nie schreibende.',
    'feld.AgentSchritt.hinweis.label': 'Hinweis an die KI',
    'feld.AgentSchritt.hinweis.hint': 'Je Sprache: was die KI in diesem Schritt tun soll und was nicht.',
    'feld.AgentSchritt.ausgabe.label': 'Ergebnis-Teil',
    'feld.AgentSchritt.ausgabe.hint':
      'Teil, der vorliegen muss, bevor „Weiter“ fortsetzt; fehlt er: „Bei Fehler“ oder weiter warten.',
    'feld.AgentSchritt.zuege.label': 'Züge',
    'feld.AgentSchritt.zuege.hint':
      '1 bis 20: danach bittet die KI die Person, mit „Weiter im Ablauf“ fortzufahren.',
    'feld.Schritt.typ.wahl.nachricht': 'Nachricht',
    'feld.Schritt.typ.wahl.modul': 'Modul',
    'feld.Schritt.typ.wahl.werkzeug': 'Werkzeug',
    'feld.Schritt.typ.wahl.verzweigung': 'Verzweigung',
    'feld.Schritt.typ.wahl.ende': 'Ende',
    'feld.Schritt.text.label': 'Text',
    'feld.Schritt.text.hint': 'Je Sprache; bei einem Modul der Satz darüber.',
    'feld.Schritt.modul.label': 'Modul',
    'feld.Schritt.modul.hint': 'Name des UI-Moduls, z. B. ui_upload.',
    'feld.Schritt.daten.label': 'Daten',
    'feld.Schritt.daten.hint': 'Daten des Moduls (JSON); {"$teil": "name"} liest einen Teil des Vorgangs.',
    'feld.Schritt.werkzeug.label': 'Werkzeug',
    'feld.Schritt.werkzeug.hint': 'Ein Dienst (z. B. strukturentwurf_aus_ordnern) oder ein lesendes WLO-Werkzeug.',
    'feld.Schritt.argumente.label': 'Argumente',
    'feld.Schritt.argumente.hint': 'JSON; {"$teil": "name"} setzt einen Teil des Vorgangs ein.',
    'feld.Schritt.schreibt.label': 'Ergebnis als Teil',
    'feld.Schritt.schreibt.hint': 'Name des Teils, unter dem das Ergebnis des Werkzeugs gespeichert wird.',
    'feld.Schritt.freigabe.label': 'Freigabe (Satz über der Vorschau)',
    'feld.Schritt.freigabe.hint':
      'Nur bei einem schreibenden WLO-Werkzeug: der Schritt zeigt diesen Satz und die Vorschau des Servers und wartet, bis die Person zustimmt. Mindestens auf Deutsch.',
    'feld.Schritt.dateien_holen.label': 'Dateien holen',
    'feld.Schritt.dateien_holen.hint':
      'Bis zu drei Dateien des Ergebnisses (ihre outputId), die beim Abholen geholt und wie ein Upload '
      + 'geprüft werden. Ihr Text steht im Teil unter texte.<outputId> — etwa volltext.texte.report.',
    'feld.Schritt.weiter.label': 'Weiter',
    'feld.Schritt.weiter.hint': 'Nächster Schritt — oder bei einer Verzweigung Regeln (wenn_teil/wenn_gewaehlt → dann, zuletzt sonst).',
    'feld.Schritt.bei_fehler.label': 'Bei Fehler',
    'feld.Schritt.bei_fehler.hint': 'Schritt, wenn Daten fehlen oder das Werkzeug nichts liefert; sonst endet der Ablauf.',
  },
  en: {
    'feld.AblaufKatalogArea.ablaeufe.label': 'Workflows',
    'feld.AblaufKatalogArea.ablaeufe.hint': 'One workflow per entry; its id is the key.',
    'feld.AblaufArea.id.label': 'Id',
    'feld.AblaufArea.id.hint': 'Lowercase letters, digits, underscore — a button starts it with this (ablauf_starten).',
    'feld.AblaufArea.titel.label': 'Title',
    'feld.AblaufArea.titel.hint': 'Per language (de, en).',
    'feld.AblaufArea.beschreibung.label': 'Description',
    'feld.AblaufArea.beschreibung.hint': 'What the workflow does, for editors.',
    'feld.AblaufArea.wann.label': 'When',
    'feld.AblaufArea.wann.hint': 'What it is meant for (for later suggestions by the AI).',
    'feld.AblaufArea.nicht_wann.label': 'When not',
    'feld.AblaufArea.nicht_wann.hint': 'What it is not meant for.',
    'feld.AblaufArea.aktiv.label': 'Switched on',
    'feld.AblaufArea.aktiv.hint': 'Off = does not start. New workflows are off.',
    'feld.AblaufArea.ausloeser.label': 'Triggers',
    'feld.AblaufArea.ausloeser.hint': 'What starts the workflow: button, AI suggestion, phrase or module answer.',
    'feld.AblaufArea.voraussetzungen.label': 'Requirements',
    'feld.AblaufArea.voraussetzungen.hint': 'Sign-in: only for people signed in to WLO.',
    'feld.AblaufArea.voraussetzungen.wahl.anmeldung': 'WLO sign-in',
    'feld.AblaufArea.schritte.label': 'Steps',
    'feld.AblaufArea.schritte.hint': '1 to 40 steps, in order unless “next” says otherwise.',
    'feld.Ausloeser.art.label': 'Kind',
    'feld.Ausloeser.art.hint':
      'Button (direct action), AI (suggests), phrase (in the message) or module (its answer starts it).',
    'feld.Ausloeser.art.wahl.knopf': 'Button',
    'feld.Ausloeser.art.wahl.text': 'Phrase in the message',
    'feld.Ausloeser.wendungen.label': 'Phrases',
    'feld.Ausloeser.wendungen.hint':
      'For “phrase”: 1 to 10 phrases of 4 to 80 characters. If one occurs in the message (case does '
      + 'not matter), the workflow starts — no wildcards or patterns.',
    'feld.Ausloeser.art.wahl.agent': 'AI suggests',
    'feld.Ausloeser.art.wahl.modul': 'Answer of a module',
    'feld.Ausloeser.modus.label': 'Mode',
    'feld.Ausloeser.modus.hint': 'For “AI”: suggest — a button appears below the answer, the person starts.',
    'feld.Ausloeser.modus.wahl.vorschlagen': 'suggest',
    'feld.Ausloeser.modul.label': 'Module',
    'feld.Ausloeser.modul.hint':
      'For “module”: its checked answer starts the workflow after its step with this module.',
    'feld.Ausloeser.wenn_teil.label': 'If part present',
    'feld.Ausloeser.wenn_teil.hint': 'Only start if this part is in the work item afterwards.',
    'feld.Schritt.id.label': 'Id',
    'feld.Schritt.id.hint': 'Unique within the workflow; target of “next” and “on error”.',
    'feld.Schritt.typ.label': 'Kind',
    'feld.Schritt.typ.hint': 'Message, module, tool, branch, AI section, job (b-api/Kestra) or end.',
    'feld.Schritt.typ.wahl.auftrag': 'Job (b-api)',
    'feld.Schritt.flow.label': 'Kestra flow',
    'feld.Schritt.flow.hint':
      'For “job”: the Kestra flow behind the b-api — only flows enabled by operations '
      + '(B_API_JOBS_FLOWS). Needs the sign-in requirement; “Check status” fetches the result.',
    'feld.Schritt.warten.label': 'While the job runs',
    'feld.Schritt.warten.hint':
      'Only for “job”. “Open”: the conversation goes on. “Locked”: until the job is done, the widget '
      + 'only accepts “Check status” and “Cancel job”.',
    'feld.Schritt.warten.wahl.frei': 'Open',
    'feld.Schritt.warten.wahl.gesperrt': 'Locked',
    'feld.Schritt.typ.wahl.agent': 'AI section',
    'feld.Schritt.agent.label': 'AI section',
    'feld.Schritt.agent.hint':
      'For “AI section”: the AI works with the person, only with these tools; “Continue workflow” '
      + 'moves on.',
    'feld.AgentSchritt.werkzeuge.label': 'Tools',
    'feld.AgentSchritt.werkzeuge.hint':
      '1 to 10: read-only WLO tools or UI modules the AI may use — never writing ones.',
    'feld.AgentSchritt.hinweis.label': 'Hint to the AI',
    'feld.AgentSchritt.hinweis.hint': 'Per language: what the AI should and should not do in this step.',
    'feld.AgentSchritt.ausgabe.label': 'Result part',
    'feld.AgentSchritt.ausgabe.hint':
      'Part that must exist before “Continue” moves on; if missing: “On error” or keep waiting.',
    'feld.AgentSchritt.zuege.label': 'Turns',
    'feld.AgentSchritt.zuege.hint':
      '1 to 20: then the AI asks the person to go on with “Continue workflow”.',
    'feld.Schritt.typ.wahl.nachricht': 'Message',
    'feld.Schritt.typ.wahl.modul': 'Module',
    'feld.Schritt.typ.wahl.werkzeug': 'Tool',
    'feld.Schritt.typ.wahl.verzweigung': 'Branch',
    'feld.Schritt.typ.wahl.ende': 'End',
    'feld.Schritt.text.label': 'Message text',
    'feld.Schritt.text.hint': 'Per language; for a module the sentence above it.',
    'feld.Schritt.modul.label': 'Module',
    'feld.Schritt.modul.hint': 'Name of the UI module, e.g. ui_upload.',
    'feld.Schritt.daten.label': 'Data',
    'feld.Schritt.daten.hint': 'Data of the module (JSON); {"$teil": "name"} reads a part of the work item.',
    'feld.Schritt.werkzeug.label': 'Tool',
    'feld.Schritt.werkzeug.hint': 'A service (e.g. strukturentwurf_aus_ordnern) or a read-only WLO tool.',
    'feld.Schritt.argumente.label': 'Arguments',
    'feld.Schritt.argumente.hint': 'JSON; {"$teil": "name"} inserts a part of the work item.',
    'feld.Schritt.schreibt.label': 'Result as part',
    'feld.Schritt.schreibt.hint': 'Name of the part the tool result is stored under.',
    'feld.Schritt.freigabe.label': 'Approval (sentence above the preview)',
    'feld.Schritt.freigabe.hint':
      'Only for a writing WLO tool: the step shows this sentence and the server preview and waits until the person agrees. At least in German.',
    'feld.Schritt.dateien_holen.label': 'Fetch files',
    'feld.Schritt.dateien_holen.hint':
      'Up to three files of the result (their outputId), fetched on pick-up and checked like an upload. '
      + 'Their text is in the part under texte.<outputId> — e.g. volltext.texte.report.',
    'feld.Schritt.weiter.label': 'Next',
    'feld.Schritt.weiter.hint': 'Next step — or for a branch, rules (wenn_teil/wenn_gewaehlt → dann, finally sonst).',
    'feld.Schritt.bei_fehler.label': 'On error',
    'feld.Schritt.bei_fehler.hint': 'Step if data is missing or the tool returns nothing; otherwise the workflow ends.',
  },
};
