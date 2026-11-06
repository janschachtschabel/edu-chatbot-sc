/**
 * Paket U3-2a: Abschnitt „Hochladen“ auf der Seite „UI-Module“ — Bereich `01-base/upload-config`.
 * Gelesen vom Auswahlfeld `ui_upload` (welche Wege es zeigt, `ui_module/dienst_upload.py`) und vom
 * Endpunkt `POST /api/ui/dokumente`, der dieselben Schalter und Grenzen noch einmal prüft.
 *
 * Schlüsselschema wie in `fields-layer-doc.ts`.
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_UPLOAD: CataloguePart = {
  de: {
    'curated.uiModule.upload.label': 'Hochladen',
    'curated.uiModule.upload.hint':
      'Was das Auswahlfeld „Ordner oder Dateien“ (ui_upload) mit einem Dokument tun darf. Es wird '
      + 'im Chat gelesen, nicht im Repositorium abgelegt; die Datei selbst wird nicht gespeichert.',
    'curated.uiModule.ablaeufe.label': 'Abläufe',
    'curated.uiModule.ablaeufe.hint':
      'Feste Abfolgen aus Nachrichten, Modulen und lesenden Werkzeugen, gestartet per Knopf '
      + '(Direktaktion ablauf_starten), auf Vorschlag der KI, durch eine Wendung oder die Antwort '
      + 'eines Moduls. Daten gehen als Teile des Vorgangs weiter ({"$teil": "name"}). '
      + 'Ein neuer Ablauf ist aus, bis er eingeschaltet wird; beim Speichern wird geprüft, ob er '
      + 'sicher läuft.',
    'feld.UploadConfigArea.upload.label': 'Dokumente im Chat',
    'feld.UploadConfigArea.upload.hint':
      'Gilt in beiden Maschinen ab dem nächsten Auswahlfeld.',
    'feld.UploadSettings.dokument_im_chat.label': 'Dokument im Chat lesen',
    'feld.UploadSettings.dokument_im_chat.hint':
      'Die Person kann ein Dokument (PDF, Word, Text, Markdown) hochladen; der Chat liest es, '
      + 'etwa um daraus einen Themenbaum zu entwerfen. Aus = das Auswahlfeld erfasst nur noch '
      + 'Ordner und Dateinamen.',
    'feld.UploadSettings.dokument_ohne_anmeldung.label': 'Auch ohne WLO-Anmeldung',
    'feld.UploadSettings.dokument_ohne_anmeldung.hint':
      'Aus = nur angemeldete Personen dürfen ein Dokument lesen lassen. An erlaubt es allen — '
      + 'jede Umwandlung kostet Rechenzeit auf dem Server.',
    'feld.UploadSettings.ablage_in_wlo.label': 'Inhalte in WLO ablegen',
    'feld.UploadSettings.ablage_in_wlo.hint':
      'An = eine angemeldete Person kann die erfassten Dateien per Klick in ihren persönlichen '
      + 'Bereich in WLO übertragen (nach einer Vorschau, je Datei höchstens so groß wie unten). '
      + 'Ohne WLO-Anmeldung nie. Wirkt erst, wenn der MCP-Server die Stapel-Ablage anbietet.',
    'feld.UploadSettings.max_mb.label': 'Größe je Dokument (MB)',
    'feld.UploadSettings.max_mb.hint': 'Höchstens so groß darf ein Dokument sein — auch jede Datei, die in WLO abgelegt wird, 1 bis 25.',
    'feld.UploadSettings.max_seiten.label': 'Seiten je PDF',
    'feld.UploadSettings.max_seiten.hint':
      'Längere PDFs werden abgewiesen, bevor sie gelesen werden, 1 bis 1000.',
    'feld.UploadSettings.aufbewahrung_h.label': 'Aufbewahrung (Stunden)',
    'feld.UploadSettings.aufbewahrung_h.hint':
      'So lange nach der letzten Nutzung bleibt der gelesene Text an der Sitzung, 1 bis 72. '
      + 'Danach löscht ihn der Aufbewahrungslauf; mit der Sitzung verschwindet er sofort.',
  },
  en: {
    'curated.uiModule.upload.label': 'Uploads',
    'curated.uiModule.upload.hint':
      'What the “folder or files” picker (ui_upload) may do with a document. It is read in the '
      + 'chat, not stored in the repository; the file itself is not kept.',
    'curated.uiModule.ablaeufe.label': 'Workflows',
    'curated.uiModule.ablaeufe.hint':
      'Fixed sequences of messages, modules and read-only tools, started by a button '
      + '(direct action ablauf_starten), on the AI’s suggestion, by a phrase or by a module answer. Data passes on as parts of the work item ({"$teil": "name"}). '
      + 'A new workflow is off until switched on; saving checks that it runs safely.',
    'feld.UploadConfigArea.upload.label': 'Documents in the chat',
    'feld.UploadConfigArea.upload.hint': 'Applies in both engines from the next picker.',
    'feld.UploadSettings.dokument_im_chat.label': 'Read a document in the chat',
    'feld.UploadSettings.dokument_im_chat.hint':
      'People can upload a document (PDF, Word, text, Markdown); the chat reads it, for example to '
      + 'draft a topic tree from it. Off = the picker only captures folders and file names.',
    'feld.UploadSettings.dokument_ohne_anmeldung.label': 'Also without WLO sign-in',
    'feld.UploadSettings.dokument_ohne_anmeldung.hint':
      'Off = only signed-in people may have a document read. On allows everyone — every '
      + 'conversion costs server time.',
    'feld.UploadSettings.ablage_in_wlo.label': 'Store contents in WLO',
    'feld.UploadSettings.ablage_in_wlo.hint':
      'On = a signed-in person can transfer the captured files to their personal area in WLO '
      + 'with a click (after a preview, each at most the size below). Never without the WLO '
      + 'sign-in. Takes effect only once the MCP server offers batch storage.',
    'feld.UploadSettings.max_mb.label': 'Size per document (MB)',
    'feld.UploadSettings.max_mb.hint': 'A document may be at most this large — so may each file stored in WLO, 1 to 25.',
    'feld.UploadSettings.max_seiten.label': 'Pages per PDF',
    'feld.UploadSettings.max_seiten.hint':
      'Longer PDFs are rejected before they are read, 1 to 1000.',
    'feld.UploadSettings.aufbewahrung_h.label': 'Retention (hours)',
    'feld.UploadSettings.aufbewahrung_h.hint':
      'How long after its last use the extracted text stays with the session, 1 to 72. Then the '
      + 'retention run deletes it; it goes at once when the session is deleted.',
  },
};
