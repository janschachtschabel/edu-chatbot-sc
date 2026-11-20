/**
 * Paket U3-2a: Abschnitt „Hochladen“ auf der Seite „UI-Module“ — Bereich `01-base/upload-config`.
 * Gelesen vom Auswahlfeld `ui_upload` (welche Orte es anbietet, `ui_module/dienst_upload.py`,
 * `upload_orte.py`) und vom Endpunkt `POST /api/ui/dokumente`, der dieselben Schalter und Grenzen noch
 * einmal prüft. Seit Paket U (Review der Oberfläche, 8) mit den Namen der Orte: „Hier im Chat“ und
 * „In WLO ablegen und erschließen“.
 *
 * Schlüsselschema wie in `fields-layer-doc.ts`.
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_UPLOAD: CataloguePart = {
  de: {
    'curated.uiModule.upload.label': 'Hochladen',
    'curated.uiModule.upload.hint':
      'Was das Auswahlfeld „Ordner oder Dateien“ (ui_upload) tun darf. Nach der Auswahl wählt die '
      + 'Person, wo die Dateien verarbeitet werden: „Hier im Chat“ (der Chat liest sie selbst, '
      + 'behält nur den Text, nie die Datei, und höchstens so viel, wie die Grenzen unten erlauben) '
      + 'oder „In WLO ablegen und erschließen“ (eigener Schalter, nur angemeldet). „Nur Namen '
      + 'senden“ geht immer.',
    'feld.UploadConfigArea.upload.label': 'Dokumente im Chat',
    'feld.UploadConfigArea.upload.hint':
      'Gilt in beiden Maschinen ab dem nächsten Auswahlfeld.',
    'feld.UploadSettings.dokument_im_chat.label': '„Hier im Chat“ anbieten',
    'feld.UploadSettings.dokument_im_chat.hint':
      // Paket U: der Ort „Hier im Chat“ mit dem Knopf „Hochladen“ löst „Lesen lassen“ ab
      'An = nach der Auswahl gibt es den Ort „Hier im Chat“: „Hochladen“ schickt jede lesbare '
      + 'Datei (PDF, Word, Text, Markdown) an den Chat; er liest sie, beschreibt Inhalte kurz und '
      + 'fragt danach, was die Person damit machen will, oder ein Ablauf führt weiter. Aus = nur '
      + '„In WLO ablegen und erschließen“ (wenn an) und „Nur Namen senden“.',
    'feld.UploadSettings.dokument_ohne_anmeldung.label': '„Hier im Chat“ auch ohne WLO-Anmeldung',
    'feld.UploadSettings.dokument_ohne_anmeldung.hint':
      'An (Vorgabe) = jede Person kann Dateien „Hier im Chat“ hochladen und damit weiterarbeiten; '
      + 'das Repositorium ist dabei nicht beteiligt. Aus = nur angemeldete Personen — jede '
      + 'Umwandlung kostet Rechenzeit auf dem Server.',
    'feld.UploadSettings.ablage_in_wlo.label': '„In WLO ablegen und erschließen“ anbieten',
    'feld.UploadSettings.ablage_in_wlo.hint':
      'An = eine angemeldete Person kann die erfassten Dateien mit „Hochladen“ in ihrem persönlichen '
      + 'Bereich in WLO ablegen (nach einer Vorschau, je Datei höchstens so groß wie unten). '
      + 'Ohne WLO-Anmeldung nie — das Feld sagt dann, dass es nach der Anmeldung geht. Ab Werk '
      + 'an: der MCP legt die Knoten an, der Kestra-Flow erzeugt mit ihren IDs Volltexte und '
      + 'Metadaten (Freigabe unter „Abläufe“). Wirkt erst, wenn der MCP-Server die Stapel-Ablage '
      + 'anbietet.',
    'feld.UploadSettings.max_mb.label': 'Größe je Dokument (MB)',
    'feld.UploadSettings.max_mb.hint': 'Höchstens so groß darf eine Datei „Hier im Chat“ sein — auch jede Datei, die in WLO abgelegt wird, 1 bis 25. Größere gehen nur mit dem Namen.',
    'feld.UploadSettings.max_seiten.label': 'Seiten je PDF',
    'feld.UploadSettings.max_seiten.hint':
      'Längere PDFs werden abgewiesen, bevor sie gelesen werden, 1 bis 1000.',
    'feld.UploadSettings.aufbewahrung_h.label': 'Aufbewahrung (Stunden)',
    'feld.UploadSettings.aufbewahrung_h.hint':
      'So lange nach der letzten Nutzung bleibt der gelesene Text an der Sitzung, 1 bis 72. '
      + 'Danach löscht ihn der Aufbewahrungslauf; mit der Sitzung verschwindet er sofort.',
    // Plan 2026-11-17, Paket U1 (E8/E13): Grenzen für „Hier im Chat“
    'feld.UploadSettings.lokal_max_dateien.label': '„Hier im Chat“: Dateien je Sitzung',
    'feld.UploadSettings.lokal_max_dateien.hint':
      'So viele Dateien (Inhalte und Strukturdokumente zusammen) liest der Chat je Sitzung '
      + 'höchstens selbst, 1 bis 30; je Inhalt kostet das einen kurzen KI-Aufruf für Titel, '
      + 'Beschreibung und Schlagworte. Darüber bietet das Feld angemeldeten Personen „In WLO '
      + 'ablegen und erschließen“ an, ohne Anmeldung nur „Nur Namen senden“. Ist die Sitzung voll, '
      + 'endet „Hier im Chat“ mit den schon gelesenen Dateien.',
    'feld.UploadSettings.lokal_max_mb_gesamt.label': '„Hier im Chat“: MB je Sitzung',
    'feld.UploadSettings.lokal_max_mb_gesamt.hint':
      'So groß dürfen die im Chat gelesenen Dateien einer Sitzung zusammen sein, 1 bis 200 '
      + '(je Datei gilt „Größe je Dokument“). Gespeichert wird nur der Text, nie die Datei.',
    // Plan 2026-11-19, Paket C: Texterkennung gescannter PDF (Studio steuert, DOCUMENT_OCR=off bremst)
    'feld.UploadSettings.ocr.label': '„Hier im Chat“: gescannte PDF per Texterkennung lesen',
    'feld.UploadSettings.ocr.hint':
      'An (Vorgabe) = eine PDF ohne Text (Scan) liest der Chat, indem er ihre Seiten als Bild an das '
      + 'KI-Modell schickt; das Upload-Feld sagt das vor dem Hochladen. Je Seite ein KI-Aufruf '
      + '(Kosten unter „Kosten“, Phase dokument_ocr), bis zu anderthalb Minuten Wartezeit. Wirkt nicht bei '
      + 'AcademicCloud (kein Bildeingang) und nicht, wenn der Betrieb DOCUMENT_OCR=off gesetzt hat. '
      + 'Aus = ein Scan bleibt „kein lesbarer Text“.',
    'feld.UploadSettings.ocr_max_seiten.label': 'Texterkennung: Seiten je PDF',
    'feld.UploadSettings.ocr_max_seiten.hint':
      'So viele Seiten einer gescannten PDF liest die Texterkennung höchstens, 1 bis 50; der Rest '
      + 'fehlt (der Befund sagt „gekürzt“). Was nach 80 Sekunden (bei Inhalten 50) nicht gelesen ist, '
      + 'fehlt ebenso. Je Gespräch höchstens „Dateien je Sitzung“ × diese Zahl.',
  },
  en: {
    'curated.uiModule.upload.label': 'Uploads',
    'curated.uiModule.upload.hint':
      'What the “folder or files” picker (ui_upload) may do. After choosing, people pick where the '
      + 'files are processed: “Here in the chat” (the chat reads them itself, keeps only the text, '
      + 'never the file, and at most what the limits below allow) or “Store and index in WLO” '
      + '(separate switch, signed-in people only). “Send names only” always works.',
    'feld.UploadConfigArea.upload.label': 'Documents in the chat',
    'feld.UploadConfigArea.upload.hint': 'Applies in both engines from the next picker.',
    'feld.UploadSettings.dokument_im_chat.label': 'Offer “Here in the chat”',
    'feld.UploadSettings.dokument_im_chat.hint':
      'On = after choosing there is the place “Here in the chat”: “Upload” sends every readable '
      + 'file (PDF, Word, text, Markdown) to the chat; it reads them, describes contents briefly and '
      + 'then asks what the person wants to do with them, or a workflow continues. Off = only '
      + '“Store and index in WLO” (if on) and “Send names only”.',
    'feld.UploadSettings.dokument_ohne_anmeldung.label': '“Here in the chat” also without WLO sign-in',
    'feld.UploadSettings.dokument_ohne_anmeldung.hint':
      'On (default) = anyone can upload files “Here in the chat” and keep working with them; the '
      + 'repository is not involved. Off = signed-in people only — every conversion costs server time.',
    'feld.UploadSettings.ablage_in_wlo.label': 'Offer “Store and index in WLO”',
    'feld.UploadSettings.ablage_in_wlo.hint':
      'On = a signed-in person can store the captured files in their personal area in WLO with '
      + '“Upload” (after a preview, each at most the size below). Never without the WLO '
      + 'sign-in — the picker then says it works after signing in. On by default: the MCP creates '
      + 'the nodes, the Kestra flow uses their IDs to create full texts and metadata (release '
      + 'under “Workflows”). Takes effect only once the MCP server offers batch storage.',
    'feld.UploadSettings.max_mb.label': 'Size per document (MB)',
    'feld.UploadSettings.max_mb.hint': 'A file “Here in the chat” may be at most this large — so may each file stored in WLO, 1 to 25. Larger ones go along by name only.',
    'feld.UploadSettings.max_seiten.label': 'Pages per PDF',
    'feld.UploadSettings.max_seiten.hint':
      'Longer PDFs are rejected before they are read, 1 to 1000.',
    'feld.UploadSettings.aufbewahrung_h.label': 'Retention (hours)',
    'feld.UploadSettings.aufbewahrung_h.hint':
      'How long after its last use the extracted text stays with the session, 1 to 72. Then the '
      + 'retention run deletes it; it goes at once when the session is deleted.',
    'feld.UploadSettings.lokal_max_dateien.label': '“Here in the chat”: files per session',
    'feld.UploadSettings.lokal_max_dateien.hint':
      'The chat reads at most this many files per session itself (contents and structure '
      + 'documents together), 1 to 30; each content file costs a short AI call for title, '
      + 'description and keywords. Beyond that the picker offers signed-in people “Store and '
      + 'index in WLO”, without sign-in only “Send names only”. Once the session is full, “Here in '
      + 'the chat” ends with the files already read.',
    'feld.UploadSettings.lokal_max_mb_gesamt.label': '“Here in the chat”: MB per session',
    'feld.UploadSettings.lokal_max_mb_gesamt.hint':
      'The files read in the chat may add up to at most this size per session, 1 to 200 (each '
      + 'file is limited by “Size per document”). Only the text is kept, never the file.',
    'feld.UploadSettings.ocr.label': '“Here in the chat”: read scanned PDFs by text recognition',
    'feld.UploadSettings.ocr.hint':
      'On (default) = the chat reads a PDF without text (a scan) by sending its pages as images to '
      + 'the AI model; the upload picker says so before uploading. One AI call per page (costs under '
      + '“Costs”, phase dokument_ocr), up to a minute and a half of waiting. No effect with AcademicCloud (no '
      + 'image input) or when operations set DOCUMENT_OCR=off. Off = a scan stays “no readable text”.',
    'feld.UploadSettings.ocr_max_seiten.label': 'Text recognition: pages per PDF',
    'feld.UploadSettings.ocr_max_seiten.hint':
      'At most this many pages of a scanned PDF are read, 1 to 50; the rest is missing (the result '
      + 'says “shortened”). Whatever is not read after 80 seconds (50 for content files) is missing '
      + 'too. Per conversation at most “files per session” × this number.',
  },
};
