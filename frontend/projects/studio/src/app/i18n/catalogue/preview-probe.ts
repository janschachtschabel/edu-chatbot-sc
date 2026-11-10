/**
 * Paket AS-8b (Plan 2026-11-09 §5n, P-9): „Ablauf ausprobieren“ in der Vorschau und der Knopf am
 * Ablauf. Eigener Teil, damit `preview.ts` klein bleibt.
 */
import type { CataloguePart } from './catalogue-part';

export const PREVIEW_PROBE: CataloguePart = {
  de: {
    'preview.probe.title': 'Ablauf ausprobieren',
    'preview.probe.lead':
      'Startet einen Ablauf im Widget unten — die gespeicherte Fassung, auch wenn er noch aus ist. '
      + 'Es ist ein Trockenlauf: Schreiben in WLO und Aufträge laufen nicht, Dateien werden nicht '
      + 'abgelegt. Anmeldung und Freigaben bleiben wie im Betrieb.',
    'preview.probe.ablauf': 'Ablauf',
    'preview.probe.aus': '{titel} (aus)',
    'preview.probe.daten': 'Startdaten (JSON, optional)',
    'preview.probe.datenHilfe':
      'Wie von einer Gastseite, etwa {"sammlung": "…"}. Sie gelten nur, wenn der Ablauf ein '
      + 'passendes Startschema hat.',
    'preview.probe.fehler.json': 'Das ist kein gültiges JSON.',
    'preview.probe.fehler.objekt': 'Startdaten sind ein JSON-Objekt in geschweiften Klammern.',
    'preview.probe.fehler.gross': 'Die Startdaten sind zu lang (höchstens 16 000 Zeichen).',
    'preview.probe.fehler.schluessel': 'Die Startdaten haben zu viele Felder (höchstens 20).',
    'preview.probe.unbekannt':
      'Den Ablauf „{kennung}“ gibt es noch nicht — erst unter „Abläufe“ speichern. Gewählt ist der '
      + 'erste der Liste.',
    'preview.probe.starten': 'Ablauf starten',
    'preview.probe.beenden': 'Probe beenden',
    'preview.probe.laeuft': 'Probe läuft: „{titel}“ — Trockenlauf.',
    'preview.probe.laden': 'Die Abläufe werden geladen …',
    'preview.probe.leer': 'Noch keine Abläufe. Lege unter „Abläufe“ einen an und speichere ihn.',
    'preview.probe.listeFehler': 'Die Liste der Abläufe ließ sich nicht laden.',
    'ablaufPruefen.ausprobieren': 'Im Widget ausprobieren',
    'ablaufPruefen.ausprobierenHinweis':
      'Öffnet die Vorschau mit diesem Ablauf. Es gilt die gespeicherte Fassung — erst speichern.',
  },
  en: {
    'preview.probe.title': 'Try a workflow',
    'preview.probe.lead':
      'Starts a workflow in the widget below — the saved version, even while it is switched off. '
      + 'It is a dry run: nothing is written to WLO, no jobs run, no files are stored. Sign-in and '
      + 'approvals work as in production.',
    'preview.probe.ablauf': 'Workflow',
    'preview.probe.aus': '{titel} (off)',
    'preview.probe.daten': 'Start data (JSON, optional)',
    'preview.probe.datenHilfe':
      'As from a host page, e.g. {"sammlung": "…"}. They only apply if the workflow has a '
      + 'matching start schema.',
    'preview.probe.fehler.json': 'This is not valid JSON.',
    'preview.probe.fehler.objekt': 'Start data are a JSON object in curly braces.',
    'preview.probe.fehler.gross': 'The start data are too long (at most 16,000 characters).',
    'preview.probe.fehler.schluessel': 'The start data have too many fields (at most 20).',
    'preview.probe.unbekannt':
      'There is no workflow “{kennung}” yet — save it under “Workflows” first. The first one of the '
      + 'list is selected.',
    'preview.probe.starten': 'Start workflow',
    'preview.probe.beenden': 'End the trial',
    'preview.probe.laeuft': 'Trial running: “{titel}” — dry run.',
    'preview.probe.laden': 'Loading the workflows …',
    'preview.probe.leer': 'No workflows yet. Create one under “Workflows” and save it.',
    'preview.probe.listeFehler': 'The list of workflows could not be loaded.',
    'ablaufPruefen.ausprobieren': 'Try in the widget',
    'ablaufPruefen.ausprobierenHinweis':
      'Opens the preview with this workflow. The saved version applies — save first.',
  },
};
