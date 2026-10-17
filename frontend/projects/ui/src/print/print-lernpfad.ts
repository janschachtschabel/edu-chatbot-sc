/**
 * Der Lernpfad als Druckansicht (Druckfenster, „Als PDF speichern“).
 *
 * Aus ``print-utils.ts`` gelöst (Paket 9, Review Paket 7 — Dateigrößen): dort
 * stehen die geteilten Bausteine (Markdown → HTML, sichere Links, Datum) und die
 * beiden anderen Drucker, hier der Lernpfad mit seinen Karten. Body verbatim.
 */
import { ChatMessage } from '../grouping/message-types';
import { BOERDI_LOGO_DATA_URL } from '../branding/boerdi-logo';
import type { TranslateFn } from '../i18n/i18n';
import { verdrahteDruckknopf } from './print-fenster';
import { PRINTABLE_CANVAS_RE, esc, printDate, printMdToHtml, safePrintHref } from './print-utils';

/**
 * Open a clean, printable Lernpfad view in a new window and trigger the
 * browser print dialog. Users can then "Save as PDF" from the dialog —
 * no server-side PDF rendering needed, works identically on all browsers.
 */
export function printLearningPath(msg: ChatMessage, t: TranslateFn): void {
  // Wenn der Lernpfad im Inline-Modus erzeugt wurde, hat das Backend einen
  // ``<!-- boerdi:printable-canvas|... -->``-Sentinel vor das Markdown
  // gestellt (siehe chat.py _apply_widget_modes_postprocess). Im PDF-
  // Render-Pfad würde printMdToHtml den Kommentar HTML-escapen und als
  // sichtbaren Text auswerfen — daher hier vorher strippen, identisch
  // zu printCanvasMaterial.
  const lpContent = (msg.content || '').replace(PRINTABLE_CANVAS_RE, '').trim();
  const cards = msg.cards || [];
  const cardsHtml = cards.map(c => {
    const types = (c.learning_resource_types || []).filter(
      t => t !== 'Sammlung' && t !== 'collection'
    );
    const meta = [
      ...(c.disciplines || []),
      ...(c.educational_contexts || []),
      ...types,
      c.license,
    ].filter(Boolean).map(x => `<span class="chip">${esc(x!)}</span>`).join('');
    // Nur http(s) durchlassen — ein ``javascript:``-URI wäre im Druckfenster
    // (das die Host-Origin erbt) sonst klickbar. Kein Link → nur Titel-Text.
    const href = safePrintHref(c.link || c.guide_url || c.wlo_url || c.url);
    const desc = c.description
      ? `<div class="desc">${esc(c.description.slice(0, 220))}${c.description.length > 220 ? '…' : ''}</div>`
      : '';
    const thumb = c.preview_url
      ? `<img class="thumb" src="${esc(c.preview_url)}" alt="">`
      : `<div class="thumb thumb-ph">📄</div>`;
    const titleHtml = href
      ? `<a href="${esc(href)}" target="_blank" rel="noopener">${esc(c.title)}</a>`
      : esc(c.title);
    return `
      <div class="card">
        ${thumb}
        <div class="card-body">
          <div class="card-title">${titleHtml}</div>
          <div class="chips">${meta}</div>
          ${desc}
          ${href ? `<div class="card-url">${esc(href)}</div>` : ''}
        </div>
      </div>`;
  }).join('');

  const today = printDate(t);
  const lpTitel = t('print.learningPath');

  const html = `<!doctype html>
<html lang="${esc(t('format.htmlLang'))}">
<head>
<meta charset="utf-8">
<title>${esc(t('print.docTitle', { title: lpTitel }))}</title>
<style>
  /* Browser-Preview: zentriertes "Papier" auf grauem Hintergrund. Im
     Druck übernehmen die @page-margins, body wird entkleidet. */
  @page { size: A4; margin: 18mm 16mm 18mm 16mm; }
  html { background: #f1f5f9; }
  body {
    font: 11pt/1.55 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
    color: #222; max-width: 760px; margin: 32px auto 64px;
    padding: 36px 44px; background: #fff;
    box-shadow: 0 1px 4px rgba(0,0,0,.08);
    border-radius: 4px;
  }
  header { display: flex; justify-content: space-between; align-items: baseline; border-bottom: 2px solid #3b82f6; padding-bottom: 6px; margin-bottom: 14px; }
  header h1 { margin: 0; font-size: 16pt; color: #1e40af; }
  header .meta { font-size: 9pt; color: #6b7280; }
  h1, h2, h3, h4 { color: #1e40af; margin: 14px 0 4px; }
  h2 { font-size: 13pt; }
  h3 { font-size: 12pt; }
  blockquote { border-left: 3px solid #c5cbd6; background: #f6f8fb; margin: 6px 0; padding: 6px 12px; color: #3a4252; }
  p { margin: 4px 0; }
  .ol, .li { display: flex; margin: 3px 0; padding-left: 2px; }
  .ol .n, .li .b { flex-shrink: 0; margin-right: 8px; color: #3b82f6; font-weight: 600; }
  a { color: #2563eb; text-decoration: none; }
  a:hover { text-decoration: underline; }
  section.cards { margin-top: 22px; page-break-before: auto; }
  section.cards h2 { font-size: 12pt; margin-bottom: 8px; }
  .card { display: flex; gap: 10px; border: 1px solid #e5e7eb; border-radius: 6px; padding: 8px; margin-bottom: 8px; page-break-inside: avoid; }
  .thumb { width: 60px; height: 60px; object-fit: cover; border-radius: 4px; flex-shrink: 0; background: #f3f4f6; display: flex; align-items: center; justify-content: center; font-size: 22pt; color: #9ca3af; }
  .card-body { flex: 1; min-width: 0; }
  .card-title { font-weight: 600; font-size: 10.5pt; }
  .card-title a { color: #1e40af; }
  .chips { margin: 3px 0; }
  .chip { display: inline-block; font-size: 8pt; background: #eef2ff; color: #4338ca; border-radius: 10px; padding: 1px 7px; margin-right: 4px; margin-bottom: 2px; }
  .desc { font-size: 9.5pt; color: #4b5563; margin: 3px 0; }
  .card-url { font-size: 8pt; color: #6b7280; word-break: break-all; }
  footer { margin-top: 24px; padding-top: 8px; border-top: 1px solid #e5e7eb; font-size: 8.5pt; color: #6b7280; text-align: center; }
  .print-bar { position: fixed; top: 0; right: 0; padding: 10px 14px; background: #fff; border-bottom-left-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,.1); z-index: 10; }
  .print-bar button { padding: 6px 14px; background: #3b82f6; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 10pt; }
  .print-bar button:hover { background: #2563eb; }
  @media print {
    html { background: #fff; }
    .print-bar { display: none; }
    /* Mindest-Padding, falls der User "Ränder: Minimum/Keine" wählt und
       damit die @page-margins (18/16mm) überschreibt. Sonst randlos. */
    body {
      padding: 12mm 14mm;
      margin: 0;
      max-width: none;
      box-shadow: none;
      border-radius: 0;
    }
  }
</style>
</head>
<body>
<div class="print-bar"><button type="button">${esc(t('print.button'))}</button></div>
<header>
  <h1><img src="${BOERDI_LOGO_DATA_URL}" alt="" style="width:28px;height:28px;vertical-align:-6px;margin-right:6px;"/> ${esc(lpTitel)}</h1>
  <span class="meta">${esc(t('print.meta', { date: today }))}</span>
</header>
<main>
  ${printMdToHtml(lpContent)}
</main>
${cards.length ? `<section class="cards"><h2>${esc(t('print.usedContents', { count: cards.length }))}</h2>${cardsHtml}</section>` : ''}
<footer>${esc(t('print.footer', { date: today }))}</footer>
<!-- Kein auto-print mehr: der User sieht erst die Preview im neuen
     Tab und klickt dann selbst "Drucken / Als PDF speichern". Vorher
     auto-print direkt nach load, was den User vor dem Druck-Dialog
     stranden ließ wenn er ihn versehentlich abbrach. -->
</body>
</html>`;

  const w = window.open('', '_blank', 'width=900,height=1100');
  if (!w) {
    alert(t('print.popupBlockedLearningPath'));
    return;
  }
  w.document.open();
  w.document.write(html);
  w.document.close();
  verdrahteDruckknopf(w);
}
